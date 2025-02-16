
import nltk
from nltk.tokenize import PunktSentenceTokenizer

import time
from itertools import accumulate

from stream2sentence import init_tokenizer
from stream2sentence.avoid_pause_words import AVOID_PAUSE_WORDS
from stream2sentence.delimiter_ignore_prefixes import DELIMITER_IGNORE_PREFIXES


init_tokenizer("nltk")

WORDS_PER_TOKEN = 0.75
preferred_sentence_fragment_delimiters_global = []
sentence_fragment_delimiters_global = []
delimiter_ignore_prefixes_global = []

def get_index_or_last(a_list, index):
    return a_list[index] if index < len(a_list) else a_list[-1]

def find_last_delimiter(s, delimiters):
    valid_indices = []
    for delimiter in delimiters:
        index = s.rfind(delimiter)
        if index != -1:
            # Get the word preceding the delimiter
            preceding_word_start = s.rfind(" ", 0, index)
            preceding_word = s[preceding_word_start:index + 1].strip()
            
            if preceding_word not in delimiter_ignore_prefixes_global:
                valid_indices.append(index)
    
    return max(valid_indices, default=-1)

def find_last_preferred_fragment_delimiter(s):
    return find_last_delimiter(s, preferred_sentence_fragment_delimiters_global)

def find_last_fragment_delimiter(s):
    return find_last_delimiter(s, sentence_fragment_delimiters_global)

def get_num_words(s):
    return len(s.split())

def find_first_greater(nums, value):
    for index, num in enumerate(nums):
        if num > value:
            return index
    return -1


def is_output_needed(has_output_started, start_time, lead_time, output_sentences, estimated_time_between_words, deadline_offset):
    cur_time = time.time()
    if not has_output_started and cur_time - start_time < lead_time:
        return False
    
    num_words_output = get_num_words(" ".join(output_sentences))
    output_deadline = num_words_output * estimated_time_between_words - deadline_offset
    return cur_time - start_time > output_deadline

def is_output_long_enough(output, min_output_length):
    num_words = get_num_words(output)
    return (num_words >= min_output_length)

def get_fragment(llm_buffer, min_output_length):
    delimiter_index = find_last_preferred_fragment_delimiter(llm_buffer)
    if delimiter_index != -1 and is_output_long_enough(llm_buffer[:delimiter_index], min_output_length):
        return llm_buffer[:delimiter_index + 1]
    
    delimiter_index = find_last_fragment_delimiter(llm_buffer)
    if delimiter_index != -1 and is_output_long_enough(llm_buffer[:delimiter_index], min_output_length):
        return llm_buffer[:delimiter_index + 1]
    return ""

def get_sentences_needed_for_min_length(sentences_on_buffer, min_output_length):
    word_lengths_of_sentences = list(map(get_num_words, sentences_on_buffer))
    sums_of_word_lens = list(accumulate(word_lengths_of_sentences))
    return find_first_greater(sums_of_word_lens, min_output_length) + 1


def generate_sentences(
    generator, 
    lead_time = 1,
    max_wait_for_fragments = [3, 2],
    target_tps = 4,
    min_output_lengths = [2, 3, 3, 4],
    preferred_sentence_fragment_delimiters = ['. ', '? ', '! ', '\n'],
    sentence_fragment_delimiters = ['; ', ': ', ', ', '* ', '**', '– '],
    delimiter_ignore_prefixes = DELIMITER_IGNORE_PREFIXES,
    wait_for_if_non_fragment = AVOID_PAUSE_WORDS,
    deadline_offsets_static = [1],
    deadline_offsets_dynamic = [0],
):
    """
    Uses a time based strategy to determine whether to yield. A target tps is provided,
    and when the outputted values are approaching the "deadline" where output will lag behind
    the target then yield best available option.

    Args:
        generator (Iterator[str]): A generator that yields chunks of text as a stream of characters.
        lead_time (float): amount of time in seconds to wait for the buffer to build for before returning values.
            Default is 1.
        max_wait_for_fragments (float): Max amount of time in seconds that the Nth sentence will wait beyond the 
            "deadline" for a "fragment" (text preceeding a fragment delimiter), which is preferred over a piece of buffer.
            The last value in the array is used for all subsequent checks.
            Default is [3, 2].
        target_tps (float): the rate in tokens per second you want to use to calculate output deadlines.
            Default is 4. (approximately the speed of human speech)
        min_output_lengths (int[]]): An array that corresponds to the minimum output size in words 
            for the corresponding output sentence, the last value in the array is used for all remaining output. 
            For example [4,5,6] would mean the first piece of output must have 4 words, the second 5 words, and all subsequent 6.
            Default is [2, 3, 3, 4]
        preferred_sentence_fragment_delimiters (str[]): Array of strings that deliniate a sentence fragment. "Preferred"
            are checked first and always used if the fragment meets the length requirement over the other fragment delimiters.
            Note the trailing spaces, added to differentiate between values like $3.5 and a proper sentence end
            Default is ['. ', '? ', '! ', '\n']
        sentence_fragment_delimiters (str[]): Array of strings that are checked after "preferred" delimiters
            Default is ['; ', ': ', ', ', '* ']
        delimiter_ignore_prefixes (str[]): Array of strings that will not be considered "delimiters" if preceeded by a delimiter.
            Used to ignore common abbreviations for things like Mr. Dr. and Mrs. where we don't want to split
            Default is a long list documented in delimiter_ignore_prefixes
        wait_for_if_non_fragment (str[]): Array of strings that the algorithm will not use as the last value if the whole buffer
            is being output. Avoids awkward pauses on common words that are unnatural to pause at. 
            Default is a long list of common words documented in avoid_pause_words.py
        deadline_offsets_static float[]: Constant amount of time in seconds to subtract from the deadline for first n sentences.
            Last value applied to all subsequent sentences
            Default is [1].
        deadline_offsets_dynamic float[]: Added to account for the time it takes a TTS engine to generate output. 
            For example, if it takes your TTS engine around 1 second to generate 10 words, you can use a value of 0.1
            so that the TTS generation time is included in the deadline. Applied to first n sentences, last value applied to all subsequent
            Default is [0].
    Yields:
        Iterator[str]: An iterator of complete sentences constructed from the
          input text stream.
    """
    global preferred_sentence_fragment_delimiters_global, sentence_fragment_delimiters_global, delimiter_ignore_prefixes_global
    preferred_sentence_fragment_delimiters_global = set(preferred_sentence_fragment_delimiters)
    sentence_fragment_delimiters_global = set(sentence_fragment_delimiters)
    delimiter_ignore_prefixes_global = set(delimiter_ignore_prefixes)
    punkt_sentence_tokenizer = PunktSentenceTokenizer()

    start_time = time.time()
    last_sentence_time = time.time()
    estimated_time_between_words = 1 / (target_tps * WORDS_PER_TOKEN)
    output_sentences = []
    llm_buffer_full = ""
    has_output_started = False


    def handle_output(output, sentence_boundary_index=None):
        nonlocal has_output_started, llm_buffer_full, output_sentences, min_output_lengths, start_time, last_sentence_time
        if not has_output_started:
            #once output has started we go based on TTS start for deadline
            start_time = time.time()
            has_output_started = True
        
        end_index = len(output) + 1
        if sentence_boundary_index != None:
            end_index = sentence_boundary_index
        llm_buffer_full = llm_buffer_full[end_index:]
        output_sentences.append(output)
        last_sentence_time = time.time()
        return output

    for token in generator:
        llm_buffer_full += token
        llm_buffer_full = llm_buffer_full.lstrip()
        if len(llm_buffer_full.split(None, 2)) < 2:
            #must have at least two words since last token may not be a full word
            continue

        llm_buffer = llm_buffer_full.rsplit(" ", 1)[0] #remove last word

        #TODO edge case with disagreement, how to identify and use len(output) as fallback?
        sentences_on_buffer = nltk.tokenize.sent_tokenize(llm_buffer)
        sentence_boundaries = list(punkt_sentence_tokenizer.span_tokenize(llm_buffer_full)) #handle white space descrepancies in full_buffer and buffer after split()

        num_sentences_output = len(output_sentences)
        min_output_length = get_index_or_last(min_output_lengths, num_sentences_output)
        sentences_needed_for_min_len = get_sentences_needed_for_min_length(sentences_on_buffer, min_output_length)

        current_output = llm_buffer
        use_first_sentence = len(sentences_on_buffer) > 1 and is_output_long_enough(sentences_on_buffer[0], min_output_length)
        if use_first_sentence:
            current_output = sentences_on_buffer[0]
        else:
            current_fragment = get_fragment(llm_buffer, min_output_length)
            if current_fragment != "":
                current_output = current_fragment
        
        num_words_for_offset = get_num_words(current_output)
        deadline_offset_dynamic = get_index_or_last(deadline_offsets_dynamic, num_sentences_output)
        deadline_offset_static = get_index_or_last(deadline_offsets_static, num_sentences_output)
        deadline_offset = (num_words_for_offset * deadline_offset_dynamic) + deadline_offset_static

        output_needed = is_output_needed(has_output_started, start_time, lead_time, output_sentences, estimated_time_between_words, deadline_offset)
        if output_needed and use_first_sentence:
            end_index = len(sentences_on_buffer[0]) if len(sentence_boundaries) == 1 else sentence_boundaries[1][0] #edge case where sentence_boundaries disagrees with nltk.tokenize.sent_tokenize
            yield handle_output(sentences_on_buffer[0], end_index)
        elif output_needed:
            output = current_fragment
            if output == "":
                output = llm_buffer
                is_not_min_length = get_num_words(output) < min_output_length
                max_wait_for_fragment = get_index_or_last(max_wait_for_fragments, num_sentences_output)
                waiting_for_fragment = (time.time() - last_sentence_time < max_wait_for_fragment)
                if " " in output:
                    _, last_word = output.rsplit(" ", 1)
                else:
                    last_word = output
                last_word_avoid_pause = last_word in wait_for_if_non_fragment

                if is_not_min_length or waiting_for_fragment or last_word_avoid_pause:
                    continue
            
            yield handle_output(output)
        else:
            if sentences_needed_for_min_len == 0 or sentences_needed_for_min_len + 2 > len(sentences_on_buffer):
                #two sentences ahead is ideal
                continue
            end_index = sentence_boundaries[sentences_needed_for_min_len][0]
            output = " ".join(sentences_on_buffer[:sentences_needed_for_min_len])
            yield handle_output(output, end_index)

    #after all tokens are processed yield whatever is left
    for sentence in nltk.tokenize.sent_tokenize(llm_buffer_full):
        yield sentence



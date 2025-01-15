

import nltk
import time
from itertools import accumulate


nltk_initialized = False

def initialize_nltk(debug=False):
    """
    Initializes NLTK by downloading required data for sentence tokenization.
    """
    global nltk_initialized
    if nltk_initialized:
        return

    print("Initializing NLTK Tokenizer")

    try:
        import nltk

        nltk.download("punkt_tab", quiet=not debug)
        nltk_initialized = True
    except Exception as e:
        print(f"Error initializing nltk tokenizer: {e}")
        nltk_initialized = False


initialize_nltk()

PREFERRED_SENTENCE_FRAGMENT_DELIMITERS = ['.', '?', '!', '\n']
SENTENCE_FRAGMENT_DELIMITERS = [';', ':', ',', '*']
WORDS_PER_TOKEN = 0.75

def find_last_preferred_fragment_delimiter(s):
    return max(s.rfind(c) for c in PREFERRED_SENTENCE_FRAGMENT_DELIMITERS)

def find_last_fragment_delimiter(s):
    return max(s.rfind(c) for c in SENTENCE_FRAGMENT_DELIMITERS)

def get_num_words(s):
    return len(s.split())

def find_first_greater(nums, value):
    for index, num in enumerate(nums):
        if num > value:
            return index
    return -1


def is_output_needed(has_output_started, start_time, lead_time, output_sentences, estimated_time_between_words):
    cur_time = time.time()
    if not has_output_started and cur_time - start_time < lead_time:
        return False
    
    num_words_output = get_num_words(" ".join(output_sentences))
    output_deadline = (num_words_output - 1) * estimated_time_between_words
    return cur_time - start_time > output_deadline

def is_output_long_enough(output, min_output_length):
    num_words = get_num_words(output)
    return (num_words >= min_output_length)

def get_partial_output(llm_buffer, sentences_on_buffer, min_output_length):
    if len(sentences_on_buffer) > 1 and is_output_long_enough(sentences_on_buffer[0], min_output_length):
        return sentences_on_buffer[0]
    
    delimiter_index = find_last_preferred_fragment_delimiter(llm_buffer)
    if delimiter_index != -1 and is_output_long_enough(llm_buffer[:delimiter_index], min_output_length):
        return llm_buffer[:delimiter_index + 1]
    
    delimiter_index = find_last_fragment_delimiter(llm_buffer)
    if delimiter_index != -1 and is_output_long_enough(llm_buffer[:delimiter_index], min_output_length):
        return llm_buffer[:delimiter_index + 1]
    return ""

def generate_sentences(
    generator, 
    lead_time = 1,
    target_tps = 4,
    min_output_length = 4,
):
    """
    Uses a time based strategy to determine whether to yield. A target tps is provided,
    and when the outputted values are approaching the "deadline" where output will lag behind
    the target then yield best available option.

    Args:
        generator (Iterator[str]): A generator that yields chunks of text as a
            stream of characters.
        lead_time (float): amount of time in seconds to wait for the buffer 
            to build for before returning values.
            Default is 1.
        target_tps (float): the rate in tokens per second you want to use 
            to calculate deadlines for output.
            Default is 4. (approximately the speed of human speech)
        min_output_length (int): if available output has fewer words than this then wait, even if deadline has been reached
            Default is 4.

    Yields:
        Iterator[str]: An iterator of complete sentences constructed from the
          input text stream.

    """

    start_time = time.time()
    estimated_time_between_words = 1 / (target_tps * WORDS_PER_TOKEN)
    output_sentences = []
    llm_buffer_full = ""
    has_output_started = False

    def handle_output(output):
        nonlocal has_output_started, llm_buffer_full, output_sentences, min_output_length, start_time, token
        if not has_output_started:
            #once output has started we go based on TTS start for deadline
            start_time = time.time()
            has_output_started = True
            
        llm_buffer_full = llm_buffer_full[len(output) + 1:]
        output_sentences.append(output)
        return output

    for token in generator:
        llm_buffer_full += token

        if get_num_words(llm_buffer_full) < 2:
            #must have at least two words since last token may not be a full word
            continue
        llm_buffer = ' '.join(llm_buffer_full.split()[:-1])
        sentences_on_buffer = nltk.tokenize.sent_tokenize(llm_buffer)

        if is_output_needed(has_output_started, start_time, lead_time, output_sentences, estimated_time_between_words):
            output = get_partial_output(llm_buffer, sentences_on_buffer, min_output_length)
            if output == "":
                output = llm_buffer
                if get_num_words(output) < min_output_length:
                    continue
            
            yield handle_output(output)
        else:
            word_lengths_of_sentences = list(map(get_num_words, sentences_on_buffer))
            sums_of_word_lens = list(accumulate(word_lengths_of_sentences))
            sentences_needed_for_min_len = find_first_greater(sums_of_word_lens, min_output_length) + 1
            if sentences_needed_for_min_len == 0 or sentences_needed_for_min_len + 2 > len(sentences_on_buffer):
                #two sentences ahead is ideal
                continue

            output = " ".join(sentences_on_buffer[:sentences_needed_for_min_len])
            yield handle_output(output)

    #after all tokens are processed yield whatever is left
    for sentence in nltk.tokenize.sent_tokenize(llm_buffer_full):
        yield sentence



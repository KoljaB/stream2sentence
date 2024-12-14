"""
Real-time processing and delivery of sentences
from a continuous stream of characters or text chunks
"""

import functools
import logging
import re
import time
from typing import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Concatenate,
    Iterable,
    Iterator,
    ParamSpec,
)

import emoji

current_tokenizer = "nltk"
stanza_initialized = False
nltk_initialized = False
nlp = None


def initialize_nltk(debug=False):
    """
    Initializes NLTK by downloading required data for sentence tokenization.
    """
    global nltk_initialized
    if nltk_initialized:
        return

    logging.info("Initializing NLTK Tokenizer")

    try:
        import nltk

        nltk.download("punkt_tab", quiet=not debug)
        nltk_initialized = True
    except Exception as e:
        print(f"Error initializing nltk tokenizer: {e}")
        nltk_initialized = False


def initialize_stanza(language: str = "en", offline=False):
    """
    Initializes Stanza by downloading required data for sentence tokenization.
    """
    global nlp, stanza_initialized
    if stanza_initialized:
        return

    logging.info("Initializing Stanza Tokenizer")

    try:
        import stanza

        if not offline:
            stanza.download(language)

        nlp = stanza.Pipeline(language, download_method=None)
        stanza_initialized = True
    except Exception as e:
        print(f"Error initializing stanza tokenizer: {e}")
        stanza_initialized = False


def _remove_links(text: str) -> str:
    """
    Removes any links from the input text.

    Args:
        text (str): Input text

    Returns:
        str: Text with links removed
    """
    pattern = (
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|"
        r"[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )

    return re.sub(pattern, "", text)


def _remove_emojis(text: str) -> str:
    """
    Removes emojis from the input text.

    Args:
        text (str): Input text

    Returns:
        str: Text with emojis removed
    """
    return emoji.replace_emoji(text, "")


async def _generate_characters(
    generator: AsyncIterable[str], log_characters: bool = False
) -> AsyncIterator[str]:
    """
    Generates individual characters from a text generator.

    Args:
        generator (Iterator[str]): Input text generator
        log_characters (bool): Whether to log the characters to the console

    Yields:
        Individual characters from the generator
    """
    if log_characters:
        print("Stream: ", end="", flush=True)
    async for chunk in generator:
        for char in chunk:
            if log_characters:
                print(char, end="", flush=True)
            yield char
    if log_characters:
        print()


def _clean_text(
    text: str,
    cleanup_text_links: bool = False,
    cleanup_text_emojis: bool = False,
    strip_text: bool = True,
) -> str:
    """
    Cleans the text by removing links and emojis.

    Args:
        text (str): Input text
        cleanup_text_links (boolean, optional): Remove non-desired links from
          the stream.
        cleanup_text_emojis (boolean, optional): Remove non-desired emojis
          from the stream.

    Returns:
        str: Cleaned text
    """
    if cleanup_text_links:
        text = _remove_links(text)
    if cleanup_text_emojis:
        text = _remove_emojis(text)
    if strip_text:
        text = text.strip()
    return text


def _tokenize_sentences(text: str, tokenize_sentences=None) -> list[str]:
    """
    Tokenizes sentences from the input text.

    Args:
        text (str): Input text
        tokenize_sentences (Callable, optional): A function that tokenizes
          sentences from the input text. Defaults to None.

    Yields:
        Iterator[str]: An iterator of sentences
    """
    if tokenize_sentences:
        sentences = tokenize_sentences(text)
    else:
        nlp_start_time = time.time()
        if current_tokenizer == "nltk":
            import nltk

            sentences = nltk.tokenize.sent_tokenize(text)
        elif current_tokenizer == "stanza":
            import stanza

            global nlp
            doc = nlp(text)
            sentences = [sentence.text for sentence in doc.sentences]
        else:
            raise ValueError(f"Unknown tokenizer: {current_tokenizer}")
        nlp_end_time = time.time()
        logging.info("Time to split sentences: " f"{nlp_end_time - nlp_start_time}")
    return sentences


def init_tokenizer(tokenizer: str, language: str = "en", offline=False, debug=False):
    """
    Initializes the sentence tokenizer.
    """
    if tokenizer == "nltk":
        initialize_nltk(debug)
    elif tokenizer == "stanza":
        initialize_stanza(language,offline=offline)
    else:
        logging.warning(f"Unknown tokenizer: {tokenizer}")

async def generate_sentences_async(
    generator: AsyncIterable[str],
    context_size: int = 12,
    context_size_look_overhead: int = 12,
    minimum_sentence_length: int = 10,
    minimum_first_fragment_length=10,
    quick_yield_single_sentence_fragment: bool = False,
    quick_yield_for_all_sentences: bool = False,
    quick_yield_every_fragment: bool = False,
    cleanup_text_links: bool = False,
    cleanup_text_emojis: bool = False,
    tokenize_sentences=None,
    tokenizer: str = "nltk",
    language: str = "en",
    log_characters: bool = False,
    sentence_fragment_delimiters: str = ".?!;:,\n…)]}。-",
    full_sentence_delimiters: str = ".?!\n…。",
    force_first_fragment_after_words=30,
    debug=False,
) -> AsyncIterator[str]:
    """
    Generates well-formed sentences from a stream of characters or text chunks
      provided by an input generator.

    Args:
        generator (Iterator[str]): A generator that yields chunks of text as a
          stream of characters.
        context_size (int): The number of characters used to establish context
          for sentence boundary detection. A larger context improves the
          accuracy of detecting sentence boundaries.
          Default is 12 characters.
        context_size_look_overhead: The number of characters to look
          over the context_size boundaries to detect sentence splitting
          characters (improves sentence detection).
        minimum_sentence_length (int): The minimum number of characters a
          sentence must have. If a sentence is shorter, it will be
          concatenated with the following one, improving the overall
          readability. This parameter does not apply to the first sentence
          fragment, which is governed by `minimum_first_fragment_length`.
          Default is 10 characters.
        minimum_first_fragment_length (int): The minimum number of characters
          required for the first sentence fragment before yielding.
          Default is 10 characters.
        quick_yield_single_sentence_fragment (bool): If set to True, the
          generator will yield the first sentence first fragment as quickly as
          possible. This is particularly useful for real-time applications
          such as speech synthesis.
        quick_yield_for_all_sentences (bool): If set to True, the
          generator will yield every sentence first fragment as quickly as
          possible (not only the first sentence first fragment)
        quick_yield_every_fragment (bool): If set to True, the
          generator not only yield every sentence first fragment, but also every
          following fragment.
        cleanup_text_links (bool): If True, removes hyperlinks from the text
          stream to ensure clean output.
        cleanup_text_emojis (bool): If True, filters out emojis from the text
          stream for clear textual content.
        tokenize_sentences (Callable): A function that tokenizes sentences
          from the input text. Defaults to None.
        tokenizer (str): The tokenizer to use for sentence tokenization.
          Default is "nltk". Can be "nltk" or "stanza".
        language (str): The language to use for sentence tokenization.
          Default is "en". Can be "multilingual" for stanze tokenizer.
        log_characters (bool): If True, logs each character to the console as
          they are processed.
        sentence_fragment_delimiters (str): A string of characters that are
          considered sentence fragment delimiters. Default is ".?!;:,\n…)]}。-".
        full_sentence_delimiters (str): A string of characters that are
          considered full sentence delimiters. Default is ".?!\n…。".
        force_first_fragment_after_words (int): The number of words after
          which the first sentence fragment is forced to be yielded.
          Default is 30 words.
        debug (bool): If True, enables debug mode for logging.

    Yields:
        Iterator[str]: An iterator of complete sentences constructed from the
          input text stream. Each yielded sentence meets the specified minimum
          length requirements and is cleaned up if specified.

    The function maintains a buffer to accumulate text chunks and applies
      natural language processing to detect sentence boundaries.
      It employs various heuristics, such as minimum sentence length and
      sentence delimiters, to ensure the quality of the output sentences.
      The function also provides options to clean up the text stream,
      making it versatile for different types of text processing applications.
    """

     # Initialize the tokenizer based on the specified tokenizer and language
    global current_tokenizer
    current_tokenizer = tokenizer
    init_tokenizer(current_tokenizer, language, debug)

    buffer = ""
    is_first_sentence = True
    word_count = 0  # Initialize word count
    last_delimiter_position = -1  # Position of last full sentence delimiter

    # Adjust quick yield flags based on settings
    if quick_yield_every_fragment:
        quick_yield_for_all_sentences = True

    if quick_yield_for_all_sentences:
        quick_yield_single_sentence_fragment = True

    async for char in _generate_characters(generator, log_characters):

        if char:
            if len(buffer) == 0:
                if not char.isalnum():
                    continue

            buffer += char
            buffer = buffer.lstrip()

            # Update word count on encountering space or sentence fragment delimiter
            if char.isspace() or char in sentence_fragment_delimiters:
                word_count += 1

            if debug:
                print("\033[36mDebug: Added char, buffer size: \"{}\"\033[0m".format(len(buffer)))

            # Check conditions to yield first sentence fragment quickly
            if (
                is_first_sentence
                and len(buffer) > minimum_first_fragment_length
                and quick_yield_single_sentence_fragment
            ):

                if (
                    buffer[-1] in sentence_fragment_delimiters
                    or char.isspace() and word_count >= force_first_fragment_after_words
                ):

                    yield_text = _clean_text(
                        buffer,
                        cleanup_text_links,
                        cleanup_text_emojis)
                    if debug:
                        if buffer[-1] in sentence_fragment_delimiters:
                            print("\033[36mDebug: Yielding first sentence fragment: \"{}\" because buffer[-1] {} is sentence frag \033[0m".format(yield_text, buffer[-1]))
                        else:
                            print("\033[36mDebug: Yielding first sentence fragment: \"{}\" because word_count {} is >= force_first_fragment_after_words \033[0m".format(yield_text, word_count))

                    yield yield_text

                    buffer = ""
                    word_count = 0
                    if not quick_yield_every_fragment:
                        is_first_sentence = False

                    continue

             # Continue accumulating characters if buffer is under minimum sentence length
            if len(buffer) <= minimum_sentence_length + context_size:

                continue

            # Update last delimiter position if a new delimiter is found
            if char in full_sentence_delimiters:
                last_delimiter_position = len(buffer) - 1

            # Define context window for checking potential sentence boundaries
            context_window_end_pos = len(buffer) - context_size - 1
            context_window_start_pos = (
                context_window_end_pos - context_size_look_overhead
            )
            if context_window_start_pos < 0:
                context_window_start_pos = 0

            # Tokenize sentences from buffer
            sentences = _tokenize_sentences(buffer, tokenize_sentences)

            if debug:
                print("\033[36mbuffer: \"{}\"\033[0m".format(buffer))
                print("\033[36mlast_delimiter_position: {}\033[0m".format(last_delimiter_position))
                print("\033[36mlen(sentences) > 2: {}\033[0m".format(len(sentences) > 2))
                print("\033[36mcontext_window_start_pos: {}\033[0m".format(context_window_start_pos))
                print("\033[36mcontext_window_end_pos: {}\033[0m".format(context_window_end_pos))

            # Combine sentences below minimum_sentence_length with the next sentence(s)
            combined_sentences = []
            temp_sentence = ""

            for sentence in sentences:
                if len(sentence) < minimum_sentence_length:
                    temp_sentence += sentence + " "
                else:
                    if temp_sentence:
                        temp_sentence += sentence
                        combined_sentences.append(temp_sentence.strip())
                        temp_sentence = ""
                    else:
                        combined_sentences.append(sentence.strip())

            # If there's a leftover temp_sentence that hasn't been appended
            if temp_sentence:
                combined_sentences.append(temp_sentence.strip())

            # Replace the original sentences with the combined_sentences
            sentences = combined_sentences

            # Process and yield sentences based on conditions
            if len(sentences) > 2 or (
                last_delimiter_position >= 0
                and context_window_start_pos
                <= last_delimiter_position
                <= context_window_end_pos
            ):
                
                if len(sentences) > 1:
                    total_length_except_last = sum(
                        len(sentence) for sentence in sentences[:-1]
                    )
                    if total_length_except_last >= minimum_sentence_length:
                        for sentence in sentences[:-1]:
                            yield_text = _clean_text(
                                sentence,
                                cleanup_text_links,
                                cleanup_text_emojis)
                            if debug:
                                print("\033[36mDebug: Yielding sentence: \"{}\"\033[0m".format(yield_text))

                            yield yield_text
                            word_count = 0

                        if quick_yield_for_all_sentences:
                            is_first_sentence = True

                        # we need to remember if the buffer ends with space
                        # - sentences returned by the tokenizers are rtrimmed
                        # - this takes any blank spaces away from the last unfinshed sentence
                        # - we have to work around this by re-adding the blank space in this case
                        ends_with_space = buffer.endswith(" ")

                        # set buffer to last unfinshed sentence returned by tokenizers
                        buffer = sentences[-1]

                        # reset the blank space if it was there:
                        if ends_with_space:
                            buffer += " "

                        # reset the last delimiter position after yielding
                        last_delimiter_position = -1 

    
    # Yield remaining buffer as final sentence(s)
    if buffer:
        sentences = _tokenize_sentences(buffer, tokenize_sentences)
        sentence_buffer = ""

        for sentence in sentences:
            sentence_buffer += sentence
            if len(sentence_buffer) < minimum_sentence_length:
                sentence_buffer += " "

                continue

            if debug:
                print("\033[36mDebug: Yielding final sentence(s): \"{}\"\033[0m".format(yield_text))
            yield_text = _clean_text(
                sentence_buffer, cleanup_text_links, cleanup_text_emojis
            )

            yield yield_text

            sentence_buffer = ""

        if sentence_buffer:
            yield_text = _clean_text(
                sentence_buffer,
                cleanup_text_links,
                cleanup_text_emojis)
            if debug:
                print("\033[36mDebug: Yielding remaining text: \"{}\"\033[0m".format(yield_text))

            yield yield_text


def _await_sync(f: Awaitable[str]) -> str:
    gen = f.__await__()
    try:
        next(gen)
        raise RuntimeError(f"{f} failed to be synchronous")
    except StopIteration as e:
        return e.value


def _async_iter_to_sync(f: AsyncIterator[str]) -> Iterator[str]:
    try:
        while True:
            yield _await_sync(f.__anext__())
    except StopAsyncIteration:
        return


P = ParamSpec("P")


def _dowrap(
    f: Callable[Concatenate[AsyncIterable[str], P], AsyncIterator[str]]
) -> Callable[Concatenate[Iterable[str], P], Iterator[str]]:
    @functools.wraps(f)
    def inner(generator: Iterable[str], *args: P.args, **kwargs: P.kwargs):
        async def gen_wrap():
            for x in generator:
                yield x

        return _async_iter_to_sync(f(gen_wrap(), *args, **kwargs))

    return inner


generate_sentences = _dowrap(generate_sentences_async)
generate_sentences.__name__ = "generate_sentences"
generate_sentences.__qualname__ = "generate_sentences"

"""
Real-time processing and delivery of sentences
from a continuous stream of characters or text chunks
"""

import collections
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
    Optional,
    ParamSpec,
)

import emoji

from stream2sentence.quick_yield_boundary import HOLD, REJECT, SPLIT, get_boundary_detector

current_tokenizer = "nltk"
current_language = "en"
stanza_initialized = False
nltk_initialized = False
nlp = None

_QUICK_YIELD_TERMINATORS = ".?!。！？؟।"
_QUICK_YIELD_CLOSING_MARKS = "\"')]}”’»›"
_QUICK_YIELD_PRE_TERMINAL_CLOSING_MARKS = ")]}"


def _normalize_tokenizer(tokenizer: str) -> str:
    tokenizer = (tokenizer or "nltk").lower().replace("_", "-")
    if tokenizer in {"rule-based", "rules"}:
        return "rule-based"
    if tokenizer in {
        "consensus",
        "nltk+rule-based",
        "nltk-rule-based",
        "nltk+rules",
        "nltk-rules",
    }:
        return "nltk+rule-based"
    return tokenizer


def initialize_nltk(language: str = "en", debug=False):
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


def _generate_characters_from_chunk(
    chunk: str, log_characters: bool = False
) -> Iterator[str]:
    """
    Generates individual characters from a text.

    Args:
        chunk (str): Input text
        log_characters (bool): Whether to log the characters to the console

    Yields:
        Individual characters from the text
    """
    for char in chunk:
        if log_characters:
            print(char, end="", flush=True)
        yield char


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


def _tokenize_sentences(
    text: str,
    tokenize_sentences=None,
    tokenizer: Optional[str] = None,
    language: Optional[str] = None,
) -> list[str]:
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
        tokenizer = _normalize_tokenizer(tokenizer or current_tokenizer)
        language = language or current_language

        if tokenizer == "nltk":
            import nltk

            sentences = nltk.tokenize.sent_tokenize(text)
        elif tokenizer == "rule-based":
            sentences = _rule_based_tokenize_sentences(text, language)
        elif tokenizer == "nltk+rule-based":
            sentences = _nltk_rule_based_tokenize_sentences(text, language)
        elif tokenizer == "stanza":
            import stanza

            global nlp
            doc = nlp(text)
            sentences = [sentence.text for sentence in doc.sentences]
        else:
            raise ValueError(f"Unknown tokenizer: {tokenizer}")
        nlp_end_time = time.time()
        logging.debug("Time to split sentences: " f"{nlp_end_time - nlp_start_time}")
    return sentences


def _rule_based_tokenize_sentences(text: str, language: str = "en") -> list[str]:
    detector = get_boundary_detector(language)
    sentence_terminators = set(".?!。！？؟।")
    closing_marks = "\"')]}”’»›"
    sentences = []
    start = 0
    index = 0

    while index < len(text):
        char = text[index]
        if char not in sentence_terminators:
            index += 1
            continue

        segment = text[start:]
        next_char = text[index + 1] if index + 1 < len(text) else None
        action = detector.classify(segment, index - start, next_char)
        if action != SPLIT:
            index += 1
            continue

        end = index + 1
        while end < len(text) and text[end] in sentence_terminators:
            end += 1
        while end < len(text) and text[end] in closing_marks:
            end += 1

        sentence = text[start:end].strip()
        if sentence:
            sentences.append(sentence)

        while end < len(text) and text[end].isspace():
            end += 1

        start = end
        index = end

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)

    return sentences


def _sentence_boundary_offsets(text: str, sentences: list[str]) -> list[int]:
    offsets = []
    search_start = 0

    for sentence in sentences[:-1]:
        sentence = sentence.strip()
        if not sentence:
            continue

        while search_start < len(text) and text[search_start].isspace():
            search_start += 1

        match_start = text.find(sentence, search_start)
        if match_start < 0:
            return []

        boundary = match_start + len(sentence)
        offsets.append(boundary)
        search_start = boundary

    return offsets


def _sentences_from_boundary_offsets(text: str, offsets: list[int]) -> list[str]:
    sentences = []
    start = 0

    for offset in offsets:
        sentence = text[start:offset].strip()
        if sentence:
            sentences.append(sentence)
        start = offset

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)

    return sentences


def _nltk_rule_based_tokenize_sentences(text: str, language: str = "en") -> list[str]:
    import nltk

    nltk_sentences = nltk.tokenize.sent_tokenize(text)
    rule_based_sentences = _rule_based_tokenize_sentences(text, language)
    nltk_offsets = set(_sentence_boundary_offsets(text, nltk_sentences))
    rule_based_offsets = set(_sentence_boundary_offsets(text, rule_based_sentences))
    consensus_offsets = sorted(nltk_offsets & rule_based_offsets)

    return _sentences_from_boundary_offsets(text, consensus_offsets)


def init_tokenizer(tokenizer: str, language: str = "en", offline=False, debug=False):
    """
    Initializes the sentence tokenizer.
    """
    global current_language, current_tokenizer
    tokenizer = _normalize_tokenizer(tokenizer)
    current_tokenizer = tokenizer
    current_language = language

    if tokenizer == "nltk":
        initialize_nltk(language, debug)
    elif tokenizer == "stanza":
        initialize_stanza(language, offline=offline)
    elif tokenizer == "rule-based":
        return
    elif tokenizer == "nltk+rule-based":
        initialize_nltk(language, debug)
        return
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
    auto_context: bool = False,
    cleanup_text_links: bool = False,
    cleanup_text_emojis: bool = False,
    tokenize_sentences=None,
    tokenizer: str = "nltk",
    language: str = "en",
    log_characters: bool = False,
    sentence_fragment_delimiters: str = ".?!;:,\n…)]}。-",
    full_sentence_delimiters: str = ".?!\n…。",
    force_first_fragment_after_words=30,
    filter_first_non_alnum_characters: bool = False,
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
        auto_context (bool): If True, safe sentence boundaries may be yielded
          before the full context_size delay when the boundary detector and
          tokenizer agree. Default is False.
        cleanup_text_links (bool): If True, removes hyperlinks from the text
          stream to ensure clean output.
        cleanup_text_emojis (bool): If True, filters out emojis from the text
          stream for clear textual content.
        tokenize_sentences (Callable): A function that tokenizes sentences
          from the input text. Defaults to None.
        tokenizer (str): The tokenizer to use for sentence tokenization.
          Default is "nltk". Can be "nltk", "stanza", "rule-based", or
          "nltk+rule-based". The "nltk+rule-based" tokenizer only splits at
          sentence boundaries where NLTK and the rule-based tokenizer agree.
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
        filter_first_non_alnum_characters (bool): If True, filters out the
          first non-alphanumeric characters from the text stream.
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
    sentence_splitter = SentenceSplitter(
        context_size=context_size,
        context_size_look_overhead=context_size_look_overhead,
        minimum_sentence_length=minimum_sentence_length,
        minimum_first_fragment_length=minimum_first_fragment_length,
        quick_yield_single_sentence_fragment=quick_yield_single_sentence_fragment,
        quick_yield_for_all_sentences=quick_yield_for_all_sentences,
        quick_yield_every_fragment=quick_yield_every_fragment,
        auto_context=auto_context,
        cleanup_text_links=cleanup_text_links,
        cleanup_text_emojis=cleanup_text_emojis,
        tokenize_sentences=tokenize_sentences,
        tokenizer=tokenizer,
        language=language,
        log_characters=log_characters,
        sentence_fragment_delimiters=sentence_fragment_delimiters,
        full_sentence_delimiters=full_sentence_delimiters,
        force_first_fragment_after_words=force_first_fragment_after_words,
        filter_first_non_alnum_characters=filter_first_non_alnum_characters,
        debug=debug,
    )

    if log_characters:
        print("Stream: ", end="", flush=True)

    async for chunk in generator:
        sentence_splitter.add(chunk)
        for sentence in sentence_splitter.stream():
            yield sentence

    if log_characters:
        print()

    for sentence in sentence_splitter.flush():
        yield sentence


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


class SentenceSplitter:
    def __init__(
        self,
        context_size: int = 12,
        context_size_look_overhead: int = 12,
        minimum_sentence_length: int = 10,
        minimum_first_fragment_length=10,
        quick_yield_single_sentence_fragment: bool = False,
        quick_yield_for_all_sentences: bool = False,
        quick_yield_every_fragment: bool = False,
        auto_context: bool = False,
        cleanup_text_links: bool = False,
        cleanup_text_emojis: bool = False,
        tokenize_sentences=None,
        tokenizer: str = "nltk",
        language: str = "en",
        log_characters: bool = False,
        sentence_fragment_delimiters: str = ".?!;:,\n…)]}。-",
        full_sentence_delimiters: str = ".?!\n…。",
        force_first_fragment_after_words=30,
        filter_first_non_alnum_characters: bool = False,
        debug=False,
    ):
        """
        Generates well-formed sentences from a stream of characters or text chunks
        provided by an input generator.

        Args:
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
            auto_context (bool): If True, safe sentence boundaries may be
            yielded before the full context_size delay when the boundary detector
            and tokenizer agree. Default is False.
            cleanup_text_links (bool): If True, removes hyperlinks from the text
            stream to ensure clean output.
            cleanup_text_emojis (bool): If True, filters out emojis from the text
            stream for clear textual content.
            tokenize_sentences (Callable): A function that tokenizes sentences
            from the input text. Defaults to None.
            tokenizer (str): The tokenizer to use for sentence tokenization.
            Default is "nltk". Can be "nltk", "stanza", "rule-based", or
            "nltk+rule-based". The "nltk+rule-based" tokenizer only splits at
            sentence boundaries where NLTK and the rule-based tokenizer agree.
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
            filter_first_non_alnum_characters (bool): If True, filters out the
            first non-alphanumeric characters from the text stream.
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

        global current_tokenizer
        current_tokenizer = _normalize_tokenizer(tokenizer)
        init_tokenizer(current_tokenizer, language, debug=debug)

        self.input_buffer = collections.deque[str]()
        self.buffer = ""
        self.is_first_sentence = True
        self.word_count = 0  # Initialize word count
        self.last_delimiter_position = -1  # Position of last full sentence delimiter
        self.pending_quick_yield_boundary = None

        # Adjust quick yield flags based on settings
        if quick_yield_every_fragment:
            quick_yield_for_all_sentences = True

        if quick_yield_for_all_sentences:
            quick_yield_single_sentence_fragment = True

        self.context_size = context_size
        self.context_size_look_overhead = context_size_look_overhead
        self.minimum_sentence_length = minimum_sentence_length
        self.minimum_first_fragment_length = minimum_first_fragment_length
        self.quick_yield_single_sentence_fragment = quick_yield_single_sentence_fragment
        self.quick_yield_for_all_sentences = quick_yield_for_all_sentences
        self.quick_yield_every_fragment = quick_yield_every_fragment
        self.auto_context = auto_context
        self.cleanup_text_links = cleanup_text_links
        self.cleanup_text_emojis = cleanup_text_emojis
        self.tokenize_sentences = tokenize_sentences
        self.tokenizer = current_tokenizer
        self.language = language
        self.quick_yield_boundary_detector = get_boundary_detector(language)
        self.log_characters = log_characters
        self.sentence_fragment_delimiters = sentence_fragment_delimiters
        self.full_sentence_delimiters = full_sentence_delimiters
        self.force_first_fragment_after_words = force_first_fragment_after_words
        self.filter_first_non_alnum_characters = filter_first_non_alnum_characters
        self.debug = debug

    def add(self, chunk: str):
        self.input_buffer.append(chunk)

    def _quick_yield_boundary_end(self, boundary_position):
        boundary_end = boundary_position
        while (
            boundary_end + 1 < len(self.buffer)
            and self.buffer[boundary_end + 1] in _QUICK_YIELD_CLOSING_MARKS
        ):
            boundary_end += 1
        return boundary_end

    def _has_quick_yield_lookahead(self, boundary_position):
        return self._quick_yield_boundary_end(boundary_position) < len(self.buffer) - 1

    def _is_quick_yield_terminal(self, boundary_position):
        return self.buffer[boundary_position] in _QUICK_YIELD_TERMINATORS

    def _is_quick_yield_pre_terminal_closing_mark(self, boundary_position):
        return self.buffer[boundary_position] in _QUICK_YIELD_PRE_TERMINAL_CLOSING_MARKS

    def _auto_context_boundary_offset(self):
        if not self.auto_context or self.last_delimiter_position < 0:
            return None

        boundary_position = self.last_delimiter_position
        boundary_end = self._quick_yield_boundary_end(boundary_position)
        if not self._has_quick_yield_lookahead(boundary_position):
            return None

        next_char = self.buffer[boundary_end + 1]
        action = self.quick_yield_boundary_detector.classify(
            self.buffer,
            boundary_position,
            next_char,
        )
        if action != SPLIT:
            return None

        return boundary_end + 1

    def _auto_context_matches_tokenizer(self, sentences, boundary_offset):
        offsets = _sentence_boundary_offsets(self.buffer, sentences)
        return bool(offsets) and offsets[0] == boundary_offset

    def _consume_quick_yield_text(self, boundary_position=None):
        if boundary_position is None:
            text = self.buffer
            self.buffer = ""
        else:
            text = self.buffer[:boundary_position + 1]
            self.buffer = self.buffer[boundary_position + 1:].lstrip()

        self.word_count = 0
        self.pending_quick_yield_boundary = None
        if not self.quick_yield_every_fragment:
            self.is_first_sentence = False

        return _clean_text(text, self.cleanup_text_links, self.cleanup_text_emojis)

    def stream(self):
        while self.input_buffer:
            chunk = self.input_buffer.popleft()
            for char in _generate_characters_from_chunk(chunk, self.log_characters):
                if char:
                    if len(self.buffer) == 0:
                        if self.filter_first_non_alnum_characters:
                            if not char.isalnum():
                                continue

                    self.buffer = (self.buffer + char).lstrip()

                    if self.pending_quick_yield_boundary is not None:
                        boundary_position = self.pending_quick_yield_boundary
                        boundary_end = self._quick_yield_boundary_end(boundary_position)
                        if self._is_quick_yield_terminal(boundary_position):
                            if not self._has_quick_yield_lookahead(boundary_position):
                                continue
                            next_char = self.buffer[boundary_end + 1]
                        elif boundary_position < len(self.buffer) - 1:
                            next_char = self.buffer[boundary_position + 1]
                        else:
                            continue

                        if (
                            self._is_quick_yield_pre_terminal_closing_mark(boundary_position)
                            and next_char in _QUICK_YIELD_TERMINATORS
                        ):
                            self.pending_quick_yield_boundary = None
                        elif boundary_position < len(self.buffer) - 1:
                            action = self.quick_yield_boundary_detector.classify(
                                self.buffer,
                                boundary_position,
                                next_char,
                            )
                            if action != HOLD:
                                self.pending_quick_yield_boundary = None
                            if action == SPLIT:
                                yield_text = self._consume_quick_yield_text(boundary_end)
                                if self.debug:
                                    print("\033[36mDebug: Yielding first sentence fragment: \"{}\" after confirming pending delimiter\033[0m".format(yield_text))
                                yield yield_text
                                continue

                    # Update word count on encountering space or sentence fragment delimiter
                    if char.isspace() or char in self.sentence_fragment_delimiters:
                        self.word_count += 1

                    if self.debug:
                        print("\033[36mDebug: Added char, buffer size: \"{}\"\033[0m".format(len(self.buffer)))

                    # Check conditions to yield first sentence fragment quickly
                    if (
                        self.is_first_sentence
                        and len(self.buffer) > self.minimum_first_fragment_length
                        and self.quick_yield_single_sentence_fragment
                    ):

                        if self.buffer[-1] in self.sentence_fragment_delimiters:
                            boundary_position = len(self.buffer) - 1
                            action = self.quick_yield_boundary_detector.classify(
                                self.buffer,
                                boundary_position,
                            )
                            if action == HOLD:
                                self.pending_quick_yield_boundary = boundary_position
                                continue
                            if action == REJECT:
                                continue
                            if self._is_quick_yield_terminal(boundary_position):
                                self.pending_quick_yield_boundary = boundary_position
                                continue
                            if self._is_quick_yield_pre_terminal_closing_mark(boundary_position):
                                self.pending_quick_yield_boundary = boundary_position
                                continue

                            yield_text = self._consume_quick_yield_text()
                            if self.debug:
                                print("\033[36mDebug: Yielding first sentence fragment: \"{}\" because buffer[-1] is sentence frag \033[0m".format(yield_text))

                            yield yield_text

                            continue

                        if char.isspace() and self.word_count >= self.force_first_fragment_after_words:
                            word_count = self.word_count
                            yield_text = self._consume_quick_yield_text()
                            if self.debug:
                                print("\033[36mDebug: Yielding first sentence fragment: \"{}\" because word_count {} is >= force_first_fragment_after_words \033[0m".format(yield_text, word_count))

                            yield yield_text

                            continue

                    if self.auto_context and char in self.full_sentence_delimiters:
                        self.last_delimiter_position = len(self.buffer) - 1

                    context_ready = (
                        len(self.buffer) > self.minimum_sentence_length + self.context_size
                    )

                    # Continue accumulating characters if buffer is under minimum sentence length
                    if not context_ready:
                        if (
                            not self.auto_context
                            or self.last_delimiter_position < 0
                            or len(self.buffer) <= self.minimum_sentence_length
                        ):
                            continue

                    elif char in self.full_sentence_delimiters:
                        self.last_delimiter_position = len(self.buffer) - 1

                    auto_context_boundary_offset = self._auto_context_boundary_offset()
                    if not context_ready and auto_context_boundary_offset is None:
                        continue

                    # Define context window for checking potential sentence boundaries
                    context_window_end_pos = len(self.buffer) - self.context_size - 1
                    context_window_start_pos = (
                        context_window_end_pos - self.context_size_look_overhead
                    )
                    if context_window_start_pos < 0:
                        context_window_start_pos = 0

                    # Tokenize sentences from buffer
                    sentences = _tokenize_sentences(
                        self.buffer,
                        self.tokenize_sentences,
                        self.tokenizer,
                        self.language,
                    )

                    if self.debug:
                        print("\033[36mbuffer: \"{}\"\033[0m".format(self.buffer))
                        print("\033[36mlast_delimiter_position: {}\033[0m".format(self.last_delimiter_position))
                        print("\033[36mlen(sentences) > 2: {}\033[0m".format(len(sentences) > 2))
                        print("\033[36mcontext_window_start_pos: {}\033[0m".format(context_window_start_pos))
                        print("\033[36mcontext_window_end_pos: {}\033[0m".format(context_window_end_pos))

                    # Combine sentences below minimum_sentence_length with the next sentence(s)
                    combined_sentences = []
                    temp_sentence = ""

                    for sentence in sentences:
                        if len(sentence) < self.minimum_sentence_length:
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
                    auto_context_ready = (
                        auto_context_boundary_offset is not None
                        and self._auto_context_matches_tokenizer(
                            sentences,
                            auto_context_boundary_offset,
                        )
                    )
                    if auto_context_ready or (
                        context_ready
                        and (
                            len(sentences) > 2
                            or (
                                self.last_delimiter_position >= 0
                                and context_window_start_pos
                                <= self.last_delimiter_position
                                <= context_window_end_pos
                            )
                        )
                    ):

                        if len(sentences) > 1:
                            total_length_except_last = sum(
                                len(sentence) for sentence in sentences[:-1]
                            )
                            if total_length_except_last >= self.minimum_sentence_length:
                                for sentence in sentences[:-1]:
                                    yield_text = _clean_text(
                                        sentence,
                                        self.cleanup_text_links,
                                        self.cleanup_text_emojis)
                                    if self.debug:
                                        print("\033[36mDebug: Yielding sentence: \"{}\"\033[0m".format(yield_text))

                                    yield yield_text
                                    self.word_count = 0

                                if self.quick_yield_for_all_sentences:
                                    self.is_first_sentence = True

                                # we need to remember if the buffer ends with space
                                # - sentences returned by the tokenizers are rtrimmed
                                # - this takes any blank spaces away from the last unfinshed sentence
                                # - we have to work around this by re-adding the blank space in this case
                                ends_with_space = self.buffer.endswith(" ")

                                # set buffer to last unfinshed sentence returned by tokenizers
                                self.buffer = sentences[-1]

                                # reset the blank space if it was there:
                                if ends_with_space:
                                    self.buffer += " "

                                # reset the last delimiter position after yielding
                                self.last_delimiter_position = -1 

    def flush(self):
        # Yield remaining buffer as final sentence(s)
        if self.buffer:
            sentences = _tokenize_sentences(
                self.buffer,
                self.tokenize_sentences,
                self.tokenizer,
                self.language,
            )
            sentence_buffer = ""

            for sentence in sentences:
                sentence_buffer += sentence
                if len(sentence_buffer) < self.minimum_sentence_length:
                    sentence_buffer += " "

                    continue

                yield_text = _clean_text(
                    sentence_buffer, self.cleanup_text_links, self.cleanup_text_emojis
                )

                if self.debug:
                    print("\033[36mDebug: Yielding final sentence(s): \"{}\"\033[0m".format(yield_text))

                yield yield_text

                sentence_buffer = ""

            if sentence_buffer:
                yield_text = _clean_text(
                    sentence_buffer,
                    self.cleanup_text_links,
                    self.cleanup_text_emojis)
                if self.debug:
                    print("\033[36mDebug: Yielding remaining text: \"{}\"\033[0m".format(yield_text))

                yield yield_text

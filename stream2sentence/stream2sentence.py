"""
Real-time processing and delivery of sentences from a continuous stream of characters or text chunks
"""

from typing import Iterator
import logging
import emoji
import time
import re

current_tokenizer = "nltk"
stanza_initialized = False
nltk_initialized = False
nlp = None

def initialize_nltk():
    """
    Initializes NLTK by downloading required data for sentence tokenization.
    """
    global nltk_initialized
    if nltk_initialized:
        return
    print ("Starting tokenizer nltk")
    import nltk
    try:
        _ = nltk.data.find('tokenizers/punkt') 
    except LookupError:
        nltk.download('punkt')
    nltk_initialized = True

def initialize_stanza(language: str = "en"):
    """
    Initializes Stanza by downloading required data for sentence tokenization.
    """
    global stanza_initialized
    if stanza_initialized:
        return
    print (f"Starting tokenizer stanza with language {language}")
    import stanza
    global nlp
    stanza.download(language)
    nlp = stanza.Pipeline(language)
    stanza_initialized = True

def _remove_links(text: str) -> str:
    """
    Removes any links from the input text.

    Args:
        text (str): Input text

    Returns:
        str: Text with links removed
    """
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.sub(pattern, '', text)

def _remove_emojis(text: str) -> str:
    """
    Removes emojis from the input text.

    Args:
        text (str): Input text
    
    Returns:
        str: Text with emojis removed
    """
    return emoji.replace_emoji(text, u'')

def _generate_characters(generator: Iterator[str], 
                         log_characters: bool = False) -> Iterator[str]:
    """
    Generates individual characters from a text generator.

    Args:
        generator (Iterator[str]): Input text generator
        log_characters (bool): Whether to log the characters to the console

    Yields:
        Individual characters from the generator
    """
    for chunk in generator:
        for char in chunk:
            if log_characters:
                print(char, end="", flush=True)
            yield char
            
def _clean_text(text: str, 
                cleanup_text_links: bool = False, 
                cleanup_text_emojis: bool = False,
                strip_text: bool = True) -> str:
    """
    Cleans the text by removing links and emojis.

    Args:
        text (str): Input text
        cleanup_text_links (boolean, optional): Remove non-desired links from the stream.
        cleanup_text_emojis (boolean, optional): Remove non-desired emojis from the stream. 
    
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

def _tokenize_sentences(text: str, tokenize_sentences = None) -> Iterator[str]:
    """
    Tokenizes sentences from the input text.

    Args:
        text (str): Input text
        tokenize_sentences (Callable, optional): A function that tokenizes sentences from the input text. Defaults to None.

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
        logging.info(f"Time to split sentences: {nlp_end_time - nlp_start_time}")
    return sentences

def _init_tokenizer(language: str = "en"):
    """
    Initializes the sentence tokenizer.
    """
    if current_tokenizer == "nltk":
        initialize_nltk()
    elif current_tokenizer == "stanza":
        initialize_stanza(language)

def generate_sentences(generator: Iterator[str],  
                       context_size: int = 12,
                       minimum_sentence_length: int = 10,
                       minimum_first_fragment_length = 10,
                       quick_yield_single_sentence_fragment: bool = False,
                       cleanup_text_links: bool = False,
                       cleanup_text_emojis: bool = False, 
                       tokenize_sentences = None,
                       tokenizer: str = "nltk",
                       language: str = "en",
                       log_characters: bool = False) -> Iterator[str]:
    """
    Generates well-formed sentences from a stream of characters or text chunks provided by an input generator.

    Args:
        generator (Iterator[str]): A generator that yields chunks of text as a stream of characters.
        context_size (int): The number of characters used to establish context for sentence boundary detection. A larger context improves the accuracy of detecting sentence boundaries. Default is 12 characters.
        minimum_sentence_length (int): The minimum number of characters a sentence must have. If a sentence is shorter, it will be concatenated with the following one, improving the overall readability. This parameter does not apply to the first sentence fragment, which is governed by `minimum_first_fragment_length`. Default is 10 characters.
        minimum_first_fragment_length (int): The minimum number of characters required for the first sentence fragment before yielding. Default is 10 characters.
        quick_yield_single_sentence_fragment (bool): If set to True, the generator will yield the first sentence fragment as quickly as possible. This is particularly useful for real-time applications such as speech synthesis.
        cleanup_text_links (bool): If True, removes hyperlinks from the text stream to ensure clean output.
        cleanup_text_emojis (bool): If True, filters out emojis from the text stream for clear textual content.
        log_characters (bool): If True, logs each character to the console as they are processed.

    Yields:
        Iterator[str]: An iterator of complete sentences constructed from the input text stream. Each yielded sentence meets the specified minimum length requirements and is cleaned up if specified.

    The function maintains a buffer to accumulate text chunks and applies natural language processing to detect sentence boundaries. It employs various heuristics, such as minimum sentence length and sentence delimiters, to ensure the quality of the output sentences. The function also provides options to clean up the text stream, making it versatile for different types of text processing applications.
    """

    global current_tokenizer
    current_tokenizer = tokenizer
    _init_tokenizer(language)

    buffer = ''
    is_first_sentence = True

    sentence_delimiters = '.?!;:,\n…)]}。'

    for char in _generate_characters(generator, log_characters):

        if char:
            buffer += char
            buffer = buffer.lstrip()

            if is_first_sentence and len(buffer) > minimum_first_fragment_length and quick_yield_single_sentence_fragment:

                if buffer[-1] in sentence_delimiters:
                    yield_text = _clean_text(buffer, cleanup_text_links, cleanup_text_emojis)
                    yield yield_text
                    buffer = ""
                    is_first_sentence = False
                    continue

            # Check if minimum length reached
            if len(buffer) <= minimum_sentence_length + context_size:
                continue

            # Potential delimiter character has to be a bit away from the end of the buffer
            # For reliable sentence detection the engine needs enough context to work with
            delimiter_char = buffer[-context_size]

            if delimiter_char in sentence_delimiters:                
                sentences = _tokenize_sentences(buffer, tokenize_sentences)
                if len(sentences) > 1:
                    if len(sentences[0]) == len(buffer) - context_size + 1:
                        yield_text = _clean_text(buffer[:-context_size + 1], cleanup_text_links, cleanup_text_emojis)
                        yield yield_text
                        buffer = buffer[-context_size + 1:]
                        is_first_sentence = False

    # Yield remaining buffer
    if buffer:
        sentences = _tokenize_sentences(buffer, tokenize_sentences)
        sentence_buffer = ""

        for sentence in sentences:
            sentence_buffer += sentence
            if len(sentence_buffer) < minimum_sentence_length:
                sentence_buffer += " "
                continue
            yield_text = _clean_text(sentence_buffer, cleanup_text_links, cleanup_text_emojis)
            yield yield_text

            sentence_buffer = ""
        
        if sentence_buffer:
            yield_text = _clean_text(sentence_buffer, cleanup_text_links, cleanup_text_emojis)
            yield yield_text
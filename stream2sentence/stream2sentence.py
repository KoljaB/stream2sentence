"""
Real-time processing and delivery of sentences from a continuous stream of characters or text chunks
"""

import re
import nltk
from typing import Iterator

def initialize_nltk():
    """
    Initializes NLTK by downloading required data for sentence tokenization.
    """
    try:
        _ = nltk.data.find('tokenizers/punkt') 
    except LookupError:
        nltk.download('punkt')

initialize_nltk()

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
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F" 
                               u"\U0001F300-\U0001F5FF"
                               u"\U0001F680-\U0001F6FF" 
                               u"\U0001F1E0-\U0001F1FF"
                               u"\U00002702-\U000027B0"  
                               u"\U000024C2-\U0001F251"
                               "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def _generate_characters(generator: Iterator[str]):
    """
    Generates individual characters from a text generator.

    Args:
        generator (Iterator[str]): Input text generator

    Yields:
        Individual characters from the generator
    """
    for chunk in generator:
        for char in chunk:
            yield char
            
def _clean_text(text: str, 
               cleanup_text_links: bool = False, 
               cleanup_text_emojis: bool = False) -> str:
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
    return text

def generate_sentences(generator: Iterator[str],  
                       context_size: int = 10,
                       minimum_sentence_length: int = 8,
                       quick_yield_single_sentence_fragment: bool = False,
                       cleanup_text_links: bool = False,
                       cleanup_text_emojis: bool = False) -> Iterator[str]:
    """
    Generates sentences from a stream of characters or input chunks.

    Args:
        generator (Iterator[str]): Input character generator
        context_size (int): The character context size for sentence detection. A larger context ensures more reliable sentence detection. Default value is 10 characters.
        minimum_sentence_length (int): Minimum character length for a sentence. Short sentences will combine with the subsequent sentence to enhance synthesis quality. Default value is 8 characters.
        quick_yield_single_sentence_fragment (bool): Whether to return a sentence fragment as fast as possible (for realtime speech synthesis)
        cleanup_text_links (boolean, optional): Remove non-desired links from the stream.
        cleanup_text_emojis (boolean, optional): Remove non-desired emojis from the stream. 

    Yields:
        Iterator[str]: Sentences based on input characters  
    """
    
    buffer = ''
    is_first_sentence = True

    sentence_delimiters = '.?!;:-,\n…)]}'

    for char in _generate_characters(generator):
        if char:
            buffer += char

            # Check if minimum length reached
            if len(buffer) <= minimum_sentence_length + context_size:
                continue

            # Potential delimiter character has to be a bit away from the end of the buffer
            # For reliable sentence detection the engine needs enough context to work with
            delimiter_char = buffer[-context_size]

            sentence_fragment_detected = False
            if delimiter_char in sentence_delimiters and buffer[-context_size + 1] == ' ':
                
                # Handle first sentence case
                if quick_yield_single_sentence_fragment and is_first_sentence:
                    sentence_fragment_detected = True
                else:
                    sentences = nltk.tokenize.sent_tokenize(buffer)
                    if len(sentences) > 1:
                        sentence_fragment_detected = True
                        
                # Yield sentence
                if sentence_fragment_detected:
                    yield _clean_text(buffer[:-context_size + 2], cleanup_text_links, cleanup_text_emojis)
                    buffer = buffer[-context_size + 2:]
                    is_first_sentence = False

    # Yield remaining buffer
    if buffer:
        yield _clean_text(buffer, cleanup_text_links, cleanup_text_emojis)
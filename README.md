# Real-Time Sentence Detection

Real-time processing and delivery of sentences from a continuous stream of characters or text chunks.

> **Hint:** *If you're interested in state-of-the-art voice solutions you might also want to <strong>have a look at [Linguflex](https://github.com/KoljaB/Linguflex)</strong>, the original project from which stream2sentence is spun off. It lets you control your environment by speaking and is one of the most capable and sophisticated open-source assistants currently available.*

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Features

- Generates sentences from a stream of text in real-time.
- Customizable to finetune/balance speed vs reliability.
- Option to clean the output by removing links and emojis from the detected sentences.
- Easy to configure and integrate.

## Installation

```bash
pip install stream2sentence
```

## Usage

Pass a generator of characters or text chunks to `generate_sentences()` to get a generator of sentences in return.

Here's a basic example:

```python
from stream2sentence import generate_sentences

# Dummy generator for demonstration
def dummy_generator():
    yield "This is a sentence. And here's another! Yet, "
    yield "there's more. This ends now."

for sentence in generate_sentences(dummy_generator()):
    print(sentence)
```

This will output:
```
This is a sentence.
And here's another!
Yet, there's more.
This ends now.
```

One main use case of this library is enable fast text to speech synthesis in the context of character feeds generated from large language models: this library enables fastest possible access to a complete sentence or sentence fragment (using the quick_yield_single_sentence_fragment flag) that then can be synthesized in realtime. The usage of this is demonstrated in the test_stream_from_llm.py file in the tests directory.

## Configuration

The `generate_sentences()` function offers various parameters to fine-tune its behavior:

### Core Parameters

- `generator: Iterator[str]`
  - The primary input source, yielding chunks of text to be processed.
  - Can be any iterator that emits text chunks of any size.

- `context_size: int = 12`
  - Number of characters considered for sentence boundary detection.
  - Larger values improve accuracy but may increase latency.
  - Default: 12 characters

- `context_size_look_overhead: int = 12`
  - Additional characters to examine beyond `context_size` for sentence splitting.
  - Enhances sentence detection accuracy.
  - Default: 12 characters

- `minimum_sentence_length: int = 10`
  - Minimum character count for a text chunk to be considered a sentence.
  - Shorter fragments are buffered until this threshold is met.
  - Default: 10 characters

- `minimum_first_fragment_length: int = 10`
  - Minimum character count required for the first sentence fragment.
  - Ensures the initial output meets a specified length threshold.
  - Default: 10 characters

### Yield Control

These parameters control how quickly and frequently the generator yields sentence fragments:

- `quick_yield_single_sentence_fragment: bool = False`
  - When True, yields the first fragment of the first sentence as quickly as possible.
  - Useful for getting immediate output in real-time applications like speech synthesis.
  - Default: False

- `quick_yield_for_all_sentences: bool = False`
  - When True, yields the first fragment of every sentence as quickly as possible.
  - Extends the quick yield behavior to all sentences, not just the first one.
  - Automatically sets `quick_yield_single_sentence_fragment` to True.
  - Default: False

- `quick_yield_every_fragment: bool = False`
  - When True, yields every fragment of every sentence as quickly as possible.
  - Provides the most granular output, yielding fragments as soon as they're detected.
  - Automatically sets both `quick_yield_for_all_sentences` and `quick_yield_single_sentence_fragment` to True.
  - Default: False

### Text Cleanup

- `cleanup_text_links: bool = False`
  - When True, removes hyperlinks from the output sentences.
  - Default: False

- `cleanup_text_emojis: bool = False`
  - When True, removes emoji characters from the output sentences.
  - Default: False

### Tokenization

- `tokenize_sentences: Callable = None`
  - Custom function for sentence tokenization.
  - If None, uses the default tokenizer specified by `tokenizer`.
  - Default: None

- `tokenizer: str = "nltk"`
  - Specifies the tokenizer to use. Options: "nltk" or "stanza"
  - Default: "nltk"

- `language: str = "en"`
  - Language setting for the tokenizer.
  - Use "en" for English or "multilingual" for Stanza tokenizer.
  - Default: "en"

### Debugging and Fine-tuning

- `log_characters: bool = False`
  - When True, logs each processed character to the console.
  - Useful for debugging or monitoring real-time processing.
  - Default: False

- `sentence_fragment_delimiters: str = ".?!;:,\n…)]}。-"`
  - Characters considered as potential sentence fragment delimiters.
  - Used for quick yielding of sentence fragments.
  - Default: ".?!;:,\n…)]}。-"

- `full_sentence_delimiters: str = ".?!\n…。"`
  - Characters considered as full sentence delimiters.
  - Used for more definitive sentence boundary detection.
  - Default: ".?!\n…。"

- `force_first_fragment_after_words: int = 15`
  - Forces the yield of the first sentence fragment after this many words.
  - Ensures timely output even with long opening sentences.
  - Default: 15 words


## Time based strategy
Instead of a purely lexigraphical strategy, a time based strategy is available.
A target tokens per second (tps) is input, and generate_sentences will yield the best
available output (full sentence, longest fragment, or any available buffer, in that order) if it is approaching a "deadline"
where what has been output would be slower than the input tps target. If LLM is more than
two full sentences ahead of the target it will output a sentence even if it's ahead of the "deadline"

`from stream2sentence.stream2sentence_time_based import generate_sentences_time_based`

### Parameters
- `generator (Iterator[str])`
  - A generator that yields chunks of text as a stream of characters.`
- `target_tps: float = 4`
  - the rate in tokens per second you want to use to calculate deadlines for output.
  - Default is 4. (approximately the speed of human speech)
- `lead_time: float = 1`
  - amount of time in seconds to wait for the buffer to build for before returning values.
- `max_wait_for_fragments = [3, 2]`
  - Max amount of time in seconds that the Nth sentence will wait beyond the "deadline" for a "fragment" (text preceeding a fragment delimiter), which is preferred over a piece of buffer.
  - The last value in the array is used for all subsequent checks.
- `min_output_lengths: int[] = [2, 3, 3, 4]`
  - An array that corresponds to the minimum output size in words for the corresponding output sentence, the last value in the array is used for all remaining output.
  - For example [4,5,6] would mean the first piece of output must have 4 words, the second 5 words, and all subsequent 6.
- `preferred_sentence_fragment_delimiters: str[] = ['. ', '? ', '! ', '\n']`
  - Array of strings that deliniate a sentence fragment. "Preferred" are checked first and always used if the fragment meets the length requirement over the other fragment delimiters.
  - Note the trailing spaces, added to differentiate between values like $3.5 and a proper sentence end
- `sentence_fragment_delimiters: str[] = ['; ', ': ', ', ', '* ', '**', '– ']`
  - Array of strings that are checked after "preferred" delimiters
- `delimiter_ignore_prefixes: str[]` 
  - Array of strings that will not be considered "delimiters" if preceeded by a delimiter.
  - Used to ignore common abbreviations for things like Mr. Dr. and Mrs. where we don't want to split
  - Default is a long list documented in delimiter_ignore_prefixes
- `wait_for_if_non_fragment: str[]`
  - Array of strings that the algorithm will not use as the last value if the whole buffer is being output (not a fragment or sentence).
  - Avoids awkward pauses on common words that are unnatural to pause at.
  - Default is a long list of common words documented in avoid_pause_words.py
- `deadline_offsets_static: float[] = [1]`
  - Constant amount of time in seconds to subtract from the deadline for first n sentences. 
  - Last value applied to all subsequent sentences
- `deadline_offsets_dynamic: float[] = [0]`: 
  - Added to account for the time it takes a TTS engine to generate output. 
  - For example, if it takes your TTS engine around 1 second to generate 10 words, you can use a value of 0.1 so that the TTS generation time is included in the deadline. 
  - Applied to first n sentences, last value applied to all subsequent

## Contributing

Any Contributions you make are welcome and **greatly appreciated**.

1. **Fork** the Project.
2. **Create** your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. **Commit** your Changes (`git commit -m 'Add some AmazingFeature'`).
4. **Push** to the Branch (`git push origin feature/AmazingFeature`).
5. **Open** a Pull Request.

## License

This project is licensed under the MIT License. For more details, see the [`LICENSE`](LICENSE) file.

---

Project created and maintained by [Kolja Beigel](https://github.com/KoljaB).

# Real-Time Sentence Detection

Real-time processing and delivery of sentences from a continuous stream of characters or text chunks.

> **Hint:** *If you're interested in state-of-the-art voice solutions you might also want to <strong>have a look at [Linguflex](https://github.com/KoljaB/Linguflex)</strong>, the original project from which stream2sentence is spun off. It lets you control your environment by speaking and is one of the most capable and sophisticated open-source assistants currently available.*

## Demo

https://github.com/user-attachments/assets/0428d806-4b30-47fa-9cfe-8fb42c95b2e4

[CLI demo code (reproduces the video above)](tests/show_consensus_stress_split.py)

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

Requires Python 3.10 or newer.

```bash
pip install stream2sentence
```

The base installation uses stream2sentence's built-in rule-based tokenizer and
does not install NLTK or Stanza. Install either tokenizer only when you need it:

```bash
pip install "stream2sentence[nltk]"
pip install "stream2sentence[stanza]"
pip install "stream2sentence[nltk,stanza]"  # both, using standard pip extras
pip install "stream2sentence[all]"          # both
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

For speech synthesis, enable `quick_yield_single_sentence_fragment` to start speaking before the first full sentence is available. See `tests/test_stream_from_llm.py` for a live API example.

Use `generate_sentences_async()` with an asynchronous input iterator. For a push-style integration, create a `SentenceSplitter`, call `add(chunk)`, consume `stream()` after each addition, and consume `flush()` at the end. It drains pending input and resets the splitter for reuse; another flush without new input yields nothing. Exhaust each returned iterator before adding more input.

### Recommended English setup

For English streams where the optional NLTK extra is installed, the recommended configuration is `tokenizer="nltk+rule-based"` with `auto_context=True`. This combines NLTK sentence splitting with stream2sentence's local boundary checks and allows safe sentence boundaries to be yielded earlier than the fixed context window when both checks support the split.

```python
for sentence in generate_sentences(
    text_stream,
    tokenizer="nltk+rule-based",
    language="en",
    auto_context=True,
):
    print(sentence)
```

### Keep already-queued sentences together

Start speaking early, then keep already-queued sentences together.
When the complete text is already queued, `AvailableTextRun` keeps a later
`We can do that tomorrow, though.` together instead of sending `though.`
to speech synthesis on its own. The first fragment keeps its usual early release.
A later sentence may wait for the usual sentence-end confirmation instead of
being released at the comma. Pass only text you already have; do not wait to
fill a batch. Ordinary strings keep the existing behavior.

See [the example and integration guide](docs/available-text-runs.md).

## Configuration

The `generate_sentences()` function offers various parameters to fine-tune its behavior:

### Core Parameters

- `generator: Iterable[str | AvailableTextRun]`
  - The primary input source, yielding chunks of text to be processed.
  - Can be any iterator that emits text chunks of any size.
  - AvailableTextRun marks text already queued. It keeps later complete sentences together; their output still follows normal sentence-end checks.

- `context_size: int = 12`
  - Number of characters considered for sentence boundary detection.
  - Larger values improve accuracy but may increase latency.
  - Default: 12 characters

- `context_size_look_overhead: int = 12`
  - Additional characters to examine beyond `context_size` for sentence splitting.
  - Enhances sentence detection accuracy.
  - Default: 12 characters

- `auto_context: bool = False`
  - Yields safe sentence boundaries before the full `context_size` delay when the boundary heuristic and tokenizer agree.
  - Falls back to the normal `context_size` and `context_size_look_overhead` behavior when the boundary is still ambiguous.
  - Recommended for English when used with `tokenizer="nltk+rule-based"`.
  - Default: False

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

- `filter_first_non_alnum_characters: bool = False`
  - Discards non-alphanumeric characters at the start of an empty output buffer, including after a yield.

### Tokenization

- `tokenize_sentences: Callable = None`
  - Custom function accepting text and returning an iterable of sentence strings, including any unfinished tail. Lists and one-shot iterators are supported.
  - Return unchanged substrings to preserve their original separators. Rewritten output uses a single space between pieces.
  - If None, uses `tokenizer`.

- `tokenizer: str = "rule-based"`
  - Specifies the tokenizer to use. Options: "nltk", "stanza", "rule-based", or "nltk+rule-based"
  - "nltk+rule-based" splits at boundaries accepted by both NLTK and the rule-based heuristic tokenizer, plus rule-based boundaries promoted by high-confidence local checks.
  - Recommended for English, especially with `auto_context=True`.
  - Default: "rule-based"

- `language: str = "en"`
  - Language setting for the tokenizer.
  - Selects rule-based language data and the Stanza pipeline. For Stanza, use a supported language code such as `"en"` or `"zh"`; `"multilingual"` is not a sentence-tokenization pipeline.
  - NLTK uses its English sentence model, including in `"nltk+rule-based"`. NLTK and Stanza download model data on first use.
  - Default: "en"

- `never_split_numbers: bool = False`
  - Treats bare integers followed by a period, such as `1.`, as non-terminal in rule-based boundary checks. Useful for numbered text; it can also hold back a sentence ending in an integer.

### Debugging and Fine-tuning

- `debug: bool = False`
  - Prints internal boundary and yield decisions.

- `log_characters: bool = False`
  - When True, logs each processed character to the console.
  - Useful for debugging or monitoring real-time processing.
  - Default: False

- `sentence_fragment_delimiters: str = ".?!;:,\n…)]}。！？؟।۔-"`
  - Characters considered as potential sentence fragment delimiters.
  - Used for quick yielding of sentence fragments.
  - Default: ".?!;:,\n…)]}。！？؟।۔-"

- `full_sentence_delimiters: str = ".?!\n…。！？؟।۔"`
  - Characters considered as full sentence delimiters.
  - Used for more definitive sentence boundary detection.
  - Default: ".?!\n…。！？؟।۔"

- `force_first_fragment_after_words: int = 30`
  - Forces the yield of the first sentence fragment after this many words.
  - Ensures timely output even with long opening sentences.
  - Default: 30 words; use `float("inf")` to disable forced word-count yielding.

- `fragment_lookahead_words: int = 0`
  - Buffers quick-yield delimiter candidates until this many complete words have
    been observed.
  - At the threshold, a confirmed delimiter from
    `full_sentence_delimiters` is preferred over an earlier soft delimiter
    such as a comma; otherwise the latest soft delimiter is used.
  - If the input stream ends before the threshold, the remaining text is flushed
    normally.
  - This counts observed words, not words in the yielded fragment. For example,
    after eight observed words the splitter may yield an earlier two-word clause.
  - Default: 0, preserving immediate quick-yield behavior.


## Time based strategy
Instead of a purely lexical strategy, a time based strategy is available.
A target tokens per second (tps) is input, and generate_sentences will yield the best
available output (full sentence, longest fragment, or any available buffer, in that order) if it is approaching a "deadline"
where what has been output would be slower than the input tps target. If LLM is more than
two full sentences ahead of the target it will output a sentence even if it's ahead of the "deadline"

`from stream2sentence.stream2sentence_time_based import generate_sentences_time_based`

### Parameters
- `generator (Iterator[str])`
  - A generator that yields text chunks.
- `target_tps: float = 4`
  - the rate in tokens per second you want to use to calculate deadlines for output.
  - Default is 4. (approximately the speed of human speech)
- `lead_time: float = 1`
  - amount of time in seconds to wait for the buffer to build for before returning values.
- `max_wait_for_fragments = [3, 2]`
  - Max amount of time in seconds that the Nth sentence will wait beyond the "deadline" for a "fragment" (text preceding a fragment delimiter), which is preferred over a piece of buffer.
  - The last value in the array is used for all subsequent checks.
- `min_output_lengths: int[] = [2, 3, 3, 4]`
  - An array that corresponds to the minimum output size in words for the corresponding output sentence, the last value in the array is used for all remaining output.
  - For example [4,5,6] would mean the first piece of output must have 4 words, the second 5 words, and all subsequent 6.
- `preferred_sentence_fragment_delimiters: str[] = ['. ', '? ', '! ', '\n']`
  - Array of strings that delimit a sentence fragment. "Preferred" are checked first and always used if the fragment meets the length requirement over the other fragment delimiters.
  - Note the trailing spaces, added to differentiate between values like $3.5 and a proper sentence end
- `sentence_fragment_delimiters: str[] = ['; ', ': ', ', ', '* ', '**', '– ']`
  - Array of strings that are checked after "preferred" delimiters
- `delimiter_ignore_prefixes: str[]` 
  - Array of strings that will not be considered "delimiters" if preceded by a delimiter.
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

## Release checks

From a source checkout, use an activated virtual environment:

```bash
python -m pip install -e ".[all]" build twine
python tools/run_release_checks.py
python -m build
python -m twine check --strict dist/stream2sentence-1.1.0*
```

The runner checks dependencies, runs all unit tests with real NLTK and Stanza integrations enabled, and runs four timing scenarios. It fails on any failed or skipped test, missing output, text mismatch, or timing outside the allowed tolerance. First use needs network access for model data; the full run takes several minutes. The two live LLM API examples are manual demos and are not part of this automated suite. On Windows, `tests/run_test.bat` runs the same checks using the project virtual environment when present.

Passing these checks is release evidence, not a claim of complete code coverage or bug-free behavior. See [the 1.1.0 release notes](RELEASE_NOTES.md).

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

# Real-Time Sentence Detection

Real-time processing and delivery of sentences from a continuous stream of characters or text chunks.

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
$ pip install stream2sentence
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

## Configuration

The `generate_sentences()` function has the following parameters:

- `generator`: Input character generator.
  Iterator that emits chunks of text. These chunks can be of any size, and they'll be processed one by one to extract sentences from them. It forms the primary source from which the function reads and generates sentences.

- `context_size`: Context size for sentence detection.  
  This controls how much context is looked at to detect sentence boundaries. It determines the number of characters around a potential delimiter (like a period) that are considered when detecting sentence boundaries. A larger context size allows more reliable sentence boundary detection, but requires buffering more characters before emitting a sentence.  
  Default is 10 characters. Increasing this can help detect sentences more accurately, at the cost of added latency.

- `minimum_sentence_length`: Minimum length of a sentence to be detected.  
  Specifies the minimum number of characters a chunk of text should have before it's considered a potential sentence. This ensures that very short sequences of characters are not mistakenly identified as sentences.Shorter fragments are ignored and kept in the buffer.  
  Default is 8 characters. Increasing this avoids emitting very short sentence fragments, at the cost of potentially missing some sentences.

- `quick_yield_single_sentence_fragment`: Yield a sentence fragment quickly for real-time applications.
When set to True, this option allows the function to quickly yield a sentence fragment as soon as it identifies a potential sentence delimiter, without waiting for further context. This is useful for applications like real-time speech synthesis where there's a need for immediate feedback even if the entire sentence isn't complete.
Default is False. Set to True for faster but potentially less accurate sentence yields.

- `cleanup_text_links`: Option to remove links from the output sentences.  
  When set to True, this option enables the function to identify and remove HTTP/HTTPS hyperlinks from the emitted output sentences. This helps clean up the output by avoiding unnecessary links.  
  Default is False. Set to True if links are not required in the output.

- `cleanup_text_emojis`: Option to remove emojis from the output sentences.  
  If True, any Unicode emoji characters are identified and removed from the emitted output sentences. This can help to clean up the output.  
  Default is False. Set to True if emojis are not required in the output.

- `log_characters`: Option to log characters to the console.
When enabled, each character processed by the function is printed to the console. This is mainly for debugging purposes to observe the flow of characters through the function.
Default is False. Set to True for a visual representation of characters being processed. Example: allows printing llm output to console when using stream2sentence to prepare input generation for text to speech synthesis.


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
# stream2sentence 1.1.2

- keeps the rupee and rupiah abbreviations `Rs.`, `Re.` and `Rp.` with the amount after them (#29)
- time-based splitting no longer repeats part of a sentence when joined sentences were separated by repeated whitespace (#27, #28)
- README explains the LLM-to-TTS use case and how to read the demo video, and adds a quick start

# stream2sentence 1.1.1

- releases a complete sentence at the end of an `AvailableTextRun` without waiting for further text
- rearms quick yield for the next sentence after a fast fragment completes a sentence
- applies leading character filtering to every output
- `cleanup_text_links` keeps surrounding punctuation and text, and removes URL fragments (#20, #23)
- time-based splitting finds earlier split points and recognises more abbreviations, including after brackets, quotes and newlines (#22, #24, #26)

# stream2sentence 1.1.0

- adds opt-in `AvailableTextRun` to keep queued later sentences together while preserving early output for the first fragment
- improves multilingual sentence boundaries, Urdu punctuation, and Chinese/Japanese spacing (#16, #17, #18)
- fixes Stanza language selection when using multiple languages
- fixes duplicate output after `flush()` and preserves queued text when tokenization fails
- supports custom tokenizers returning iterators
- adds complete release checks and includes the MIT license in both package formats

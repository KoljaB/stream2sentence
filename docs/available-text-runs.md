# Keep queued sentences together

Start speaking early, then keep already-queued sentences together.

While the first speech fragment plays, more text can arrive. If a later sentence
is already queued in full, `AvailableTextRun` keeps it in one speech request:

| Ordinary quick yielding | With `AvailableTextRun` |
| --- | --- |
| “We can do that tomorrow,” **\|** “though.” | “We can do that tomorrow, though.” |

The first fragment keeps its usual early release. Later sentences stay together,
giving speech synthesis the whole sentence instead of a tiny, separate ending.

## When it waits

Keeping a later sentence together can mean releasing it later than the part before
the comma. If the queued text already confirms the sentence ending, it can come
out without more input. Otherwise, the normal sentence-end checks still need
following text or the end of the stream. An input batch ending is not the stream
ending. This tradeoff is intentional.

## Use it

Wrap text you already have; do not wait to collect more:

~~~python
from stream2sentence import AvailableTextRun, generate_sentences

text = (
    "All right, the first check is complete. "
    "We can do that tomorrow, though."
)

for fragment in generate_sentences(
    [AvailableTextRun(text, run_id=1)],
    quick_yield_for_all_sentences=True,
    minimum_first_fragment_length=9,
    force_first_fragment_after_words=float("inf"),
):
    print(fragment)
~~~

Output (the input stream ends after this batch):

~~~text
All right,
the first check is complete.
We can do that tomorrow, though.
~~~

## Integration

- Ordinary strings keep the existing behavior. `quick_yield_every_fragment=True`
  also keeps explicit fragment-by-fragment output.
- Works with `generate_sentences()`, `generate_sentences_async()` and
  `SentenceSplitter.add()`. Upgrading alone does not enable it.
- Collect only text already queued. Limit batch size and stop at control events
  such as a voice change.
- Give each batch a new integer `run_id`. Already-queued pieces of the same
  batch may share it; the id never tells the splitter to await another piece.
  Plain strings or a different id end that batch.
- Existing minimum lengths and lookahead settings still apply. An incomplete
  following sentence keeps its usual early-fragment behavior.

This helps when text has accumulated. It does not guarantee faster audio:
larger speech requests can take longer to synthesize.

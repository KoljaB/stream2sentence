"""A fully emitted sentence must rearm the configured next-sentence fast path."""
import unittest

from stream2sentence import SentenceSplitter


def splitter(**overrides):
    options = dict(tokenizer="rule-based", language="en", minimum_sentence_length=10,
                   minimum_first_fragment_length=9,
                   quick_yield_single_sentence_fragment=True,
                   quick_yield_for_all_sentences=True,
                   quick_yield_every_fragment=False,
                   sentence_fragment_delimiters=".?!;:,\n…。-—",
                   force_first_fragment_after_words=float("inf"),
                   fragment_lookahead_words=0)
    options.update(overrides)
    return SentenceSplitter(**options)


def feed(stream, chunks):
    out = []
    for chunk in chunks:
        stream.add(chunk)
        out.extend(stream.stream())
    return out


class QuickYieldSentenceResetTests(unittest.TestCase):
    def test_complete_fast_sentence_releases_next_clause_without_future_text(self):
        for ending in ("?", "!", ".", "？", "！", "。"):
            with self.subTest(ending=ending):
                stream = splitter(sentence_fragment_delimiters=".?!;:,\n…。-—？！")
                first = "You know what is funny" + ending
                clause = "You've been in that car a hundred times probably,"
                # Preserve the detector's existing lookahead into the next sentence.
                initial = feed(stream, [first, " ", "You've been in that car "])
                self.assertEqual(initial, [first])
                self.assertEqual(feed(stream, ["a hundred times probably,"]), [clause])
                # A comma starts the slow remainder of this sentence, not another fast clause.
                self.assertEqual(feed(stream, [" doing the same turns,"]), [])
                tail = " the same stops — and then one morning it is yours."
                rest = feed(stream, [tail]) + list(stream.flush())
                self.assertEqual(" ".join(rest), "doing the same turns," + tail)

    def test_every_sentence_option_still_controls_rearming(self):
        stream = splitter(quick_yield_for_all_sentences=False)
        self.assertEqual(
            feed(stream, ["You know what is funny? ", "The following "]),
            ["You know what is funny?"],
        )
        self.assertEqual(feed(stream, ["clause is ready,"]), [])

    def test_comma_fragment_does_not_rearm_sentence_fast_path(self):
        stream = splitter()
        self.assertEqual(
            feed(stream, ["The first clause is ready,"]), ["The first clause is ready,"]
        )
        self.assertEqual(feed(stream, [" and a second clause is ready,"]), [])

    def test_abbreviation_does_not_become_a_complete_sentence(self):
        stream = splitter()
        self.assertEqual(feed(stream, ["I spoke to Dr.", " Smith, "]), ["I spoke to Dr. Smith,"])
        self.assertEqual(feed(stream, [" and his colleague waited,"]), [])


if __name__ == "__main__":
    unittest.main()

"""Completed available sentences need no following voice instruction as lookahead."""
import unittest

from stream2sentence import AvailableTextRun, SentenceSplitter

OPTIONS = dict(tokenizer="rule-based", language="en", minimum_sentence_length=10,
               minimum_first_fragment_length=9, quick_yield_for_all_sentences=True,
               sentence_fragment_delimiters=".?!;:,\n…。-—？！",
               force_first_fragment_after_words=float("inf"), fragment_lookahead_words=0)


class AvailableSentenceReleaseTests(unittest.TestCase):
    def test_available_sentence_releases_on_existing_whitespace_without_future_input(self):
        for sentence in ("Oh, you did it!", "Is everything ready?",
                         "The first sentence is complete.",
                         'She said, "That is ready!"',
                         "The first sentence is complete。"):
            with self.subTest(sentence=sentence):
                splitter = SentenceSplitter(**OPTIONS)
                initial = []
                for index, char in enumerate(sentence):
                    splitter.add(AvailableTextRun(char, index))
                    initial.extend(splitter.stream())
                splitter.add(AvailableTextRun(" ", len(sentence)))
                released = initial + list(splitter.stream())
                self.assertEqual(" ".join(released), sentence)
                # No next word, complete voice instruction, or end-of-stream was supplied.
                self.assertFalse(splitter.buffer.strip())

    def test_incomplete_or_ambiguous_terminal_prefix_still_waits(self):
        for tail in ("Ask our colleague Dr.", "The number is 3.", "This is just."):
            with self.subTest(tail=tail):
                splitter = SentenceSplitter(**OPTIONS)
                splitter.add(AvailableTextRun(tail, 1))
                self.assertEqual(list(splitter.stream()), [])
                if tail.endswith("Dr.") or tail.endswith("3."):
                    splitter.add(AvailableTextRun(" ", 2))
                    self.assertEqual(list(splitter.stream()), [])

    def test_split_ellipsis_is_kept_before_confirming_whitespace(self):
        splitter = SentenceSplitter(**OPTIONS)
        output = []
        for index, part in enumerate(("This is just.", ".", ".", " ")):
            splitter.add(AvailableTextRun(part, index))
            values = list(splitter.stream())
            if index < 3:
                self.assertEqual(values, [])
            output.extend(values)
        output.extend(splitter.flush())
        self.assertEqual("".join(output), "This is just...")

    def test_unmarked_input_retains_its_lookahead_contract(self):
        splitter = SentenceSplitter(**OPTIONS)
        splitter.add("Oh, you did it! ")
        self.assertEqual(list(splitter.stream()), [])

    def test_configured_fragment_lookahead_is_preserved(self):
        splitter = SentenceSplitter(**dict(OPTIONS, fragment_lookahead_words=8))
        splitter.add(AvailableTextRun("Oh, you did it! ", 1))
        self.assertEqual(list(splitter.stream()), [])


if __name__ == "__main__":
    unittest.main()

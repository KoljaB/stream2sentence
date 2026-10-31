"""find_last_delimiter must find valid split points, and only valid ones."""
import unittest
from unittest import mock

import stream2sentence.stream2sentence_time_based as tb
from stream2sentence.delimiter_ignore_prefixes import DELIMITER_IGNORE_PREFIXES

PREFERRED = [". ", "? ", "! ", "\n"]


class FindLastDelimiterTests(unittest.TestCase):
    def setUp(self):
        # generate_sentences_time_based sets this global at runtime.
        patcher = mock.patch.object(
            tb, "delimiter_ignore_prefixes_global", set(DELIMITER_IGNORE_PREFIXES)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_split(self, text, expected):
        index = tb.find_last_delimiter(text, PREFERRED)
        self.assertEqual(text[:index + 1] if index != -1 else None, expected)

    def test_trailing_abbreviation_does_not_mask_earlier_boundary(self):
        cases = {
            "stop here. ask Dr. Lee": "stop here.",
            "done now. per Mr. Smith and Dr. Jones": "done now.",
            "really? ask Dr. Lee": "really?",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assert_split(text, expected)

    def test_later_sentence_end_wins(self):
        self.assert_split("Ask Mr. Lee now. then go on", "Ask Mr. Lee now.")
        self.assert_split("One two. three four", "One two.")

    def test_abbreviation_is_never_a_split_point(self):
        cases = [
            "See Dr. foo bar",
            "Mr. Smith met Dr. Lee today",
            "Dr. Lee and Mr. Smith arrived",
            "ask (Dr. Lee and Mr. Smith arrived",
            "ask [Dr. Lee and Mr. Smith arrived",
            'he said "Dr. Lee and Mr. Smith agreed',
            "he said “Dr. Lee and Mr. Smith agreed",
            "ask **Dr. Lee and Mr. Smith arrived",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assert_split(text, None)

    def test_newline_before_abbreviation(self):
        self.assert_split("we met\nDr. Lee and Mr. Smith today", "we met\n")
        self.assert_split("we met\tDr. Lee today", None)

    def test_opening_punctuation_on_ordinary_word_still_splits(self):
        self.assert_split("it ended (finally. then more", "it ended (finally.")

    def test_no_delimiter_or_blank_text(self):
        for text in ("", "no split point here", "\n"):
            with self.subTest(text=text):
                self.assertIn(tb.find_last_delimiter(text, PREFERRED), (-1, 0))

    def test_overlapping_delimiter_occurrences(self):
        self.assertEqual(tb.find_last_delimiter("a ***b", ["**"]), 3)


if __name__ == "__main__":
    unittest.main()

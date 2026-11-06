"""handle_output must cut the running buffer at the real sentence boundary.

When several sentences are joined for output, ``" ".join`` collapses the
whitespace that separated them in the source (repeated spaces). The emitted
string is therefore shorter than the text it consumed, so slicing the buffer
by ``len(output)`` leaves the trailing characters of the last joined sentence
behind, and they are re-emitted on the next turn -- a content duplication. The
generator must slice at the boundary located in the raw buffer instead,
whenever that boundary covers exactly the emitted text apart from whitespace.
"""

import unittest
from unittest import mock

import stream2sentence.stream2sentence_time_based as tb


class FrozenClock:
    """Never advances, so is_output_needed stays False and the generator
    takes the multi-sentence 'two sentences ahead' branch that joins
    sentences with a single space before emitting them."""

    def __call__(self):
        return 1000.0


def collect(text, chunk, **kwargs):
    gen = (text[i:i + chunk] for i in range(0, len(text), chunk))
    return list(tb.generate_sentences_time_based(gen, **kwargs))


def nonspace(string):
    return "".join(string.split())


class TimeBasedBufferSlicingTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(tb.time, "time", FrozenClock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repeated_spaces_between_sentences_do_not_duplicate_content(self):
        # Four spaces between every sentence: the join collapses each gap to a
        # single space, so the boundary in the raw buffer sits beyond
        # len(output). Slicing by len(output) used to leave a fragment behind.
        text = "    ".join(["Go now."] * 6)
        output = collect(
            text,
            chunk=2,
            lead_time=100,
            max_wait_for_fragments=[0, 0],
            deadline_offsets_static=[0],
            min_output_lengths=[5],
        )
        self.assertEqual(nonspace("".join(output)), nonspace(text))

    def test_mixed_spacing_and_closing_marks_do_not_duplicate_content(self):
        text = (
            "Short one.    Short one.    Short one. \n Short one."
            "\tStop right there! \n Short one."
        )
        output = collect(
            text,
            chunk=2,
            lead_time=100,
            max_wait_for_fragments=[0, 0],
            deadline_offsets_static=[0],
            min_output_lengths=[5],
        )
        self.assertEqual(nonspace("".join(output)), nonspace(text))


if __name__ == "__main__":
    unittest.main()

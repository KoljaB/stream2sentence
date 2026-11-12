"""minimum_later_fragment_length: after a stream's first output, a cut inside a sentence
(comma, semicolon, colon, dash) needs that many characters; sentence ends do not."""

import unittest

from stream2sentence import SentenceSplitter

REPLY = (
    "Ach, das ist doch überhaupt kein Problem. Ich warte einfach, so lange du reden willst. "
    "Deine Pausen dürfen ruhig so lang sein, wie du brauchst."
)
LONG_SECOND = (
    "Na gut, dann eben so. Wenn du mal einen wirklich langen Satz sagst, der immer weiter "
    "geht und noch ein Komma hat, dann wird der irgendwann geteilt, damit die Stimme nicht "
    "zu lange wartet."
)


def split(text, later=0, step=3, **options):
    settings = dict(
        tokenizer="rule-based", minimum_sentence_length=10, minimum_first_fragment_length=9,
        quick_yield_single_sentence_fragment=True, quick_yield_for_all_sentences=True,
        quick_yield_every_fragment=False,
    )
    settings.update(options)
    splitter = SentenceSplitter(minimum_later_fragment_length=later, **settings)
    out = []
    for start in range(0, len(text), step):
        splitter.add(text[start:start + step])
        out.extend(splitter.stream())
    out.extend(splitter.flush())
    return out


class MinimumLaterFragmentLength(unittest.TestCase):
    def test_default_keeps_the_cut_at_every_first_comma(self):
        self.assertEqual(split(REPLY), [
            "Ach, das ist doch überhaupt kein Problem.",
            "Ich warte einfach,", "so lange du reden willst.",
            "Deine Pausen dürfen ruhig so lang sein,", "wie du brauchst.",
        ])

    def test_later_sentences_under_the_length_come_whole(self):
        self.assertEqual(split(REPLY, later=80), [
            "Ach, das ist doch überhaupt kein Problem.",
            "Ich warte einfach, so lange du reden willst.",
            "Deine Pausen dürfen ruhig so lang sein, wie du brauchst.",
        ])

    def test_the_result_does_not_depend_on_how_the_text_arrives(self):
        expected = split(REPLY, later=80, step=3)
        for step in (1, 2, 5, 11, 40, len(REPLY)):
            self.assertEqual(split(REPLY, later=80, step=step), expected, step)

    def test_the_first_output_is_still_cut_early(self):
        text = "Well, that depends on a few things, honestly. And then, we will see."
        self.assertEqual(split(text)[0], "Well, that depends on a few things,")
        self.assertEqual(split(text, later=80)[0], "Well, that depends on a few things,")
        # what follows is not cut at its comma again ("honestly." is too short to stand
        # alone, so it is joined with the next sentence, as without the option)
        self.assertEqual(split(text, later=80)[1:], ["honestly. And then, we will see."])

    def test_a_long_later_sentence_is_cut_once_after_the_length(self):
        parts = split(LONG_SECOND, later=80)
        self.assertEqual(parts[0], "Na gut, dann eben so.")
        # cut at the first comma that lies more than 80 characters into the sentence
        self.assertEqual(
            parts[1],
            "Wenn du mal einen wirklich langen Satz sagst, der immer weiter geht und noch "
            "ein Komma hat,",
        )
        self.assertGreater(len(parts[1]), 80)
        self.assertEqual(len(parts), 3)
        self.assertEqual(" ".join(parts), LONG_SECOND)

    def test_other_marks_inside_a_sentence_follow_the_same_rule(self):
        for mark in (";", ":", " -"):
            text = f"Okay, verstanden. Das ist einfach{mark} wir machen das morgen zusammen."
            cut = split(text)
            whole = split(text, later=80)
            self.assertGreater(len(cut), len(whole), mark)
            self.assertEqual(whole[0], "Okay, verstanden.")
            self.assertEqual(len(whole), 2, mark)

    def test_sentence_ends_are_released_as_before(self):
        text = "Alles klar. Das passt. Dann bis morgen. Ich freue mich schon darauf."
        self.assertEqual(split(text, later=80), split(text))
        self.assertEqual(split(text, later=80)[0], "Alles klar.")

    def test_a_smaller_length_cuts_earlier(self):
        text = ("Alles klar soweit. Ich warte einfach, so lange du reden willst, "
                "und dann sehen wir weiter.")
        self.assertEqual(split(text, later=15)[1], "Ich warte einfach,")
        self.assertEqual(split(text, later=40)[1], "Ich warte einfach, so lange du reden willst,")

    def test_no_text_is_lost_in_any_language(self):
        texts = (
            REPLY, LONG_SECOND,
            "Sure, no problem. I can wait, really, as long as you need, and then we continue.",
            "D'accord, pas de souci. Je t'attends, vraiment, aussi longtemps qu'il le faut.",
            "好的，没问题。我可以等，真的，你慢慢说，不着急。",
        )
        for text in texts:
            for later in (0, 20, 80, 500):
                joined = "".join("".join(split(text, later=later)).split())
                self.assertEqual(joined, "".join(text.split()), (text[:20], later))

    def test_a_new_stream_starts_with_an_early_cut_again(self):
        splitter = SentenceSplitter(
            tokenizer="rule-based", minimum_sentence_length=10, minimum_first_fragment_length=9,
            quick_yield_single_sentence_fragment=True, quick_yield_for_all_sentences=True,
            minimum_later_fragment_length=80,
        )
        for _ in range(2):
            splitter.add("Well, that depends on a few things, honestly. ")
            first = list(splitter.stream())
            rest = list(splitter.flush())
            self.assertEqual((first + rest)[0], "Well, that depends on a few things,")


if __name__ == "__main__":
    unittest.main()

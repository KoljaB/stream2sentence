import asyncio
import unittest

from stream2sentence import (
    AvailableTextRun,
    SentenceSplitter,
    generate_sentences,
    generate_sentences_async,
)


REPORTED_TEXT = "Hello there friend! -- What now is this. ** Okay then fine."
CLEAN_SENTENCES = ["Hello there friend!", "What now is this.", "Okay then fine."]


def one_sentence(text):
    return [text] if text else []


class LeadingCharacterFilterTests(unittest.TestCase):
    def test_issue19_original_repro(self):
        self.assertEqual(
            list(generate_sentences(
                [REPORTED_TEXT], filter_first_non_alnum_characters=True,
            )),
            CLEAN_SENTENCES,
        )

    def test_chunk_boundaries_and_quick_yield_modes(self):
        text = "** " + REPORTED_TEXT
        modes = ({}, {"quick_yield_single_sentence_fragment": True},
                 {"quick_yield_for_all_sentences": True},
                 {"quick_yield_every_fragment": True})
        for size in (1, 2, 7, len(text)):
            for mode in modes:
                with self.subTest(size=size, mode=mode):
                    chunks = [text[i:i + size] for i in range(0, len(text), size)]
                    self.assertEqual(
                        list(generate_sentences(
                            chunks, filter_first_non_alnum_characters=True, **mode,
                        )),
                        CLEAN_SENTENCES,
                    )

    def test_each_early_fragment_is_filtered(self):
        text = "** Hello there friend, -- what now is this, ** okay then fine."
        for chunks in ([text], list(text)):
            self.assertEqual(
                list(generate_sentences(
                    chunks, filter_first_non_alnum_characters=True,
                    quick_yield_every_fragment=True,
                )),
                ["Hello there friend,", "what now is this,", "okay then fine."],
            )

    def test_meaningful_prefixes_require_caller_normalization(self):
        cases = (
            ("-3 degrees is very cold.", "3 degrees is very cold."),
            ("$5 was the price today.", "5 was the price today."),
            ('"This is a quoted statement."', 'This is a quoted statement."'),
            ("Minus 3 degrees is very cold.", "Minus 3 degrees is very cold."),
        )
        for tail, expected in cases:
            for boundary in ("!", ","):
                for enabled in (False, True):
                    with self.subTest(tail=tail, boundary=boundary, enabled=enabled):
                        first = "Hello there friend" + boundary
                        self.assertEqual(
                            list(generate_sentences(
                                [first + " " + tail],
                                quick_yield_for_all_sentences=True,
                                filter_first_non_alnum_characters=enabled,
                            )),
                            [first, expected if enabled else tail],
                        )

    def test_disabled_filter_preserves_the_reported_prefixes(self):
        text = "** " + REPORTED_TEXT
        expected = ["** Hello there friend!", "-- What now is this.",
                    "** Okay then fine."]
        for chunks in ([text], list(text)):
            self.assertEqual(list(generate_sentences(chunks)), expected)

    def test_unicode_and_interior_punctuation_are_preserved(self):
        for text, expected in (
            ("** Über die Brücke.", "Über die Brücke."),
            ("-- 中文句子。", "中文句子。"),
            ("** ٣ apples.", "٣ apples."),
            ("-- 123 apples.", "123 apples."),
            ("** Text with -3, $5, and **emphasis**.",
             "Text with -3, $5, and **emphasis**."),
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    list(generate_sentences(
                        list(text), tokenize_sentences=one_sentence,
                        minimum_sentence_length=1000,
                        filter_first_non_alnum_characters=True,
                    )),
                    [expected],
                )

    def test_symbol_only_outputs_are_suppressed(self):
        for text in ("", "***", "?! -- ", "🙂", "**|Ready to speak."):
            with self.subTest(text=text):
                self.assertEqual(
                    list(generate_sentences(
                        [text], tokenize_sentences=lambda value: value.split("|"),
                        minimum_sentence_length=1, context_size=1000,
                        filter_first_non_alnum_characters=True,
                    )),
                    ["Ready to speak."] if "|" in text else [],
                )

    def test_tokenization_keeps_original_punctuation(self):
        text = "** Hello there friend, -3 degrees is very cold."
        seen = []

        def tokenize(value):
            seen.append(value)
            return one_sentence(value)

        self.assertEqual(
            list(generate_sentences(
                [text], tokenize_sentences=tokenize,
                minimum_sentence_length=1000,
                filter_first_non_alnum_characters=True,
            )),
            ["Hello there friend, -3 degrees is very cold."],
        )
        self.assertEqual(seen, [text])

    def test_other_cleanup_runs_before_prefix_filtering(self):
        self.assertEqual(
            list(generate_sentences(
                ["https://example.com ** 🙂 Ready to speak."],
                tokenize_sentences=one_sentence, minimum_sentence_length=1000,
                cleanup_text_links=True, cleanup_text_emojis=True,
                filter_first_non_alnum_characters=True,
            )),
            ["Ready to speak."],
        )

    def test_flush_tail_and_splitter_reuse(self):
        for minimum in (1, 1000):
            splitter = SentenceSplitter(
                minimum_sentence_length=minimum,
                filter_first_non_alnum_characters=True,
            )
            for prefix, text in (("** ", "First short tail"), ("-- ", "Second short tail")):
                with self.subTest(minimum=minimum, text=text):
                    splitter.add(prefix + text)
                    self.assertEqual(list(splitter.stream()), [])
                    self.assertEqual(list(splitter.flush()), [text])
                    self.assertEqual(list(splitter.flush()), [])

    def test_async_generator_filters_each_output(self):
        async def collect(quick):
            async def source():
                for char in REPORTED_TEXT:
                    yield char
            return [part async for part in generate_sentences_async(
                source(), quick_yield_for_all_sentences=quick,
                filter_first_non_alnum_characters=True,
            )]

        for quick in (False, True):
            with self.subTest(quick=quick):
                self.assertEqual(asyncio.run(collect(quick)), CLEAN_SENTENCES)

    def test_available_text_runs_filter_each_output(self):
        chunks = [AvailableTextRun(REPORTED_TEXT, 7)]
        output = list(generate_sentences(
            chunks, quick_yield_for_all_sentences=True,
            filter_first_non_alnum_characters=True,
        ))
        self.assertTrue(output)
        self.assertEqual(output[0], CLEAN_SENTENCES[0])
        self.assertTrue(all(part and part[0].isalnum() for part in output))
        self.assertIn("What now is this.", " ".join(output))
        self.assertIn("Okay then fine.", " ".join(output))


if __name__ == "__main__":
    unittest.main()

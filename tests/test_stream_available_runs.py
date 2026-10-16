from __future__ import annotations

import asyncio
import unittest

import stream2sentence as s2s
from stream2sentence import stream2sentence as implementation


BASE_OPTIONS = dict(
    tokenizer="rule-based",
    language="en",
    minimum_sentence_length=10,
    minimum_first_fragment_length=9,
    quick_yield_single_sentence_fragment=True,
    quick_yield_for_all_sentences=True,
    quick_yield_every_fragment=False,
    sentence_fragment_delimiters=".!?;:,\n…)]}。-—",
    force_first_fragment_after_words=float("inf"),
    fragment_lookahead_words=0,
)


class StreamAvailableRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_long_unpunctuated_tail_is_conserved_with_bounded_tokenizer_scans(self):
        text = "Fair point, " + " ".join(["word"] * 256)
        calls = 0
        original = implementation._tokenize_sentences

        def counted(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        implementation._tokenize_sentences = counted
        try:
            async def source():
                yield text

            values = [
                value
                async for value in s2s.generate_sentences_async(
                    source(),
                    **dict(BASE_OPTIONS, quick_yield_single_sentence_fragment=False,
                           quick_yield_for_all_sentences=False),
                )
            ]
        finally:
            implementation._tokenize_sentences = original

        self.assertEqual("".join(values), text)
        self.assertLessEqual(calls, 4)

    async def test_first_available_fragment_does_not_wait_for_future_input(self):
        release = asyncio.Event()

        async def source():
            yield s2s.AvailableTextRun("The first clause is ready,", 1)
            await release.wait()
            yield " The future tail arrives only after release."

        stream = s2s.generate_sentences_async(source(), **BASE_OPTIONS)
        try:
            first = await asyncio.wait_for(stream.__anext__(), timeout=0.5)
            self.assertEqual(first, "The first clause is ready,")
        finally:
            release.set()
            await stream.aclose()

    async def test_supported_terminators_and_custom_tokenizer_keep_contract(self):
        mixed = (
            "First clause is ready, and it remains complete. "
            "Arabic؟ Next clause is ready, though. Hindi। Final clause is done."
        )

        async def mixed_source():
            yield s2s.AvailableTextRun(mixed, 1)

        mixed_values = [
            value
            async for value in s2s.generate_sentences_async(
                mixed_source(),
                **dict(BASE_OPTIONS, quick_yield_every_fragment=True),
            )
        ]
        self.assertEqual(
            " ".join(value.strip() for value in mixed_values if value.strip()),
            " ".join(mixed.split()),
        )
        joined_mixed = " ".join(value.strip() for value in mixed_values if value.strip())
        for mark in (".", "؟", "।"):
            self.assertIn(mark, joined_mixed)

        seen = []

        def custom_tokenizer(text):
            seen.append(text)
            return [part for part in text.split("|") if part]

        async def custom_source():
            yield "Custom first|Custom second"

        custom_values = [
            value
            async for value in s2s.generate_sentences_async(
                custom_source(),
                **dict(
                    BASE_OPTIONS,
                    quick_yield_single_sentence_fragment=False,
                    quick_yield_for_all_sentences=False,
                    tokenize_sentences=custom_tokenizer,
                ),
            )
        ]
        self.assertEqual(custom_values, ["Custom first", "Custom second"])
        self.assertTrue(seen)


if __name__ == "__main__":
    unittest.main()

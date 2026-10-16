import asyncio
import unittest

import stream2sentence as s2s


OPTIONS = dict(
    tokenizer="rule-based", language="en", minimum_sentence_length=10,
    minimum_first_fragment_length=9, quick_yield_single_sentence_fragment=True,
    quick_yield_for_all_sentences=True, quick_yield_every_fragment=False,
    sentence_fragment_delimiters=".!?;:,\n…)]}。-—",
    force_first_fragment_after_words=float("inf"), fragment_lookahead_words=0,
)
TEXT = (
    "Fair point, no specific train time was mentioned, and it was the whole camera. "
    "It sounds like you're going to be sprinting from work to the shop, though."
)


async def collect(chunks, **overrides):
    async def source():
        for chunk in chunks:
            yield chunk
    return [part async for part in s2s.generate_sentences_async(
        source(), **dict(OPTIONS, **overrides)
    )]


class AvailableTextRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_already_available_later_sentence_keeps_its_comma_tail(self):
        fragments = await collect([s2s.AvailableTextRun(TEXT, 1)])
        self.assertEqual(fragments, [
            "Fair point,",
            "no specific train time was mentioned, and it was the whole camera.",
            "It sounds like you're going to be sprinting from work to the shop, though.",
        ])

    async def test_german_available_sentence_keeps_its_tail(self):
        text = (
            "Gut, der erste Schritt ist fertig, und der nächste ist klar. "
            "Der letzte Check ist abgeschlossen, allerdings."
        )
        fragments = await collect([s2s.AvailableTextRun(text, 1)], language="de")
        self.assertEqual(fragments[-1], "Der letzte Check ist abgeschlossen, allerdings.")
        self.assertEqual("".join("".join(fragments).split()), "".join(text.split()))

    async def test_unmarked_source_keeps_existing_streaming_behavior(self):
        fragments = await collect([TEXT])
        self.assertEqual(fragments[0], "Fair point,")
        self.assertEqual(fragments[-2:], [
            "It sounds like you're going to be sprinting from work to the shop,", "though.",
        ])

    async def test_first_fragment_does_not_wait_for_future_input(self):
        for lookahead in (0, 8):
            for marked in (False, True):
                with self.subTest(lookahead=lookahead, marked=marked):
                    release = asyncio.Event()

                    async def source():
                        text = "Fair point, the opening words are already here "
                        yield s2s.AvailableTextRun(text, 1) if marked else text
                        await release.wait()
                        yield "and the rest arrives later."

                    stream = s2s.generate_sentences_async(
                        source(), **dict(OPTIONS, fragment_lookahead_words=lookahead)
                    )
                    try:
                        first = await asyncio.wait_for(anext(stream), timeout=1.0)
                        self.assertEqual(first, "Fair point,")
                        self.assertFalse(release.is_set())
                        release.set()
                        self.assertEqual([part async for part in stream], [
                            "the opening words are already here and the rest arrives later.",
                        ])
                    finally:
                        release.set()
                        await stream.aclose()

    async def test_confirmed_later_sentence_does_not_request_future_input(self):
        opening = "All right, the first check is complete and everything works correctly. "
        sentence = "We can run the remaining tests tomorrow after the meeting, though."
        context = " We will discuss the results together."
        for lookahead in (0, 8):
            with self.subTest(lookahead=lookahead):
                release = asyncio.Event()
                requested_more = asyncio.Event()

                async def source():
                    yield s2s.AvailableTextRun(opening + sentence + context, 1)
                    requested_more.set()
                    await release.wait()

                stream = s2s.generate_sentences_async(
                    source(), **dict(OPTIONS, fragment_lookahead_words=lookahead)
                )
                try:
                    actual = [await asyncio.wait_for(anext(stream), 1.0) for _ in range(3)]
                    self.assertEqual(actual, [
                        "All right,",
                        "the first check is complete and everything works correctly.",
                        sentence,
                    ])
                    self.assertFalse(requested_more.is_set())
                    release.set()
                    self.assertEqual([part async for part in stream], [context.strip()])
                finally:
                    release.set()
                    await stream.aclose()

    async def test_later_sentence_at_batch_end_waits_for_confirmation_or_stream_end(self):
        opening = "All right, the first check is complete and everything works correctly. "
        sentence = "We can run the remaining tests tomorrow after the meeting, though."
        context = " We will discuss the results together."
        expected_opening = [
            "All right,", "the first check is complete and everything works correctly.",
        ]
        for lookahead in (0, 8):
            for completion in ("context", "stream_end"):
                with self.subTest(lookahead=lookahead, completion=completion):
                    options = dict(OPTIONS, fragment_lookahead_words=lookahead)
                    plain = s2s.SentenceSplitter(**options)
                    plain.add(opening + sentence)
                    self.assertEqual(list(plain.stream()), expected_opening + [
                        "We can run the remaining tests tomorrow after the meeting,",
                    ])

                    paused = asyncio.Event()
                    release = asyncio.Event()
                    finish = asyncio.Event()

                    async def source():
                        yield s2s.AvailableTextRun(opening + sentence, 1)
                        paused.set()
                        await release.wait()
                        if completion == "context":
                            yield s2s.AvailableTextRun(context, 2)
                            await finish.wait()

                    stream = s2s.generate_sentences_async(source(), **options)
                    pending = paused_wait = None
                    try:
                        actual = [await asyncio.wait_for(anext(stream), 1.0) for _ in range(2)]
                        self.assertEqual(actual, expected_opening)
                        pending = asyncio.create_task(anext(stream))
                        paused_wait = asyncio.create_task(paused.wait())
                        done, _ = await asyncio.wait(
                            (pending, paused_wait), timeout=1.0,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        # The producer reached its gate, but no comma fragment escaped.
                        self.assertIn(paused_wait, done)
                        self.assertFalse(pending.done())
                        release.set()
                        self.assertEqual(await asyncio.wait_for(pending, 1.0), sentence)
                        self.assertFalse(finish.is_set())
                        finish.set()
                        remainder = [part async for part in stream]
                        self.assertEqual(remainder, [context.strip()] if completion == "context" else [])
                    finally:
                        release.set()
                        finish.set()
                        tasks = [task for task in (pending, paused_wait) if task is not None]
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        await stream.aclose()

    async def test_every_fragment_mode_preserves_text(self):
        marked = await collect([s2s.AvailableTextRun(TEXT, 1)], quick_yield_every_fragment=True)
        ordinary = await collect([TEXT], quick_yield_every_fragment=True)
        self.assertEqual(marked, ordinary)
        self.assertEqual("".join("".join(marked).split()), "".join(TEXT.split()))

    async def test_partial_following_sentence_is_not_blocked_by_previous_decision(self):
        opening = "Fair point, this is the rest of the opening sentence. "
        complete = "Everything works correctly, according to our latest test. "
        for delimiter in (",", ";", ":"):
            for run_ids in ((1,), (1, 1), (1, 2)):
                with self.subTest(delimiter=delimiter, run_ids=run_ids):
                    partial = "The third sentence starts here" + delimiter
                    tail = " but more text will arrive"
                    texts = ([opening + complete + partial + tail] if len(run_ids) == 1
                             else [opening, complete + partial + tail])
                    release = asyncio.Event()
                    async def source():
                        for text, run_id in zip(texts, run_ids):
                            yield s2s.AvailableTextRun(text, run_id)
                        await release.wait()
                        yield s2s.AvailableTextRun(" later.", 3)
                    stream = s2s.generate_sentences_async(source(), **OPTIONS)
                    try:
                        actual = [await asyncio.wait_for(anext(stream), 1.0) for _ in range(4)]
                        self.assertEqual(actual, [
                            "Fair point,", "this is the rest of the opening sentence.",
                            complete.strip(), partial,
                        ])
                        self.assertFalse(release.is_set())
                        release.set()
                        actual.extend([part async for part in stream])
                        self.assertEqual("".join("".join(actual).split()),
                                         "".join((opening + complete + partial + tail + " later.").split()))
                    finally:
                        release.set()
                        await stream.aclose()

    async def test_next_complete_sentence_still_keeps_its_tail(self):
        text = ("Fair point, this is the rest of the opening sentence. "
                "Everything works correctly, according to our latest test. "
                "The third sentence stays together, including this tail.")
        fragments = await collect([s2s.AvailableTextRun(text, 1)])
        self.assertEqual(fragments[-2:], [
            "Everything works correctly, according to our latest test.",
            "The third sentence stays together, including this tail.",
        ])

    async def test_queued_inputs_keep_their_own_markers(self):
        for chunks in (
            [s2s.AvailableTextRun(TEXT, 1), " A plain sentence follows, with its tail."],
            [TEXT, s2s.AvailableTextRun(" A marked sentence follows, with its tail.", 2)],
        ):
            with self.subTest(chunks=chunks):
                expected = await collect(chunks)
                splitter = s2s.SentenceSplitter(**OPTIONS)
                for chunk in chunks:
                    splitter.add(chunk)
                actual = list(splitter.stream()) + list(splitter.flush())
                self.assertEqual(actual, expected)

    async def test_sync_entry_point_accepts_available_runs(self):
        actual = list(s2s.generate_sentences([s2s.AvailableTextRun(TEXT, 1)], **OPTIONS))
        self.assertEqual(actual, await collect([s2s.AvailableTextRun(TEXT, 1)]))

    async def test_incomplete_abbreviation_or_number_does_not_block_fragment(self):
        opening = "All right, the first check is complete. "
        fragment = "We should ask our colleague,"
        for suffix in ("Dr.", "Mr.", "Prof.", "etc.", "1.", "3.14.", "-2.5.", "+1.", "3,14."):
            for queued in (False, True):
                with self.subTest(suffix=suffix, queued=queued):
                    text = opening + fragment + " " + suffix
                    splitter = s2s.SentenceSplitter(**OPTIONS)
                    if queued:
                        splitter.add(s2s.AvailableTextRun(opening, 1))
                        splitter.add(s2s.AvailableTextRun(fragment + " " + suffix, 1))
                    else:
                        splitter.add(s2s.AvailableTextRun(text, 1))
                    self.assertEqual(list(splitter.stream()), [
                        "All right,", "the first check is complete.", fragment,
                    ])
                    self.assertEqual(splitter.buffer, suffix)

    def test_many_available_sentences_share_one_lookahead_scan(self):
        from unittest.mock import patch
        from stream2sentence import stream2sentence as implementation

        opening = "All right, the first check is complete. "
        sentence = "Every request is already queued, and this complete sentence is ready. "
        text = opening + sentence * 150
        for queued in (False, True):
            with self.subTest(queued=queued):
                large_scans = []
                original = implementation._tokenize_sentences
                def counted(candidate, *args, **kwargs):
                    if len(candidate) > len(sentence) * 3:
                        large_scans.append(len(candidate))
                    return original(candidate, *args, **kwargs)
                splitter = s2s.SentenceSplitter(**OPTIONS)
                chunks = [opening] + [sentence] * 150 if queued else [text]
                for chunk in chunks:
                    splitter.add(s2s.AvailableTextRun(chunk, 1))
                with patch.object(implementation, "_tokenize_sentences", counted):
                    fragments = list(splitter.stream()) + list(splitter.flush())
                self.assertEqual(fragments, ["All right,", "the first check is complete."] + [sentence.strip()] * 150)
                self.assertLessEqual(len(large_scans), 1, large_scans)

    async def test_snapshot_offsets_survive_whitespace_and_word_lookahead(self):
        for gap in (" ", "   ", "\n", " \n\t "):
            for lookahead in (0, 3, 8):
                for terminal in (".", "!", "?", '."'):
                    with self.subTest(gap=gap, lookahead=lookahead, terminal=terminal):
                        text = ("Fair point, this is the rest of the opening sentence." + gap
                                + "Everything works correctly, according to our latest test." + gap
                                + "The last sentence stays together, including its tail" + terminal)
                        values = await collect([s2s.AvailableTextRun(text, 1)],
                                               fragment_lookahead_words=lookahead)
                        self.assertEqual(values[-1], "The last sentence stays together, including its tail" + terminal)
                        self.assertEqual("".join("".join(values).split()), "".join(text.split()))

    async def test_rewriting_custom_tokenizer_falls_back_to_plain_behavior(self):
        import re
        def rewrite(text):
            return [part.upper() for part in re.split(r"(?<=[.!?])\s+", text) if part]
        marked = await collect([s2s.AvailableTextRun(TEXT, 1)], tokenize_sentences=rewrite)
        plain = await collect([TEXT], tokenize_sentences=rewrite)
        self.assertEqual(marked, plain)

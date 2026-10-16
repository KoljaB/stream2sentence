import concurrent.futures
import importlib
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from stream2sentence import AvailableTextRun, SentenceSplitter, generate_sentences
from test_time_based import compare_results


class AvailableRunBoundaryTests(unittest.TestCase):
    def test_buffer_replacement_preserves_text_across_run_and_chunk_boundaries(self):
        original = [
            "मस्ते?beta,gamm", "gamma।beta", "  epsilon",
            ".beta。中文.नमस्त", "े.", "Dr.  مرحبا!3.",
        ]
        variants = (
            original,
            [part.replace("beta", "delta").replace("epsilon", "one two three") for part in original],
            [part.replace("  ", "\n\t").replace("!", "?") for part in original],
        )
        for texts in variants:
            expected = "".join("".join(texts).split())
            for ids in ((1, 1, 1, 2, 3, 4), (1, 1, 1, 2, 3, 2)):
                for split_chunks in (False, True):
                    for lookahead in (0, 3, 8):
                        with self.subTest(texts=texts, ids=ids, split=split_chunks, lookahead=lookahead):
                            splitter = SentenceSplitter(
                                minimum_first_fragment_length=9,
                                quick_yield_for_all_sentences=True,
                                force_first_fragment_after_words=float("inf"),
                                fragment_lookahead_words=lookahead,
                            )
                            output = []
                            for text, run_id in zip(texts, ids):
                                parts = list(text) if split_chunks else [text]
                                for part in parts:
                                    splitter.add(AvailableTextRun(part, run_id))
                                    output.extend(splitter.stream())
                                    boundary = splitter.pending_quick_yield_boundary
                                    if boundary is not None:
                                        self.assertGreaterEqual(boundary, 0)
                                        self.assertLess(boundary, len(splitter.buffer))
                            output.extend(splitter.flush())
                            self.assertEqual("".join("".join(output).split()), expected)

    def test_plain_input_still_yields_the_first_fragment_early(self):
        splitter = SentenceSplitter(
            minimum_first_fragment_length=9,
            quick_yield_for_all_sentences=True,
        )
        splitter.add("All right, more text will arrive")
        self.assertEqual(list(splitter.stream()), ["All right,"])
        splitter.add(" later.")
        self.assertEqual(list(splitter.stream()) + list(splitter.flush()),
                         ["more text will arrive later."])


class StanzaLanguageTests(unittest.TestCase):
    def setUp(self):
        self.core = importlib.import_module("stream2sentence.stream2sentence")
        self.calls = []

        def build(language, **kwargs):
            def pipeline(text):
                self.calls.append(language)
                return SimpleNamespace(sentences=[SimpleNamespace(text=text.strip())])
            return pipeline

        self.stanza = SimpleNamespace(Pipeline=mock.Mock(side_effect=build), download=mock.Mock())
        self.cache_patch = mock.patch.dict(self.core._stanza_pipelines, clear=True)
        self.loader_patch = mock.patch.object(self.core, "_load_optional_dependency", return_value=self.stanza)
        self.cache_patch.start()
        self.loader_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.addCleanup(self.loader_patch.stop)
        old_tokenizer, old_language = self.core.current_tokenizer, self.core.current_language
        self.addCleanup(setattr, self.core, "current_tokenizer", old_tokenizer)
        self.addCleanup(setattr, self.core, "current_language", old_language)

    def test_models_are_cached_by_language_and_reused_offline(self):
        english = self.core.initialize_stanza("en", offline=True)
        chinese = self.core.initialize_stanza("zh", offline=True)
        self.assertIsNot(english, chinese)
        self.assertIs(self.core.initialize_stanza("en"), english)
        self.assertIs(self.core.initialize_stanza("zh"), chinese)
        self.assertEqual(self.stanza.Pipeline.call_args_list, [
            mock.call("en", download_method=None), mock.call("zh", download_method=None),
        ])
        self.stanza.download.assert_not_called()

    def test_interleaved_splitters_keep_their_languages(self):
        english = SentenceSplitter(tokenizer="stanza", language="en", minimum_sentence_length=1000)
        chinese = SentenceSplitter(tokenizer="stanza", language="zh", minimum_sentence_length=1000)
        for splitter, text in ((english, "An English sentence."), (chinese, "中文句子。")):
            splitter.add(text)
            self.assertEqual(list(splitter.stream()) + list(splitter.flush()), [text])
        self.assertEqual(self.calls, ["en", "zh"])

    def test_failed_initialization_can_be_retried(self):
        pipeline = object()
        self.stanza.Pipeline.side_effect = [RuntimeError("model unavailable"), pipeline]
        with self.assertRaisesRegex(RuntimeError, "model unavailable"):
            self.core.initialize_stanza("en", offline=True)
        self.assertIs(self.core.initialize_stanza("en", offline=True), pipeline)
        self.assertEqual(self.stanza.Pipeline.call_count, 2)

    def test_concurrent_initialization_constructs_one_model(self):
        pipeline = object()
        ready = threading.Barrier(4)

        def build(*args, **kwargs):
            time.sleep(0.01)
            return pipeline

        def initialize():
            ready.wait(timeout=5)
            return self.core.initialize_stanza("en", offline=True)

        self.stanza.Pipeline.side_effect = build
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: initialize(), range(4)))
        self.assertTrue(all(result is pipeline for result in results))
        self.stanza.Pipeline.assert_called_once_with("en", download_method=None)

    def test_splitter_does_not_read_another_initializers_global_tokenizer(self):
        original = self.core.init_tokenizer

        def initialize(tokenizer, language, **kwargs):
            original(tokenizer, language, **kwargs)
            self.core.current_tokenizer = "nltk"

        with mock.patch.object(self.core, "init_tokenizer", side_effect=initialize):
            splitter = SentenceSplitter(tokenizer="stanza", language="zh")
        self.assertEqual(splitter.tokenizer, "stanza")


class CjkClosingMarkTests(unittest.TestCase):
    def test_closing_marks_stay_with_their_sentences(self):
        for opening, closing in zip("「『（【〔《〈", "」』）】〕》〉"):
            for terminal in ("。", "！", "？"):
                text = opening + "你好" + terminal + closing + "他说。然后走了。"
                expected = [opening + "你好" + terminal + closing, "他说。", "然后走了。"]
                for size in (1, 2, len(text)):
                    for quick in (False, True):
                        with self.subTest(opening=opening, terminal=terminal, size=size, quick=quick):
                            chunks = [text[i:i + size] for i in range(0, len(text), size)]
                            actual = list(generate_sentences(
                                chunks, tokenizer="rule-based", language="zh",
                                minimum_sentence_length=1, minimum_first_fragment_length=1,
                                context_size=2, quick_yield_for_all_sentences=quick,
                                force_first_fragment_after_words=float("inf"),
                            ))
                            self.assertEqual(actual, expected)

    def test_incomplete_quotes_and_nonterminal_closers_are_preserved(self):
        for text in ("「你好。", "「你好」继续说", "「3.14」仍然有效。"):
            for size in (1, len(text)):
                with self.subTest(text=text, size=size):
                    self.assertEqual(list(generate_sentences(
                        [text[i:i + size] for i in range(0, len(text), size)],
                        language="zh", minimum_sentence_length=1,
                    )), [text])



class FlushLifecycleTests(unittest.TestCase):
    def test_flush_is_idempotent_and_splitter_can_be_reused(self):
        splitter = SentenceSplitter(minimum_sentence_length=1)
        splitter.add("First sentence. Second sentence.")
        self.assertEqual(list(splitter.stream()), ["First sentence."])
        self.assertEqual(list(splitter.flush()), ["Second sentence."])
        self.assertEqual(list(splitter.flush()), [])
        splitter.add(" Third sentence.")
        self.assertEqual(list(splitter.stream()) + list(splitter.flush()), ["Third sentence."])
        self.assertEqual(list(splitter.flush()), [])

    def test_reuse_resets_first_fragment_and_available_run_state(self):
        text = "All right, the first check is complete. We can do that tomorrow, though."
        for lookahead in (0, 3, 8):
            for quick_all in (False, True):
                options = dict(
                    minimum_first_fragment_length=9,
                    quick_yield_single_sentence_fragment=True,
                    quick_yield_for_all_sentences=quick_all,
                    force_first_fragment_after_words=float("inf"),
                    fragment_lookahead_words=lookahead,
                )
                splitter = SentenceSplitter(**options)
                for marked in (True, True, False, True):
                    with self.subTest(lookahead=lookahead, quick_all=quick_all, marked=marked):
                        chunks = [AvailableTextRun(text, 1)] if marked else [text]
                        expected = list(generate_sentences(chunks, **options))
                        actual = []
                        for chunk in chunks:
                            splitter.add(chunk)
                            actual.extend(splitter.stream())
                        actual.extend(splitter.flush())
                        self.assertEqual(actual, expected)
                        self.assertEqual(list(splitter.flush()), [])

    def test_flush_drains_pending_chunks_and_handles_empty_input(self):
        splitter = SentenceSplitter(minimum_sentence_length=1)
        self.assertEqual(list(splitter.flush()), [])
        for chunks in (
            ["", "First sentence.", " Second sentence."],
            [AvailableTextRun("「你好。」", 1), AvailableTextRun("他说。", 1)],
            ["3.14 is a number.", " Unfinished tail"],
            ["", "  "],
        ):
            with self.subTest(chunks=chunks):
                for chunk in chunks:
                    splitter.add(chunk)
                self.assertEqual(list(splitter.flush()), list(generate_sentences(
                    chunks, minimum_sentence_length=1,
                )))
                self.assertEqual(list(splitter.flush()), [])

    def test_tokenizer_failure_keeps_tail_for_retry(self):
        tokenizer = mock.Mock(side_effect=[RuntimeError("temporary failure"), ["Unfinished tail"]])
        splitter = SentenceSplitter(tokenize_sentences=tokenizer, minimum_sentence_length=1000)
        splitter.add("Unfinished tail")
        self.assertEqual(list(splitter.stream()), [])
        with self.assertRaisesRegex(RuntimeError, "temporary failure"):
            list(splitter.flush())
        self.assertEqual(list(splitter.flush()), ["Unfinished tail"])
        self.assertEqual(list(splitter.flush()), [])



class StreamFailureRecoveryTests(unittest.TestCase):
    def test_failure_preserves_unprocessed_chunk_for_stream_and_flush(self):
        for operation in ("stream", "flush"):
            for marked in (False, True):
                with self.subTest(operation=operation, marked=marked):
                    tokenizer = mock.Mock(side_effect=[RuntimeError("temporary"), ["First. Tail"]])
                    splitter = SentenceSplitter(
                        tokenize_sentences=tokenizer, minimum_sentence_length=1,
                        context_size=0,
                    )
                    chunk = AvailableTextRun("First. Tail", 1) if marked else "First. Tail"
                    splitter.add(chunk)
                    with self.assertRaisesRegex(RuntimeError, "temporary"):
                        list(getattr(splitter, operation)())
                    # Retry uses a normal tokenizer, after the injected failure.
                    splitter.tokenize_sentences = lambda text: [text]
                    self.assertEqual(list(splitter.flush()), ["First. Tail"])
                    self.assertEqual(list(splitter.flush()), [])

    def test_retry_after_output_preserves_remaining_chunks_and_run_ids(self):
        core = importlib.import_module("stream2sentence.stream2sentence")
        for marked in (False, True):
            failed = False

            def tokenize(text):
                nonlocal failed
                if text.startswith("Second") and not failed:
                    failed = True
                    raise RuntimeError("temporary")
                return core._rule_based_tokenize_sentences(text)

            splitter = SentenceSplitter(
                tokenize_sentences=tokenize, minimum_sentence_length=1,
                minimum_first_fragment_length=1, context_size=0,
            )
            texts = ["First sentence. Second sentence.", " Third tail"]
            for text in texts:
                splitter.add(AvailableTextRun(text, 7) if marked else text)
            output = []
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                for part in splitter.flush():
                    output.append(part)
            self.assertEqual(output, ["First sentence."])
            if marked:
                self.assertTrue(all(
                    isinstance(part, AvailableTextRun) and part.run_id == 7
                    for part in splitter.input_buffer
                ))
            output.extend(splitter.flush())
            self.assertEqual(output, ["First sentence.", "Second sentence.", "Third tail"])
            self.assertEqual(list(splitter.flush()), [])

    def test_available_run_lookahead_failure_preserves_future_text(self):
        core = importlib.import_module("stream2sentence.stream2sentence")
        failed = False

        def tokenize(text):
            nonlocal failed
            if "tomorrow" in text and not failed:
                failed = True
                raise RuntimeError("temporary")
            return core._rule_based_tokenize_sentences(text)

        splitter = SentenceSplitter(
            tokenize_sentences=tokenize,
            minimum_first_fragment_length=9,
            quick_yield_for_all_sentences=True,
            force_first_fragment_after_words=float("inf"),
        )
        text = "All right, the first check is complete. We can do that tomorrow, though."
        splitter.add(AvailableTextRun(text, 1))
        output = []
        with self.assertRaisesRegex(RuntimeError, "temporary"):
            for part in splitter.flush():
                output.append(part)
        output.extend(splitter.flush())
        self.assertEqual("".join("".join(output).split()), "".join(text.split()))
        self.assertEqual(list(splitter.flush()), [])


class TimingComparisonTests(unittest.TestCase):
    def test_missing_and_extra_outputs_fail(self):
        expected = [["First sentence.", "1.0"], ["Second sentence.", "2.0"]]
        for actual in ([], expected[:1], expected + [["Extra.", "3.0"]]):
            with self.subTest(actual=actual):
                with self.assertRaises(ValueError):
                    compare_results(actual, expected)

    def test_text_and_timing_mismatches_fail(self):
        for actual in ([["Wrong sentence.", "1.0"]], [["First sentence.", "1.5"]]):
            with self.subTest(actual=actual):
                with self.assertRaises(ValueError):
                    compare_results(actual, [["First sentence.", "1.0"]])

    def test_matching_outputs_within_tolerance_pass(self):
        compare_results([["First sentence.", "1.2"]], [["First sentence.", "1.0"]])

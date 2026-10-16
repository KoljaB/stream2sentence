import importlib
import unittest

from stream2sentence import SentenceSplitter, generate_sentences, init_tokenizer
from stream2sentence.quick_yield_boundary import HOLD, REJECT, SPLIT, get_boundary_detector


implementation = importlib.import_module("stream2sentence.stream2sentence")


class ConsensusMultilingualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_tokenizer("nltk+rule-based")

    def tokenize(self, text, language="en", tokenizer="nltk+rule-based"):
        return implementation._tokenize_sentences(
            text, tokenizer=tokenizer, language=language
        )

    def test_unspaced_punctuation_runs_keep_the_whole_terminator(self):
        for punctuation in ("?", "!", "?!", "??", "!!", "!?", "！？", "？!", "?!\""):
            first = "你好吗" + punctuation
            with self.subTest(punctuation=punctuation):
                self.assertEqual(
                    self.tokenize(first + "我很好！今天很好。", "zh"),
                    [first, "我很好！", "今天很好。"],
                )

    def test_mixed_script_sentence_endings_are_not_blanket_rejected(self):
        cases = [
            ("hi", "उत्तर 42।", "फिर आगे बढ़ें।"),
            ("bn", "উত্তর 42।", "আবার চেষ্টা করুন।"),
            ("ur", "جواب 42۔", "پھر آگے بڑھیں۔"),
            ("zh", "结果是42。", "然后继续。"),
            ("zh", "请打开API。", "然后继续。"),
            ("zh", "请打开API!", "然后继续。"),
            ("zh", "结果是42？", "然后继续。"),
            ("zh", "结果是４２。", "然后继续。"),
        ]
        for language, first, second in cases:
            with self.subTest(language=language, first=first):
                self.assertEqual(
                    self.tokenize(first + " " + second, language), [first, second]
                )
        self.assertEqual(
            self.tokenize("请打开API!然后继续。", "zh"),
            ["请打开API!", "然后继续。"],
        )

    def test_numeric_tokens_use_unicode_digits_in_both_tokenizers(self):
        for number in ("2。5", "２。５", "२。५", "٢。٥", "2。５", "２。5"):
            for tokenizer in ("rule-based", "nltk+rule-based"):
                with self.subTest(number=number, tokenizer=tokenizer):
                    first = f"Version {number} is out."
                    self.assertEqual(
                        self.tokenize(first + " Yes.", tokenizer=tokenizer),
                        [first, "Yes."],
                    )

    def test_numeric_prefix_waits_for_local_lookahead(self):
        detector = get_boundary_detector("zh")
        for digits in ("42", "４２", "४२", "٤٢"):
            prefix = "结果是" + digits + "。"
            index = len(prefix) - 1
            with self.subTest(digits=digits):
                self.assertEqual(detector.classify(prefix, index), HOLD)
                self.assertEqual(detector.classify(prefix + "５", index, "５"), REJECT)
                self.assertEqual(detector.classify(prefix + "然", index, "然"), SPLIT)

    def test_abbreviations_and_ascii_tokens_keep_their_full_stop(self):
        for text in (
            "Meet Dr。 Smith today.",
            "Meet Mr。 Smith today.",
            "Meet Prof。 Smith today.",
            "Visit example。com today.",
            "Use release2。beta today.",
        ):
            for tokenizer in ("rule-based", "nltk+rule-based"):
                with self.subTest(text=text, tokenizer=tokenizer):
                    self.assertEqual(self.tokenize(text, tokenizer=tokenizer), [text])

    def test_ambiguous_abbreviation_can_still_end_a_sentence(self):
        self.assertEqual(
            self.tokenize("They joined Acme Inc。 Then they left."),
            ["They joined Acme Inc。", "Then they left."],
        )

    def test_urdu_abbreviations_remain_protected_after_consensus_override(self):
        for abbreviation in ("ق.م.", "ق۔م۔", "ق.م۔", "ق۔م."):
            first = f"یہ واقعہ 300 {abbreviation} میں پیش آیا۔"
            expected = [first, "اگلا جملہ ہے۔"]
            text = " ".join(expected)
            for size in (1, 3, 7, len(text)):
                with self.subTest(abbreviation=abbreviation, size=size):
                    chunks = [text[i:i + size] for i in range(0, len(text), size)]
                    self.assertEqual(
                        list(generate_sentences(
                            chunks, tokenizer="nltk+rule-based", language="ur"
                        )),
                        expected,
                    )

    def test_urdu_abbreviation_prefix_does_not_emit(self):
        for abbreviation in ("ق۔م۔", "ق.م۔", "ق۔م."):
            splitter = SentenceSplitter(
                tokenizer="nltk+rule-based", language="ur", auto_context=True
            )
            prefix = f"یہ واقعہ 300 {abbreviation} "
            with self.subTest(abbreviation=abbreviation):
                for char in prefix:
                    splitter.add(char)
                    self.assertEqual(list(splitter.stream()), [])
                splitter.add("میں پیش آیا۔ اگلا جملہ ہے۔")
                self.assertEqual(
                    list(splitter.stream()) + list(splitter.flush()),
                    [prefix + "میں پیش آیا۔", "اگلا جملہ ہے۔"],
                )

    def test_unspaced_ascii_and_cjk_closing_marks_stay_conservative(self):
        self.assertEqual(
            self.tokenize("Hello!Next sentence."),
            ["Hello!Next sentence."],
        )
        for closing in "」』）】〕》〉":
            text = "你好。" + closing + "他说。然后走了。"
            with self.subTest(closing=closing):
                self.assertEqual(
                    self.tokenize(text, "zh"),
                    ["你好。" + closing + "他说。", "然后走了。"],
                )

    def test_native_delimiters_emit_before_the_source_finishes(self):
        cases = [
            ("en", "Hello there.", " The following sentence is deliberately left unfinished"),
            ("hi", "नमस्ते दोस्त।", " मैं यहाँ बैठकर एक बहुत लंबा उत्तर लिख रहा हूँ"),
            ("bn", "আমি ভালো আছি।", " আমি এখানে বসে একটি অনেক দীর্ঘ উত্তর লিখছি"),
            ("ur", "میں ٹھیک ہوں۔", " میں یہاں بیٹھ کر ایک بہت لمبا جواب لکھ رہا ہوں"),
            ("zh", "今天这里的天气真的非常好。", "接下来我们准备继续讨论一个还没有写完的话题"),
            ("zh", "今天这里的天气真的非常好！", "接下来我们准备继续讨论一个还没有写完的话题"),
            ("zh", "今天这里的天气真的非常好吗？", "接下来我们准备继续讨论一个还没有写完的话题"),
            ("ur", "کیا آج یہاں کا موسم واقعی بہت اچھا ہے؟", " میں یہاں بیٹھ کر ایک بہت لمبا جواب لکھ رہا ہوں"),
        ]
        for language, first, tail in cases:
            for size in (1, 3, 7):
                for quick_yield in (False, True):
                    with self.subTest(language=language, first=first, size=size, quick=quick_yield):
                        progress = {"consumed": 0, "exhausted": False}
                        text = first + tail

                        def source():
                            for i in range(0, len(text), size):
                                progress["consumed"] = min(i + size, len(text))
                                yield text[i:i + size]
                            progress["exhausted"] = True

                        output = generate_sentences(
                            source(), tokenizer="nltk+rule-based", language=language,
                            quick_yield_single_sentence_fragment=quick_yield,
                        )
                        try:
                            self.assertEqual(next(output), first)
                            self.assertFalse(progress["exhausted"])
                            self.assertLess(progress["consumed"], len(text))
                        finally:
                            output.close()

    def test_numeric_tokens_survive_quick_yield_and_chunk_boundaries(self):
        first = "Version ２。５ is out."
        text = first + " The next sentence continues for a little longer."
        for size in (1, 3, 7, len(text)):
            for tokenizer in ("rule-based", "nltk+rule-based"):
                with self.subTest(size=size, tokenizer=tokenizer):
                    chunks = [text[i:i + size] for i in range(0, len(text), size)]
                    self.assertEqual(
                        list(generate_sentences(
                            chunks, tokenizer=tokenizer,
                            quick_yield_single_sentence_fragment=True,
                        )),
                        [first, "The next sentence continues for a little longer."],
                    )

    def test_custom_delimiters_remain_authoritative(self):
        splitter = SentenceSplitter(
            tokenizer="nltk+rule-based", language="hi",
            sentence_fragment_delimiters=".?!", full_sentence_delimiters=".?!",
        )
        first = "आज सुबह यहाँ मौसम बहुत अच्छा है।"
        tail = " मैं यहाँ बैठकर एक बहुत लंबा उत्तर लिख रहा हूँ"
        splitter.add(first + tail)
        self.assertEqual(list(splitter.stream()), [])
        self.assertEqual(list(splitter.flush()), [first, tail.strip()])


if __name__ == "__main__":
    unittest.main()

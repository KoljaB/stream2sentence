import re
import unittest

from stream2sentence import SentenceSplitter, generate_sentences


def generator_result(sentences):
    yield from sentences


def custom_tokenizer(result_type):
    def tokenize(text):
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?。！？])\s*", text)
            if sentence.strip()
        ]
        return result_type(sentences)

    return tokenize


RESULT_TYPES = (list, tuple, iter, generator_result)
STREAMING_TEXT = (
    "Hello world. Another sentence. "
    "This last sentence has enough lookahead to trigger streaming."
)


class CustomTokenizerTests(unittest.TestCase):
    def test_result_types_preserve_sentences_across_chunk_sizes(self):
        cases = (
            ("", []),
            ("Hello world.", ["Hello world."]),
            (
                STREAMING_TEXT,
                [
                    "Hello world.",
                    "Another sentence.",
                    "This last sentence has enough lookahead to trigger streaming.",
                ],
            ),
            (
                "你好。今天天气很好！我们去公园吧？",
                ["你好。今天天气很好！", "我们去公园吧？"],
            ),
        )
        for text, expected in cases:
            for result_type in RESULT_TYPES:
                for size in (1, 3, max(1, len(text))):
                    with self.subTest(
                        text=text, result_type=result_type.__name__, chunk_size=size
                    ):
                        chunks = [
                            text[index:index + size]
                            for index in range(0, len(text), size)
                        ]
                        self.assertEqual(
                            list(generate_sentences(
                                chunks,
                                tokenize_sentences=custom_tokenizer(result_type),
                            )),
                            expected,
                        )

    def test_stream_and_flush_preserve_their_output(self):
        for result_type in RESULT_TYPES:
            splitter = SentenceSplitter(
                tokenize_sentences=custom_tokenizer(result_type),
            )
            splitter.add(STREAMING_TEXT)
            during_stream = list(splitter.stream())
            at_end = list(splitter.flush())

            with self.subTest(result_type=result_type.__name__, phase="stream"):
                self.assertEqual(
                    during_stream,
                    ["Hello world.", "Another sentence."],
                )
            with self.subTest(result_type=result_type.__name__, phase="flush"):
                self.assertEqual(
                    at_end,
                    ["This last sentence has enough lookahead to trigger streaming."],
                )


if __name__ == "__main__":
    unittest.main()

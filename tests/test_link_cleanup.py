import unittest

from stream2sentence import generate_sentences
from stream2sentence.stream2sentence import _remove_links


def cleaned(text, chunked=False):
    chunks = list(text) if chunked else [text]
    return list(generate_sentences(chunks, cleanup_text_links=True))


class LinkCleanupTests(unittest.TestCase):
    def test_punctuation_after_a_link_is_kept(self):
        cases = {
            "Read the docs at https://example.com/docs. Then restart the server now.":
                ["Read the docs at .", "Then restart the server now."],
            "Is it https://example.com/a? Yes it is the right one.":
                ["Is it ?", "Yes it is the right one."],
            "Open https://example.com/a, then log in with your account.":
                ["Open , then log in with your account."],
            "See the page (https://example.com/a) for all the details.":
                ["See the page () for all the details."],
            "See the page [https://example.com/a] for all the details.":
                ["See the page [] for all the details."],
        }
        for text, expected in cases.items():
            for chunked in (False, True):
                with self.subTest(text=text, chunked=chunked):
                    self.assertEqual(cleaned(text, chunked), expected)

    def test_whole_link_is_removed(self):
        cases = {
            "Open https://example.com/page#setup to begin the install.":
                ["Open  to begin the install."],
            "Check https://staging.example.com/v1.2/status?ok=false&x=1 again later.":
                ["Check  again later."],
            "Read https://en.wikipedia.org/wiki/Python_(language) for the history.":
                ["Read  for the history."],
            "Read about it at http://example.com/a.":
                ["Read about it at ."],
        }
        for text, expected in cases.items():
            for chunked in (False, True):
                with self.subTest(text=text, chunked=chunked):
                    self.assertEqual(cleaned(text, chunked), expected)

    def test_text_without_links_is_unchanged(self):
        text = "Prices rose 3.5% (from $10, to $12). Nobody saw it coming."
        self.assertEqual(
            cleaned(text), ["Prices rose 3.5% (from $10, to $12).", "Nobody saw it coming."]
        )

    def test_text_touching_a_link_is_kept(self):
        cases = {
            "请看https://example.com/a然后重启服务器。下一句话在这里。":
                "请看然后重启服务器。下一句话在这里。",
            "请看 https://example.com/a。然后重启服务器。":
                "请看 。然后重启服务器。",
            "詳細はhttps://example.com/aを見てください。次の文です。":
                "詳細はを見てください。次の文です。",
            "자세한 내용은 https://example.com/a에서 확인하세요.":
                "자세한 내용은 에서 확인하세요.",
            "|https://a.com|second|third|": "||second|third|",
            "Visit `https://example.com/a` now.": "Visit `` now.",
            "“https://example.com/a” tail": "“” tail",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(_remove_links(text), expected)

    def test_ascii_links_with_symbols_are_removed_whole(self):
        cases = {
            "Open https://example.com/~user/page?a=1&b=2#top now.": "Open  now.",
            "Open https://example.com/a_b-c/d.html now.": "Open  now.",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(_remove_links(text), expected)


if __name__ == "__main__":
    unittest.main()

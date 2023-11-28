import unittest
from stream2sentence import generate_sentences

class TestSentenceGenerator(unittest.TestCase):

    def test_chinese(self):
        text = "我喜欢读书。天气很好。我们去公园吧。今天是星期五。早上好。这是我的朋友。请帮我。吃饭了吗？我在学中文。晚安。"
        expected = ["我喜欢读书。", "天气很好。", "我们去公园吧。", "今天是星期五。", "早上好。", "这是我的朋友。", "请帮我。", "吃饭了吗？", "我在学中文。晚安。"]
        sentences = list(generate_sentences(text, minimum_sentence_length = 2, context_size=2, tokenizer="stanza", language="zh"))
        self.assertEqual(sentences, expected)    

    def test_generator(self):
        def generator():
            yield "Hallo, "
            yield "wie geht es dir?"
            yield "Mir geht es gut."
        expected = ["Hallo,", "wie geht es dir?", "Mir geht es gut."]
        sentences = list(generate_sentences(generator(), minimum_sentence_length = 3, context_size=5, minimum_first_fragment_length = 3, quick_yield_single_sentence_fragment=True))
        self.assertEqual(sentences, expected)    

    def test_return_incomplete_last(self):
        text = "How I feel? I feel fine"
        expected = ["How I feel?", "I feel fine"]
        sentences = list(generate_sentences(text))
        self.assertEqual(sentences, expected)    

    def test_hello_world(self):
        text = "Hello, world."
        expected = ["Hello,", "world."]
        sentences = list(generate_sentences(text, quick_yield_single_sentence_fragment=True, minimum_sentence_length=3, minimum_first_fragment_length=3))
        self.assertEqual(sentences, expected)    

    def test_hello_world2(self):
        text = "Hello, world! Hello all, my dear friends of realtime apps."
        expected = ["Hello, world!", "Hello all, my dear friends of realtime apps."]
        sentences = list(generate_sentences(text, minimum_sentence_length=3))
        self.assertEqual(sentences, expected)    

    def test_basic(self):
        text = "This is a test. This is another test sentence. Just testing out the module."
        expected = ["This is a test.", "This is another test sentence.", "Just testing out the module."]
        sentences = list(generate_sentences(text))
        self.assertEqual(sentences, expected)

    def test_tricky_sentence1(self):
        text = "Good muffins cost $3.88 in New York. Please buy me two of them."
        expected = ["Good muffins cost $3.88 in New York.", "Please buy me two of them."]
        sentences = list(generate_sentences(text))
        self.assertEqual(sentences, expected)

    def test_tricky_sentence2(self):
        text = "I called Dr. Jones. I called Dr. Jones."
        expected = ["I called Dr. Jones.", "I called Dr. Jones."]
        sentences = list(generate_sentences(text))
        self.assertEqual(sentences, expected)

    def test_quick_yield(self):
        text = "First, this. Second, this."
        expected = ["First,", "this.", "Second, this."]
        sentences = list(generate_sentences(text, quick_yield_single_sentence_fragment=True, minimum_sentence_length=3, minimum_first_fragment_length=3))
        self.assertEqual(sentences, expected)

    def test_quick_yield2(self):
        text = "First, this. Second, this."
        expected = ["First,", "this. Second, this."]
        sentences = list(generate_sentences(text, quick_yield_single_sentence_fragment=True, minimum_sentence_length=6, minimum_first_fragment_length=3))
        self.assertEqual(sentences, expected)

    def test_quick_yield3(self):
        text = "First, this. Second, this."
        expected = ["First, this.", "Second, this."]
        sentences = list(generate_sentences(text, quick_yield_single_sentence_fragment=True, minimum_sentence_length=3, minimum_first_fragment_length=6))
        self.assertEqual(sentences, expected)

    def test_quick_yield4(self):
        text = "First, this. Second, this."
        expected = ["First, this.", "Second, this."]
        sentences = list(generate_sentences(text, quick_yield_single_sentence_fragment=True, minimum_sentence_length=6, minimum_first_fragment_length=6))
        self.assertEqual(sentences, expected)

    def test_minimum_length1(self):
        text = "Short. Longer sentence."
        expected = ["Short.", "Longer sentence."]
        sentences = list(generate_sentences(text, minimum_sentence_length=6)) # two sentences, len("Short.") == 6
        self.assertEqual(sentences, expected)

    def test_minimum_length2(self):
        text = "Short. Longer sentence."
        expected = ["Short. Longer sentence."]
        sentences = list(generate_sentences(text, minimum_sentence_length=7)) # one sentences, len("Short.") == 6
        self.assertEqual(sentences, expected)

    def test_cleanup(self):
        text = "Text with link: https://www.example.com and emoji 😀" 
        expected = ["Text with link:  and emoji"]
        sentences = list(generate_sentences(text, cleanup_text_links=True, cleanup_text_emojis=True))
        self.assertEqual(sentences, expected)

    def test_check1(self):
        text = "I'll go with a glass of red wine. Thank you." 
        expected = ["I'll go with a glass of red wine.", "Thank you."]
        sentences = list(generate_sentences(text, minimum_sentence_length=10, minimum_first_fragment_length=10, quick_yield_single_sentence_fragment=True, cleanup_text_links=True, cleanup_text_emojis=True))
        self.assertEqual(sentences, expected)

    def test_very_short(self):
        text = "Excuse me?" 
        expected = ["Excuse me?"]
        sentences = list(generate_sentences(text, minimum_sentence_length=18, minimum_first_fragment_length=10, quick_yield_single_sentence_fragment=True, cleanup_text_links=True, cleanup_text_emojis=True))
        self.assertEqual(sentences, expected)

    def test_log_characters(self):
        text = "Hello world"
        print ()
        sentences = list(generate_sentences(text, log_characters=True))
        print ()
        print ()
        print (f"test_log_characters succeeded, if {text} was printed above.")
        print ()
        # Check characters were printed
        self.assertTrue(sentences) 

    def test_not_log_characters(self):
        text = "Do not show these characters." 
        expected = ["Do not show these characters."]
        sentences = list(generate_sentences(text, log_characters=False))
        print(f"\ntest_not_log_characters succeeded, if \"{text}\" was not printed above.")
        self.assertEqual(sentences, expected)

if __name__ == '__main__':
    unittest.main()
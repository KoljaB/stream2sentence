import unittest
from stream2sentence import generate_sentences

class TestSentenceGenerator(unittest.TestCase):

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
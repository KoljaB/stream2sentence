import importlib
import inspect
import os
import re
import unittest
from unittest import mock
from stream2sentence import SentenceSplitter, generate_sentences, generate_sentences_async


def simple_sentence_tokenizer(text):
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def single_sentence_tokenizer(text):
    text = text.strip()
    return [text] if text else []


TOKENIZERS_UNDER_TEST = ("nltk", "rule-based")
AUTO_CONTEXT_WORKFLOW_TOKENIZER = "nltk+rule-based"
RUN_STANZA_INTEGRATION = os.environ.get("STREAM2SENTENCE_RUN_STANZA_TESTS") == "1"


MULTILINGUAL_DELIMITERS = ".?!;:,\n…)]}。！？؟।-"
MULTILINGUAL_FULL_DELIMITERS = ".?!\n…。！？؟।"


def chunk_text(text, size):
    return [text[index:index + size] for index in range(0, len(text), size)]


CONSENSUS_STRESS_INPUT = """Dr. A. J. Rivera met Mr. O'Neil at 8:05 a.m. in St. John's, N.L., to review sec. 3.2 of the U.S. export memo before breakfast. The memo said that Acme Widgets, Inc., not Acme Widgets Co. Ltd., shipped 1.5-mm parts from No. 4 Dock to Apt. 2B via FedEx, etc., and nobody was surprised. Prof. Nguyen wrote “see Fig. 2.1, Eq. (4.3), and fn. 7” in the margin, although the margin also had the file name draft.v0.9.final.pdf on it. Maya emailed qa.bot+alerts@example.co.uk about https://staging.example.com/v1.2/status?ok=false, but the error was just “timeout at 10.0.0.5:443,” not a crash. The changelog entry “v2.0.0-beta.3 fixes U.S.-only i18n bugs” looked final, yet Sam kept typing because “beta.3” was not a sentence by itself. In the transcript, the speaker says “I live on E. 5th St. near Washington, D.C.” while the sentence continues with a note about background noise. The invoice lists 12.50 EUR, 3.14159 kg, Item No. A.7, Ref. ID X.Y.Z., and the harmless label “End.” printed in the middle of the page. When the router logs “eth0: link down... retrying in 0.5 sec.” it is still part of the same report sentence, not the end of the user-facing sentence. The legal draft names Smith v. Jones, 123 F.3d 456, 458 n.2 (9th Cir. 1999), and then continues with “cf. Brown, supra,” without stopping. Our parser should keep reading after labels like a. setup, b. train, c. eval, because those list markers are not sentence endings in this context. Even punctuation-heavy brand names like Yahoo! Finance, Guess?, and Who? Weekly can sit inside a perfectly normal sentence without ending it. Finally, the note “call me at 555.0100 ext. 42 before 6 p.m., unless Jan. 3 is a holiday” contains four tempting dots before the real full stop."""

CONSENSUS_STRESS_EXPECTED = [
    "Dr. A. J. Rivera met Mr. O'Neil at 8:05 a.m. in St. John's, N.L., to review sec. 3.2 of the U.S. export memo before breakfast.",
    "The memo said that Acme Widgets, Inc., not Acme Widgets Co. Ltd., shipped 1.5-mm parts from No. 4 Dock to Apt. 2B via FedEx, etc., and nobody was surprised.",
    "Prof. Nguyen wrote “see Fig. 2.1, Eq. (4.3), and fn. 7” in the margin, although the margin also had the file name draft.v0.9.final.pdf on it.",
    "Maya emailed qa.bot+alerts@example.co.uk about https://staging.example.com/v1.2/status?ok=false, but the error was just “timeout at 10.0.0.5:443,” not a crash.",
    "The changelog entry “v2.0.0-beta.3 fixes U.S.-only i18n bugs” looked final, yet Sam kept typing because “beta.3” was not a sentence by itself.",
    "In the transcript, the speaker says “I live on E. 5th St. near Washington, D.C.” while the sentence continues with a note about background noise.",
    "The invoice lists 12.50 EUR, 3.14159 kg, Item No. A.7, Ref. ID X.Y.Z., and the harmless label “End.” printed in the middle of the page.",
    "When the router logs “eth0: link down... retrying in 0.5 sec.” it is still part of the same report sentence, not the end of the user-facing sentence.",
    "The legal draft names Smith v. Jones, 123 F.3d 456, 458 n.2 (9th Cir. 1999), and then continues with “cf. Brown, supra,” without stopping.",
    "Our parser should keep reading after labels like a. setup, b. train, c. eval, because those list markers are not sentence endings in this context.",
    "Even punctuation-heavy brand names like Yahoo! Finance, Guess?, and Who? Weekly can sit inside a perfectly normal sentence without ending it.",
    "Finally, the note “call me at 555.0100 ext. 42 before 6 p.m., unless Jan. 3 is a holiday” contains four tempting dots before the real full stop.",
]


def quick_yield_sentences(
    text,
    tokenize_sentences=simple_sentence_tokenizer,
    language="en",
    tokenizer="nltk",
    **kwargs,
):
    stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
    nltk_initialized = stream2sentence_module.nltk_initialized
    stream2sentence_module.nltk_initialized = True
    try:
        return list(generate_sentences(
            text,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=3,
            minimum_first_fragment_length=3,
            tokenize_sentences=tokenize_sentences,
            tokenizer=tokenizer,
            language=language,
            **kwargs,
        ))
    finally:
        stream2sentence_module.nltk_initialized = nltk_initialized


class TestSentenceGenerator(unittest.TestCase):

    def test_new_options_are_appended_after_032_positional_parameters(self):
        expected_tail = [
            "cleanup_text_links",
            "cleanup_text_emojis",
            "tokenize_sentences",
            "tokenizer",
            "language",
            "log_characters",
            "sentence_fragment_delimiters",
            "full_sentence_delimiters",
            "force_first_fragment_after_words",
            "filter_first_non_alnum_characters",
            "debug",
            "auto_context",
            "never_split_numbers",
        ]

        for callable_ in (generate_sentences, generate_sentences_async, SentenceSplitter):
            with self.subTest(callable_=callable_):
                names = list(inspect.signature(callable_).parameters)
                self.assertEqual(names[-len(expected_tail):], expected_tail)

    def assertQuickYieldSingleSentence(self, text, language="en", **kwargs):
        self.assertQuickYieldSentences(
            text,
            [text],
            tokenize_sentences=single_sentence_tokenizer,
            language=language,
            **kwargs,
        )

    def assertQuickYieldSentences(
        self,
        text,
        expected,
        tokenize_sentences=simple_sentence_tokenizer,
        language="en",
        **kwargs,
    ):
        for tokenizer in TOKENIZERS_UNDER_TEST:
            with self.subTest(tokenizer=tokenizer, text=text):
                self.assertEqual(
                    quick_yield_sentences(
                        text,
                        tokenize_sentences=tokenize_sentences,
                        language=language,
                        tokenizer=tokenizer,
                        **kwargs,
                    ),
                    expected,
                )

    def assertGeneratedSentences(self, source, expected, **kwargs):
        for tokenizer in TOKENIZERS_UNDER_TEST:
            with self.subTest(tokenizer=tokenizer):
                stream = source() if callable(source) else source
                self.assertEqual(
                    list(generate_sentences(stream, tokenizer=tokenizer, **kwargs)),
                    expected,
                )

    def assertAutoContextSentences(self, text, expected):
        self.assertEqual(
            list(generate_sentences(
                list(text),
                tokenizer="nltk+rule-based",
                language="en",
                minimum_sentence_length=1,
                minimum_first_fragment_length=1,
                context_size=1,
                context_size_look_overhead=128,
                auto_context=True,
            )),
            expected,
        )

    def assertAutoContextSentencesForBoundaryTokenizers(self, text, expected):
        for tokenizer in ("rule-based", AUTO_CONTEXT_WORKFLOW_TOKENIZER):
            with self.subTest(tokenizer=tokenizer, text=text):
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer=tokenizer,
                        language="en",
                        minimum_sentence_length=1,
                        minimum_first_fragment_length=1,
                        context_size=1,
                        context_size_look_overhead=128,
                        auto_context=True,
                    )),
                    expected,
                )

    def assertGoldSentenceBoundaries(self, language_name, language_code, text, expected):
        stream_variants = {
            "single_chunk": [text],
            "character_stream": list(text),
            "seven_char_chunks": chunk_text(text, 7),
        }
        for stream_name, stream in stream_variants.items():
            with self.subTest(language=language_name, stream=stream_name):
                sentences = list(generate_sentences(
                    stream,
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=64,
                    tokenizer="rule-based",
                    language=language_code,
                    sentence_fragment_delimiters=MULTILINGUAL_DELIMITERS,
                    full_sentence_delimiters=MULTILINGUAL_FULL_DELIMITERS,
                ))
                self.assertEqual(sentences, expected)

    @unittest.skipUnless(
        RUN_STANZA_INTEGRATION,
        "set STREAM2SENTENCE_RUN_STANZA_TESTS=1 to run slow Stanza integration tests",
    )
    def test_chinese(self):
        text = "我喜欢读书。天气很好。我们去公园吧。今天是星期五。早上好。这是我的朋友。请帮我。吃饭了吗？我在学中文。晚安。"
        #expected = ["我喜欢读书。", "天气很好。", "我们去公园吧。", "今天是星期五。", "早上好。", "这是我的朋友。", "请帮我。吃饭了吗？", "我在学中文。", "晚安。"]
        #expected = ["我喜欢读书。", "天气很好。", "我们去公园吧。", "今天是星期五。", "早上好。", "这是我的朋友。", "请帮我。", "吃饭了吗？", "我在学中文。", "晚安。"]
        expected = ["我喜欢读书。", "天气很好。", "我们去公园吧。", "今天是星期五。", "早上好。", "这是我的朋友。", "请帮我。吃饭了吗？我在学中文。", "晚安。"] # this changed with new stanza version
        sentences = list(generate_sentences(text, minimum_sentence_length=2, context_size=2, tokenizer="stanza", language="zh"))
        self.assertEqual(sentences, expected)    

    @unittest.skipUnless(
        RUN_STANZA_INTEGRATION,
        "set STREAM2SENTENCE_RUN_STANZA_TESTS=1 to run slow Stanza integration tests",
    )
    def test_chinese2(self):
        text = """
        胡/爷/爷，我/来/给/您/讲/一下/下/周/每/天/的/安/排。 
        周/一/：/9:00-10:00：晨/练/太/极/拳/，/地点/：/活/动/室/。
        10:30-11:30：园/艺/活/动/菠菜/种/植/，/地点/：/花/园/。
        14:00-15:00：手/工/制/作/睡/眠/香/囊/，/地点/：/手/工/室/。
        15:30-16:30：观/看/老/电/影/，/地点/：/影/音/室/。

        周/二/：/9:00-10:00：八/段/锦/简/化/版/，/地点/：/大/厅/。
        10:30-11:30：书/法/练/习/，/地点/：/书/画/室/。
        14:00-15:00：棋/牌/娱/乐/象/棋/、/围/棋/等/，/地点/：/棋/牌/室/。
        15:30-16:30：养/生/讲/座/春/天/养/生/1/，/地点/：/会/议/室/。
        大/厅/"""
        expected = [
            "胡/爷/爷，我/来/给/您/讲/一下/下/周/每/天/的/安/排。",
            "周/一/：/9:00-10:00：晨/练/太/极/拳/，/地点/：/活/动/室/。",
            "10:30-11:30：园/艺/活/动/菠菜/种/植/，/地点/：/花/园/。",
            "14:00-15:00：手/工/制/作/睡/眠/香/囊/，/地点/：/手/工/室/。",
            "15:30-16:30：观/看/老/电/影/，/地点/：/影/音/室/。",
            "周/二/：/9:00-10:00：八/段/锦/简/化/版/，/地点/：/大/厅/。",
            "10:30-11:30：书/法/练/习/，/地点/：/书/画/室/。",
            "14:00-15:00：棋/牌/娱/乐/象/棋/、/围/棋/等/，/地点/：/棋/牌/室/。",
            "15:30-16:30：养/生/讲/座/春/天/养/生/1/，/地点/：/会/议/室/。",
            "大/厅/",
        ]
        sentences = list(generate_sentences(text, minimum_sentence_length=2, context_size=2, tokenizer="stanza", language="zh"))
        self.assertEqual(sentences, expected)    

    def test_generator(self):
        def generator():
            yield "Hallo, "
            yield "wie geht es dir? "
            yield "Mir geht es gut."
        expected = ["Hallo,", "wie geht es dir?", "Mir geht es gut."]
        self.assertGeneratedSentences(
            generator,
            expected,
            minimum_sentence_length=3,
            context_size=5,
            minimum_first_fragment_length=3,
            quick_yield_single_sentence_fragment=True,
        )

    def test_return_incomplete_last(self):
        text = "How I feel? I feel fine"
        expected = ["How I feel?", "I feel fine"]
        self.assertGeneratedSentences(text, expected)

    def test_hello_world(self):
        text = "Hello, world."
        expected = ["Hello,", "world."]
        self.assertGeneratedSentences(
            text,
            expected,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=3,
            minimum_first_fragment_length=3,
        )

    def test_hello_world2(self):
        text = "Hello, world! Hello all, my dear friends of realtime apps."
        expected = ["Hello, world!", "Hello all, my dear friends of realtime apps."]
        self.assertGeneratedSentences(text, expected, minimum_sentence_length=3)

    def test_basic(self):
        text = "This is a test. This is another test sentence. Just testing out the module."
        expected = ["This is a test.", "This is another test sentence.", "Just testing out the module."]
        self.assertGeneratedSentences(text, expected)

    def test_tricky_sentence1(self):
        text = "Good muffins cost $3.88 in New York. Please buy me two of them."
        expected = ["Good muffins cost $3.88 in New York.", "Please buy me two of them."]
        self.assertGeneratedSentences(text, expected)

    def test_tricky_sentence2(self):
        text = "I called Dr. Jones. I called Dr. Jones."
        expected = ["I called Dr. Jones.", "I called Dr. Jones."]
        self.assertGeneratedSentences(text, expected)

    def test_quick_yield(self):
        text = "First, this. Second, this."
        expected = ["First,", "this.", "Second, this."]
        self.assertGeneratedSentences(
            text,
            expected,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=3,
            minimum_first_fragment_length=3,
        )

    def test_quick_yield2(self):
        text = "First, this. Second, this."
        expected = ["First,", "this. Second, this."]
        self.assertGeneratedSentences(
            text,
            expected,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=6,
            minimum_first_fragment_length=3,
        )

    def test_quick_yield3(self):
        text = "First, this. Second, this."
        expected = ["First, this.", "Second, this."]
        self.assertGeneratedSentences(
            text,
            expected,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=3,
            minimum_first_fragment_length=6,
        )

    def test_quick_yield4(self):
        text = "First, this. Second, this."
        expected = ["First, this.", "Second, this."]
        self.assertGeneratedSentences(
            text,
            expected,
            quick_yield_single_sentence_fragment=True,
            minimum_sentence_length=6,
            minimum_first_fragment_length=6,
        )

    def test_quick_yield_does_not_split_decimal_price(self):
        text = "The price for Pure Leaf Sweet Tea is $3.5 for small size and $5 for large size."
        expected = ["The price for Pure Leaf Sweet Tea is $3.5 for small size and $5 for large size."]
        self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_does_not_split_decimal_amount(self):
        text = "Good muffins cost $3.88 in New York. Please buy me two of them."
        expected = ["Good muffins cost $3.88 in New York.", "Please buy me two of them."]
        self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_does_not_split_time(self):
        text = "Meet me at 10:30, okay?"
        expected = ["Meet me at 10:30, okay?"]
        self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_does_not_split_currency_amounts(self):
        cases = [
            "The price is $3.50 today.",
            "The price is $1,250 today.",
            "The price is \u20ac3.50 today.",
            "The price is 3,50 \u20ac today.",
            "The price is \u00a312.99 today.",
            "The price is \u00a51,250 today.",
            "The price is CHF 12.90 today.",
            "The price is 12.90 USD today.",
            "The refund is -$3.50 today.",
            "The discount is 12.5% today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_numeric_formats(self):
        cases = [
            "The value is 1,234,567 units today.",
            "The ratio is 3.14159 in the report.",
            "The date is 2024-04-15 in the report.",
            "The date is 04.15.2024 in the report.",
            "The meeting runs 10:30-11:30 tomorrow.",
            "The range is 9-10 units today.",
            "The score was 3:2 after overtime.",
            "The identifier is 123-456-789 in the report.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_bare_integer_periods(self):
        cases = [
            "The plan includes step 1. setup before step 2. train today.",
            "The chess line is 1. d4 Nf6 2. c4 e6 3. Nc3 Bb4+ today.",
            "The score was 3. Next month it improved.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text, never_split_numbers=True)

    def test_quick_yield_uses_default_numeric_period_policy(self):
        text = "The score was 3. Next month it improved."
        expected = ["The score was 3.", "Next month it improved."]
        self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_does_not_split_technical_tokens(self):
        cases = [
            "Version v2.0.1 is available now.",
            "Connect to 192.168.0.1 before testing.",
            "Open config.json before restarting.",
            "Visit example.com before checkout.",
            "Email support@example.com before noon.",
            "The package is stream2sentence-0.3.2 today.",
            "The model is gpt-4.1-mini in config.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_domain_names(self):
        cases = [
            "Visit example.com before checkout.",
            "Open docs.python.org before editing.",
            "Use api.example.co.uk for staging.",
            "Ping status.my-service.internal before deploy.",
            "Check my-service.dev.local before release.",
            "Read developer.mozilla.org for details.",
            "Use cdn.assets.example.net before launch.",
            "The host is auth.eu-west-1.example.com today.",
            "The domain is example.travel today.",
            "The service is foo.bar.baz.internal today.",
            "The hostname is db-01.prod.local today.",
            "The endpoint is checkout.service.cluster.local today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_urls(self):
        cases = [
            "Open https://example.com before checkout.",
            "Open https://api.example.com/v1/users before checkout.",
            "Open https://docs.example.com/v2.0/api#section-3 before checkout.",
            "Open https://example.com/search?q=version%201.2.3 before checkout.",
            "Call http://127.0.0.1:8000/health before deploy.",
            "Call ws://localhost:8080/socket before deploy.",
            "Call wss://api.example.com/v1/stream before deploy.",
            "Use s3://bucket-name/releases/v1.2.3/file.zip today.",
            "Use git+ssh://git@example.com/org/repo.git today.",
            "Use postgres://user:pass@db.example.com:5432/app today.",
            "Use file:///C:/Users/Start/config.json today.",
            "Open https://example.com/path/file-1.2.3.tar.gz today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_email_addresses(self):
        cases = [
            "Email support@example.com before noon.",
            "Email first.last@example.com before noon.",
            "Email name+tag@example.co.uk before noon.",
            "Email service-account@sub.domain.io before noon.",
            "Email build.bot+ci@example.dev before noon.",
            "Email alerts_123@example-monitoring.local before noon.",
            "Email ops-team@eu-west-1.example.com before noon.",
            "Email release.2024.04@example.org before noon.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_version_numbers(self):
        cases = [
            "Version v2.0.1 is available now.",
            "Version 1.0.0-beta.1 is available now.",
            "Version 2024.04.15 is available now.",
            "Python 3.11.9 is installed today.",
            "CUDA 12.4 is installed today.",
            "The runtime is .NET 8.0 today.",
            "Node.js 20.11.1 is installed today.",
            "OpenSSL 3.2.1 is installed today.",
            "PostgreSQL 16.2 is installed today.",
            "glibc 2.39 is installed today.",
            "The migration is schema-v12.3.4 today.",
            "The release is 0.3.2.post1 today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_file_names_and_paths(self):
        cases = [
            "Open config.prod.json before restarting.",
            "Open app.module.tsx before building.",
            "Download archive.tar.gz before installing.",
            "Check requirements-dev.txt before installing.",
            "Read pyproject.toml before packaging.",
            "Load package-lock.json before npm install.",
            "Import scope-package-name today.",
            "Use stream2sentence-0.3.2 today.",
            "Open C:\\Users\\Start\\config.json before restarting.",
            "Open /opt/app/v1.2/config.yaml before restarting.",
            "Read src/components/Button.test.tsx before merge.",
            "Load dist/app.min.js before upload.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_network_identifiers(self):
        cases = [
            "Connect to 192.168.0.1 before testing.",
            "Open 127.0.0.1:8000 before testing.",
            "Use 10.0.0.5/24 for the subnet.",
            "Connect to [2001:db8::1]:443 before testing.",
            "The IPv6 address is fe80::1ff:fe23:4567:890a today.",
            "The MAC address is aa:bb:cc:dd:ee:ff today.",
            "The container listens on 0.0.0.0:8080 today.",
            "The host is db-01.prod.local today.",
            "The CIDR block is 172.16.0.0/12 today.",
            "The service address is redis://cache.local:6379 today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_command_tokens(self):
        cases = [
            "Run python -m pytest before merging.",
            "Use --model=gpt-4.1-mini for the run.",
            "Set DATABASE_URL=postgres://user:pass@db:5432/app before launch.",
            "Pass --retry-count=3 before launch.",
            "Use --output=dist/app.min.js before upload.",
            "Run npm install scope-package-name before build.",
            "Run git checkout feature/splitter-v2.0 before testing.",
            "Run docker.io/library/python:3.11-slim today.",
            "Set image=ghcr.io/org/app:v1.2.3 before deploy.",
            "Run pytest tests/test_stream2sentence.py::TestSentenceGenerator today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_release_and_cloud_identifiers(self):
        cases = [
            "The issue is PROJ-1234 today.",
            "The tag is release-2024.04.15 today.",
            "The build is 2024-04-15T10:30:00Z today.",
            "The digest is sha256:abc123.def456 today.",
            "The image is ghcr.io/org/app:v1.2.3 today.",
            "The ARN is arn:aws:s3:::bucket-name today.",
            "The region is eu-west-1 today.",
            "The zone is us-central1-a today.",
            "The bucket is logs-prod-2024.04.15 today.",
            "The job is ingest-v2.0.1-rc.3 today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_does_not_split_abbreviations(self):
        cases = [
            "I called Dr. Smith today.",
            "The meeting is at 3 p.m. tomorrow.",
            "The launch is at 3:22 p.m. EDT today.",
            "The call starts at 9:00 a.m. PST tomorrow.",
            "Use e.g. apples in the list.",
            "Smith et al. reported the result.",
            "See op. cit. for details.",
            "The value is ca. 10 today.",
            "The match is Team A vs. Team B tonight.",
            "See Fig. 2 in the paper.",
            "The office is on St. Patrick Avenue today.",
            "The company is Acme Inc. today.",
            "The U.S. Bureau responded today.",
            "The U.S. Constitution matters today.",
            "The U.S. Environmental Protection Agency responded today.",
            "The U.S. Endangered Species Act applies today.",
            "The U.S. Food and Drug Administration issued guidance today.",
            "The U.S. East Coast braced for rain today.",
            "The U.S. Marines arrived today.",
            "The U.S. Memory Championships started today.",
            "The U.S. Minerals Management Service responded today.",
            "The U.S. Securities and Exchange Commission responded today.",
            "The U.S. Vice President spoke today.",
            "U.N. Secretary-General Antonio Guterres spoke today.",
            "The U.N. Children\u2019s Fund responded today.",
            "The U.N. High Commissioner for Human Rights spoke today.",
            "The U.N. Atlas of the Oceans lists coastal cities today.",
            "A. Karpov vs. B. Spassky played today.",
            "A. Karpov won the match today.",
            "The meeting is at 3 p.m. Monday.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_preserves_closing_marks(self):
        cases = [
            ('"Hello." Next.', ['"Hello."', "Next."]),
            ('"Hello!" Next.', ['"Hello!"', "Next."]),
            ('"Hello?" Next.', ['"Hello?"', "Next."]),
            ('"Really)." Next.', ['"Really)."', "Next."]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_keeps_lowercase_continuations_after_closing_marks(self):
        cases = [
            'The status label "Ready." stayed visible during the demo.',
            'Maya asked "done?" before the timer started.',
            'The checklist item {ready.} stayed visible until noon.',
            'The checklist item (done.) stayed visible until noon.',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_keeps_comma_continuation_after_question_mark(self):
        cases = [
            "The headline mentioned Guess?, and the editor left it unchanged.",
            '"Really?", she asked before leaving.',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_quick_yield_splits_after_terminal_punctuation_clusters(self):
        cases = [
            ("Wait?! Next.", ["Wait?!", "Next."]),
            ('"Wait?!" Next.', ['"Wait?!"', "Next."]),
            ("Stop!! Next.", ["Stop!!", "Next."]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSentences(text, expected)

    def test_quick_yield_abbreviation_sentence_boundaries(self):
        cases = [
            (
                "The U.S. Army arrived today. It stayed.",
                ["The U.S. Army arrived today.", "It stayed."],
            ),
            (
                "He lives in the U.S. It is large.",
                ["He lives in the U.S.", "It is large."],
            ),
            (
                "Smith et al. reported the result. It held.",
                ["Smith et al. reported the result.", "It held."],
            ),
            (
                "See op. cit. for details. Continue.",
                ["See op. cit. for details.", "Continue."],
            ),
            (
                "The value is ca. 10 today. Continue.",
                ["The value is ca. 10 today.", "Continue."],
            ),
            (
                "The answer is A. Then it changed.",
                ["The answer is A.", "Then it changed."],
            ),
            (
                "John is as old as I. Tom disagreed.",
                ["John is as old as I.", "Tom disagreed."],
            ),
            (
                "He likes traveling and so do I. Long trips are fun.",
                ["He likes traveling and so do I.", "Long trips are fun."],
            ),
            (
                "A. Karpov won the match today.",
                ["A. Karpov won the match today."],
            ),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                sentences = list(generate_sentences(
                    text,
                    quick_yield_single_sentence_fragment=True,
                    minimum_sentence_length=1,
                    minimum_first_fragment_length=1,
                    tokenizer="rule-based",
                    language="en",
                ))
                self.assertEqual(sentences, expected)

    def test_nltk_tokenizer_uses_nltk_sent_tokenize(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_tokenizer = stream2sentence_module.current_tokenizer
        old_language = stream2sentence_module.current_language

        try:
            stream2sentence_module.current_tokenizer = "nltk"
            stream2sentence_module.current_language = "en"
            with mock.patch.object(
                stream2sentence_module,
                "_rule_based_tokenize_sentences",
                side_effect=AssertionError("nltk tokenizer must not use rule-based tokenizer"),
            ):
                with mock.patch(
                    "nltk.tokenize.sent_tokenize",
                    return_value=["One.", "Two."],
                ) as sent_tokenize:
                    self.assertEqual(
                        stream2sentence_module._tokenize_sentences("One. Two."),
                        ["One.", "Two."],
                    )
                    sent_tokenize.assert_called_once_with("One. Two.")
        finally:
            stream2sentence_module.current_tokenizer = old_tokenizer
            stream2sentence_module.current_language = old_language

    def test_rule_based_tokenizer_uses_rule_based_sentences(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_tokenizer = stream2sentence_module.current_tokenizer
        old_language = stream2sentence_module.current_language

        try:
            stream2sentence_module.current_tokenizer = "rule-based"
            stream2sentence_module.current_language = "en"
            with mock.patch(
                "nltk.tokenize.sent_tokenize",
                side_effect=AssertionError("rule-based tokenizer must not use NLTK"),
            ):
                with mock.patch.object(
                    stream2sentence_module,
                    "_rule_based_tokenize_sentences",
                    return_value=["One.", "Two."],
                ) as rule_based_tokenize:
                    self.assertEqual(
                        stream2sentence_module._tokenize_sentences("One. Two."),
                        ["One.", "Two."],
                    )
                    rule_based_tokenize.assert_called_once_with(
                        "One. Two.",
                        "en",
                        never_split_numbers=False,
                    )
        finally:
            stream2sentence_module.current_tokenizer = old_tokenizer
            stream2sentence_module.current_language = old_language

    def test_consensus_tokenizer_requires_nltk_and_rule_based_agreement(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        text = "One. Two."

        with mock.patch(
            "nltk.tokenize.sent_tokenize",
            return_value=["One. Two."],
        ) as sent_tokenize:
            with mock.patch.object(
                stream2sentence_module,
                "_rule_based_tokenize_sentences",
                return_value=["One.", "Two."],
            ) as rule_based_tokenize:
                self.assertEqual(
                    stream2sentence_module._tokenize_sentences(
                        text,
                        tokenizer="nltk+rule-based",
                        language="en",
                    ),
                    ["One. Two."],
                )
                sent_tokenize.assert_called_once_with(text)
                rule_based_tokenize.assert_called_once_with(
                    text,
                    "en",
                    never_split_numbers=False,
                )

    def test_consensus_tokenizer_keeps_shared_boundaries(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        text = "One. Two. Three."

        with mock.patch(
            "nltk.tokenize.sent_tokenize",
            return_value=["One.", "Two. Three."],
        ):
            with mock.patch.object(
                stream2sentence_module,
                "_rule_based_tokenize_sentences",
                return_value=["One.", "Two.", "Three."],
            ):
                self.assertEqual(
                    stream2sentence_module._tokenize_sentences(
                        text,
                        tokenizer="consensus",
                        language="en",
                    ),
                    ["One.", "Two. Three."],
                )

    def test_consensus_tokenizer_handles_punctuation_heavy_char_stream(self):
        self.assertEqual(
            list(generate_sentences(
                list(CONSENSUS_STRESS_INPUT),
                tokenizer="nltk+rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=12,
                context_size_look_overhead=64,
            )),
            CONSENSUS_STRESS_EXPECTED,
        )

    def test_auto_context_yields_before_fixed_context_window(self):
        splitter = SentenceSplitter(
            tokenizer="rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=12,
            auto_context=True,
        )

        yielded = []
        for char in "Hello world. N":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(yielded, ["Hello world."])
        self.assertEqual(splitter.buffer, "N")

    def test_auto_context_disabled_keeps_fixed_context_window(self):
        splitter = SentenceSplitter(
            tokenizer="rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=12,
            auto_context=False,
        )

        yielded = []
        for char in "Hello world. N":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(yielded, [])
        self.assertEqual(splitter.buffer, "Hello world. N")

    def test_auto_context_requires_consensus_tokenizer_agreement(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_nltk_initialized = stream2sentence_module.nltk_initialized
        stream2sentence_module.nltk_initialized = True
        try:
            splitter = SentenceSplitter(
                tokenizer="nltk+rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=12,
                context_size_look_overhead=12,
                auto_context=True,
            )
            with mock.patch(
                "nltk.tokenize.sent_tokenize",
                return_value=["Hello world. N"],
            ):
                yielded = []
                for char in "Hello world. N":
                    splitter.add(char)
                    yielded.extend(splitter.stream())

            self.assertEqual(yielded, [])
            self.assertEqual(splitter.buffer, "Hello world. N")
        finally:
            stream2sentence_module.nltk_initialized = old_nltk_initialized

    def test_auto_context_yields_when_consensus_tokenizer_agrees(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_nltk_initialized = stream2sentence_module.nltk_initialized
        stream2sentence_module.nltk_initialized = True
        try:
            splitter = SentenceSplitter(
                tokenizer="nltk+rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=12,
                context_size_look_overhead=12,
                auto_context=True,
            )
            with mock.patch(
                "nltk.tokenize.sent_tokenize",
                return_value=["Hello world.", "N"],
            ):
                yielded = []
                for char in "Hello world. N":
                    splitter.add(char)
                    yielded.extend(splitter.stream())

            self.assertEqual(yielded, ["Hello world."])
            self.assertEqual(splitter.buffer, "N")
        finally:
            stream2sentence_module.nltk_initialized = old_nltk_initialized

    def test_auto_context_requires_boundary_detector_split(self):
        splitter = SentenceSplitter(
            tokenize_sentences=lambda text: ["I met Dr.", "S"],
            tokenizer="rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=12,
            auto_context=True,
        )

        yielded = []
        for char in "I met Dr. S":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(yielded, [])
        self.assertEqual(splitter.buffer, "I met Dr. S")

    def test_auto_context_holds_known_initialism_continuation_words(self):
        cases = [
            (
                "The U.N. Development Programme responded today.",
                "The U.N. Development ",
            ),
            (
                "The U.N. Security Council met today.",
                "The U.N. Security ",
            ),
            (
                "The U.N. Secretariat issued a statement today.",
                "The U.N. Secretariat ",
            ),
            (
                "The U.N. Framework Convention remains in force today.",
                "The U.N. Framework ",
            ),
            (
                "The U.N. Economic and Social Council met today.",
                "The U.N. Economic ",
            ),
            (
                "The U.N. Relief and Works Agency responded today.",
                "The U.N. Relief ",
            ),
            (
                "The U.S. Supreme Court ruled today.",
                "The U.S. Supreme ",
            ),
            (
                "The U.S. Capitol Police responded today.",
                "The U.S. Capitol ",
            ),
            (
                "The U.S. Civil War changed the country today.",
                "The U.S. Civil ",
            ),
            (
                "The U.S. Olympic Committee released the roster today.",
                "The U.S. Olympic ",
            ),
            (
                "The U.S. Olympic team won today.",
                "The U.S. Olympic ",
            ),
            (
                "The U.S. Open begins Monday.",
                "The U.S. Open ",
            ),
            (
                "The U.S. Naval Academy admitted new midshipmen today.",
                "The U.S. Naval ",
            ),
            (
                "The U.S. Tax Court issued an opinion today.",
                "The U.S. Tax ",
            ),
            (
                "The U.S. Fish and Wildlife Service announced a rule today.",
                "The U.S. Fish ",
            ),
            (
                "The U.S. Forest Service closed the trail today.",
                "The U.S. Forest ",
            ),
            (
                "The U.S. Secret Service investigated the incident today.",
                "The U.S. Secret ",
            ),
            (
                "The U.S. Virgin Islands reported the result today.",
                "The U.S. Virgin ",
            ),
            (
                "The U.S. Women's national team won today.",
                "The U.S. Women's ",
            ),
            (
                "The U.S. Soccer team will play today.",
                "The U.S. Soccer ",
            ),
            (
                "The U.S. Botanic Garden opened today.",
                "The U.S. Botanic ",
            ),
            (
                "Members of the U.S. House of Representatives are elected today.",
                "Members of the U.S. House ",
            ),
            (
                "The U.S. Marine Corps deployed today.",
                "The U.S. Marine ",
            ),
            (
                "The U.S. State Department responded today.",
                "The U.S. State ",
            ),
            (
                "The U.S. Republican Party changed its platform today.",
                "The U.S. Republican ",
            ),
            (
                "The E.U. Commission responded today.",
                "The E.U. Commission ",
            ),
            (
                "The E.U. Digital Markets Act applies today.",
                "The E.U. Digital ",
            ),
            (
                "The E.U. AI Act passed today.",
                "The E.U. AI ",
            ),
            (
                "The E.U. General Data Protection Regulation applies today.",
                "The E.U. General ",
            ),
            (
                "The U.K. Prime Minister spoke today.",
                "The U.K. Prime ",
            ),
            (
                "The U.K. Foreign Office responded today.",
                "The U.K. Foreign ",
            ),
            (
                "The U.K. Home Office issued guidance today.",
                "The U.K. Home ",
            ),
            (
                "The D.C. Circuit ruled today.",
                "The D.C. Circuit ",
            ),
            (
                "The D.C. Council voted today.",
                "The D.C. Council ",
            ),
        ]

        for text, prefix in cases:
            with self.subTest(text=text):
                splitter = SentenceSplitter(
                    tokenizer="rule-based",
                    language="en",
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in prefix:
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, [])
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer="rule-based",
                        language="en",
                        minimum_sentence_length=1,
                        context_size=1,
                        context_size_look_overhead=128,
                        auto_context=True,
                    )),
                    [text],
                )

    def test_auto_context_splits_after_initialisms_before_unlisted_words(self):
        cases = [
            (
                "He lives in the U.S. It is large.",
                "He lives in the U.S. It ",
                ["He lives in the U.S."],
                "It ",
            ),
            (
                "The report mentions the E.U. It changed.",
                "The report mentions the E.U. It ",
                ["The report mentions the E.U."],
                "It ",
            ),
            (
                "She moved to the U.K. It rained.",
                "She moved to the U.K. It ",
                ["She moved to the U.K."],
                "It ",
            ),
            (
                "The office is in D.C. It closed.",
                "The office is in D.C. It ",
                ["The office is in D.C."],
                "It ",
            ),
        ]

        for text, prefix, expected_yielded, expected_buffer in cases:
            with self.subTest(text=text):
                splitter = SentenceSplitter(
                    tokenizer="rule-based",
                    language="en",
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in prefix:
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, expected_yielded)
                self.assertEqual(splitter.buffer, expected_buffer)

    def test_auto_context_holds_time_abbreviation_continuations(self):
        cases = [
            (
                "The call starts at 9:00 a.m. ET tomorrow.",
                "The call starts at 9:00 a.m. ET ",
            ),
            (
                "The call starts at 9:00 a.m. Eastern time tomorrow.",
                "The call starts at 9:00 a.m. Eastern ",
            ),
            (
                "The call starts at 9:00 a.m. UTC+2 tomorrow.",
                "The call starts at 9:00 a.m. UTC+2 ",
            ),
            (
                "Meet at 7 p.m. Mumbai time.",
                "Meet at 7 p.m. Mumbai t",
            ),
            (
                "Meet at 7 p.m. Buenos Aires time.",
                "Meet at 7 p.m. Buenos Aires ",
            ),
            (
                "At 7 p.m. I have dinner with my family.",
                "At 7 p.m. I ",
            ),
            (
                "At 7 p.m. Tom has dinner with his family.",
                "At 7 p.m. Tom ",
            ),
        ]

        for text, prefix in cases:
            with self.subTest(text=text):
                splitter = SentenceSplitter(
                    tokenizer="rule-based",
                    language="en",
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in prefix:
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, [])
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer="rule-based",
                        language="en",
                        minimum_sentence_length=1,
                        context_size=1,
                        context_size_look_overhead=128,
                        auto_context=True,
                    )),
                    [text],
                )

    def test_auto_context_splits_time_abbreviation_before_sentence_starter(self):
        text = "The meeting ended at 7 p.m. The room emptied."
        splitter = SentenceSplitter(
            tokenizer="rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=1,
            context_size_look_overhead=128,
            auto_context=True,
        )

        yielded = []
        for char in "The meeting ended at 7 p.m. The ":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(yielded, ["The meeting ended at 7 p.m."])
        self.assertEqual(splitter.buffer, "The ")
        self.assertEqual(
            list(generate_sentences(
                list(text),
                tokenizer="rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=1,
                context_size_look_overhead=128,
                auto_context=True,
            )),
            ["The meeting ended at 7 p.m.", "The room emptied."],
        )

    def test_auto_context_holds_reference_label_continuations(self):
        cases = [
            (
                "See Fig. S1 in the supplement today.",
                "See Fig. S1 ",
            ),
            (
                "See Art. IV in the Constitution today.",
                "See Art. IV ",
            ),
            (
                "The sample is No. IV in the catalog today.",
                "The sample is No. IV ",
            ),
        ]

        for text, prefix in cases:
            with self.subTest(text=text):
                splitter = SentenceSplitter(
                    tokenizer="rule-based",
                    language="en",
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in prefix:
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, [])
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer="rule-based",
                        language="en",
                        minimum_sentence_length=1,
                        context_size=1,
                        context_size_look_overhead=128,
                        auto_context=True,
                    )),
                    [text],
                )

    def test_auto_context_holds_punctuated_name_continuations(self):
        cases = [
            (
                "E! News aired the segment today.",
                "E! News ",
            ),
            (
                "Yahoo! Sports published the story today.",
                "Yahoo! Sports ",
            ),
            (
                "OK! Magazine published the interview today.",
                "OK! Magazine ",
            ),
            (
                "Guess? Inc. reported earnings today.",
                "Guess? Inc. ",
            ),
        ]

        for text, prefix in cases:
            with self.subTest(text=text):
                splitter = SentenceSplitter(
                    tokenizer="rule-based",
                    language="en",
                    minimum_sentence_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in prefix:
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, [])
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer="rule-based",
                        language="en",
                        minimum_sentence_length=1,
                        context_size=1,
                        context_size_look_overhead=128,
                        auto_context=True,
                    )),
                    [text],
                )

    def test_auto_context_holds_retained_local_false_positive_cases(self):
        cases_by_family = {
            "title and rank abbreviations": """
                Hon. Smith spoke.
                Supt. Chalmers arrived.
                Pfc. Davis reported.
                Spec. Brown testified.
                Sfc. Miller briefed them.
                Fr. Brown entered.
                Br. Andrew replied.
                Mx. Taylor signed.
                Mgr. Lefebvre presided.
                Comm. Smith objected.
                Adj. Grant arrived.
                Pfc. Johnson saluted.
                Spec. Lee answered.
                Sfc. Garcia arrived.
                Hon. Justice Clark dissented.
            """,
            "lowercase styled initials": """
                e. e. cummings wrote.
                k. d. lang sang.
                p. j. harvey performed.
                m. ward played.
            """,
            "u.s. initialism continuations": """
                U.S. Bank closed.
                U.S. Steel reopened.
                U.S. Cellular expanded.
                U.S. News aired.
                U.S. Airways returned.
                U.S. Bancorp rose.
                U.S. Chamber replied.
                U.S. Figure Skating qualified.
                U.S. Ski trained.
                U.S. Rowing qualified.
                U.S. Cycling qualified.
                U.S. Track qualified.
                U.S. Anti-Doping Agency appealed.
                U.S. Holocaust Memorial Museum opened.
                U.S. Strategic Command responded.
                U.S. Central Command responded.
                U.S. Cyber Command responded.
                U.S. International Trade Commission ruled.
                U.S. Consumer Product Safety Commission warned.
                The U.S. West Coast is rainy.
                The U.S. Small Business Administration replied.
                The U.S. Library of Congress replied.
            """,
            "u.n. initialism continuations": """
                U.N. Women replied.
                U.N. Habitat reported.
                U.N. Global Compact replied.
                U.N. Water reported.
                U.N. Volunteers expanded.
                U.N. University enrolled students.
                U.N. Treaty Series changed.
                U.N. Convention changed.
                U.N. Protocol entered force.
                U.N. Office on Drugs and Crime responded.
                U.N. Migration Network met.
                U.N. Global Pulse responded.
                The U.N. International Center reopened.
                The U.N. International Court ruled.
                The U.N. Conference resumed.
                The U.N. Commission reported.
                The U.N. Peacebuilding Commission met.
                The U.N. Disarmament Commission met.
                The U.N. Statistical Commission met.
                The U.N. Permanent Forum opened.
                The U.N. Forum on Forests met.
                The U.N. Appeals Tribunal ruled.
                The U.N. Administrative Tribunal ruled.
                The U.N. Trusteeship Council adjourned.
            """,
            "u.k. initialism continuations": """
                U.K. Finance reported.
                U.K. Biobank expanded.
                U.K. Statistics Authority responded.
                U.K. Research and Innovation met.
                U.K. Competition and Markets Authority ruled.
                U.K. Health Security Agency warned.
                U.K. Space Agency replied.
                U.K. Export Finance replied.
                U.K. Intellectual Property Office replied.
                The U.K. Civil Service responded.
                The U.K. Border Force responded.
                The U.K. Crown Court ruled.
                The U.K. Ministry of Defence replied.
                The U.K. Office for National Statistics replied.
                The U.K. Financial Conduct Authority fined it.
                The U.K. Atomic Energy Authority replied.
                The U.K. Infrastructure Bank invested.
            """,
            "e.u. initialism continuations": """
                E.U. Taxonomy applies.
                E.U. Chips Act passed.
                E.U. Emissions Trading System expanded.
                E.U. Merger Regulation applies.
                E.U. Delegation reopened.
                E.U. Ombudsman reported.
                E.U. Agency reviewed it.
                E.U. Data Act entered force.
                E.U. Cyber Resilience Act passed.
                E.U. Battery Regulation applies.
                The E.U. Space Programme expanded.
                The E.U. Drug Agency warned.
                The E.U. Aviation Safety Agency replied.
                The E.U. Banking Authority warned.
                The E.U. Securities Authority warned.
                The E.U. Insurance Authority warned.
                The E.U. Border Agency replied.
                The E.U. Foreign Affairs Council met.
                The E.U. Fundamental Rights Agency replied.
            """,
            "d.c. initialism continuations": """
                D.C. Bar replied.
                D.C. Police reported.
                D.C. Superior Court ruled.
                D.C. Metro met.
                D.C. Housing Authority replied.
                D.C. Water warned.
                D.C. Health Department warned.
                The D.C. Fire Department responded.
                The D.C. Court of Appeals ruled.
                The D.C. Library reopened.
                The D.C. Lottery reported.
                The D.C. Jail closed.
            """,
            "time abbreviation continuations": """
                Meet at 7 p.m. Berlin time.
                Meet at 7 p.m. New York time.
                Meet at 7 p.m. London time.
                Meet at 7 p.m. Tokyo time.
                Meet at 7 p.m. Singapore time.
                Meet at 7 p.m. Sydney time.
                Meet at 7 p.m. Los Angeles time.
                Meet at 7 p.m. Jan. 3.
                Meet at 7 p.m. Feb. 4.
                Meet at 7 p.m. Mar. 5.
                Meet at 7 p.m. Apr. 6.
                Meet at 7 p.m. Sept. 7.
                Meet at 7 p.m. Oct. 8.
                Meet at 7 p.m. Nov. 9.
                Meet at 7 p.m. Dec. 10.
            """,
            "formal reference labels": """
                See Tbl. S1.
                See Tbls. S1.
                See Tab. S1.
                See Tabs. S1.
                See App. A.
                See Apps. A.
                See Supp. A.
                See Suppl. S1.
                See Exh. A.
                See Exhs. A.
                See Sch. A.
                See Sched. A.
                See Pt. IV.
                See Pts. IV.
                See Para. A.
                See Paras. A.
                See Subsec. A.
                See Subsecs. A.
                See Reg. A-7.
                See Regs. A-7.
                See Stat. A.
                See Stats. A.
                See Alg. S1.
                See Thm. IV.
                See Prop. A.
                See Cor. A.
                See Lem. A.
                See Defn. A.
                See Obs. A.
                See Rem. A.
                See Hyp. A.
                See Prob. A.
                See p. S5.
                See Ex. A.
            """,
            "initials before surname particles": """
                L. van Beethoven arrived.
                J. de Vries arrived.
                C. du Pont arrived.
                A. von Humboldt arrived.
                M. de la Cruz arrived.
                V. de Souza arrived.
                J. da Silva arrived.
                G. di Lorenzo arrived.
                N. al-Khatib arrived.
                R. del Toro arrived.
                S. dos Santos arrived.
                T. de Jong arrived.
                H. van Dyke arrived.
            """,
            "punctuated brands and titles": """
                Yahoo! Japan posted.
                Yahoo! Answers archived it.
                Yahoo! Auctions listed it.
                Yahoo! Weather updated it.
                Yahoo! Fantasy opened.
                E! Online published it.
                E! True Hollywood Story aired.
                E! Red Carpet aired.
                OK! UK published it.
                OK! Australia published it.
                Jeopardy! Tournament of Champions aired.
                Jeopardy! National College Championship aired.
                Jeopardy! The Greatest of All Time aired.
                Guess? Jeans opened.
                Guess? Originals launched.
                Yahoo! Inc. reported.
                Yahoo! Life published it.
                Yahoo! Entertainment posted it.
                Yahoo! Tech reviewed it.
                Yahoo! Movies listed it.
                Yahoo! Search indexed it.
                Yahoo! Messenger closed.
                Yahoo! Groups archived it.
                Yahoo! Directory listed it.
                E! Insider aired it.
                E! Live aired it.
                Jeopardy! Invitational Tournament aired.
                Jeopardy! College Championship aired.
                Jeopardy! Teen Tournament aired.
                Jeopardy! Kids Week aired.
                Guess? Kids opened.
                Guess? Factory opened.
                Guess? Watches launched.
            """,
            "scientific and taxonomic abbreviations": """
                The sample was E. coli var. K-12.
                The isolate was Bacillus sp. ATCC 6051.
                The report lists Quercus spp. Q1.
                The key lists Rosa sect. Caninae.
                The catalog lists Drosophila subg. Sophophora.
                The note marks Candida ser. A.
                The isolate was E. coli str. K-12.
            """,
            "company suffix continuations": """
                Acme LLC. CEO resigned.
                Acme LLP. Partner testified.
                Acme PLC. Board approved it.
                Acme Pty. Ltd. CEO resigned.
                Acme GmbH. Director resigned.
            """,
            "weekday date continuations": """
                Meet Sun. Jan. 3.
                Meet Wed. Jan. 6.
            """,
            "legal reporter citations": """
                Cite 123 F. Supp. 2d 456.
                Cite 123 F. Supp. 3d 456.
                Cite 123 Fed. Appx. 456.
                Cite 123 Cal. App. 5th 456.
                Cite 123 N.Y. App. Div. 456.
                Cite 123 Cal. Rptr. 3d 456.
                Cite 123 Mass. App. Ct. 456.
                Cite 123 Ill. App. 3d 456.
                Cite 123 So. 2d 456.
                Cite 123 A. 2d 456.
                Cite 123 U.S. Dist. LEXIS 456.
                Cite 123 N.Y. Misc. 456.
            """,
            "legal rule and statute citation chains": """
                See Fed. R. Civ. P. 56 today.
                See Fed. R. Evid. 403 today.
                See U.S. Const. amend. XIV today.
                See Pub. L. No. 117-2 today.
                See Cal. Code Civ. Proc. \u00a7 425.16 today.
                See Tex. R. Civ. P. 91a today.
                See Va. Code \u00a7 8.01-243 today.
                See W. Va. Code \u00a7 55-2-12 today.
                See 88 Fed. Reg. 12345 today.
                See 17 C.F.R. pt. 240 today.
                See Rest. 2d Torts \u00a7 402A today.
                See Model Bus. Corp. Act \u00a7 8.30 today.
            """,
            "state legal and government continuations": """
                The Mass. Appeals Court ruled today.
                The Calif. Supreme Court ruled today.
                The Va. State Corporation Commission responded.
                The Miss. Supreme Court ruled today.
                The W. Va. Supreme Court ruled today.
            """,
            "title and office abbreviation chains": """
                Asst. Prof. Smith spoke.
                Asst. U.S. Atty. Rivera filed it.
                Acting Asst. Sec. Taylor testified.
                Dist. Atty. Reyes filed it.
                Admin. Asst. Rivera answered.
            """,
            "place prefix continuations": """
                Pt. Reyes is foggy today.
                Pt. Lookout reopened today.
                Ft. Lauderdale is sunny today.
                Ft. Collins voted today.
                Sts. Peter and Paul opened today.
            """,
            "new exact initialism continuations": """
                U.S.A. Swimming announced the roster.
                U.S.A. Gymnastics replied today.
                U.N. Environmental Programme warned today.
                U.N. Educational Organization responded.
                E.U. Green Deal passed today.
                E.U. Carbon Border Adjustment Mechanism applied today.
            """,
            "report labels and measured values": """
                The est. 5 cases remain open.
                The est. $5 million cost was approved.
                The temp. 37 C reading was recorded.
                See Eqn. S1 today.
                See Appxs. A-C today.
                See Assumps. A-B today.
                See Aux. Fig. S1 today.
            """,
            "company suffix chains": """
                Acme Pte. Ltd. filed today.
                Acme Sdn. Bhd. filed today.
            """,
        }

        for family, block in cases_by_family.items():
            cases = [line.strip() for line in block.splitlines() if line.strip()]
            for text in cases:
                with self.subTest(family=family, text=text):
                    self.assertAutoContextSentences(text, [text])

    def test_auto_context_generalized_edge_case_families_for_rule_tokenizers(self):
        cases_by_family = {
            "legal citation chains": [
                "See Fed. R. Civ. P. 56 today.",
                "See U.S. Const. amend. XIV today.",
                "See Va. Code \u00a7 8.01-243 today.",
                "See Model Bus. Corp. Act \u00a7 8.30 today.",
            ],
            "state and place continuations": [
                "The Miss. Supreme Court ruled today.",
                "The W. Va. Supreme Court ruled today.",
                "Ft. Lauderdale is sunny today.",
                "Sts. Peter and Paul opened today.",
            ],
            "title and company chains": [
                "Asst. U.S. Atty. Rivera filed it.",
                "Admin. Asst. Rivera answered.",
                "Acme Pte. Ltd. filed today.",
                "Acme Inc. CEO resigned.",
            ],
            "formal labels and initialisms": [
                "The est. $5 million cost was approved.",
                "See Appxs. A-C today.",
                "U.N. Environmental Programme warned today.",
                "E.U. Carbon Border Adjustment Mechanism applied today.",
            ],
        }

        for family, cases in cases_by_family.items():
            for text in cases:
                with self.subTest(family=family, text=text):
                    self.assertAutoContextSentencesForBoundaryTokenizers(text, [text])

    def test_auto_context_generalized_heuristics_keep_counterexamples_splittable(self):
        cases = [
            (
                "The title was Asst. It changed.",
                ["The title was Asst.", "It changed."],
            ),
            (
                "The estimate says est. It changed.",
                ["The estimate says est.", "It changed."],
            ),
            (
                "The place marker says Pt. It changed.",
                ["The place marker says Pt.", "It changed."],
            ),
            (
                "The abbreviation was Va. It changed.",
                ["The abbreviation was Va.", "It changed."],
            ),
            (
                "The merged company was Acme Widgets Inc. Nobody objected.",
                ["The merged company was Acme Widgets Inc.", "Nobody objected."],
            ),
            (
                "The answer was plan B. I changed it.",
                ["The answer was plan B.", "I changed it."],
            ),
            (
                "The company asked for my C.V. I sent it.",
                ["The company asked for my C.V.", "I sent it."],
            ),
            (
                "I met A. Karpov today.",
                ["I met A. Karpov today."],
            ),
        ]

        for text, expected in cases:
            with self.subTest(text=text):
                self.assertAutoContextSentencesForBoundaryTokenizers(text, expected)

    def test_auto_context_holds_partial_legal_roman_numeral_prefix(self):
        for tokenizer in ("rule-based", AUTO_CONTEXT_WORKFLOW_TOKENIZER):
            with self.subTest(tokenizer=tokenizer):
                splitter = SentenceSplitter(
                    tokenizer=tokenizer,
                    language="en",
                    minimum_sentence_length=1,
                    minimum_first_fragment_length=1,
                    context_size=1,
                    context_size_look_overhead=128,
                    auto_context=True,
                )

                yielded = []
                for char in "See U.S. Const. amend. X":
                    splitter.add(char)
                    yielded.extend(splitter.stream())

                self.assertEqual(yielded, [])

    def test_auto_context_splits_contextual_abbreviations_before_sentence_starters(self):
        cases = [
            (
                "The category is Misc. Delete it.",
                ["The category is Misc.", "Delete it."],
            ),
            (
                "The district label is Dist. It changed.",
                ["The district label is Dist.", "It changed."],
            ),
            (
                "Cite 123 U.S. It changed.",
                ["Cite 123 U.S.", "It changed."],
            ),
            (
                "The note marks Candida ser. This changed.",
                ["The note marks Candida ser.", "This changed."],
            ),
        ]

        for text, expected in cases:
            with self.subTest(text=text):
                self.assertAutoContextSentences(text, expected)

    def test_auto_context_does_not_yield_after_bare_integer_period(self):
        splitter = SentenceSplitter(
            tokenize_sentences=lambda text: [
                "The chess annotation `1. d4 Nf6 2. c4 e6 3.",
                "N",
            ],
            tokenizer="nltk+rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=64,
            auto_context=True,
            never_split_numbers=True,
        )

        yielded = []
        for char in "The chess annotation `1. d4 Nf6 2. c4 e6 3. N":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(yielded, [])

    def test_auto_context_uses_default_numeric_period_policy(self):
        splitter = SentenceSplitter(
            tokenize_sentences=lambda text: [
                "The chess annotation `1. d4 Nf6 2. c4 e6 3.",
                "N",
            ],
            tokenizer="nltk+rule-based",
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=64,
            auto_context=True,
        )

        yielded = []
        for char in "The chess annotation `1. d4 Nf6 2. c4 e6 3. N":
            splitter.add(char)
            yielded.extend(splitter.stream())

        self.assertEqual(
            yielded,
            ["The chess annotation `1. d4 Nf6 2. c4 e6 3."],
        )

    def test_punctuated_name_continuations_are_exact(self):
        cases = [
            (
                "Who? Weekly covered the story. Readers noticed.",
                ["Who? Weekly covered the story.", "Readers noticed."],
            ),
            (
                "Who? It was Sam.",
                ["Who?", "It was Sam."],
            ),
            (
                "Yahoo! Finance posted the quote. Traders noticed.",
                ["Yahoo! Finance posted the quote.", "Traders noticed."],
            ),
            (
                "Yahoo! It posted a quote.",
                ["Yahoo!", "It posted a quote."],
            ),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(
                    list(generate_sentences(
                        list(text),
                        tokenizer=AUTO_CONTEXT_WORKFLOW_TOKENIZER,
                        language="en",
                        minimum_sentence_length=1,
                        context_size=12,
                        context_size_look_overhead=64,
                    )),
                    expected,
                )

    def test_sentence_splitter_stream_uses_instance_tokenizer(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_nltk_initialized = stream2sentence_module.nltk_initialized
        stream2sentence_module.nltk_initialized = True
        try:
            splitter = SentenceSplitter(
                tokenizer="rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=1,
                context_size_look_overhead=24,
            )
            SentenceSplitter(tokenizer="nltk", language="en")
            splitter.add("One. Two. Three.")
            with mock.patch(
                "nltk.tokenize.sent_tokenize",
                side_effect=AssertionError("stream must use the splitter tokenizer"),
            ):
                sentences = list(splitter.stream()) + list(splitter.flush())
            self.assertEqual(sentences, ["One.", "Two.", "Three."])
        finally:
            stream2sentence_module.nltk_initialized = old_nltk_initialized

    def test_sentence_splitter_flush_uses_instance_tokenizer(self):
        stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
        old_nltk_initialized = stream2sentence_module.nltk_initialized
        stream2sentence_module.nltk_initialized = True
        try:
            splitter = SentenceSplitter(
                tokenizer="rule-based",
                language="en",
                minimum_sentence_length=1,
            )
            SentenceSplitter(tokenizer="nltk", language="en")
            splitter.buffer = "One. Two."
            with mock.patch(
                "nltk.tokenize.sent_tokenize",
                side_effect=AssertionError("flush must use the splitter tokenizer"),
            ):
                self.assertEqual(list(splitter.flush()), ["One.", "Two."])
        finally:
            stream2sentence_module.nltk_initialized = old_nltk_initialized

    def test_rule_based_tokenizer_uses_right_context(self):
        cases = [
            (
                "I wonder whether Tom and Mary are OK. Tom has to do that, whether he wants to or not.",
                [
                    "I wonder whether Tom and Mary are OK.",
                    "Tom has to do that, whether he wants to or not.",
                ],
            ),
            (
                "The student wants to get a job in the U.S. Could you please help him?",
                [
                    "The student wants to get a job in the U.S.",
                    "Could you please help him?",
                ],
            ),
            (
                "We left the building at about 6 p.m. Add salt before you fry the egg.",
                [
                    "We left the building at about 6 p.m.",
                    "Add salt before you fry the egg.",
                ],
            ),
            (
                "The meeting is at 3 p.m. tomorrow.",
                ["The meeting is at 3 p.m. tomorrow."],
            ),
            (
                "The spacecraft lifted off at 3:22 p.m. EDT on May 30.",
                ["The spacecraft lifted off at 3:22 p.m. EDT on May 30."],
            ),
            (
                "The U.S. Bureau responded today.",
                ["The U.S. Bureau responded today."],
            ),
            (
                "The U.S. Constitution matters today.",
                ["The U.S. Constitution matters today."],
            ),
            (
                "The U.S. Environmental Protection Agency responded today.",
                ["The U.S. Environmental Protection Agency responded today."],
            ),
            (
                "The U.S. Endangered Species Act applies today.",
                ["The U.S. Endangered Species Act applies today."],
            ),
            (
                "The U.S. Food and Drug Administration issued guidance today.",
                ["The U.S. Food and Drug Administration issued guidance today."],
            ),
            (
                "The U.S. East Coast braced for rain today.",
                ["The U.S. East Coast braced for rain today."],
            ),
            (
                "The U.S. Marines arrived today.",
                ["The U.S. Marines arrived today."],
            ),
            (
                "The U.S. Memory Championships started today.",
                ["The U.S. Memory Championships started today."],
            ),
            (
                "The U.S. Minerals Management Service responded today.",
                ["The U.S. Minerals Management Service responded today."],
            ),
            (
                "The U.S. Securities and Exchange Commission responded today.",
                ["The U.S. Securities and Exchange Commission responded today."],
            ),
            (
                "The U.S. Vice President spoke today.",
                ["The U.S. Vice President spoke today."],
            ),
            (
                "U.N. Secretary-General Antonio Guterres spoke today.",
                ["U.N. Secretary-General Antonio Guterres spoke today."],
            ),
            (
                "The U.N. Children\u2019s Fund responded today.",
                ["The U.N. Children\u2019s Fund responded today."],
            ),
            (
                "The U.N. High Commissioner for Human Rights spoke today.",
                ["The U.N. High Commissioner for Human Rights spoke today."],
            ),
            (
                "The U.N. Atlas of the Oceans lists coastal cities today.",
                ["The U.N. Atlas of the Oceans lists coastal cities today."],
            ),
            (
                "A. Karpov vs. B. Spassky, Candidates Tournament semifinal, Leningrad, 1974.",
                [
                    "A. Karpov vs. B. Spassky, Candidates Tournament semifinal, Leningrad, 1974.",
                ],
            ),
            (
                "A. Karpov won the match today.",
                ["A. Karpov won the match today."],
            ),
            (
                "The answer is A. Then it changed.",
                ["The answer is A.", "Then it changed."],
            ),
            (
                "John is as old as I. Tom disagreed.",
                ["John is as old as I.", "Tom disagreed."],
            ),
            (
                "He likes traveling and so do I. Long trips are fun.",
                ["He likes traveling and so do I.", "Long trips are fun."],
            ),
            (
                "The meeting is at 3 p.m. Monday.",
                ["The meeting is at 3 p.m. Monday."],
            ),
            (
                "Who first reached the summit of Mt. Everest? Ivy needs water.",
                [
                    "Who first reached the summit of Mt. Everest?",
                    "Ivy needs water.",
                ],
            ),
            (
                "Your ex-wife called. Mr. and Mrs. Yamada will come home next month.",
                [
                    "Your ex-wife called.",
                    "Mr. and Mrs. Yamada will come home next month.",
                ],
            ),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                sentences = list(generate_sentences(
                    text,
                    minimum_sentence_length=1,
                    context_size=12,
                    context_size_look_overhead=24,
                    tokenizer="rule-based",
                    language="en",
                ))
                self.assertEqual(sentences, expected)

    def test_quick_yield_does_not_split_parenthesized_values(self):
        cases = [
            "Option (3) is selected today.",
            "The value [3.5] is listed today.",
            "The payload {id:123} is queued today.",
            "The dosage (3.5 mg) is listed today.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertQuickYieldSingleSentence(text)

    def test_minimum_length1(self):
        text = "Short. Longer sentence."
        expected = ["Short.", "Longer sentence."]
        self.assertGeneratedSentences(text, expected, minimum_sentence_length=6) # two sentences, len("Short.") == 6

    def test_minimum_length2(self):
        text = "Short. Longer sentence."
        expected = ["Short. Longer sentence."]
        self.assertGeneratedSentences(text, expected, minimum_sentence_length=7) # one sentences, len("Short.") == 6

    def test_cleanup(self):
        text = "Text with link: https://www.example.com and emoji 😀" 
        expected = ["Text with link:  and emoji"]
        self.assertGeneratedSentences(
            text,
            expected,
            cleanup_text_links=True,
            cleanup_text_emojis=True,
        )

    def test_check1(self):
        text = "I'll go with a glass of red wine. Thank you." 
        expected = ["I'll go with a glass of red wine.", "Thank you."]
        self.assertGeneratedSentences(
            text,
            expected,
            minimum_sentence_length=10,
            minimum_first_fragment_length=10,
            quick_yield_single_sentence_fragment=True,
            cleanup_text_links=True,
            cleanup_text_emojis=True,
        )

    def test_very_short(self):
        text = "Excuse me?" 
        expected = ["Excuse me?"]
        self.assertGeneratedSentences(
            text,
            expected,
            minimum_sentence_length=18,
            minimum_first_fragment_length=10,
            quick_yield_single_sentence_fragment=True,
            cleanup_text_links=True,
            cleanup_text_emojis=True,
        )

    def test_log_characters(self):
        text = "Hello world"
        print ()
        results = []
        for tokenizer in TOKENIZERS_UNDER_TEST:
            with self.subTest(tokenizer=tokenizer):
                results.append(list(generate_sentences(
                    text,
                    tokenizer=tokenizer,
                    log_characters=True,
                )))
        print ()
        print ()
        print (f"test_log_characters succeeded, if {text} was printed above.")
        print ()
        # Check characters were printed
        self.assertTrue(all(results))

    def test_not_log_characters(self):
        text = "Do not show these characters." 
        expected = ["Do not show these characters."]
        self.assertGeneratedSentences(text, expected, log_characters=False)
        print(f"\ntest_not_log_characters succeeded, if \"{text}\" was not printed above.")

    def test_multilingual_gold_sentence_boundaries(self):
        for language_name, language_code, text, expected in MULTILINGUAL_GOLD_BOUNDARY_CASES:
            self.assertGoldSentenceBoundaries(language_name, language_code, text, expected)


MULTILINGUAL_GOLD_BOUNDARY_CASES = [
    (
        "english",
        "en",
        "Dr. Smith arrived at 5 p.m. He waved. Version 3.10.12 works.",
        [
            "Dr. Smith arrived at 5 p.m.",
            "He waved.",
            "Version 3.10.12 works.",
        ],
    ),
    (
        "mandarin",
        "zh",
        "我喜欢读书。天气很好。请帮我！吃饭了吗？我在学中文。",
        [
            "我喜欢读书。",
            "天气很好。",
            "请帮我！",
            "吃饭了吗？",
            "我在学中文。",
        ],
    ),
    (
        "hindi",
        "hi",
        "आज डॉ. शर्मा आएंगे। बैठक 10:30 बजे है। क्या तुम आओगे? ठीक है।",
        [
            "आज डॉ. शर्मा आएंगे।",
            "बैठक 10:30 बजे है।",
            "क्या तुम आओगे?",
            "ठीक है।",
        ],
    ),
    (
        "spanish",
        "es",
        "El Sr. García llega hoy. La versión v2.0.1 está lista. ¿Vienes mañana? Perfecto.",
        [
            "El Sr. García llega hoy.",
            "La versión v2.0.1 está lista.",
            "¿Vienes mañana?",
            "Perfecto.",
        ],
    ),
    (
        "french",
        "fr",
        "Nous voyons M. Dupont aujourd'hui. La version v2.0.1 est prête. Où est-elle ? Très bien.",
        [
            "Nous voyons M. Dupont aujourd'hui.",
            "La version v2.0.1 est prête.",
            "Où est-elle ?",
            "Très bien.",
        ],
    ),
    (
        "arabic",
        "ar",
        "اليوم يصل د. أحمد. الإصدار v2.0.1 جاهز. هل تأتي غدًا؟ حسنًا.",
        [
            "اليوم يصل د. أحمد.",
            "الإصدار v2.0.1 جاهز.",
            "هل تأتي غدًا؟",
            "حسنًا.",
        ],
    ),
    (
        "portuguese",
        "pt",
        "O Sr. Silva chega hoje. A versão v2.0.1 está pronta. Você vem amanhã? Ótimo.",
        [
            "O Sr. Silva chega hoje.",
            "A versão v2.0.1 está pronta.",
            "Você vem amanhã?",
            "Ótimo.",
        ],
    ),
    (
        "russian",
        "ru",
        "Сегодня указан ул. Ленина. Версия v2.0.1 готова. Ты придёшь завтра? Хорошо.",
        [
            "Сегодня указан ул. Ленина.",
            "Версия v2.0.1 готова.",
            "Ты придёшь завтра?",
            "Хорошо.",
        ],
    ),
    (
        "german",
        "de",
        "Heute kommt Dr. Müller. Version v2.0.1 ist verfügbar. Kommst du morgen? Gut.",
        [
            "Heute kommt Dr. Müller.",
            "Version v2.0.1 ist verfügbar.",
            "Kommst du morgen?",
            "Gut.",
        ],
    ),
    (
        "japanese",
        "ja",
        "今日はNo.5を選びます。バージョンv2.0.1は利用可能です。明日来ますか？はい。",
        [
            "今日はNo.5を選びます。",
            "バージョンv2.0.1は利用可能です。",
            "明日来ますか？",
            "はい。",
        ],
    ),
    (
        "turkish",
        "tr",
        "Bugün Dr. Yılmaz geliyor. Sürüm v2.0.1 hazır. Yarın gelecek misin? Tamam.",
        [
            "Bugün Dr. Yılmaz geliyor.",
            "Sürüm v2.0.1 hazır.",
            "Yarın gelecek misin?",
            "Tamam.",
        ],
    ),
]


MULTILINGUAL_QUICK_YIELD_CASES = [
    ("mandarin", "currency", "价格是¥3.50。"),
    ("mandarin", "measurement", "长度是3.5公里。"),
    ("mandarin", "domain", "请访问example.com。"),
    ("mandarin", "version", "版本v2.0.1已经发布。"),
    ("mandarin", "email", "请发送邮件到support@example.com。"),
    ("mandarin", "time", "会议时间是10:30。"),
    ("mandarin", "file_name", "配置文件是config.prod.json。"),
    ("mandarin", "ip_address", "服务器地址是192.168.0.1。"),
    ("hindi", "currency", "कीमत ₹3.50 है।"),
    ("hindi", "measurement", "दूरी 3.5 किमी है।"),
    ("hindi", "domain", "कृपया example.com खोलें।"),
    ("hindi", "version", "संस्करण v2.0.1 उपलब्ध है।"),
    ("hindi", "email", "ईमेल support@example.com पर भेजें।"),
    ("hindi", "time", "बैठक 10:30 पर है।"),
    ("hindi", "file_name", "फ़ाइल config.prod.json खोलें।"),
    ("hindi", "ip_address", "सर्वर 192.168.0.1 पर है।"),
    ("spanish", "currency", "El precio es 3,50 € hoy."),
    ("spanish", "measurement", "La distancia es 3,5 km hoy."),
    ("spanish", "domain", "Visita example.com antes de pagar."),
    ("spanish", "version", "La versión v2.0.1 está lista."),
    ("spanish", "email", "Escribe a soporte@example.com hoy."),
    ("spanish", "time", "La reunión es a las 10:30 hoy."),
    ("spanish", "file_name", "Abre config.prod.json antes de reiniciar."),
    ("spanish", "ip_address", "El servidor es 192.168.0.1 hoy."),
    ("french", "currency", "Le prix est de 3,50 € aujourd'hui."),
    ("french", "measurement", "La distance est de 3,5 km aujourd'hui."),
    ("french", "domain", "Visite example.com avant de payer."),
    ("french", "version", "La version v2.0.1 est prête."),
    ("french", "email", "Écris à support@example.com aujourd'hui."),
    ("french", "time", "La réunion est à 10:30 aujourd'hui."),
    ("french", "file_name", "Ouvre config.prod.json avant de redémarrer."),
    ("french", "ip_address", "Le serveur est 192.168.0.1 aujourd'hui."),
    ("arabic", "currency", "السعر هو ٣.٥ ر.س اليوم."),
    ("arabic", "measurement", "المسافة ٣.٥ كم اليوم."),
    ("arabic", "domain", "افتح example.com قبل الدفع."),
    ("arabic", "version", "الإصدار v2.0.1 جاهز."),
    ("arabic", "email", "أرسل إلى support@example.com اليوم."),
    ("arabic", "time", "الاجتماع عند 10:30 اليوم."),
    ("arabic", "file_name", "افتح config.prod.json قبل التشغيل."),
    ("arabic", "ip_address", "الخادم هو 192.168.0.1 اليوم."),
    ("portuguese", "currency", "O preço é R$ 3,50 hoje."),
    ("portuguese", "measurement", "A distância é 3,5 km hoje."),
    ("portuguese", "domain", "Visite example.com antes de pagar."),
    ("portuguese", "version", "A versão v2.0.1 está pronta."),
    ("portuguese", "email", "Envie email para suporte@example.com hoje."),
    ("portuguese", "time", "A reunião é às 10:30 hoje."),
    ("portuguese", "file_name", "Abra config.prod.json antes de reiniciar."),
    ("portuguese", "ip_address", "O servidor é 192.168.0.1 hoje."),
    ("russian", "currency", "Цена составляет 3,50 ₽ сегодня."),
    ("russian", "measurement", "Расстояние составляет 3,5 км сегодня."),
    ("russian", "domain", "Откройте example.com перед оплатой."),
    ("russian", "version", "Версия v2.0.1 уже готова."),
    ("russian", "email", "Напишите на support@example.com сегодня."),
    ("russian", "time", "Встреча в 10:30 сегодня."),
    ("russian", "file_name", "Откройте config.prod.json перед запуском."),
    ("russian", "ip_address", "Сервер находится на 192.168.0.1 сегодня."),
    ("german", "currency", "Der Preis beträgt 3,50 € heute."),
    ("german", "measurement", "Die Entfernung beträgt 3,5 km heute."),
    ("german", "domain", "Besuche example.com vor dem Kauf."),
    ("german", "version", "Version v2.0.1 ist verfügbar."),
    ("german", "email", "Schreibe an support@example.com heute."),
    ("german", "time", "Das Treffen ist um 10:30 heute."),
    ("german", "file_name", "Öffne config.prod.json vor dem Neustart."),
    ("german", "ip_address", "Der Server ist 192.168.0.1 heute."),
    ("japanese", "currency", "価格は1,250円です。"),
    ("japanese", "measurement", "距離は3.5 kmです。"),
    ("japanese", "domain", "支払い前にexample.comを開きます。"),
    ("japanese", "version", "バージョンv2.0.1は利用可能です。"),
    ("japanese", "email", "support@example.comにメールします。"),
    ("japanese", "time", "会議は10:30です。"),
    ("japanese", "file_name", "config.prod.jsonを開きます。"),
    ("japanese", "ip_address", "サーバーは192.168.0.1です。"),
    ("turkish", "currency", "Fiyat bugün ₺3,50."),
    ("turkish", "measurement", "Mesafe bugün 3,5 km."),
    ("turkish", "domain", "Ödeme öncesi example.com aç."),
    ("turkish", "version", "Sürüm v2.0.1 hazır."),
    ("turkish", "email", "Bugün support@example.com adresine yaz."),
    ("turkish", "time", "Toplantı bugün 10:30 saatinde."),
    ("turkish", "file_name", "Yeniden başlatmadan önce config.prod.json aç."),
    ("turkish", "ip_address", "Sunucu bugün 192.168.0.1 adresinde."),
    ("mandarin", "local_amount", "价格是人民币1,250.50元。"),
    ("mandarin", "local_date", "日期是2024.04.15。"),
    ("mandarin", "time_range", "时间是10:30-11:30。"),
    ("mandarin", "local_percent", "折扣是12.5%。"),
    ("mandarin", "temperature", "体温是36.5℃。"),
    ("hindi", "local_amount", "राशि ₹1,23,456.78 है।"),
    ("hindi", "local_date", "तारीख 15.04.2024 है।"),
    ("hindi", "time_range", "बैठक 10:30-11:30 तक है।"),
    ("hindi", "local_abbreviation", "आज डॉ. शर्मा आएंगे।"),
    ("hindi", "metric_weight", "वजन 2.5 किग्रा है।"),
    ("spanish", "local_amount", "El importe es 1.234,56 € hoy."),
    ("spanish", "local_date", "La fecha es 15.04.2024 hoy."),
    ("spanish", "time_range", "El horario es 10:30-11:30 hoy."),
    ("spanish", "local_abbreviation", "El Sr. García llega hoy."),
    ("spanish", "temperature", "La temperatura es 36,5 °C hoy."),
    ("french", "local_amount", "Le montant est de 1\u202f234,56 € aujourd'hui."),
    ("french", "local_date", "La date est le 15.04.2024 aujourd'hui."),
    ("french", "time_range", "L'horaire est 10:30-11:30 aujourd'hui."),
    ("french", "local_abbreviation", "Nous voyons M. Dupont aujourd'hui."),
    ("french", "temperature", "La température est de 36,5 °C aujourd'hui."),
    ("arabic", "local_amount", "المبلغ هو ١٬٢٣٤.٥٦ ر.س اليوم."),
    ("arabic", "local_date", "التاريخ هو 15.04.2024 اليوم."),
    ("arabic", "time_range", "الموعد من 10:30-11:30 اليوم."),
    ("arabic", "local_abbreviation", "اليوم يصل د. أحمد."),
    ("arabic", "temperature", "الحرارة ٣٦.٥ °C اليوم."),
    ("portuguese", "local_amount", "O valor é R$ 1.234,56 hoje."),
    ("portuguese", "local_date", "A data é 15.04.2024 hoje."),
    ("portuguese", "time_range", "O horário é 10:30-11:30 hoje."),
    ("portuguese", "local_abbreviation", "O Sr. Silva chega hoje."),
    ("portuguese", "temperature", "A temperatura é 36,5 °C hoje."),
    ("russian", "local_amount", "Сумма составляет 1 234,56 ₽ сегодня."),
    ("russian", "local_date", "Дата 15.04.2024 сегодня."),
    ("russian", "time_range", "Время 10:30-11:30 сегодня."),
    ("russian", "local_abbreviation", "Сегодня указана ул. Ленина."),
    ("russian", "temperature", "Температура 36,5 °C сегодня."),
    ("german", "local_amount", "Der Betrag beträgt 1.234,56 € heute."),
    ("german", "local_date", "Das Datum ist 15.04.2024 heute."),
    ("german", "time_range", "Die Zeit ist 10:30-11:30 heute."),
    ("german", "local_abbreviation", "Heute kommt Dr. Müller."),
    ("german", "temperature", "Die Temperatur beträgt 36,5 °C heute."),
    ("japanese", "local_amount", "税込価格は1,250円です。"),
    ("japanese", "local_date", "日付は2024.04.15です。"),
    ("japanese", "time_range", "時間は10:30-11:30です。"),
    ("japanese", "local_abbreviation", "今日はNo.5を選びます。"),
    ("japanese", "temperature", "体温は36.5℃です。"),
    ("turkish", "local_amount", "Tutar bugün ₺1.234,56."),
    ("turkish", "local_date", "Tarih bugün 15.04.2024."),
    ("turkish", "time_range", "Saat bugün 10:30-11:30."),
    ("turkish", "local_abbreviation", "Bugün Dr. Yılmaz geliyor."),
    ("turkish", "temperature", "Sıcaklık bugün 36,5 °C."),
]


LANGUAGE_CODES = {
    "mandarin": "zh",
    "hindi": "hi",
    "spanish": "es",
    "french": "fr",
    "arabic": "ar",
    "portuguese": "pt",
    "russian": "ru",
    "german": "de",
    "japanese": "ja",
    "turkish": "tr",
}


def _make_multilingual_quick_yield_test(text, language):
    def test(self):
        self.assertQuickYieldSingleSentence(text, language=language)

    return test


for language, category, text in MULTILINGUAL_QUICK_YIELD_CASES:
    test_name = f"test_quick_yield_multilingual_{language}_{category}"
    setattr(
        TestSentenceGenerator,
        test_name,
        _make_multilingual_quick_yield_test(text, LANGUAGE_CODES[language]),
    )

if __name__ == '__main__':
    unittest.main()

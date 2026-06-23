import importlib
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
        ))
    finally:
        stream2sentence_module.nltk_initialized = nltk_initialized


class TestSentenceGenerator(unittest.TestCase):

    def assertQuickYieldSingleSentence(self, text, language="en"):
        self.assertQuickYieldSentences(
            text,
            [text],
            tokenize_sentences=single_sentence_tokenizer,
            language=language,
        )

    def assertQuickYieldSentences(
        self,
        text,
        expected,
        tokenize_sentences=simple_sentence_tokenizer,
        language="en",
    ):
        for tokenizer in TOKENIZERS_UNDER_TEST:
            with self.subTest(tokenizer=tokenizer, text=text):
                self.assertEqual(
                    quick_yield_sentences(
                        text,
                        tokenize_sentences=tokenize_sentences,
                        language=language,
                        tokenizer=tokenizer,
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
            "Use e.g. apples in the list.",
            "Smith et al. reported the result.",
            "See op. cit. for details.",
            "The value is ca. 10 today.",
            "The match is Team A vs. Team B tonight.",
            "See Fig. 2 in the paper.",
            "The office is on St. Patrick Avenue today.",
            "The company is Acme Inc. today.",
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
                    rule_based_tokenize.assert_called_once_with("One. Two.", "en")
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
                rule_based_tokenize.assert_called_once_with(text, "en")

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
                        tokenizer="nltk+rule-based",
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

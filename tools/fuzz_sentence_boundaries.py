"""Randomized sentence-boundary stress harness for stream2sentence.

This is intentionally not part of the deterministic unit-test suite. It builds
known intended sentence lists, streams the joined text one character at a time,
and compares the resulting sentence boundaries with the known list.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sqlite3
import sys
import time
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_CONTEXTS_PATH = REPO_ROOT / "stream2sentence" / "data" / "language_contexts.json"
DEFAULT_SENTENCE_DB = REPO_ROOT / "downloads" / "tatoeba" / "cleaned_eng_v1" / "cleaner.sqlite"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_generate_sentences():
    """Load the splitter module without running package import side effects."""
    package_dir = REPO_ROOT / "stream2sentence"
    package = types.ModuleType("stream2sentence")
    package.__path__ = [str(package_dir)]
    sys.modules["stream2sentence"] = package

    module_name = "stream2sentence.stream2sentence"
    module_path = package_dir / "stream2sentence.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.generate_sentences


generate_sentences = load_generate_sentences()

MULTILINGUAL_DELIMITERS = ".?!;:,\n\u2026)]}\u3002\uff01\uff1f\u061f\u0964-"
MULTILINGUAL_FULL_DELIMITERS = ".?!\n\u2026\u3002\uff01\uff1f\u061f\u0964"

NAMES = [
    "Ada",
    "Maya",
    "Sam",
    "Rivera",
    "Nguyen",
    "O'Neil",
    "Patel",
    "Chen",
]

NOUNS = [
    "deploy",
    "invoice",
    "router",
    "brief",
    "draft",
    "parser",
    "transcript",
    "monitor",
]

DOMAINS = [
    "example.com",
    "docs.python.org",
    "api.example.co.uk",
    "db-01.prod.local",
    "checkout.service.cluster.local",
]

URLS = [
    "https://example.com/search?q=version%201.2.3",
    "https://staging.example.com/v1.2/status?ok=false",
    "http://127.0.0.1:8000/health",
    "s3://bucket-name/releases/v1.2.3/file.zip",
    "postgres://user:pass@db.example.com:5432/app",
]

FILES = [
    "config.prod.json",
    "archive.tar.gz",
    "pyproject.toml",
    "src/components/Button.test.tsx",
    "C:\\Users\\Start\\config.json",
    "/opt/app/v1.2/config.yaml",
]

COMMANDS = [
    "python -m pytest tests/test_stream2sentence.py::TestSentenceGenerator",
    "docker.io/library/python:3.11-slim",
    "--model=gpt-4.1-mini",
    "git checkout feature/splitter-v2.0",
    "image=ghcr.io/org/app:v1.2.3",
]


@dataclass(frozen=True, slots=True)
class SentenceSpec:
    text: str
    label: str
    scope_hint: str = "candidate-local"


@dataclass(frozen=True, slots=True)
class DatabaseSentence:
    rowid: int
    source_id: int
    part_index: int
    decision: str
    text: str

    def to_spec(self) -> SentenceSpec:
        return SentenceSpec(
            self.text,
            f"database:{self.source_id}:{self.part_index}",
            "database-clean-corpus",
        )


@dataclass(frozen=True)
class CaseSpec:
    language: str
    sentences: tuple[SentenceSpec, ...]
    separator: str

    @property
    def text(self) -> str:
        return self.separator.join(sentence.text for sentence in self.sentences)

    @property
    def expected(self) -> list[str]:
        return [sentence.text for sentence in self.sentences]

    @property
    def labels(self) -> list[str]:
        return [sentence.label for sentence in self.sentences]


@dataclass
class BoundaryIssue:
    kind: str
    offset: int
    label: str
    scope_hint: str
    window: str
    repro_text: str
    repro_expected: list[str]
    repro_actual: list[str]


@dataclass
class Mismatch:
    iteration: int
    seed: int
    language: str
    tokenizer: str
    never_split_numbers: bool
    labels: list[str]
    text: str
    expected: list[str]
    actual: list[str]
    issues: list[BoundaryIssue]


def load_language_contexts() -> dict:
    with LANGUAGE_CONTEXTS_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def load_database_sentences(
    db_path: Path,
    rng: random.Random,
    sample_size: int,
    max_sentence_chars: int,
) -> list[DatabaseSentence]:
    if not db_path.exists():
        raise FileNotFoundError(f"sentence database not found: {db_path}")

    with sqlite3.connect(db_path) as connection:
        if sample_size == 0:
            rows = connection.execute(
                """
                SELECT rowid, source_id, part_index, decision, text
                FROM clean_sentences
                WHERE length(text) <= ?
                ORDER BY source_id, part_index
                """,
                (max_sentence_chars,),
            ).fetchall()
            sentences = [
                DatabaseSentence(
                    rowid=row[0],
                    source_id=row[1],
                    part_index=row[2],
                    decision=row[3],
                    text=row[4].strip(),
                )
                for row in rows
                if row[4].strip()
            ]
            if len(sentences) < 3:
                raise ValueError(
                    f"need at least 3 database sentences from {db_path}, found {len(sentences)}"
                )
            return sentences

        sentences: list[DatabaseSentence] = []
        seen_rowids: set[int] = set()
        bounds = connection.execute(
            "SELECT min(rowid), max(rowid) FROM clean_sentences"
        ).fetchone()
        if not bounds or bounds[0] is None or bounds[1] is None:
            raise ValueError(f"no clean_sentences rows found in {db_path}")

        min_rowid, max_rowid = bounds
        attempts = 0
        max_attempts = max(sample_size * 20, 100)
        while len(sentences) < sample_size and attempts < max_attempts:
            attempts += 1
            start_rowid = rng.randint(min_rowid, max_rowid)
            row = connection.execute(
                """
                SELECT rowid, source_id, part_index, decision, text
                FROM clean_sentences
                WHERE rowid >= ? AND length(text) <= ?
                ORDER BY rowid
                LIMIT 1
                """,
                (start_rowid, max_sentence_chars),
            ).fetchone()
            if row is None or row[0] in seen_rowids:
                continue

            text = row[4].strip()
            if not text:
                continue

            seen_rowids.add(row[0])
            sentences.append(
                DatabaseSentence(
                    rowid=row[0],
                    source_id=row[1],
                    part_index=row[2],
                    decision=row[3],
                    text=text,
                )
            )

    if len(sentences) < 3:
        raise ValueError(
            f"need at least 3 database sentences from {db_path}, found {len(sentences)}"
        )

    return sentences


def sentence_spans(text: str, sentences: Sequence[str]) -> list[tuple[int, int]]:
    spans = []
    search_start = 0
    for sentence in sentences:
        while search_start < len(text) and text[search_start].isspace():
            search_start += 1
        match_start = text.find(sentence.strip(), search_start)
        if match_start < 0:
            return []
        match_end = match_start + len(sentence.strip())
        spans.append((match_start, match_end))
        search_start = match_end
    return spans


def boundary_offsets(text: str, sentences: Sequence[str]) -> list[int]:
    spans = sentence_spans(text, sentences)
    if not spans and sentences:
        return []
    return [end for _, end in spans[:-1]]


def window_around(text: str, offset: int, radius: int = 50) -> str:
    start = max(0, offset - radius)
    end = min(len(text), offset + radius)
    return text[start:offset] + "<BOUNDARY>" + text[offset:end]


def run_stream(text: str, args: argparse.Namespace, language: str) -> list[str]:
    return list(
        generate_sentences(
            list(text),
            tokenizer=args.tokenizer,
            language=language,
            minimum_sentence_length=1,
            minimum_first_fragment_length=1,
            context_size=args.context_size,
            context_size_look_overhead=args.context_size_look_overhead,
            auto_context=args.auto_context,
            never_split_numbers=args.never_split_numbers,
            sentence_fragment_delimiters=MULTILINGUAL_DELIMITERS,
            full_sentence_delimiters=MULTILINGUAL_FULL_DELIMITERS,
        )
    )


def choose(rng: random.Random, values: Sequence[str]) -> str:
    return rng.choice(values)


def plain_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    return SentenceSpec(
        f"{choose(rng, NAMES)} confirmed the {choose(rng, NOUNS)} before lunch.",
        "plain",
    )


def abbreviation_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    language_context = contexts["languages"].get(language, contexts["languages"]["en"])
    preferred = {"no.", "fig.", "ref.", "sec.", "eq.", "art.", "vol."}
    abbreviations = [
        abbreviation
        for abbreviation in language_context.get("abbreviations", [])
        if abbreviation.casefold() in preferred
    ] or ["No.", "Fig.", "Ref.", "Sec.", "Eq."]
    abbreviation = choose(rng, abbreviations)
    return SentenceSpec(
        f"The note uses {abbreviation} 7 as a local reference today.",
        "context-abbreviation",
    )


def decimal_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    amount = f"{rng.randint(1, 999)}.{rng.randint(10, 99)}"
    return SentenceSpec(
        f"The invoice lists ${amount}, 3.14159 kg, and 1.5-mm parts today.",
        "numeric-decimal",
    )


def domain_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    return SentenceSpec(
        f"Visit {choose(rng, DOMAINS)} before checkout.",
        "domain",
    )


def url_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    return SentenceSpec(
        f"Open {choose(rng, URLS)} before deploy.",
        "url",
    )


def email_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    local = choose(rng, ["support", "first.last", "build.bot+ci", "release.2024.04"])
    domain = choose(rng, ["example.com", "example.co.uk", "sub.domain.io"])
    return SentenceSpec(
        f"Email {local}@{domain} before noon.",
        "email",
    )


def file_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    return SentenceSpec(
        f"Open {choose(rng, FILES)} before restarting.",
        "file-path",
    )


def command_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    return SentenceSpec(
        f"Run {choose(rng, COMMANDS)} before release.",
        "command-token",
    )


def citation_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    volume = rng.randint(100, 999)
    page = rng.randint(100, 999)
    return SentenceSpec(
        f"The brief cites Smith v. Jones, {volume} F.3d {page}, 458 n.2 (9th Cir. 1999), before the conclusion.",
        "legal-citation",
    )


def chess_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del rng, contexts, language
    return SentenceSpec(
        "The chess line is 1. d4 Nf6 2. c4 e6 3. Nc3 Bb4+ today.",
        "bare-number-period",
        "requires-never-split-numbers",
    )


def quote_continuation_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts, language
    word = choose(rng, ["Ready", "Done", "End", "Stop"])
    return SentenceSpec(
        f'The status label "{word}." stayed visible during the demo.',
        "quoted-period-lowercase-continuation",
    )


def question_quote_continuation_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts, language
    word = choose(rng, ["ready", "done", "safe", "green"])
    return SentenceSpec(
        f'Maya asked "{word}?" before the timer started.',
        "quoted-question-lowercase-continuation",
    )


def parenthesized_continuation_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts, language
    word = choose(rng, ["done", "ready", "archived", "green"])
    opener, closer = choose(rng, [("(", ")"), ("[", "]"), ("{", "}")])
    return SentenceSpec(
        f"The checklist item {opener}{word}.{closer} stayed visible until noon.",
        "bracketed-period-lowercase-continuation",
    )


def punctuated_name_comma_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts, language
    name = choose(rng, ["Guess?", "Stop!", "Really?", "Help!"])
    return SentenceSpec(
        f"The headline mentioned {name}, and the editor left it unchanged.",
        "punctuated-token-comma-continuation",
    )


def code_like_sentence(rng: random.Random, contexts: dict, language: str) -> SentenceSpec:
    del contexts, language
    key = choose(rng, ["status", "message", "label"])
    value = choose(rng, ["Done.", "Ready?", "Stop!"])
    return SentenceSpec(
        f'The payload {{"{key}": "{value}", "ok": true}} stayed queued today.',
        "json-like-snippet",
        "likely-out-of-scope-stateful",
    )


def markdown_code_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts, language
    move = choose(rng, ["1. d4 Nf6 2. c4 e6", "config.prod.json", "print('Done.')"])
    return SentenceSpec(
        f"The note showed `{move}` before the final paragraph.",
        "markdown-code-span",
        "likely-out-of-scope-stateful",
    )


def multilingual_sentence(
    rng: random.Random, contexts: dict, language: str
) -> SentenceSpec:
    del contexts
    if language == "zh":
        samples = [
            "\u8bf7\u8bbf\u95eeexample.com\u3002",
            "\u7248\u672cv2.0.1\u5df2\u7ecf\u53d1\u5e03\u3002",
            "\u4f1a\u8bae\u65f6\u95f4\u662f10:30\u3002",
        ]
    elif language == "ja":
        samples = [
            "example.com\u3092\u958b\u304d\u307e\u3059\u3002",
            "\u30d0\u30fc\u30b8\u30e7\u30f3v2.0.1\u306f\u5229\u7528\u53ef\u80fd\u3067\u3059\u3002",
            "\u4f1a\u8b70\u306f10:30\u3067\u3059\u3002",
        ]
    else:
        samples = [
            f"{choose(rng, NAMES)} confirmed version v2.0.1 today.",
            f"Visit {choose(rng, DOMAINS)} before checkout.",
        ]
    return SentenceSpec(choose(rng, samples), f"multilingual-{language}")


SENTENCE_FACTORIES: tuple[
    Callable[[random.Random, dict, str], SentenceSpec],
    ...,
] = (
    plain_sentence,
    decimal_sentence,
    domain_sentence,
    url_sentence,
    email_sentence,
    file_sentence,
    command_sentence,
    quote_continuation_sentence,
    question_quote_continuation_sentence,
    parenthesized_continuation_sentence,
    punctuated_name_comma_sentence,
)

ENGLISH_ONLY_FACTORIES: tuple[
    Callable[[random.Random, dict, str], SentenceSpec],
    ...,
] = (
    abbreviation_sentence,
    citation_sentence,
    chess_sentence,
)


STATEFUL_FACTORIES: tuple[
    Callable[[random.Random, dict, str], SentenceSpec],
    ...,
] = (
    code_like_sentence,
    markdown_code_sentence,
)


def abbreviation_boundary_case(rng: random.Random) -> CaseSpec:
    first = choose(
        rng,
        [
            "The crate held bolts, tape, etc.",
            "The merged company was Acme Widgets Inc.",
            "The office closed at 6 p.m.",
        ],
    )
    second = choose(
        rng,
        [
            "Then the crew left.",
            "It reopened on Monday.",
            "Nobody objected.",
        ],
    )
    return CaseSpec(
        "en",
        (
            SentenceSpec(first, "abbreviation-at-intended-boundary"),
            SentenceSpec(second, "plain"),
        ),
        choose(rng, [" ", "  ", "\n"]),
    )


def database_case(
    rng: random.Random,
    args: argparse.Namespace,
    database_sentences: Sequence[DatabaseSentence],
) -> CaseSpec:
    count = rng.randint(args.min_sentences, args.max_sentences)
    if count > len(database_sentences):
        raise ValueError(
            f"database has {len(database_sentences)} usable sentences, "
            f"but this case requested {count}"
        )
    selected = rng.sample(database_sentences, count)
    return CaseSpec(
        "en",
        tuple(sentence.to_spec() for sentence in selected),
        choose(rng, [" ", "  ", "\n", "\n\n"]),
    )


def mixed_database_case(
    rng: random.Random,
    contexts: dict,
    args: argparse.Namespace,
    database_sentences: Sequence[DatabaseSentence],
) -> CaseSpec:
    count = rng.randint(args.min_sentences, args.max_sentences)
    synthetic_factories = list(SENTENCE_FACTORIES) + list(ENGLISH_ONLY_FACTORIES)
    if args.include_out_of_scope:
        synthetic_factories.extend(STATEFUL_FACTORIES)

    sentences: list[SentenceSpec] = []
    for _ in range(count):
        if rng.random() < args.database_fraction:
            sentences.append(choose(rng, database_sentences).to_spec())
            continue
        spec = rng.choice(synthetic_factories)(rng, contexts, "en")
        if (
            spec.scope_hint == "requires-never-split-numbers"
            and not args.never_split_numbers
            and not args.include_policy_ambiguity
        ):
            spec = plain_sentence(rng, contexts, "en")
        sentences.append(spec)

    return CaseSpec("en", tuple(sentences), choose(rng, [" ", "  ", "\n", "\n\n"]))


def random_case(
    rng: random.Random,
    contexts: dict,
    args: argparse.Namespace,
    database_sentences: Sequence[DatabaseSentence],
) -> CaseSpec:
    if args.source == "database":
        return database_case(rng, args, database_sentences)
    if args.source == "mixed":
        return mixed_database_case(rng, contexts, args, database_sentences)

    language = choose(rng, args.languages)
    separator = choose(rng, [" ", "  ", "\n", "\n\n"])

    if language in {"zh", "ja"} and rng.random() < 0.65:
        count = rng.randint(2, 5)
        sentences = tuple(multilingual_sentence(rng, contexts, language) for _ in range(count))
        return CaseSpec(language, sentences, separator)

    if rng.random() < 0.12:
        return abbreviation_boundary_case(rng)

    factories = list(SENTENCE_FACTORIES)
    if language == "en":
        factories.extend(ENGLISH_ONLY_FACTORIES)
    if args.include_out_of_scope:
        factories.extend(STATEFUL_FACTORIES)

    count = rng.randint(args.min_sentences, args.max_sentences)
    sentences = []
    for _ in range(count):
        factory = rng.choice(factories)
        spec = factory(rng, contexts, language)
        if (
            spec.scope_hint == "requires-never-split-numbers"
            and not args.never_split_numbers
            and not args.include_policy_ambiguity
        ):
            spec = plain_sentence(rng, contexts, language)
        sentences.append(spec)

    return CaseSpec(language, tuple(sentences), separator)


def issue_label_for_offset(case: CaseSpec, offset: int) -> tuple[str, str]:
    spans = sentence_spans(case.text, case.expected)
    for index, (start, end) in enumerate(spans):
        if start <= offset <= end:
            spec = case.sentences[index]
            return spec.label, spec.scope_hint
    return "unknown", "unknown"


def repro_for_issue(
    case: CaseSpec,
    kind: str,
    offset: int,
    args: argparse.Namespace,
) -> tuple[str, list[str], list[str]]:
    spans = sentence_spans(case.text, case.expected)
    if not spans:
        actual = run_stream(case.text, args, case.language)
        return case.text, case.expected, actual

    if kind == "false_positive":
        sentence_indexes = [
            index for index, (start, end) in enumerate(spans) if start < offset < end
        ]
        if not sentence_indexes:
            sentence_indexes = [
                min(range(len(spans)), key=lambda index: abs(spans[index][1] - offset))
            ]
        index = sentence_indexes[0]
        expected = [case.expected[index]]
    else:
        expected_offsets = boundary_offsets(case.text, case.expected)
        try:
            index = expected_offsets.index(offset)
            expected = [case.expected[index], case.expected[index + 1]]
        except (ValueError, IndexError):
            expected = case.expected

    repro_text = " ".join(expected)
    repro_actual = run_stream(repro_text, args, case.language)
    if repro_actual == expected and len(expected) == 1:
        # Some early boundaries only trigger when the following sentence gives
        # the stream more lookahead. Include the next sentence if available.
        original_index = case.expected.index(expected[0])
        if original_index + 1 < len(case.expected):
            expected = [case.expected[original_index], case.expected[original_index + 1]]
            repro_text = " ".join(expected)
            repro_actual = run_stream(repro_text, args, case.language)
    return repro_text, expected, repro_actual


def collect_mismatch(
    iteration: int,
    seed: int,
    case: CaseSpec,
    actual: list[str],
    args: argparse.Namespace,
) -> Mismatch | None:
    expected = case.expected
    if actual == expected:
        return None

    expected_offsets = set(boundary_offsets(case.text, expected))
    actual_offsets = set(boundary_offsets(case.text, actual))

    issues: list[BoundaryIssue] = []
    for offset in sorted(actual_offsets - expected_offsets):
        label, scope_hint = issue_label_for_offset(case, offset)
        repro_text, repro_expected, repro_actual = repro_for_issue(
            case, "false_positive", offset, args
        )
        issues.append(
            BoundaryIssue(
                kind="false_positive",
                offset=offset,
                label=label,
                scope_hint=scope_hint,
                window=window_around(case.text, offset),
                repro_text=repro_text,
                repro_expected=repro_expected,
                repro_actual=repro_actual,
            )
        )

    for offset in sorted(expected_offsets - actual_offsets):
        label, scope_hint = issue_label_for_offset(case, offset)
        repro_text, repro_expected, repro_actual = repro_for_issue(
            case, "false_negative", offset, args
        )
        issues.append(
            BoundaryIssue(
                kind="false_negative",
                offset=offset,
                label=label,
                scope_hint=scope_hint,
                window=window_around(case.text, offset),
                repro_text=repro_text,
                repro_expected=repro_expected,
                repro_actual=repro_actual,
            )
        )

    if not issues:
        issues.append(
            BoundaryIssue(
                kind="alignment_mismatch",
                offset=-1,
                label="unknown",
                scope_hint="inspect",
                window=case.text[:120],
                repro_text=case.text,
                repro_expected=expected,
                repro_actual=actual,
            )
        )

    return Mismatch(
        iteration=iteration,
        seed=seed,
        language=case.language,
        tokenizer=args.tokenizer,
        never_split_numbers=args.never_split_numbers,
        labels=case.labels,
        text=case.text,
        expected=expected,
        actual=actual,
        issues=issues,
    )


def issue_signature(issue: BoundaryIssue) -> tuple[str, str, str]:
    return (issue.kind, issue.label, issue.scope_hint)


def unique_mismatches(mismatches: Iterable[Mismatch]) -> list[Mismatch]:
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for mismatch in mismatches:
        keep_issues = []
        for issue in mismatch.issues:
            signature = issue_signature(issue)
            if signature in seen:
                continue
            seen.add(signature)
            keep_issues.append(issue)
        if keep_issues:
            mismatch.issues = keep_issues
            unique.append(mismatch)
    return unique


def print_report(
    seed: int,
    iterations: int,
    elapsed: float,
    mismatches: list[Mismatch],
    args: argparse.Namespace,
) -> None:
    unique = unique_mismatches(mismatches)
    print(f"seed: {seed}")
    print(f"duration_seconds: {elapsed:.2f}")
    print(f"iterations: {iterations}")
    print(f"raw_mismatched_cases: {len(mismatches)}")
    print(f"unique_issue_signatures: {sum(len(m.issues) for m in unique)}")
    print(f"source: {args.source}")
    if args.source in {"database", "mixed"}:
        print(f"database: {args.database}")
        database_scope = "all" if args.database_sample_size == 0 else str(args.database_sample_size)
        print(f"database_sample_size: {database_scope}")
        print(f"database_loaded_sentences: {args.database_loaded_sentences}")
    print(
        f"rerun: {sys.executable} tools/fuzz_sentence_boundaries.py "
        f"--seed {seed} --duration {args.duration} --tokenizer {args.tokenizer} "
        f"--source {args.source}"
    )
    print()

    for mismatch_index, mismatch in enumerate(unique[: args.max_report], 1):
        print(f"== mismatch {mismatch_index} ==")
        print(
            f"iteration={mismatch.iteration} language={mismatch.language} "
            f"tokenizer={mismatch.tokenizer} never_split_numbers={mismatch.never_split_numbers}"
        )
        print(f"labels={', '.join(mismatch.labels)}")
        for issue in mismatch.issues:
            print(
                f"- {issue.kind} label={issue.label} "
                f"scope_hint={issue.scope_hint} offset={issue.offset}"
            )
            print(f"  window={issue.window!r}")
            print(f"  repro_text={issue.repro_text!r}")
            print(f"  expected={issue.repro_expected!r}")
            print(f"  actual={issue.repro_actual!r}")
        print()


def write_json_report(
    seed: int,
    iterations: int,
    elapsed: float,
    mismatches: list[Mismatch],
    output: Path,
    args: argparse.Namespace,
) -> None:
    payload = {
        "seed": seed,
        "duration_seconds": elapsed,
        "iterations": iterations,
        "source": args.source,
        "database": str(args.database) if args.source in {"database", "mixed"} else None,
        "database_sample_size": (
            "all" if args.source in {"database", "mixed"} and args.database_sample_size == 0
            else args.database_sample_size if args.source in {"database", "mixed"}
            else None
        ),
        "database_loaded_sentences": (
            args.database_loaded_sentences if args.source in {"database", "mixed"} else None
        ),
        "mismatches": [asdict(mismatch) for mismatch in mismatches],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Randomized stream2sentence sentence-boundary stress harness."
    )
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--source",
        choices=["synthetic", "database", "mixed"],
        default="synthetic",
        help="Sentence source: synthetic templates, the cleaned Tatoeba SQLite database, or both.",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_SENTENCE_DB)
    parser.add_argument(
        "--database-sample-size",
        type=int,
        default=0,
        help="Database working-set size. Use 0 to load all clean_sentences rows into RAM.",
    )
    parser.add_argument("--database-fraction", type=float, default=0.7)
    parser.add_argument("--max-database-sentence-chars", type=int, default=240)
    parser.add_argument("--tokenizer", default="rule-based")
    parser.add_argument("--context-size", type=int, default=1)
    parser.add_argument("--context-size-look-overhead", type=int, default=128)
    parser.add_argument("--auto-context", action="store_true")
    parser.add_argument(
        "--never-split-numbers",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Treat bare integer tokens ending in a period as non-boundaries. "
            "Defaults to false for --source database and true otherwise."
        ),
    )
    parser.add_argument("--include-out-of-scope", action="store_true")
    parser.add_argument("--include-policy-ambiguity", action="store_true")
    parser.add_argument("--min-sentences", type=int, default=2)
    parser.add_argument("--max-sentences", type=int, default=6)
    parser.add_argument("--max-report", type=int, default=12)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-mismatch", action="store_true")
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en", "es", "fr", "de", "zh", "ja"],
        help="Language codes to sample. Each generated text block uses one language.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.never_split_numbers is None:
        args.never_split_numbers = args.source != "database"

    seed = args.seed if args.seed is not None else time.time_ns()
    rng = random.Random(seed)
    contexts = load_language_contexts()
    database_sentences: list[DatabaseSentence] = []

    if args.source in {"database", "mixed"}:
        database_sentences = load_database_sentences(
            args.database,
            rng,
            args.database_sample_size,
            args.max_database_sentence_chars,
        )
        args.database_loaded_sentences = len(database_sentences)
        if len(database_sentences) < args.max_sentences:
            raise ValueError(
                f"database sample has {len(database_sentences)} sentences, "
                f"but --max-sentences is {args.max_sentences}"
            )
    else:
        args.database_loaded_sentences = 0

    started = time.monotonic()
    deadline = started + args.duration
    mismatches: list[Mismatch] = []
    iterations = 0

    while time.monotonic() < deadline:
        iterations += 1
        case = random_case(rng, contexts, args, database_sentences)
        actual = run_stream(case.text, args, case.language)
        mismatch = collect_mismatch(iterations, seed, case, actual, args)
        if mismatch is not None:
            mismatches.append(mismatch)

    elapsed = time.monotonic() - started
    print_report(seed, iterations, elapsed, mismatches, args)
    if args.output:
        write_json_report(seed, iterations, elapsed, mismatches, args.output, args)
        print(f"wrote_json_report: {args.output}")

    return 1 if args.fail_on_mismatch and mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())

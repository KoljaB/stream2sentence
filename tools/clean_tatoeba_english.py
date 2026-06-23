"""Build a conservative one-sentence-per-row Tatoeba dataset.

The cleaner runs language-neutral hygiene checks first. It then applies
language-specific sentence-boundary logic for the selected language. English is
the default and currently the only language with tokenizer-backed splitting.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from nltk.tokenize import sent_tokenize


SCHEMA_VERSION = 1
DEFAULT_INPUT = Path("downloads/tatoeba/sentences.csv")
DEFAULT_OUTPUT_DIR = Path("downloads/tatoeba/cleaned_eng_v1")
DEFAULT_DB = DEFAULT_OUTPUT_DIR / "cleaner.sqlite"
DEFAULT_EXPORT = DEFAULT_OUTPUT_DIR / "eng_clean_single_sentences.tsv"
DEFAULT_REJECT_EXPORT = DEFAULT_OUTPUT_DIR / "eng_rejected_rows.tsv"
DEFAULT_STANZA_MODEL_DIR = Path("downloads/tatoeba/stanza_resources")

LANGUAGE_ALIASES = {
    "en": "eng",
    "eng": "eng",
    "english": "eng",
}
NLTK_LANGUAGE_BY_TATOEBA = {
    "eng": "english",
}
STANZA_LANGUAGE_BY_TATOEBA = {
    "eng": "en",
}

TERMINATORS = ".?!"
CLOSERS = "\"')]}”’»›"
OPENERS = "\"'([{“‘«‹"
MAX_SENTENCE_CHARS = 280
MIN_SENTENCE_CHARS = 2

URL_OR_EMAIL_RE = re.compile(
    r"(?:https?://|www\.|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)
BARE_DOMAIN_RE = re.compile(
    r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"(?:com|org|net|edu|gov|mil|int|io|ai|app|dev|de|fr|es|it|pt|ru|jp|cn|uk|us)\b",
    re.IGNORECASE,
)
BAD_SPACE_RE = re.compile(r"\s+")
TOKEN_BEFORE_DOT_RE = re.compile(r"([A-Za-z]+|[A-Z])\.$")

ABBREVIATIONS = {
    "adj",
    "adm",
    "adv",
    "al",
    "approx",
    "apr",
    "aug",
    "ave",
    "bros",
    "capt",
    "cf",
    "cmdr",
    "co",
    "col",
    "corp",
    "dec",
    "dept",
    "dr",
    "e.g",
    "ed",
    "eds",
    "est",
    "etc",
    "ex",
    "feb",
    "fig",
    "gen",
    "gov",
    "hon",
    "i.e",
    "inc",
    "jan",
    "jr",
    "jul",
    "jun",
    "ltd",
    "lt",
    "maj",
    "mar",
    "messrs",
    "mrs",
    "mr",
    "ms",
    "mt",
    "no",
    "nov",
    "oct",
    "op",
    "pl",
    "prof",
    "rep",
    "rev",
    "sen",
    "sep",
    "sept",
    "sgt",
    "sr",
    "st",
    "vs",
}

LOWER_INITIAL_ABBREVIATIONS = {"a.m", "p.m"}


@dataclass(frozen=True)
class SplitResult:
    parts: list[str]
    method: str
    reason: str


def normalize_language_code(language: str) -> str:
    key = language.strip().lower()
    return LANGUAGE_ALIASES.get(key, key)


def normalize_space(text: str) -> str:
    return BAD_SPACE_RE.sub(" ", text).strip()


def has_letter(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def terminal_index(text: str) -> int:
    i = len(text) - 1
    while i >= 0 and text[i] in CLOSERS:
        i -= 1
    return i


def terminal_span(text: str) -> tuple[int, int]:
    end = terminal_index(text)
    if end < 0 or text[end] not in TERMINATORS:
        return -1, -1
    start = end
    while start - 1 >= 0 and text[start - 1] in TERMINATORS:
        start -= 1
    return start, end


def has_internal_terminator(text: str) -> bool:
    start, end = terminal_span(text)
    return any(ch in TERMINATORS and not (start <= i <= end) for i, ch in enumerate(text))


def has_balanced_light_punctuation(text: str) -> bool:
    pairs = [("(", ")"), ("[", "]"), ("{", "}")]
    for left, right in pairs:
        if text.count(left) != text.count(right):
            return False

    if text.count('"') % 2:
        return False
    for left, right in [("“", "”"), ("«", "»"), ("‹", "›")]:
        if text.count(left) != text.count(right):
            return False

    return True


def previous_token(text: str, dot_index: int) -> str:
    start = dot_index - 1
    while start >= 0 and (text[start].isalpha() or text[start] == "."):
        start -= 1
    return text[start + 1 : dot_index]


def next_non_space(text: str, index: int) -> str:
    i = index + 1
    while i < len(text) and text[i].isspace():
        i += 1
    return text[i] if i < len(text) else ""


def is_acronym_dot(text: str, dot_index: int) -> bool:
    prev = text[dot_index - 1] if dot_index > 0 else ""
    nxt = text[dot_index + 1] if dot_index + 1 < len(text) else ""
    prev_prev = text[dot_index - 2] if dot_index > 1 else ""
    next_next = text[dot_index + 2] if dot_index + 2 < len(text) else ""

    if not prev.isupper():
        return False
    if nxt.isupper() and next_next == ".":
        return True
    if prev_prev == "." and (dot_index < len(text) - 1):
        return True
    return False


def is_initial_dot(text: str, dot_index: int) -> bool:
    if dot_index == 0 or not text[dot_index - 1].isupper():
        return False
    before = text[dot_index - 2] if dot_index > 1 else " "
    if before and not before.isspace() and before not in OPENERS:
        return False
    nxt = next_non_space(text, dot_index)
    return bool(nxt and nxt.isupper())


def is_decimal_or_version_dot(text: str, dot_index: int) -> bool:
    before = text[dot_index - 1] if dot_index > 0 else ""
    after = text[dot_index + 1] if dot_index + 1 < len(text) else ""
    return before.isdigit() and after.isdigit()


def is_known_abbreviation_dot(text: str, dot_index: int) -> bool:
    token = previous_token(text, dot_index).lower()
    if not token:
        return False

    window = text[max(0, dot_index - 3) : min(len(text), dot_index + 3)].lower()
    if "a.m." in window or "p.m." in window:
        return True

    if token in ABBREVIATIONS:
        return True

    for abbrev in LOWER_INITIAL_ABBREVIATIONS:
        if text[max(0, dot_index - len(abbrev)) : dot_index].lower() == abbrev:
            return True

    return False


def is_safe_internal_dot(text: str, dot_index: int) -> bool:
    if text[dot_index : dot_index + 3] == "...":
        return False
    if text[max(0, dot_index - 2) : dot_index + 1] == "...":
        return False

    if is_decimal_or_version_dot(text, dot_index):
        return True
    if is_acronym_dot(text, dot_index):
        return True
    if is_initial_dot(text, dot_index):
        return True
    if is_known_abbreviation_dot(text, dot_index):
        return True

    return False


def validate_general_text(text: str) -> tuple[bool, str]:
    s = normalize_space(text)
    if len(s) < MIN_SENTENCE_CHARS:
        return False, "too_short"
    if len(s) > MAX_SENTENCE_CHARS:
        return False, "too_long"
    if "\t" in text or "\n" in text or "\r" in text:
        return False, "contains_control_space"
    if not has_letter(s):
        return False, "no_letter"
    if URL_OR_EMAIL_RE.search(s):
        return False, "url_or_email"
    if IPV4_RE.search(s):
        return False, "ip_address"
    if BARE_DOMAIN_RE.search(s):
        return False, "bare_domain"
    if "..." in s or "…" in s:
        return False, "ellipsis"
    if not has_balanced_light_punctuation(s):
        return False, "unbalanced_punctuation"

    return True, "ok"


def validate_single_sentence(text: str, language: str = "eng") -> tuple[bool, str]:
    s = normalize_space(text)
    ok, reason = validate_general_text(s)
    if not ok:
        return False, reason

    start, end = terminal_span(s)
    if end < 0:
        return False, "missing_final_terminator"

    if normalize_language_code(language) != "eng":
        if has_internal_terminator(s):
            return False, "language_specific_not_available"
        return True, "ok"

    for i, ch in enumerate(s):
        if start <= i <= end:
            continue
        if ch in "?!":
            return False, "internal_question_or_exclamation"
        if ch == "." and not is_safe_internal_dot(s, i):
            return False, "unsafe_internal_dot"

    return True, "ok"


def clean_parts(parts: Iterable[str]) -> list[str]:
    return [normalize_space(part) for part in parts if normalize_space(part)]


def parts_equal(left: Sequence[str], right: Sequence[str]) -> bool:
    return [normalize_space(x) for x in left] == [normalize_space(x) for x in right]


def split_with_nltk(text: str, language: str) -> list[str]:
    nltk_language = NLTK_LANGUAGE_BY_TATOEBA[normalize_language_code(language)]
    return clean_parts(sent_tokenize(text, language=nltk_language))


def split_with_stanza(nlp, text: str) -> list[str]:
    doc = nlp(text)
    return clean_parts(sentence.text for sentence in doc.sentences)


def reconstruction_matches(original: str, parts: Sequence[str]) -> bool:
    return normalize_space(" ".join(parts)) == normalize_space(original)


def classify_text(text: str, nlp_holder: dict[str, object], language: str = "eng") -> SplitResult:
    language = normalize_language_code(language)
    s = normalize_space(text)
    if not s:
        return SplitResult([], "none", "empty")

    general_ok, general_reason = validate_general_text(s)
    if not general_ok:
        return SplitResult([], "general", general_reason)

    simple_ok, simple_reason = validate_single_sentence(s, language)
    if simple_ok:
        return SplitResult([s], f"rules:{language}", "accepted_simple")

    if language not in NLTK_LANGUAGE_BY_TATOEBA or language not in STANZA_LANGUAGE_BY_TATOEBA:
        return SplitResult([], f"rules:{language}", simple_reason)

    nltk_parts = split_with_nltk(s, language)
    if not nltk_parts:
        return SplitResult([], "nltk", "nltk_empty")

    needs_stanza = has_internal_terminator(s) or len(nltk_parts) != 1
    if not needs_stanza:
        if simple_ok and reconstruction_matches(s, nltk_parts):
            return SplitResult([s], "rules+nltk", "accepted_simple")
        return SplitResult([], "rules+nltk", simple_reason)

    if nlp_holder.get("pipeline") is None:
        import stanza

        nlp_holder["pipeline"] = stanza.Pipeline(
            lang=STANZA_LANGUAGE_BY_TATOEBA[language],
            processors="tokenize",
            model_dir=str(DEFAULT_STANZA_MODEL_DIR.resolve()),
            download_method=None,
            tokenize_no_ssplit=False,
            verbose=False,
        )

    stanza_parts = split_with_stanza(nlp_holder["pipeline"], s)

    if not parts_equal(nltk_parts, stanza_parts):
        detail = {
            "nltk": nltk_parts,
            "stanza": stanza_parts,
        }
        return SplitResult([], "nltk+stanza", "tokenizer_disagreement:" + json.dumps(detail, ensure_ascii=False))

    parts = nltk_parts
    if not reconstruction_matches(s, parts):
        return SplitResult([], "nltk+stanza", "reconstruction_mismatch")

    rejected_reasons = []
    for part in parts:
        ok, reason = validate_single_sentence(part, language)
        if not ok:
            rejected_reasons.append(reason)

    if rejected_reasons:
        return SplitResult([], "nltk+stanza", "part_rejected:" + ",".join(sorted(set(rejected_reasons))))

    reason = "accepted_split_agree" if len(parts) > 1 else "accepted_single_agree"
    return SplitResult(parts, "nltk+stanza", reason)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_rows (
            source_id INTEGER PRIMARY KEY,
            input_line INTEGER NOT NULL,
            original_text TEXT NOT NULL,
            status TEXT NOT NULL,
            method TEXT NOT NULL,
            reason TEXT NOT NULL,
            processed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clean_sentences (
            source_id INTEGER NOT NULL,
            part_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            decision TEXT NOT NULL,
            PRIMARY KEY (source_id, part_index)
        );
        CREATE INDEX IF NOT EXISTS idx_source_rows_status ON source_rows(status);
        CREATE INDEX IF NOT EXISTS idx_clean_sentences_decision ON clean_sentences(decision);
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    return conn


def get_last_input_line(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM metadata WHERE key='last_input_line'").fetchone()
    return int(row[0]) if row else 0


def set_last_input_line(conn: sqlite3.Connection, line_number: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('last_input_line', ?)",
        (str(line_number),),
    )


def set_complete(conn: sqlite3.Connection, complete: bool) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('complete', ?)",
        ("1" if complete else "0",),
    )


def write_result(
    conn: sqlite3.Connection,
    source_id: int,
    input_line: int,
    original_text: str,
    result: SplitResult,
) -> None:
    status = "accepted" if result.parts else "rejected"
    conn.execute(
        """
        INSERT OR REPLACE INTO source_rows
            (source_id, input_line, original_text, status, method, reason, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (source_id, input_line, original_text, status, result.method, result.reason, time.time()),
    )
    conn.execute("DELETE FROM clean_sentences WHERE source_id = ?", (source_id,))
    for idx, part in enumerate(result.parts):
        decision = "split" if len(result.parts) > 1 else "single"
        conn.execute(
            """
            INSERT OR REPLACE INTO clean_sentences(source_id, part_index, text, decision)
            VALUES (?, ?, ?, ?)
            """,
            (source_id, idx, part, decision),
        )


def iter_tatoeba_rows(path: Path, start_after_line: int) -> Iterable[tuple[int, int, str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for input_line, row in enumerate(reader, start=1):
            if input_line <= start_after_line:
                continue
            if len(row) != 3:
                continue
            source_id_raw, lang, text = row
            try:
                source_id = int(source_id_raw)
            except ValueError:
                continue
            yield input_line, source_id, lang, text


def command_clean(args: argparse.Namespace) -> None:
    target_language = normalize_language_code(args.language)
    max_target_rows = args.max_rows
    if args.max_english is not None:
        max_target_rows = args.max_english

    conn = connect(args.db)
    last_input_line = get_last_input_line(conn)
    nlp_holder: dict[str, object] = {}
    counters: Counter[str] = Counter()
    processed_target = 0
    last_committed_line = last_input_line
    started = time.perf_counter()

    print(f"target_language={target_language}", flush=True)
    print(f"resume_after_input_line={last_input_line}", flush=True)
    try:
        conn.execute("BEGIN")
        for input_line, source_id, lang, text in iter_tatoeba_rows(args.input, last_input_line):
            last_committed_line = input_line
            if lang != target_language:
                set_last_input_line(conn, input_line)
                if input_line % args.commit_every == 0:
                    conn.commit()
                    conn.execute("BEGIN")
                continue

            result = classify_text(text, nlp_holder, target_language)
            write_result(conn, source_id, input_line, text, result)
            counters["target_processed"] += 1
            counters["accepted" if result.parts else "rejected"] += 1
            if len(result.parts) > 1:
                counters["split_source_rows"] += 1
                counters["split_output_sentences"] += len(result.parts)
            counters[result.reason.split(":", 1)[0]] += 1
            processed_target += 1

            set_last_input_line(conn, input_line)
            if processed_target % args.report_every == 0:
                elapsed = time.perf_counter() - started
                rate = processed_target / elapsed if elapsed else 0.0
                print(
                    "progress "
                    f"target_this_run={processed_target} "
                    f"input_line={input_line} "
                    f"accepted={counters['accepted']} "
                    f"rejected={counters['rejected']} "
                    f"split_rows={counters['split_source_rows']} "
                    f"rate={rate:.1f}/s",
                    flush=True,
                )
            if processed_target % args.commit_every == 0:
                conn.commit()
                conn.execute("BEGIN")

            if max_target_rows and processed_target >= max_target_rows:
                set_complete(conn, False)
                conn.commit()
                print("stopped=max_rows", flush=True)
                break
        else:
            set_complete(conn, True)
            conn.commit()
            print("stopped=eof", flush=True)
    except KeyboardInterrupt:
        conn.rollback()
        print("interrupted; last committed work remains in sqlite", file=sys.stderr, flush=True)
        raise
    finally:
        elapsed = time.perf_counter() - started
        print(
            f"processed_target_this_run={processed_target} "
            f"last_seen_input_line={last_committed_line} "
            f"elapsed_seconds={elapsed:.1f}",
            flush=True,
        )
        conn.close()


def command_stats(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    stats = {}
    stats["source_rows"] = conn.execute("SELECT COUNT(*) FROM source_rows").fetchone()[0]
    stats["accepted_source_rows"] = conn.execute(
        "SELECT COUNT(*) FROM source_rows WHERE status='accepted'"
    ).fetchone()[0]
    stats["rejected_source_rows"] = conn.execute(
        "SELECT COUNT(*) FROM source_rows WHERE status='rejected'"
    ).fetchone()[0]
    stats["clean_sentences"] = conn.execute("SELECT COUNT(*) FROM clean_sentences").fetchone()[0]
    stats["split_source_rows"] = conn.execute(
        "SELECT COUNT(*) FROM source_rows WHERE reason='accepted_split_agree'"
    ).fetchone()[0]
    stats["last_input_line"] = get_last_input_line(conn)
    complete = conn.execute("SELECT value FROM metadata WHERE key='complete'").fetchone()
    stats["complete"] = complete[0] if complete else "0"
    reason_rows = conn.execute(
        """
        SELECT
            CASE
                WHEN instr(reason, ':') > 0 THEN substr(reason, 1, instr(reason, ':') - 1)
                ELSE reason
            END AS reason_group,
            COUNT(*)
        FROM source_rows
        GROUP BY reason_group
        ORDER BY COUNT(*) DESC
        LIMIT 25
        """
    ).fetchall()
    print(json.dumps(stats, indent=2, sort_keys=True))
    print("top_reasons")
    for reason, count in reason_rows:
        print(f"{count}\t{reason}")
    conn.close()


def command_export(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["source_id", "part_index", "decision", "text"])
        for row in conn.execute(
            """
            SELECT source_id, part_index, decision, text
            FROM clean_sentences
            ORDER BY source_id, part_index
            """
        ):
            writer.writerow(row)

    with args.reject_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["source_id", "status", "method", "reason", "original_text"])
        for row in conn.execute(
            """
            SELECT source_id, status, method, reason, original_text
            FROM source_rows
            WHERE status = 'rejected'
            ORDER BY source_id
            """
        ):
            writer.writerow(row)

    print(f"exported_clean={args.output}")
    print(f"exported_rejects={args.reject_output}")
    conn.close()


def command_audit(args: argparse.Namespace) -> None:
    language = normalize_language_code(args.language)
    conn = connect(args.db)
    total = conn.execute("SELECT COUNT(*) FROM clean_sentences").fetchone()[0]
    if total < args.sample_size:
        raise SystemExit(f"not enough clean sentences for audit: {total} < {args.sample_size}")

    rng = random.Random(args.seed)
    offsets = sorted(rng.sample(range(total), args.sample_size))
    failures = []
    rows = []
    for offset in offsets:
        row = conn.execute(
            """
            SELECT source_id, part_index, decision, text
            FROM clean_sentences
            ORDER BY source_id, part_index
            LIMIT 1 OFFSET ?
            """,
            (offset,),
        ).fetchone()
        source_id, part_index, decision, text = row
        ok, reason = validate_single_sentence(text, language)
        rows.append((source_id, part_index, decision, reason, text))
        if not ok:
            failures.append((source_id, part_index, reason, text))

    print(f"audit_seed={args.seed}")
    print(f"audit_sample_size={args.sample_size}")
    print(f"audit_failures={len(failures)}")
    for source_id, part_index, decision, reason, text in rows:
        print(f"{source_id}\t{part_index}\t{decision}\t{reason}\t{text}")

    if failures:
        raise SystemExit(1)
    conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)

    subparsers = parser.add_subparsers(dest="command", required=True)

    clean = subparsers.add_parser("clean")
    clean.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    clean.add_argument("--language", default="en")
    clean.add_argument("--max-rows", type=int, default=0)
    clean.add_argument("--max-english", type=int, default=None, help=argparse.SUPPRESS)
    clean.add_argument("--commit-every", type=int, default=1000)
    clean.add_argument("--report-every", type=int, default=10000)
    clean.set_defaults(func=command_clean)

    stats = subparsers.add_parser("stats")
    stats.set_defaults(func=command_stats)

    export = subparsers.add_parser("export")
    export.add_argument("--output", type=Path, default=DEFAULT_EXPORT)
    export.add_argument("--reject-output", type=Path, default=DEFAULT_REJECT_EXPORT)
    export.set_defaults(func=command_export)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--language", default="en")
    audit.add_argument("--sample-size", type=int, default=100)
    audit.add_argument("--seed", type=int, default=20260620)
    audit.set_defaults(func=command_audit)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

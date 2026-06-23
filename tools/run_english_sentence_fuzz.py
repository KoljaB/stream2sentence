"""Run a long English sentence-boundary fuzz test.

The test builds random two- or three-sentence documents from the cleaned
Tatoeba English corpus, streams each document character by character through
stream2sentence, and writes every mismatch immediately to a JSONL file.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from stream2sentence import generate_sentences


DEFAULT_DATASET = Path("downloads/tatoeba/cleaned_eng_v1/eng_clean_single_sentences.tsv")
DEFAULT_FAILURE_FILE = Path("downloads/tatoeba/cleaned_eng_v1/english_sentence_fuzz_failures.jsonl")


@dataclass(frozen=True)
class SentenceRow:
    source_id: str
    part_index: str
    decision: str
    text: str


def char_stream(text: str) -> Iterable[str]:
    for char in text:
        yield char


def load_sentences(path: Path, max_sentence_chars: int) -> list[SentenceRow]:
    sentences: list[SentenceRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"source_id", "part_index", "decision", "text"}
        if set(reader.fieldnames or []) < required:
            raise ValueError(f"{path} must contain columns: {sorted(required)}")

        for row in reader:
            text = row["text"].strip()
            if not text or len(text) > max_sentence_chars:
                continue
            sentences.append(
                SentenceRow(
                    source_id=row["source_id"],
                    part_index=row["part_index"],
                    decision=row["decision"],
                    text=text,
                )
            )

    if len(sentences) < 3:
        raise ValueError(f"Need at least 3 usable sentences in {path}, found {len(sentences)}")

    return sentences


def run_case(rows: Sequence[SentenceRow]) -> list[str]:
    text = " ".join(row.text for row in rows)
    return list(
        generate_sentences(
            char_stream(text),
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=24,
            tokenizer="rule-based",
            language="en",
        )
    )


def write_failure(handle, failure: dict) -> None:
    handle.write(json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def command_run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    rng = random.Random(args.seed)
    rows = load_sentences(args.dataset, args.max_sentence_chars)
    load_finished = time.monotonic()

    args.failure_file.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"

    cases = 0
    failures = 0
    successes = 0
    deadline = time.monotonic() + args.duration_seconds
    last_report = time.monotonic()

    print(f"dataset={args.dataset}")
    print(f"usable_sentences={len(rows)}")
    print(f"seed={args.seed}")
    print(f"duration_seconds={args.duration_seconds}")
    print(f"failure_file={args.failure_file}")
    print(f"load_seconds={load_finished - started:.3f}")

    with args.failure_file.open(mode, encoding="utf-8", newline="\n") as failure_handle:
        while time.monotonic() < deadline:
            cases += 1
            sentence_count = rng.choice((2, 3))
            selected = rng.sample(rows, sentence_count)
            expected = [row.text for row in selected]
            input_text = " ".join(expected)
            actual: list[str] | None = None
            exception = None

            try:
                actual = run_case(selected)
            except Exception as exc:  # pragma: no cover - failure report path
                exception = repr(exc)

            if actual != expected:
                failures += 1
                write_failure(
                    failure_handle,
                    {
                        "case_index": cases,
                        "elapsed_seconds": round(time.monotonic() - started, 6),
                        "seed": args.seed,
                        "source_rows": [
                            {
                                "source_id": row.source_id,
                                "part_index": row.part_index,
                                "decision": row.decision,
                            }
                            for row in selected
                        ],
                        "input": input_text,
                        "expected": expected,
                        "actual": actual,
                        "exception": exception,
                    },
                )
            else:
                successes += 1

            if args.max_cases and cases >= args.max_cases:
                break

            now = time.monotonic()
            if now - last_report >= args.report_every_seconds:
                rate = cases / (now - load_finished) if now > load_finished else 0.0
                print(
                    f"progress green={successes} red={failures} cases={cases} "
                    f"elapsed_seconds={now - started:.1f} rate={rate:.1f}/s",
                    flush=True,
                )
                last_report = now

    elapsed = time.monotonic() - started
    print(
        f"done green={successes} red={failures} cases={cases} elapsed_seconds={elapsed:.3f} "
        f"failure_file={args.failure_file}",
        flush=True,
    )
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--duration-seconds", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=20260620)
    parser.add_argument("--failure-file", type=Path, default=DEFAULT_FAILURE_FILE)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-sentence-chars", type=int, default=240)
    parser.add_argument("--report-every-seconds", type=float, default=10.0)
    parser.set_defaults(func=command_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Watch sentence splitting of the punctuation-heavy fixture in real time."""

import argparse
import importlib
from pathlib import Path
import shutil
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


TOKENIZER_CHOICES = ("nltk+rule-based", "consensus", "rule-based", "nltk", "stanza")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tokenizer",
        choices=TOKENIZER_CHOICES,
        default="nltk+rule-based",
        help="sentence tokenizer to run in the visual splitter",
    )
    parser.add_argument(
        "--auto-context",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="yield safe boundaries before the fixed context window when possible",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="seconds to sleep after printing each streamed character",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print match counts to stderr after the live sentence display",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    import nltk

    def char_stream(text):
        for char in text:
            pending_chars.append(char)
            if live_mode:
                print_live_char(char)
            if live_mode and args.delay > 0:
                time.sleep(args.delay)
            yield char

    def print_live_char(char):
        if char != "\n" and stream_state["column"] >= terminal_width - 1:
            print()
            stream_state["rows"] += 1
            stream_state["column"] = 0
        print(char, end="", flush=True)
        if char == "\n":
            stream_state["rows"] += 1
            stream_state["column"] = 0
        else:
            stream_state["column"] += 1

    def print_live_text(text):
        for char in text:
            print_live_char(char)

    def take_replay_tail(sentence):
        pending_text = "".join(pending_chars)
        sentence_start = pending_text.find(sentence)
        if sentence_start == -1:
            pending_chars.clear()
            return ""

        tail = pending_text[sentence_start + len(sentence) :]
        if tail[:1].isspace():
            tail = tail[1:]
        pending_chars[:] = tail
        return tail

    def redraw_live_fragment(sentence, replay_tail):
        clear_live_fragment()
        print_live_text(sentence)
        print()
        stream_state["rows"] = 0
        stream_state["column"] = 0
        if replay_tail:
            print_live_text(replay_tail)

    def clear_live_fragment():
        rows = stream_state["rows"]
        if rows:
            print(f"\x1b[{rows}F", end="")
        print("\r\x1b[J", end="", flush=True)
        stream_state["rows"] = 0
        stream_state["column"] = 0

    nltk_download = nltk.download
    nltk.download = lambda *args, **kwargs: True

    from stream2sentence import generate_sentences
    from tests.test_stream2sentence import (
        CONSENSUS_STRESS_EXPECTED,
        CONSENSUS_STRESS_INPUT,
    )

    stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
    nltk_initialized = stream2sentence_module.nltk_initialized
    initialize_nltk = stream2sentence_module.initialize_nltk
    stream2sentence_module.nltk_initialized = True
    stream2sentence_module.initialize_nltk = lambda *args, **kwargs: None
    live_mode = sys.stdout.isatty()
    terminal_width = max(shutil.get_terminal_size((100, 20)).columns, 20)
    stream_state = {"column": 0, "rows": 0}
    pending_chars = []
    sentences = []
    try:
        for sentence in generate_sentences(
            char_stream(CONSENSUS_STRESS_INPUT),
            tokenizer=args.tokenizer,
            language="en",
            minimum_sentence_length=1,
            context_size=12,
            context_size_look_overhead=64,
            auto_context=args.auto_context,
        ):
            sentences.append(sentence)
            replay_tail = take_replay_tail(sentence)
            if live_mode:
                redraw_live_fragment(sentence, replay_tail)
            else:
                print(sentence)
    finally:
        stream2sentence_module.nltk_initialized = nltk_initialized
        stream2sentence_module.initialize_nltk = initialize_nltk
        nltk.download = nltk_download

    if live_mode and stream_state["column"]:
        print()

    if args.summary:
        print("--- summary ---", file=sys.stderr)
        print(
            f"actual_count={len(sentences)} expected_count={len(CONSENSUS_STRESS_EXPECTED)}",
            file=sys.stderr,
        )
        print(f"matches_expected={sentences == CONSENSUS_STRESS_EXPECTED}", file=sys.stderr)

    if sentences == CONSENSUS_STRESS_EXPECTED:
        return 0

    print("--- mismatch ---", file=sys.stderr)
    print(
        f"actual_count={len(sentences)} expected_count={len(CONSENSUS_STRESS_EXPECTED)}",
        file=sys.stderr,
    )
    print("--- expected ---", file=sys.stderr)
    for index, sentence in enumerate(CONSENSUS_STRESS_EXPECTED, start=1):
        print(f"{index}. {sentence}", file=sys.stderr)
        print(file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

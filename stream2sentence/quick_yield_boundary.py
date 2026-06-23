"""
Context checks for low-latency sentence fragment boundaries.
"""

import json
import os
import unicodedata
from functools import lru_cache


SPLIT = "split"
HOLD = "hold"
REJECT = "reject"

_OPENING_MARKS = "\"'([{“‘«‹"
_CLOSING_MARKS = "\"')]}”’»›"

_EN_AMBIGUOUS_ABBREVIATIONS = {
    "a.d.",
    "a.m.",
    "art.",
    "arts.",
    "b.c.",
    "p.m.",
    "fig.",
    "figs.",
    "jr.",
    "ex.",
    "miss.",
    "no.",
    "p.",
    "sun.",
    "u.s.",
    "u.s.a.",
    "u.k.",
    "u.n.",
    "e.u.",
    "d.c.",
    "wed.",
}

_EN_SINGLE_TOKEN_ABBREVIATIONS = {
    "adm.",
    "amb.",
    "apr.",
    "approx.",
    "art.",
    "arts.",
    "assoc.",
    "assn.",
    "atty.",
    "aug.",
    "ave.",
    "bldg.",
    "blvd.",
    "bros.",
    "capt.",
    "cf.",
    "ch.",
    "chap.",
    "chaps.",
    "cmdr.",
    "co.",
    "col.",
    "corp.",
    "cpl.",
    "ct.",
    "dec.",
    "dept.",
    "det.",
    "div.",
    "dr.",
    "ed.",
    "eds.",
    "eq.",
    "eqs.",
    "esq.",
    "etc.",
    "ex.",
    "feb.",
    "fig.",
    "figs.",
    "fri.",
    "gen.",
    "gov.",
    "hwy.",
    "ibid.",
    "inc.",
    "incl.",
    "insp.",
    "jan.",
    "jr.",
    "jun.",
    "ln.",
    "ltd.",
    "lt.",
    "maj.",
    "mar.",
    "max.",
    "min.",
    "miss.",
    "mon.",
    "mr.",
    "mrs.",
    "ms.",
    "mt.",
    "no.",
    "nos.",
    "nov.",
    "ofc.",
    "p.",
    "pkwy.",
    "pl.",
    "pp.",
    "pres.",
    "prof.",
    "pvt.",
    "rd.",
    "ref.",
    "refs.",
    "rep.",
    "rev.",
    "rm.",
    "sat.",
    "sec.",
    "secs.",
    "sen.",
    "sep.",
    "sept.",
    "sgt.",
    "sr.",
    "st.",
    "ste.",
    "sun.",
    "ter.",
    "thu.",
    "thur.",
    "thurs.",
    "trans.",
    "tue.",
    "tues.",
    "univ.",
    "viz.",
    "vol.",
    "vols.",
    "vs.",
    "wed.",
}

_EN_EXTRA_ABBREVIATIONS = {
    "apt.",
    "apr.",
    "b.c.",
    "ca.",
    "et al.",
    "cir.",
    "ext.",
    "fn.",
    "loc.",
    "loc. cit.",
    "op.",
    "op. cit.",
    "jul.",
    "oct.",
}

_EN_INITIALISM_CONTINUATION_WORDS = {
    "air",
    "army",
    "congress",
    "department",
    "embassy",
    "federal",
    "forces",
    "government",
    "navy",
    "senate",
}

# Exact fixed-title continuations only; "Who?" still splits unless followed by
# "Weekly", and "Yahoo!" still splits unless followed by "Finance".
_EN_PUNCTUATED_NAME_CONTINUATIONS = {
    "who?": {"weekly"},
    "yahoo!": {"finance"},
}


_LANGUAGE_CONTEXTS = None


def _load_language_contexts():
    global _LANGUAGE_CONTEXTS
    if _LANGUAGE_CONTEXTS is None:
        path = os.path.join(os.path.dirname(__file__), "data", "language_contexts.json")
        with open(path, encoding="utf-8") as file:
            _LANGUAGE_CONTEXTS = json.load(file)
    return _LANGUAGE_CONTEXTS


def _normalize_language(language):
    contexts = _load_language_contexts()
    language = (language or contexts["default_language"]).lower()

    for code, context in contexts["languages"].items():
        aliases = [code] + context.get("aliases", [])
        if language in aliases:
            return code

    return contexts["default_language"]


def _is_mark(char):
    return unicodedata.category(char).startswith("M")


def _keep_english_abbreviation(abbreviation):
    abbreviation = abbreviation.casefold()
    if abbreviation in {"ok.", "okay."}:
        return False
    if abbreviation in _EN_EXTRA_ABBREVIATIONS:
        return True
    if abbreviation.count(".") > 1:
        return True
    return abbreviation in _EN_SINGLE_TOKEN_ABBREVIATIONS


@lru_cache(maxsize=None)
def _language_detector_config(language):
    contexts = _load_language_contexts()
    language = _normalize_language(language)
    generic = contexts["languages"]["generic"]
    language_context = contexts["languages"][language]

    abbreviations = generic.get("abbreviations", []) + language_context.get("abbreviations", [])
    abbreviations = [abbreviation.casefold() for abbreviation in abbreviations]
    if language == "en":
        abbreviations.extend(_EN_EXTRA_ABBREVIATIONS)
        abbreviations = [
            abbreviation for abbreviation in abbreviations
            if _keep_english_abbreviation(abbreviation)
        ]

    return (
        language,
        tuple(sorted(set(abbreviations), key=len, reverse=True)),
        frozenset(generic.get("currency_symbols", [])),
    )


@lru_cache(maxsize=None)
def get_boundary_detector(language="en"):
    return QuickYieldBoundaryDetector(language)


class QuickYieldBoundaryDetector:
    """Decides if a fragment delimiter is safe to yield immediately."""

    def __init__(self, language="en"):
        self.language, self.abbreviations, self.currency_symbols = _language_detector_config(language)

    def classify(self, buffer, delimiter_index, next_char=None):
        delimiter = buffer[delimiter_index]

        if delimiter in "\n\u3002\uff01":
            return SPLIT

        if delimiter == "!":
            return self._classify_punctuated_name(buffer, delimiter_index)

        if delimiter in "?\uff1f":
            return self._classify_question_mark(buffer, delimiter_index, next_char)

        if delimiter in ")]}":
            return REJECT if self._closes_bracketed_value(buffer, delimiter_index) else SPLIT

        if delimiter == ".":
            return self._classify_period(buffer, delimiter_index, next_char)

        if delimiter == ",":
            return self._classify_comma(buffer, delimiter_index, next_char)

        if delimiter == ":":
            return self._classify_colon(buffer, delimiter_index, next_char)

        if delimiter == "-":
            return self._classify_hyphen(next_char)

        return SPLIT

    def _classify_period(self, buffer, delimiter_index, next_char):
        left = buffer[: delimiter_index + 1]
        abbreviation = self._matching_abbreviation(left)
        if abbreviation:
            if next_char is not None and self._continues_token(next_char):
                return REJECT
            if abbreviation in _EN_AMBIGUOUS_ABBREVIATIONS:
                return self._classify_ambiguous_abbreviation(buffer, delimiter_index, abbreviation)
            return REJECT

        token = self._current_token(left)
        if next_char is not None and self._continues_token(next_char):
            return REJECT
        if self.language == "en" and self._is_dotted_initialism(token):
            return self._classify_dotted_initialism(buffer, delimiter_index, token)

        if next_char is None:
            return HOLD

        return REJECT if self._continues_token(next_char) else SPLIT

    def _classify_question_mark(self, buffer, delimiter_index, next_char):
        if not self._inside_url_token(buffer, delimiter_index):
            punctuated_name_action = self._classify_punctuated_name(buffer, delimiter_index)
            if punctuated_name_action != SPLIT:
                return punctuated_name_action
            return SPLIT

        if next_char is None:
            return HOLD
        return REJECT if self._continues_token(next_char) else SPLIT

    def _classify_punctuated_name(self, buffer, delimiter_index):
        if self.language != "en":
            return SPLIT

        key = self._current_token(buffer[:delimiter_index + 1]).strip(
            _OPENING_MARKS + _CLOSING_MARKS + ".,;:"
        ).casefold()
        continuations = _EN_PUNCTUATED_NAME_CONTINUATIONS.get(key)
        if not continuations:
            return SPLIT

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not ended and clean_token.casefold() not in continuations:
            return HOLD
        return REJECT if clean_token.casefold() in continuations else SPLIT

    def _classify_comma(self, buffer, delimiter_index, next_char):
        previous = self._previous_char(buffer, delimiter_index)

        if previous and previous.isdigit():
            if ":" in self._current_token(buffer[:delimiter_index]):
                return REJECT
            if next_char is None:
                return HOLD
            return REJECT if next_char.isdigit() else SPLIT

        return SPLIT

    def _classify_colon(self, buffer, delimiter_index, next_char):
        previous = self._previous_char(buffer, delimiter_index)

        if previous and (self._is_token_char(previous) or previous in ":/]"):
            if next_char is None:
                return HOLD
            return REJECT if self._continues_token(next_char) else SPLIT

        return SPLIT

    def _classify_hyphen(self, next_char):
        if next_char is None:
            return HOLD
        return REJECT if self._continues_token(next_char) else SPLIT

    def _matching_abbreviation(self, text):
        folded = text.casefold()
        for abbreviation in self.abbreviations:
            if not folded.endswith(abbreviation):
                continue

            prefix = folded[: -len(abbreviation)]
            if not prefix:
                return abbreviation

            previous = prefix[-1]
            if previous.isspace() or previous in _OPENING_MARKS + "/":
                return abbreviation
            if abbreviation in _EN_AMBIGUOUS_ABBREVIATIONS and previous.isdigit():
                return abbreviation

            if abbreviation.isascii() and not previous.isascii():
                return abbreviation

        return None

    def _ends_with_abbreviation(self, text):
        return self._matching_abbreviation(text) is not None

    def _classify_ambiguous_abbreviation(self, buffer, delimiter_index, abbreviation):
        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = clean_token.casefold()
        if not ended and len(folded) < 3:
            return HOLD
        if abbreviation.count(".") > 1 and not ended:
            return HOLD
        if (
            abbreviation.count(".") > 1
            and folded in _EN_INITIALISM_CONTINUATION_WORDS
        ):
            return REJECT
        if abbreviation == "no." and len(clean_token) == 1 and clean_token.isupper():
            return REJECT
        if clean_token[0].islower() or clean_token[0].isdigit():
            return REJECT
        return SPLIT

    def _next_token(self, buffer, delimiter_index):
        right = buffer[delimiter_index + 1:]
        if not right or right.isspace():
            return None, False

        right = right.lstrip().lstrip(_OPENING_MARKS).lstrip()
        if not right:
            return None, False

        end = 0
        while (
            end < len(right)
            and not right[end].isspace()
            and right[end] not in ".?!;:,)]}"
        ):
            end += 1

        return right[:end], end < len(right)

    def _classify_dotted_initialism(self, buffer, delimiter_index, current_token):
        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD
        if not ended and len(clean_token) < 2:
            return HOLD

        previous = self._previous_token_before_current(buffer[:delimiter_index + 1])
        if len(clean_token) == 1 and clean_token.isupper():
            right = buffer[delimiter_index + 1:].lstrip().lstrip(_OPENING_MARKS).lstrip()
            if len(right) > len(token) and right[len(token)] == ".":
                return REJECT
        if current_token.count(".") > 1:
            return REJECT

        if previous[:1].isupper() and clean_token[:1].isupper():
            return REJECT

        return SPLIT

    @staticmethod
    def _is_dotted_initialism(token):
        parts = token.split(".")
        return (
            len(parts) >= 2
            and parts[-1] == ""
            and all(len(part) == 1 and part.isalpha() for part in parts[:-1])
        )

    @staticmethod
    def _previous_token_before_current(text):
        before_current = text.rstrip().rsplit(None, 1)
        if len(before_current) < 2:
            return ""
        return before_current[0].rsplit(None, 1)[-1].strip(_OPENING_MARKS + _CLOSING_MARKS)

    def _closes_bracketed_value(self, buffer, delimiter_index):
        delimiter = buffer[delimiter_index]
        opener = {"}": "{", "]": "[", ")": "("}[delimiter]
        left = buffer[:delimiter_index]

        return left.rfind(opener) > left.rfind(delimiter)

    def _continues_token(self, char):
        return self._is_token_char(char) or char in "./:-\\?"

    def _is_token_char(self, char):
        return (
            char.isalnum()
            or _is_mark(char)
            or char in self.currency_symbols
            or char in "_/@#%+=~\\&"
        )

    def _inside_url_token(self, buffer, delimiter_index):
        token = self._current_token(buffer[:delimiter_index + 1])
        return "://" in token

    @staticmethod
    def _current_token(text):
        return text.rsplit(None, 1)[-1]

    @staticmethod
    def _previous_char(buffer, delimiter_index):
        if delimiter_index == 0:
            return None
        return buffer[delimiter_index - 1]

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
_TERMINAL_MARKS = ".?!？"

_EN_AMBIGUOUS_ABBREVIATIONS = {
    "a.d.",
    "a.m.",
    "art.",
    "arts.",
    "b.c.",
    "corp.",
    "etc.",
    "p.m.",
    "fig.",
    "figs.",
    "gmbh.",
    "inc.",
    "jr.",
    "llc.",
    "llp.",
    "ltd.",
    "ex.",
    "miss.",
    "no.",
    "p.",
    "plc.",
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
    "defn.",
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
    "gmbh.",
    "gov.",
    "hon.",
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
    "llc.",
    "llp.",
    "lt.",
    "maj.",
    "mar.",
    "max.",
    "min.",
    "miss.",
    "mgr.",
    "mon.",
    "mr.",
    "mrs.",
    "ms.",
    "mx.",
    "mt.",
    "no.",
    "nos.",
    "nov.",
    "ofc.",
    "p.",
    "pfc.",
    "pkwy.",
    "pl.",
    "plc.",
    "pp.",
    "pres.",
    "prof.",
    "pvt.",
    "pty.",
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
    "sfc.",
    "sgt.",
    "spec.",
    "sr.",
    "st.",
    "ste.",
    "sun.",
    "supt.",
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
    "adj.",
    "apt.",
    "apr.",
    "b.c.",
    "br.",
    "ca.",
    "comm.",
    "et al.",
    "cir.",
    "ext.",
    "fn.",
    "fr.",
    "gmbh.",
    "loc.",
    "loc. cit.",
    "llc.",
    "llp.",
    "op.",
    "op. cit.",
    "plc.",
    "pty.",
    "jul.",
    "oct.",
}

_EN_INITIALISM_CONTINUATION_WORDS = {
    "american",
    "americans",
    "air",
    "army",
    "bureau",
    "congress",
    "department",
    "embassy",
    "federal",
    "forces",
    "government",
    "marshal",
    "marshalls",
    "marshals",
    "national",
    "navy",
    "senate",
    "secretary",
    "secretary-general",
}

_EN_INITIALISM_CONTINUATION_FIRST_WORDS = {
    "d.c.": {
        "bar",
        "circuit",
        "code",
        "council",
        "court",
        "district",
        "fire",
        "health",
        "housing",
        "jail",
        "library",
        "lottery",
        "metro",
        "police",
        "public",
        "superior",
        "united",
        "water",
    },
    "e.u.": {
        "agency",
        "ai",
        "artificial",
        "aviation",
        "banking",
        "battery",
        "border",
        "carbon",
        "central",
        "chips",
        "commission",
        "council",
        "court",
        "critical",
        "cyber",
        "data",
        "delegation",
        "digital",
        "drug",
        "emissions",
        "foreign",
        "fundamental",
        "general",
        "green",
        "insurance",
        "member",
        "merger",
        "net",
        "ombudsman",
        "parliament",
        "securities",
        "single",
        "space",
        "taxonomy",
    },
    "u.k.": {
        "atomic",
        "biobank",
        "border",
        "cabinet",
        "competition",
        "conservative",
        "civil",
        "crown",
        "export",
        "financial",
        "finance",
        "foreign",
        "health",
        "home",
        "house",
        "infrastructure",
        "intellectual",
        "labour",
        "ministry",
        "office",
        "parliament",
        "prime",
        "research",
        "space",
        "statistics",
        "supreme",
    },
    "u.n.": {
        "administrative",
        "appeals",
        "atlas",
        "charter",
        "children's",
        "climate",
        "commission",
        "conference",
        "convention",
        "development",
        "disarmament",
        "economic",
        "educational",
        "environmental",
        "environment",
        "food",
        "framework",
        "forum",
        "general",
        "global",
        "habitat",
        "high",
        "human",
        "international",
        "migration",
        "mission",
        "office",
        "peacebuilding",
        "peacekeeping",
        "permanent",
        "population",
        "protocol",
        "refugee",
        "relief",
        "security",
        "secretariat",
        "special",
        "statistical",
        "treaty",
        "trusteeship",
        "university",
        "volunteers",
        "water",
        "women",
        "world",
    },
    "u.s.": {
        "agency",
        "airways",
        "anti-doping",
        "attorney",
        "atty",
        "bank",
        "bankruptcy",
        "bancorp",
        "botanic",
        "capitol",
        "cellular",
        "central",
        "census",
        "chamber",
        "civil",
        "centers",
        "coast",
        "conference",
        "constitution",
        "consumer",
        "court",
        "customs",
        "cyber",
        "democratic",
        "district",
        "east",
        "education",
        "endangered",
        "environmental",
        "figure",
        "fish",
        "food",
        "forest",
        "geological",
        "holocaust",
        "house",
        "international",
        "justice",
        "labor",
        "marine",
        "marines",
        "memory",
        "men's",
        "military",
        "minerals",
        "mint",
        "naval",
        "news",
        "olympic",
        "open",
        "park",
        "patent",
        "postal",
        "president",
        "public",
        "republican",
        "securities",
        "secret",
        "soccer",
        "space",
        "state",
        "steel",
        "strategic",
        "supreme",
        "small",
        "ski",
        "library",
        "rowing",
        "cycling",
        "track",
        "tax",
        "trade",
        "treasury",
        "virgin",
        "vice",
        "west",
        "women's",
    },
    "u.s.a.": {
        "archery",
        "baseball",
        "basketball",
        "cycling",
        "fencing",
        "gymnastics",
        "hockey",
        "rowing",
        "soccer",
        "softball",
        "swimming",
        "track",
        "volleyball",
        "water",
        "wrestling",
    },
}

_EN_TIME_ABBREVIATION_CONTINUATIONS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}

_EN_TIME_ZONE_CONTINUATIONS = {
    "acdt",
    "acst",
    "aedt",
    "aest",
    "akdt",
    "akst",
    "awst",
    "bst",
    "cdt",
    "cest",
    "cet",
    "cst",
    "ct",
    "edt",
    "eest",
    "eet",
    "est",
    "et",
    "gmt",
    "hdt",
    "hst",
    "ist",
    "jst",
    "kst",
    "mdt",
    "mst",
    "mt",
    "nzdt",
    "nzst",
    "pdt",
    "pst",
    "pt",
    "utc",
    "wet",
    "west",
}

_EN_NAMED_TIME_ZONE_CONTINUATIONS = {
    "central",
    "eastern",
    "mountain",
    "pacific",
}

_EN_TIME_CITY_PHRASES = {
    ("berlin", "time"),
    ("london", "time"),
    ("los", "angeles", "time"),
    ("new", "york", "time"),
    ("singapore", "time"),
    ("sydney", "time"),
    ("tokyo", "time"),
}

_EN_TIME_PHRASE_BLOCKED_STARTERS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "it",
    "we",
    "they",
    "i",
    "there",
    "here",
    "what",
    "who",
    "why",
    "how",
    "when",
    "where",
    "dinner",
    "breakfast",
    "lunch",
    "bed",
    "school",
    "class",
    "work",
    "game",
}

_EN_MONTH_ABBREVIATIONS = {
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
}

_EN_WEEKDAY_ABBREVIATIONS = {
    "mon.",
    "tue.",
    "tues.",
    "wed.",
    "thu.",
    "thur.",
    "thurs.",
    "fri.",
    "sat.",
    "sun.",
}

_EN_LABEL_ABBREVIATIONS = {
    "alg.",
    "app.",
    "apps.",
    "appx.",
    "appxs.",
    "assump.",
    "assumps.",
    "art.",
    "arts.",
    "aux.",
    "cor.",
    "coroll.",
    "corolls.",
    "corr.",
    "corrs.",
    "def.",
    "defn.",
    "defs.",
    "diam.",
    "eqn.",
    "eqns.",
    "ex.",
    "exh.",
    "exhs.",
    "expt.",
    "expts.",
    "fig.",
    "figs.",
    "freq.",
    "ht.",
    "hyp.",
    "ident.",
    "idents.",
    "lem.",
    "no.",
    "nos.",
    "obs.",
    "p.",
    "para.",
    "paras.",
    "prob.",
    "prop.",
    "pt.",
    "pts.",
    "reg.",
    "regs.",
    "rem.",
    "sch.",
    "sched.",
    "stat.",
    "stats.",
    "subsec.",
    "subsecs.",
    "supp.",
    "suppl.",
    "tab.",
    "tabs.",
    "tbl.",
    "tbls.",
    "temp.",
    "thm.",
    "wt.",
}

_EN_LABEL_CHAIN_CONTINUATIONS = {
    abbreviation.rstrip(".") for abbreviation in _EN_LABEL_ABBREVIATIONS
}

_EN_LEGAL_REPORTER_ABBREVIATIONS = {
    "app.",
    "appx.",
    "cal.",
    "dist.",
    "fed.",
    "ill.",
    "mass.",
    "misc.",
    "rptr.",
    "so.",
    "supp.",
}

_EN_LEGAL_REPORTER_CONTINUATIONS = {
    "app",
    "appx",
    "ct",
    "div",
    "dist",
    "lexis",
    "misc",
    "rptr",
    "supp",
}

_EN_LEGAL_REPORTER_INITIALISMS = {
    "a.",
    "f.",
    "n.y.",
    "u.s.",
}

_EN_LEGAL_CITATION_ABBREVIATIONS = {
    "am.",
    "amend.",
    "ann.",
    "app.",
    "ariz.",
    "ark.",
    "art.",
    "bankr.",
    "bus.",
    "cal.",
    "calif.",
    "cent.",
    "civ.",
    "colo.",
    "comp.",
    "conn.",
    "corp.",
    "crim.",
    "d.c.",
    "del.",
    "evid.",
    "fed.",
    "fla.",
    "ga.",
    "gen.",
    "h.",
    "h.j.",
    "ill.",
    "ind.",
    "inst.",
    "kan.",
    "ky.",
    "l.",
    "la.",
    "mass.",
    "md.",
    "me.",
    "mich.",
    "minn.",
    "miss.",
    "mo.",
    "model.",
    "mont.",
    "n.c.",
    "n.d.",
    "n.h.",
    "n.j.",
    "n.m.",
    "neb.",
    "nev.",
    "no.",
    "okla.",
    "or.",
    "p.",
    "pa.",
    "proc.",
    "pub.",
    "r.",
    "reg.",
    "res.",
    "rest.",
    "rev.",
    "s.",
    "s.c.",
    "s.j.",
    "stat.",
    "tenn.",
    "tex.",
    "unif.",
    "u.s.",
    "va.",
    "vt.",
    "wash.",
    "wis.",
    "wyo.",
}

_EN_LEGAL_CITATION_CONTINUATIONS = {
    "act",
    "agency",
    "amend",
    "ann",
    "app",
    "bankr",
    "bus",
    "c",
    "cent",
    "cf",
    "civ",
    "code",
    "commercial",
    "comp",
    "const",
    "corp",
    "crim",
    "evid",
    "fed",
    "gen",
    "h",
    "inst",
    "l",
    "law",
    "laws",
    "model",
    "no",
    "p",
    "penal",
    "principles",
    "proc",
    "pt",
    "r",
    "reg",
    "res",
    "rev",
    "rule",
    "rules",
    "s",
    "stat",
    "tit",
    "torts",
}

_EN_STATE_LEGAL_ABBREVIATIONS = {
    "ariz.",
    "ark.",
    "ala.",
    "cal.",
    "calif.",
    "colo.",
    "conn.",
    "d.c.",
    "del.",
    "fla.",
    "ga.",
    "ill.",
    "ind.",
    "kan.",
    "ky.",
    "la.",
    "mass.",
    "md.",
    "me.",
    "mich.",
    "minn.",
    "miss.",
    "mo.",
    "mont.",
    "n.c.",
    "n.d.",
    "n.h.",
    "n.j.",
    "n.m.",
    "neb.",
    "nev.",
    "okla.",
    "or.",
    "pa.",
    "s.c.",
    "tenn.",
    "tex.",
    "va.",
    "vt.",
    "wash.",
    "wis.",
    "w.",
    "w.va.",
    "wyo.",
}

_EN_STATE_LEGAL_CONTINUATIONS = {
    "appeals",
    "chancery",
    "civ",
    "code",
    "comp",
    "court",
    "department",
    "dept",
    "evid",
    "gen",
    "laws",
    "penal",
    "proc",
    "public",
    "rev",
    "rule",
    "stat",
    "state",
    "supreme",
}

_EN_TITLE_CHAIN_ABBREVIATIONS = {
    "admin.",
    "assoc.",
    "asst.",
    "atty.",
    "dep.",
    "dir.",
    "dist.",
    "emer.",
    "exec.",
    "hon.",
    "prof.",
    "rt.",
    "sec.",
    "vis.",
}

_EN_TITLE_CHAIN_CONTINUATIONS = {
    "admin",
    "assoc",
    "asst",
    "atty",
    "dep",
    "dir",
    "dist",
    "emer",
    "exec",
    "hon",
    "prof",
    "sec",
    "u",
    "vis",
}

_EN_TITLE_NAME_ABBREVIATIONS = {
    "admin.",
    "asst.",
    "atty.",
    "dep.",
    "dir.",
    "dist.",
    "emer.",
    "exec.",
    "hon.",
    "prof.",
    "sec.",
    "vis.",
}

_EN_PLACE_PREFIX_CONTINUATIONS = {
    "pt.": {
        "arena",
        "barrow",
        "defiance",
        "judith",
        "loma",
        "lookout",
        "mugu",
        "pleasant",
        "reyes",
        "roberts",
    },
    "ft.": {
        "collins",
        "lauderdale",
        "myers",
        "worth",
    },
    "sts.": {
        "cyril",
        "joachim",
        "peter",
    },
}

_EN_REPORT_VALUE_ABBREVIATIONS = {
    "avg.",
    "conc.",
    "diam.",
    "est.",
    "freq.",
    "ht.",
    "temp.",
    "wt.",
}

_EN_COMPANY_SUFFIX_ABBREVIATIONS = {
    "bhd.",
    "co.",
    "corp.",
    "gmbh.",
    "inc.",
    "llc.",
    "llp.",
    "ltd.",
    "plc.",
    "pte.",
    "pty.",
    "sdn.",
}

_EN_COMPANY_SUFFIX_CONTINUATIONS = {
    "bhd",
    "board",
    "ceo",
    "cfo",
    "chair",
    "co",
    "corp",
    "cto",
    "director",
    "gmbh",
    "inc",
    "limited",
    "ltd",
    "partner",
    "plc",
}

_EN_STRONG_SENTENCE_STARTERS = {
    "he",
    "here",
    "i",
    "it",
    "nobody",
    "she",
    "that",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "we",
}

_EN_SCIENTIFIC_ABBREVIATIONS = {
    "sect.",
    "ser.",
    "sp.",
    "spp.",
    "str.",
    "subg.",
    "var.",
}

_EN_SCIENTIFIC_CONTEXT_EPITHETS = {
    "coli",
}

_EN_SCIENTIFIC_BLOCKED_CONTINUATIONS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "it",
    "we",
    "they",
}

_EN_LOWERCASE_STYLED_INITIAL_CONTINUATIONS = {
    "e.": {"e"},
    "k.": {"d"},
    "p.": {"j"},
}

_EN_LOWERCASE_STYLED_SURNAME_CONTINUATIONS = {
    "d.": {"lang"},
    "e.": {"cummings"},
    "j.": {"harvey"},
    "m.": {"ward"},
}

_EN_LEADING_TIME_PREFIXES = {
    ("after",),
    ("around",),
    ("at",),
    ("at", "about"),
    ("before",),
    ("by",),
    ("from",),
    ("until",),
}

_ROMAN_NUMERAL_CHARS = frozenset("ivxlcdm")

_EN_SURNAME_PARTICLES = {
    "al",
    "da",
    "de",
    "del",
    "di",
    "dos",
    "du",
    "van",
    "von",
}

# Exact fixed-title continuations only; "Who?" still splits unless followed by
# "Weekly", and "Yahoo!" still splits unless followed by "Finance".
_EN_PUNCTUATED_NAME_CONTINUATIONS = {
    "e!": {"entertainment", "insider", "live", "news", "online", "red", "true"},
    "guess?": {
        "factory",
        "inc",
        "jeans",
        "kids",
        "originals",
        "watches",
    },
    "jeopardy!": {
        "college",
        "invitational",
        "kids",
        "masters",
        "national",
        "teen",
        "the",
        "tournament",
    },
    "ok!": {"australia", "magazine", "uk"},
    "who?": {"weekly"},
    "yahoo!": {
        "answers",
        "auctions",
        "directory",
        "entertainment",
        "fantasy",
        "finance",
        "groups",
        "inc",
        "japan",
        "life",
        "mail",
        "messenger",
        "movies",
        "news",
        "search",
        "sports",
        "tech",
        "weather",
    },
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
def get_boundary_detector(language="en", never_split_numbers=False):
    return QuickYieldBoundaryDetector(language, never_split_numbers)


class QuickYieldBoundaryDetector:
    """Decides if a fragment delimiter is safe to yield immediately."""

    def __init__(self, language="en", never_split_numbers=False):
        self.language, self.abbreviations, self.currency_symbols = _language_detector_config(language)
        self.never_split_numbers = never_split_numbers

    def classify(self, buffer, delimiter_index, next_char=None):
        delimiter = buffer[delimiter_index]

        if delimiter in "\n\u3002\uff01":
            return SPLIT

        if delimiter == "!":
            return self._classify_exclamation_mark(buffer, delimiter_index)

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

    def is_high_confidence_sentence_boundary(self, buffer, delimiter_index):
        if self.language != "en" or delimiter_index < 0:
            return False
        if delimiter_index >= len(buffer) or buffer[delimiter_index] != ".":
            return False

        token, ended = self._next_token(buffer, delimiter_index)
        if not token or not ended:
            return False

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return False

        left = buffer[: delimiter_index + 1]
        abbreviation = self._matching_abbreviation(left)
        if (
            abbreviation in _EN_AMBIGUOUS_ABBREVIATIONS
            and self._is_strong_sentence_starter(clean_token)
        ):
            return True

        current_token = self._current_token(left)
        if not self._is_dotted_initialism(current_token):
            return False

        if self._is_strong_sentence_starter(clean_token):
            return True

        previous = self._previous_token_before_current(left)
        return (
            self._is_single_upper_initial(previous)
            and self._left_has_initials_phrase(buffer, delimiter_index)
            and self._is_capitalized_phrase_token(clean_token)
        )

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
        if self.never_split_numbers and token[:-1].isdigit():
            return REJECT
        if next_char is not None and self._continues_token(next_char):
            return REJECT
        if self.language == "en" and self._is_dotted_initialism(token):
            return self._classify_dotted_initialism(buffer, delimiter_index, token)

        contextual_action = self._classify_contextual_period_token(
            buffer,
            delimiter_index,
            token,
        )
        if contextual_action is not None:
            return contextual_action

        continuation_action = self._classify_terminal_continuation(buffer, delimiter_index)
        if continuation_action is not None:
            return continuation_action

        return REJECT if self._continues_token(next_char) else SPLIT

    def _classify_exclamation_mark(self, buffer, delimiter_index):
        punctuated_name_action = self._classify_punctuated_name(buffer, delimiter_index)
        if punctuated_name_action != SPLIT:
            return punctuated_name_action

        continuation_action = self._classify_terminal_continuation(buffer, delimiter_index)
        return continuation_action if continuation_action is not None else SPLIT

    def _classify_question_mark(self, buffer, delimiter_index, next_char):
        if not self._inside_url_token(buffer, delimiter_index):
            punctuated_name_action = self._classify_punctuated_name(buffer, delimiter_index)
            if punctuated_name_action != SPLIT:
                return punctuated_name_action
            continuation_action = self._classify_terminal_continuation(buffer, delimiter_index)
            return continuation_action if continuation_action is not None else SPLIT

        if next_char is None:
            return HOLD
        return REJECT if self._continues_token(next_char) else SPLIT

    def _classify_terminal_continuation(self, buffer, delimiter_index):
        index = delimiter_index + 1
        while index < len(buffer) and buffer[index] in _TERMINAL_MARKS:
            index += 1
        while index < len(buffer) and buffer[index] in _CLOSING_MARKS:
            index += 1
        while index < len(buffer) and buffer[index].isspace():
            index += 1

        if index >= len(buffer):
            return HOLD

        next_visible = buffer[index]
        if next_visible == "," or next_visible.islower():
            return REJECT
        return None

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

        if self._previous_non_closing_char(buffer, delimiter_index) in _TERMINAL_MARKS:
            return REJECT

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
        initialism_word_action = self._classify_initialism_word_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if initialism_word_action is not None:
            return initialism_word_action
        legal_citation_action = self._classify_legal_citation_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if legal_citation_action is not None:
            return legal_citation_action
        state_legal_action = self._classify_state_legal_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if state_legal_action is not None:
            return state_legal_action
        company_suffix_action = self._classify_company_suffix_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if company_suffix_action is not None:
            return company_suffix_action
        if abbreviation in _EN_LEGAL_REPORTER_INITIALISMS:
            legal_action = self._classify_legal_reporter_continuation(
                buffer,
                delimiter_index,
            )
            if legal_action is not None:
                return legal_action
        time_action = self._classify_time_abbreviation_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if time_action is not None:
            return time_action
        weekday_action = self._classify_weekday_date_continuation(
            buffer,
            delimiter_index,
            abbreviation,
        )
        if weekday_action is not None:
            return weekday_action
        if (
            abbreviation in {"a.m.", "p.m."}
            and (
                folded in _EN_TIME_ABBREVIATION_CONTINUATIONS
                or folded in _EN_TIME_ZONE_CONTINUATIONS
                or folded in _EN_NAMED_TIME_ZONE_CONTINUATIONS
                or self._is_utc_offset_token(folded)
                or self._is_leading_time_phrase(buffer, delimiter_index)
            )
        ):
            return REJECT
        if abbreviation in _EN_LABEL_ABBREVIATIONS and self._is_label_continuation(
            clean_token
        ):
            return REJECT
        if abbreviation == "no." and len(clean_token) == 1 and clean_token.isupper():
            return REJECT
        if self._is_strong_sentence_starter(clean_token):
            return SPLIT
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

    def _classify_initialism_word_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation.count(".") <= 1:
            return None

        words = _EN_INITIALISM_CONTINUATION_FIRST_WORDS.get(abbreviation)
        if not words:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = self._normalize_phrase_token(token)
        if not clean_token:
            return HOLD

        if clean_token in words:
            return REJECT
        if not ended and any(word.startswith(clean_token) for word in words):
            return HOLD

        return None

    def _classify_contextual_period_token(self, buffer, delimiter_index, token):
        if self.language != "en":
            return None

        folded = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ",;:!?").casefold()
        if not folded:
            return None

        place_action = self._classify_place_prefix_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if place_action is not None:
            return place_action

        title_action = self._classify_title_chain_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if title_action is not None:
            return title_action

        company_suffix_action = self._classify_company_suffix_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if company_suffix_action is not None:
            return company_suffix_action

        legal_citation_action = self._classify_legal_citation_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if legal_citation_action is not None:
            return legal_citation_action

        state_legal_action = self._classify_state_legal_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if state_legal_action is not None:
            return state_legal_action

        report_value_action = self._classify_report_value_continuation(
            buffer,
            delimiter_index,
            folded,
        )
        if report_value_action is not None:
            return report_value_action

        if folded in _EN_LABEL_ABBREVIATIONS:
            label_action = self._classify_contextual_label_continuation(
                buffer,
                delimiter_index,
            )
            if label_action is not None:
                return label_action

        if folded in _EN_SCIENTIFIC_ABBREVIATIONS:
            scientific_action = self._classify_scientific_abbreviation_continuation(
                buffer,
                delimiter_index,
            )
            if scientific_action is not None:
                return scientific_action

        if folded in _EN_LEGAL_REPORTER_ABBREVIATIONS:
            legal_action = self._classify_legal_reporter_continuation(
                buffer,
                delimiter_index,
            )
            if legal_action is not None:
                return legal_action

        return None

    def _classify_contextual_label_continuation(self, buffer, delimiter_index):
        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = clean_token.casefold()
        if folded in _EN_LABEL_CHAIN_CONTINUATIONS:
            return REJECT
        if not ended and any(
            continuation.startswith(folded)
            for continuation in _EN_LABEL_CHAIN_CONTINUATIONS
        ):
            return HOLD
        if not ended and self._could_be_label_continuation_prefix(folded):
            return HOLD
        return REJECT if self._is_label_continuation(clean_token) else None

    def _classify_legal_citation_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if (
            abbreviation not in _EN_LEGAL_CITATION_ABBREVIATIONS
            and not self._has_legal_citation_context(buffer, delimiter_index)
        ):
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if not ended and self._could_be_legal_citation_prefix(folded):
            return HOLD
        return REJECT if self._is_legal_citation_continuation(clean_token) else None

    def _classify_state_legal_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in _EN_STATE_LEGAL_ABBREVIATIONS:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if folded in _EN_STATE_LEGAL_CONTINUATIONS:
            return REJECT
        if not ended and any(
            continuation.startswith(folded)
            for continuation in _EN_STATE_LEGAL_CONTINUATIONS
        ):
            return HOLD
        return None

    def _classify_title_chain_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in _EN_TITLE_CHAIN_ABBREVIATIONS:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if folded in _EN_TITLE_CHAIN_CONTINUATIONS:
            return REJECT
        if not ended and any(
            continuation.startswith(folded)
            for continuation in _EN_TITLE_CHAIN_CONTINUATIONS
        ):
            return HOLD
        if (
            abbreviation in _EN_TITLE_NAME_ABBREVIATIONS
            and self._is_capitalized_phrase_token(clean_token)
            and not self._is_strong_sentence_starter(clean_token)
        ):
            return REJECT
        return None

    def _classify_place_prefix_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        continuations = _EN_PLACE_PREFIX_CONTINUATIONS.get(abbreviation)
        if not continuations:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if folded in continuations:
            return REJECT
        if not ended and any(continuation.startswith(folded) for continuation in continuations):
            return HOLD
        return None

    def _classify_report_value_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in _EN_REPORT_VALUE_ABBREVIATIONS:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if not ended and self._could_be_report_value_prefix(clean_token, folded):
            return HOLD
        return REJECT if self._is_report_value_continuation(clean_token) else None

    def _classify_company_suffix_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in _EN_COMPANY_SUFFIX_ABBREVIATIONS:
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = self._normalize_phrase_token(clean_token)
        if folded in _EN_COMPANY_SUFFIX_CONTINUATIONS:
            return REJECT
        if not ended and any(
            continuation.startswith(folded)
            for continuation in _EN_COMPANY_SUFFIX_CONTINUATIONS
        ):
            return HOLD
        return None

    def _classify_legal_reporter_continuation(self, buffer, delimiter_index):
        if not self._has_legal_reporter_context(buffer, delimiter_index):
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = clean_token.casefold()
        if not ended and (
            any(word.startswith(folded) for word in _EN_LEGAL_REPORTER_CONTINUATIONS)
            or any(char.isdigit() for char in clean_token)
        ):
            return HOLD

        if folded in _EN_LEGAL_REPORTER_CONTINUATIONS:
            return REJECT
        if any(char.isdigit() for char in clean_token):
            return REJECT
        return None

    def _has_legal_reporter_context(self, buffer, delimiter_index):
        previous = self._previous_token_before_current(buffer[:delimiter_index + 1])
        previous = previous.strip(_OPENING_MARKS + _CLOSING_MARKS + ",;:!?")
        if not previous:
            return False

        folded = previous.casefold()
        if self._is_legal_volume_token(previous):
            return True
        return (
            folded in _EN_LEGAL_REPORTER_ABBREVIATIONS
            or folded in _EN_LEGAL_REPORTER_INITIALISMS
        )

    def _has_legal_citation_context(self, buffer, delimiter_index):
        previous = self._previous_token_before_current(buffer[:delimiter_index + 1])
        previous = previous.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not previous:
            return False

        folded = previous.casefold()
        return (
            folded in _EN_LEGAL_CITATION_ABBREVIATIONS
            or folded in _EN_LEGAL_CITATION_CONTINUATIONS
            or folded in _EN_STATE_LEGAL_ABBREVIATIONS
            or self._is_legal_volume_token(previous)
        )

    def _could_be_legal_citation_prefix(self, token):
        if not token:
            return False
        return (
            token[:1].isdigit()
            or token in {"\u00a7", "\u00c2\u00a7"}
            or all(char in _ROMAN_NUMERAL_CHARS for char in token)
            or any(word.startswith(token) for word in _EN_LEGAL_CITATION_CONTINUATIONS)
        )

    def _is_legal_citation_continuation(self, token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not token:
            return False

        folded = self._normalize_phrase_token(token)
        if folded in _EN_LEGAL_CITATION_CONTINUATIONS:
            return True
        if token.startswith("\u00a7") or token.startswith("\u00c2\u00a7"):
            return True
        if token[:1].isdigit():
            return True
        return len(folded) > 1 and all(char in _ROMAN_NUMERAL_CHARS for char in folded)

    @staticmethod
    def _is_legal_volume_token(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        return token.isdigit()

    def _classify_scientific_abbreviation_continuation(self, buffer, delimiter_index):
        if not self._has_scientific_abbreviation_context(buffer, delimiter_index):
            return None

        token, ended = self._next_token(buffer, delimiter_index)
        if not token:
            return HOLD

        clean_token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not clean_token:
            return HOLD

        folded = clean_token.casefold()
        if not ended:
            return HOLD
        if (
            folded in _EN_SCIENTIFIC_BLOCKED_CONTINUATIONS
            and not (len(clean_token) == 1 and clean_token.isupper())
        ):
            return None
        return REJECT if self._is_scientific_continuation_token(clean_token) else None

    def _has_scientific_abbreviation_context(self, buffer, delimiter_index):
        previous = self._previous_token_before_current(buffer[:delimiter_index + 1])
        previous = previous.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not previous:
            return False

        if previous.casefold() in _EN_SCIENTIFIC_CONTEXT_EPITHETS:
            return True

        return self._is_capitalized_phrase_token(previous)

    @staticmethod
    def _is_scientific_continuation_token(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not token:
            return False
        return (
            token[:1].isupper()
            or any(char.isdigit() for char in token)
            or "-" in token
        )

    @staticmethod
    def _could_be_label_continuation_prefix(token):
        if not token:
            return False
        return (
            token.isdigit()
            or token.isalpha()
            or any(char.isdigit() for char in token)
            or (token.endswith("-") and token[:-1].isalpha())
        )

    @staticmethod
    def _normalize_phrase_token(token):
        return token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?").casefold().replace(
            "\u2018",
            "'",
        ).replace(
            "\u2019",
            "'",
        )

    @staticmethod
    def _is_utc_offset_token(token):
        for prefix in ("utc+", "utc-", "gmt+", "gmt-"):
            if token.startswith(prefix) and token[len(prefix):].isdigit():
                return True
        return False

    def _classify_time_abbreviation_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in {"a.m.", "p.m."}:
            return None

        phrase_action = self._classify_next_phrase(
            buffer,
            delimiter_index,
            _EN_TIME_CITY_PHRASES,
        )
        if phrase_action is not None:
            return phrase_action

        capitalized_time_phrase_action = (
            self._classify_capitalized_time_phrase_continuation(
                buffer,
                delimiter_index,
            )
        )
        if capitalized_time_phrase_action is not None:
            return capitalized_time_phrase_action

        month_action = self._classify_month_date_continuation(buffer, delimiter_index)
        if month_action is not None:
            return month_action

        return None

    def _classify_capitalized_time_phrase_continuation(
        self,
        buffer,
        delimiter_index,
    ):
        tokens, last_complete = self._next_raw_tokens(buffer, delimiter_index, 4)
        if not tokens:
            return HOLD

        folded_tokens = [self._normalize_phrase_token(token) for token in tokens]
        first = folded_tokens[0]
        if first in _EN_TIME_PHRASE_BLOCKED_STARTERS:
            return None

        for index, folded in enumerate(folded_tokens):
            if folded == "time":
                if index == 0:
                    return None
                if index == len(tokens) - 1 and not last_complete:
                    return HOLD
                return (
                    REJECT
                    if self._tokens_are_capitalized_phrase(tokens[:index])
                    else None
                )

            if (
                index > 0
                and index == len(tokens) - 1
                and not last_complete
                and "time".startswith(folded)
            ):
                return (
                    HOLD
                    if self._tokens_are_capitalized_phrase(tokens[:index])
                    else None
                )

        if len(tokens) >= 4:
            return None

        return HOLD if self._tokens_are_capitalized_phrase(tokens) else None

    def _classify_weekday_date_continuation(
        self,
        buffer,
        delimiter_index,
        abbreviation,
    ):
        if abbreviation not in _EN_WEEKDAY_ABBREVIATIONS:
            return None
        return self._classify_month_date_continuation(buffer, delimiter_index)

    def _classify_month_date_continuation(self, buffer, delimiter_index):
        tokens, last_complete = self._next_clean_tokens(buffer, delimiter_index, 2)
        if not tokens:
            return HOLD

        first = tokens[0]
        if first in _EN_MONTH_ABBREVIATIONS:
            if len(tokens) == 1:
                return HOLD
            return REJECT if self._starts_with_digit(tokens[1]) else None

        if (
            len(tokens) == 1
            and not last_complete
            and any(month.startswith(first) for month in _EN_MONTH_ABBREVIATIONS)
        ):
            return HOLD

        return None

    def _classify_next_phrase(self, buffer, delimiter_index, phrases):
        tokens, last_complete = self._next_clean_tokens(buffer, delimiter_index, 4)
        if not tokens:
            return HOLD

        for phrase in phrases:
            if len(tokens) >= len(phrase) and tuple(tokens[:len(phrase)]) == phrase:
                return REJECT

            if len(tokens) > len(phrase):
                continue

            prefix_tokens = tokens[:-1]
            if tuple(prefix_tokens) != phrase[:len(prefix_tokens)]:
                continue

            last_token = tokens[-1]
            phrase_token = phrase[len(prefix_tokens)]
            if last_token == phrase_token or (
                not last_complete and phrase_token.startswith(last_token)
            ):
                return HOLD

        return None

    def _next_clean_tokens(self, buffer, delimiter_index, max_tokens):
        raw_tokens, last_complete = self._next_raw_tokens(
            buffer,
            delimiter_index,
            max_tokens,
        )
        return (
            [self._normalize_phrase_token(token) for token in raw_tokens],
            last_complete,
        )

    def _next_raw_tokens(self, buffer, delimiter_index, max_tokens):
        right = buffer[delimiter_index + 1:]
        tokens = []
        last_complete = False
        index = 0

        while index < len(right) and len(tokens) < max_tokens:
            while (
                index < len(right)
                and (
                    right[index].isspace()
                    or right[index] in _OPENING_MARKS
                    or right[index] in ".;:,)]}"
                )
            ):
                index += 1

            if index >= len(right):
                break

            start = index
            while (
                index < len(right)
                and not right[index].isspace()
                and right[index] not in ".?!;:,)]}"
            ):
                index += 1

            clean_token = right[start:index].strip(
                _OPENING_MARKS + _CLOSING_MARKS + ".,;:!?"
            )
            if clean_token:
                tokens.append(clean_token)
                last_complete = index < len(right)

            if index == start:
                index += 1

        return tokens, last_complete

    @classmethod
    def _tokens_are_capitalized_phrase(cls, tokens):
        return bool(tokens) and all(
            cls._is_capitalized_phrase_token(token) for token in tokens
        )

    @staticmethod
    def _is_capitalized_phrase_token(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        return (
            bool(token)
            and token[:1].isupper()
            and any(char.isalpha() for char in token)
        )

    @staticmethod
    def _starts_with_digit(token):
        return bool(token) and token[0].isdigit()

    @staticmethod
    def _is_label_continuation(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not token:
            return False

        if token[:1].isdigit():
            return all(char.isdigit() or char in ".-" for char in token)

        if len(token) == 1 and token.isupper():
            return True

        if (
            any(char.isalpha() for char in token)
            and all(char.isupper() or char == "-" for char in token)
        ):
            return True

        folded = token.casefold()
        if len(folded) > 1 and all(char in _ROMAN_NUMERAL_CHARS for char in folded):
            return True

        return (
            any(char.isdigit() for char in token)
            and any(char.isalpha() for char in token)
            and not any(char.islower() for char in token)
        )

    def _could_be_report_value_prefix(self, token, folded):
        if not token:
            return False
        return (
            token[:1].isdigit()
            or token[:1] in self.currency_symbols
            or folded in _EN_LABEL_CHAIN_CONTINUATIONS
            or any(continuation.startswith(folded) for continuation in _EN_LABEL_CHAIN_CONTINUATIONS)
        )

    def _is_report_value_continuation(self, token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        if not token:
            return False

        folded = self._normalize_phrase_token(token)
        return (
            token[:1].isdigit()
            or token[:1] in self.currency_symbols
            or folded in _EN_LABEL_CHAIN_CONTINUATIONS
            or self._is_label_continuation(token)
        )

    @staticmethod
    def _is_strong_sentence_starter(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?")
        return token.casefold() in _EN_STRONG_SENTENCE_STARTERS

    def _left_has_initials_phrase(self, buffer, delimiter_index):
        left = buffer[: delimiter_index + 1]
        tokens = [
            token.strip(_OPENING_MARKS + _CLOSING_MARKS + ".,;:!?").casefold()
            for token in left.split()
        ]
        tokens = [token for token in tokens if token]
        window = tokens[-6:]
        return "initials" in window and any(
            verb in window for verb in {"are", "were", "is"}
        )

    def _is_leading_time_phrase(self, buffer, delimiter_index):
        words = buffer[:delimiter_index + 1].casefold().strip().split()
        if len(words) < 3 or words[-1] not in {"a.m.", "p.m."}:
            return False

        time_token = words[-2]
        if not self._is_clock_time_token(time_token):
            return False

        return tuple(words[:-2]) in _EN_LEADING_TIME_PREFIXES

    @staticmethod
    def _is_clock_time_token(token):
        if ":" in token:
            hour, minute = token.split(":", 1)
            return hour.isdigit() and minute.isdigit()
        return token.isdigit()

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
        lowercase_styled_action = self._classify_lowercase_styled_initial(
            buffer,
            delimiter_index,
            current_token,
            clean_token,
            ended,
        )
        if lowercase_styled_action is not None:
            return lowercase_styled_action

        current_key = current_token.strip(
            _OPENING_MARKS + _CLOSING_MARKS
        ).casefold()
        legal_citation_action = self._classify_legal_citation_continuation(
            buffer,
            delimiter_index,
            current_key,
        )
        if legal_citation_action is not None:
            return legal_citation_action

        if current_key in _EN_LEGAL_REPORTER_INITIALISMS:
            legal_action = self._classify_legal_reporter_continuation(
                buffer,
                delimiter_index,
            )
            if legal_action is not None:
                return legal_action

        if self._is_single_upper_initial(current_token) and clean_token[:1].islower():
            return REJECT

        if self._is_single_upper_initial(current_token):
            particle_action = self._classify_surname_particle_continuation(
                clean_token,
                ended,
            )
            if particle_action is not None:
                return particle_action

        if len(clean_token) == 1 and clean_token.isupper():
            right = buffer[delimiter_index + 1:].lstrip().lstrip(_OPENING_MARKS).lstrip()
            if len(right) > len(token) and right[len(token)] == ".":
                return REJECT
        if current_token.count(".") > 1:
            if self._is_strong_sentence_starter(clean_token):
                return SPLIT
            return REJECT

        if previous[:1].isupper() and clean_token[:1].isupper():
            if (
                self._is_single_upper_initial(previous)
                and self._left_has_initials_phrase(buffer, delimiter_index)
            ):
                return SPLIT
            return REJECT

        single_initial_action = self._classify_single_upper_initial(
            buffer,
            delimiter_index,
            current_token,
            clean_token,
        )
        if single_initial_action is not None:
            return single_initial_action

        return SPLIT

    def _classify_surname_particle_continuation(self, clean_token, ended):
        folded = clean_token.casefold()
        if folded in _EN_SURNAME_PARTICLES:
            return REJECT
        if any(folded.startswith(f"{particle}-") for particle in _EN_SURNAME_PARTICLES):
            return REJECT
        if not ended and any(particle.startswith(folded) for particle in _EN_SURNAME_PARTICLES):
            return HOLD
        return None

    def _classify_lowercase_styled_initial(
        self,
        buffer,
        delimiter_index,
        current_token,
        clean_token,
        ended,
    ):
        current = current_token.strip(_OPENING_MARKS + _CLOSING_MARKS).casefold()
        if not self._is_single_lower_initial(current):
            return None

        folded = clean_token.casefold()
        initial_continuations = _EN_LOWERCASE_STYLED_INITIAL_CONTINUATIONS.get(
            current,
            set(),
        )
        if folded in initial_continuations:
            if self._next_token_is_followed_by_period(buffer, delimiter_index):
                return REJECT
            return HOLD if not ended else None

        if (
            not ended
            and any(target.startswith(folded) for target in initial_continuations)
        ):
            return HOLD

        surname_continuations = _EN_LOWERCASE_STYLED_SURNAME_CONTINUATIONS.get(
            current,
            set(),
        )
        if folded in surname_continuations:
            return REJECT
        if (
            not ended
            and any(target.startswith(folded) for target in surname_continuations)
        ):
            return HOLD
        return None

    def _classify_single_upper_initial(
        self,
        buffer,
        delimiter_index,
        current_token,
        clean_token,
    ):
        if (
            not self._is_single_upper_initial(current_token)
            or not clean_token[:1].isupper()
        ):
            return None

        previous = self._previous_token_before_current(
            buffer[:delimiter_index + 1]
        ).casefold()
        if current_token.strip(_OPENING_MARKS + _CLOSING_MARKS) == "I." and previous:
            return SPLIT
        if self._is_strong_sentence_starter(clean_token):
            return SPLIT

        return SPLIT if previous == "is" else REJECT

    @staticmethod
    def _is_dotted_initialism(token):
        parts = token.split(".")
        return (
            len(parts) >= 2
            and parts[-1] == ""
            and all(len(part) == 1 and part.isalpha() for part in parts[:-1])
        )

    @staticmethod
    def _is_single_upper_initial(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS)
        return len(token) == 2 and token[0].isupper() and token[1] == "."

    @staticmethod
    def _is_single_lower_initial(token):
        token = token.strip(_OPENING_MARKS + _CLOSING_MARKS)
        return len(token) == 2 and token[0].islower() and token[1] == "."

    def _next_token_is_followed_by_period(self, buffer, delimiter_index):
        right = buffer[delimiter_index + 1:]
        if not right:
            return False

        index = 0
        while index < len(right) and (
            right[index].isspace() or right[index] in _OPENING_MARKS
        ):
            index += 1
        while (
            index < len(right)
            and not right[index].isspace()
            and right[index] not in ".?!;:,)]}"
        ):
            index += 1
        return index < len(right) and right[index] == "."

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

    @staticmethod
    def _previous_non_closing_char(buffer, delimiter_index):
        index = delimiter_index - 1
        while index >= 0 and buffer[index] in _CLOSING_MARKS:
            index -= 1
        if index < 0:
            return None
        return buffer[index]

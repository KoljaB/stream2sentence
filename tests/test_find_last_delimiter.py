"""Regression tests for find_last_delimiter abbreviation masking.

find_last_delimiter must not let a trailing ignored abbreviation (e.g. "Dr. ")
hide an earlier, valid split point for the same delimiter. Before the fix it
used s.rfind(delimiter), which only inspected the LAST occurrence of each
delimiter; if that occurrence was an ignored abbreviation the whole delimiter
was discarded and every earlier valid boundary was lost, suppressing the
low-latency fragment yield this library exists to provide.
"""

import stream2sentence.stream2sentence_time_based as tb
from stream2sentence.delimiter_ignore_prefixes import DELIMITER_IGNORE_PREFIXES

PREFERRED = [". ", "? ", "! ", "\n"]


def _setup():
    # find_last_delimiter reads this module global (set by
    # generate_sentences_time_based at runtime); populate it for direct tests.
    tb.delimiter_ignore_prefixes_global = set(DELIMITER_IGNORE_PREFIXES)


def test_earlier_delimiter_not_masked_by_trailing_abbreviation():
    _setup()
    # "stop here. " is a valid sentence end; "Dr. " later is an ignored
    # abbreviation. The valid boundary after "here" must still be found.
    s = "stop here. ask Dr. Lee"
    index = tb.find_last_delimiter(s, PREFERRED)
    assert index == s.index(". "), index
    assert s[: index + 1] == "stop here."


def test_multiple_trailing_abbreviations_do_not_mask_earlier_boundary():
    _setup()
    s = "done now. per Mr. Smith and Dr. Jones"
    index = tb.find_last_delimiter(s, PREFERRED)
    assert s[: index + 1] == "done now."


def test_real_sentence_end_after_abbreviation_still_wins():
    _setup()
    # A genuine later sentence end ("now. ") must still be preferred over the
    # earlier one, and the abbreviation ("Mr. ") must remain ignored.
    s = "Ask Mr. Lee now. then go on"
    index = tb.find_last_delimiter(s, PREFERRED)
    assert s[: index + 1] == "Ask Mr. Lee now."


def test_abbreviation_only_still_returns_no_delimiter():
    _setup()
    # No valid boundary exists (only an ignored abbreviation); must stay -1 so
    # the fix does not introduce a false split.
    s = "See Dr. foo bar"
    assert tb.find_last_delimiter(s, PREFERRED) == -1


def test_single_valid_delimiter_unchanged():
    _setup()
    s = "One two. three four"
    index = tb.find_last_delimiter(s, PREFERRED)
    assert s[: index + 1] == "One two."

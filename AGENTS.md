# AGENTS.md instructions

When explaining how something works, always start with a one-sentence plain-English summary of the goal, then build up from first principles before referencing code or internals. Define any non-obvious term the first time you use it. Use concrete examples or timelines where the concept involves timing or state.

## Generalizing Bug Fixes

When fixing a bug, do not patch only the exact repro unless the domain is truly closed and exact matching is the safest design.

Prefer the most general safe fix that covers the underlying local pattern family:

- First identify the smallest structural pattern that explains the failure.
- Then design the fix around that pattern, not around the literal example text.
- Add guardrails so the broader fix does not create obvious false positives or false negatives.
- Add regression tests for the original repro, several nearby variants, partial or streaming prefixes when relevant, and at least one counterexample where the fix must not apply.

For streaming or low-context behavior, a good general fix should use bounded local evidence:

- adjacent tokens
- short lookahead
- short lookbehind
- token shape such as capitalization, digits, punctuation, or known abbreviation class
- small domain vocabularies only when they represent a real category

Avoid fixes that require document-level state, balanced parsing, arbitrary prior context, or assumptions about being inside quotes, Markdown, JSON, code, brackets, or tables unless the task explicitly asks for a parser.

For ambiguous text, prefer a conservative local heuristic with counter-tests over a broad global rule. For example, do not make `Misc.` always non-terminal if the real issue is citation-shaped text like `123 N.Y. Misc. 456.`; instead, detect the citation shape and keep ordinary cases like `The category is Misc. Delete it.` working.

A fix is too specific if it only handles the discovered sentence and not obvious siblings. A fix is too broad if it changes unrelated natural uses without local evidence.

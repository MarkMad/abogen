# AGENTS.md — Segmentation & Subtitle System Contract

This document is the source of truth for how text is split for **voice
processing** (TTS engine segmentation) and **subtitle processing**, across
languages, TTS engines, and subtitle modes. It was written after a bug where
sentence modes "processed all text as a whole" (one merged engine segment →
one giant subtitle). **Do not change this behavior without updating this
table.**

## Voice processing — split pattern passed to the TTS engine

`get_split_pattern(language, mode)` in `abogen/domain/split_pattern.py` is the
default; the spaCy pre-TTS path overrides it. Both UIs must stay in sync:
`spacy_pre_tts_segmentation` (`abogen/domain/conversion_pipeline.py`, WebUI)
and the inline branch in `abogen/pyqt/conversion.py` (~line 860, PyQt).

| Subtitle mode | English (en-US/en-GB) | Non-English, spaCy ON | Non-English, spaCy OFF | CJK (ja/zh) |
|---|---|---|---|---|
| Disabled | `\n` | spaCy pre-split, engine `\n` | `\n+` | `(?<=[.!?؟。！？।])\s*\|\n+` |
| Line | `\n` | spaCy pre-split, engine `\n` | `\n` | `(?<=[.!?؟。！？।])\s*\|\n+` |
| Sentence | `\n` | spaCy pre-split, engine `\n` | `(?<=[.!?؟。！？।])\s+\|\n+` | `(?<=[.!?؟。！？।])\s*\|\n+` |
| Sentence + Comma | `\n` | spaCy pre-split, engine `\n` | `(?<=[.!?,؟。！？،،、।])\s+\|\n+` (commas kept) | `(?<=[.!?,؟。！？،،、।])\s*\|\n+` |
| Sentence + Highlighting | `\n+` | `\n+` | `\n+` | `\n+` |
| N words ("5 words") | `\n` (→ Disabled) | `\n+` | `\n+` | Disabled CJK pattern |

Rules baked into this table:

- **English voice splitting is ALWAYS newline-only** for Disabled, Line,
  Sentence, and Sentence + Comma. English sentence/comma boundaries are
  produced ONLY at subtitle time (spaCy post-TTS / regex fallback). Never add
  punctuation to the English engine pattern.
- **Non-English + spaCy ON**: spaCy pre-segments the text (pre-TTS); the
  engine pattern is `\n` for Sentence AND Sentence + Comma — **never commas**.
  spaCy is skipped when the toggle is off, mode is Disabled/Line, or input is
  a subtitle file.
- **Non-English + spaCy OFF** (toggle off, spaCy failure, subtitle input): the
  default pattern is used — Sentence + Comma KEEPS its commas here. This is
  the intentional fallback, not a bug.
- CJK: punctuation-based patterns for Disabled/Line (historical); spacing is
  `\s*` (no spaces needed between CJK chars).
- Engine-level extra chunking (applies after the pattern): kokoro English
  re-chunks at ~510 phonemes; kokoro non-English at ~400 chars; supertonic
  caps each part at 300 chars.

## Subtitle processing — post-TTS, from tokens

| Mode | Behavior |
|---|---|
| Disabled | no subtitles |
| Line | one entry per TTS segment (line) |
| Sentence | sentence boundaries: English → spaCy; others → regex on `[.!?…]` |
| Sentence + Comma | sentence + comma boundaries at subtitle time (both languages) — commas never affect voice |
| Sentence + Highlighting | karaoke `{\kf…}` per word, grouped by sentence |
| N words | groups of N words by whitespace counting |

Token granularity (timing quality): kokoro English emits **per-word tokens**
with timestamps; kokoro non-English and supertonic emit **no tokens** → each
engine segment becomes one FakeToken, split by regex with proportional timing
when it contains multiple sentences.

## Hard invariants (breaking these reintroduces the original bug)

1. `Pipeline.__call__` (`abogen/tts_plugin/utils.py`) must yield ONE `Segment`
   per engine segment (with tokens) — never merge segments back into the
   whole text. `SynthesizedAudio.segments` carries the per-segment data;
   engines expose it in `plugins/kokoro/engine.py` and
   `plugins/supertonic/engine.py`.
2. `tts_segments` (`abogen/domain/conversion_pipeline.py`) restores trailing
   whitespace on segment-boundary tokens ONLY for real per-word tokens, never
   for FakeToken fallbacks.
3. `_to_language_enum` must return `lang_code` as-is when it is already a
   `Language` enum (`str(Language.ES)` is `"Language.ES"`, which silently
   resolved to EN_US and disabled spaCy pre-TTS for every language in WebUI).
4. English must never use spaCy for PRE-TTS segmentation — only for subtitles.

## Guarded by tests

- `tests/test_split_pattern.py` — English newline-only; non-English sentence
  patterns; CJK behavior.
- `tests/test_domain_conversion_pipeline.py` — `tts_segments` / spaCy
  segmentation helpers.
- Full suite: `python -m pytest tests/ -q` (expect 1566+ passing).

## Delegate tasks

The main agent orchestrates delegated work and remains responsible for
architecture, integration, verification, and the final result. Delegate via the
`Agent` tool by picking the right *agent type* first, then (only if needed) a
*model tier* that fits the complexity. Do not delegate by default: a spawned
agent starts cold and must re-derive context.

### Agent types

- `Explore` — read-only search across many files/naming conventions; returns
  conclusions, not file dumps. State breadth (`medium` or `very thorough`). Use
  it to locate segmentation entry points, trace callers of `get_split_pattern`,
  or map which tests cover a module. It locates code; it does not review it.
- `Plan` — read-only architect for designing an implementation strategy,
  listing critical files and trade-offs before a large or risky change.
- `general-purpose` — multi-step research or implementation that can run in
  parallel with the main agent's own work (bounded refactor, patch adapted
  across several files, independent investigations).
- `claude-code-guide` — only for questions about Claude Code / Agent SDK /
  Claude API itself, not this codebase.

### Model tier by complexity

Omit `model` to inherit the main agent's model. Override only when the task
clearly warrants it, and never silently pick a more expensive tier.

| Complexity | Examples | Tier |
|---|---|---|
| Low — mechanical, read-only, well-specified | file/symbol lookup, listing callers, running the test suite and summarizing failures, bulk renames | `haiku` |
| Medium — bounded implementation with a clear spec | adapting a patch across files, adding tests for a known contract, a refactor with an understood cause | `sonnet` |
| High — subtle, cross-cutting, or contract-sensitive | root-causing a segmentation/subtitle regression, changes touching the hard invariants above, concurrency or pipeline timing bugs, security-sensitive code | `opus` (or keep on the main agent) |

### Routing rules

- Small, well-defined, low-risk edits (copy edits, minor styling, a one-line
  fix with an understood cause, small test updates): do them directly.
- Broad read-only context gathering: `Explore`.
- Design before a large change: `Plan`, then implement.
- Independent or self-contained multi-step work: `general-purpose`, in the
  background if the main agent has useful work to continue.
- Never delegate: changes to the segmentation/subtitle contract in this file,
  edits to the hard invariants, broad integration, or final review. The main
  agent owns these.
- Both UIs (WebUI and PyQt) must stay in sync for any segmentation change; a
  delegated change that touches one side must be checked against the other.

### Briefs and lifecycle

- Briefs must be self-contained: the request, relevant paths, constraints,
  acceptance criteria, and which tests to run. State whether the agent may edit
  files or is read-only.
- Keep scope narrow. Ask for changed files, checks performed, and unresolved
  issues. Do not let a sub-agent delegate further.
- Launch independent agents in parallel (multiple `Agent` calls in one
  response). Do not run two agents that edit the same files concurrently. Use
  worktree isolation (`isolation: "worktree"`) when parallel edits could
  overlap.
- Completion of a background agent is delivered as a notification; do not poll
  or sleep. To continue an agent with its context intact, use `SendMessage`
  with its ID instead of spawning a new one.
- While an agent works, do independent work (inspect callers, identify
  regression risks, prepare verification); do not duplicate its task.

### Verification and communication

- An agent's report describes what it intended, not necessarily what it did.
  Review the actual diff and run proportionate verification
  (`python -m pytest tests/ -q`, or the targeted test files listed above for
  segmentation work) before reporting completion.
- Report faithfully: failing tests, skipped steps, and fallbacks are stated
  plainly.
- Answer simple conversational questions directly. If an agent type is
  unavailable, do the work directly and briefly mention the fallback.
- Do not ask for confirmation merely to use this workflow; respect the user's
  latest instructions and permission boundaries.

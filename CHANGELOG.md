# Changelog

Every cut of the ACRI specification is anchored here (version carrier #2;
carrier #1 is the git tag — see the repository README, "Versioning").

## v0.2-draft — 2026-10-28 (drafted; NOT cut, undecided)

Errata draft against v0.1, carried in `spec/acri-v0.2-draft.md` with each
revision tagged inline `[v0.2-draft]`. Three revisions:

1. **§1.1 `position` erratum** — when `anchor = "none"`, `line`/`col` MAY be
   `0` (the honest no-position sentinel); the `≥1` constraint applies only
   to real positions (`exact`/`name-first`). Evidence: the reference
   implementation has emitted `{"line": 0, "col": 0, "anchor": "none"}` for
   its input-unreadable envelope (`LEX000`) since v1.15.0.
2. **§1.1 Example refresh** — replaced the v0.1 example (flat `line`/`col`
   only) with a capture showing the dual-write location form (flat pair plus
   nested `position` object), captured verbatim from Lom v1.16.0 via
   `check --json` on a live probe; the "captured verbatim" claim remains
   true of the new example.
3. **§5 change-protocol additions** — (a) immutability of a numbered cut:
   any textual change to a cut requires a new version number; (b) version
   carriers: every cut is anchored by a git tag plus an entry in this
   CHANGELOG.

Until v0.2 is cut, v0.1 remains the operative specification.

## v0.1 — 2026-10-12 (cut)

Initial version. The cut is the file `spec/acri-v0.1.md` itself, byte-
identical to the Lom main repository's `specs/acri/acri-v0.1.md` at the time
of this repository's founding (immutability of a numbered cut applies from
this entry onward). Content: L0 object model (Diagnostic, RepairSuggestion,
three safety axioms) — L1 CLI protocol (commands, envelope, exit-code
matrix, conformance levels) — L2 repair-benchmark methodology (informative)
— reference consumer — change protocol — governance.

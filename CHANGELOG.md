# Changelog

Every cut of the ACRI specification is anchored here (version carrier #2;
carrier #1 is the git tag — see the repository README, "Versioning").
Repository milestones outside the specification itself (e.g. conformance
engineering batches) are also anchored here, clearly labeled as such.

## Conformance Batch 2+3+4 — 2026-10-28 (delivered; not a spec cut)

The executable conformance suite (engineering batches 2-4 of
`conformance/README.md`): runner + all 14 probes of
`conformance/suite-design.md` + the first adapter manifest + the first full
run against the reference implementation. No specification text changed.

1. **Runner** (`conformance/suite/`, Python, standard library only) — drives
   the toolchain under test exclusively through its CLI via subprocess
   (stdout + exit code; nothing imported from the implementation), decides
   every probe into the three-state vocabulary (`conformant` /
   `by-mapping` / `non-conformant`; OPTIONAL-absent = `skipped`, not
   failed), emits one line per probe plus the aggregate summary, and writes
   a Markdown evidence artifact to `conformance/.tmp/` (gitignored).
   Mutating probes run on per-run workspace copies — committed probe files
   are never mutated. C-03 takes a second `--baseline` adapter manifest
   (single-release runs report `skipped`); C-12 is the manual tier
   (`manual-pending` placeholder, no machine decision).
2. **Adapter manifest** (`conformance/adapters/lom.json`) — Lom command
   templates (`check --json` / `fix --plan --json` / `fix --apply` /
   `codes --json` / `explain <code> --json`), envelope field addressing for
   every probed schema (`lom-diag/v1`, `lom-fix/v1`, `lom-apply/v1`,
   `lom-codes/v1`, `lom-explain/v1`, `l2-fix/v2`), the registered mappings
   (§1.2 enum-name case normalization; the `anchor:"none"` 0:0 sentinel per
   the v0.2-draft erratum), and the two registered deviations with their
   re-check recipes.
3. **Probe files** (`conformance/probes/lom/`) — clean / error / warnings-
   only / mixed-suggestions (spans the confidence/action grid: high-insert,
   high-replace, medium-replace, low-hint on spatially distinct targets) /
   hint-only (the `fixed == bad` guard) / `l2-fail.txt` (rejection lines
   captured verbatim from the real self-compiler pipeline) / a `pkg-mixed`
   fixture (PKG002 path). The runner self-verifies every probe triggers
   its expected condition before probing (8/8 ok on the first run).
4. **First run — Lom v1.16.0** (binary
   `D:\lom-lang\lom\target\release\lom.exe`): 7 `conformant` (C-01, C-05,
   C-06, C-07, C-08, C-09, C-10), 5 `by-mapping` (C-02, C-04, C-11, C-13,
   C-14), 0 `non-conformant`, C-03 `skipped` (single release), C-12
   `manual-pending`. Consistent with `implementations/lom.md`, including
   the dual-write `position` form (C-01/C-02), the OPTIONAL `explain`
   present (C-10), and both registered deviations re-verified live (C-14:
   `pkg-expand` mixed failure exits 1 carrying PKG002; the LSP band exits 1
   on exit-without-shutdown).

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

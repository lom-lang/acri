# Implementation registration: Lom (reference implementation)

| Field | Value |
|---|---|
| Implementation | **Lom** — LLM-repair-native dynamic language and toolchain (Rust, zero third-party crates) |
| Repository | https://github.com/lom-lang/lom (main repository) |
| Role | Reference implementation of ACRI (specification §0, §6) |
| Registered | 2026-10-28 (this repository's founding batch) |
| Conformance since | **v1.15.0** (tag `v1.15.0`, 2026-10-28) — native L0; L1 substance since v1.10.0 (β-2) |
| Verified against | ACRI v0.1 (`spec/acri-v0.1.md` in this repository) |

## Conformance claim (per specification §2.3)

- **L0 — Conformant (native, dual-write transition).** Since v1.15.0 the
  `check --json` envelope (`lom-diag/v1`) carries the §1.1 `position` object
  natively: the nested `{"line","col","anchor"}` is dual-written alongside
  the flat top-level `line`/`col` pair, which is retained (append-only) for
  v1-era consumers under the forward-compatibility axiom. `anchor` is
  `"exact"` for precise-point channels and `"none"` with an honest `0:0` for
  the positionless input-unreadable channel (`LEX000`) — the very shape the
  v0.2-draft erratum legitimizes. §1.2 suggestion enums match after
  documented case normalization; §1.3 axioms are honored (see the mapping).
- **L1 — Conformant.** All REQUIRED §2.1 commands present (`check --json`,
  `fix --plan/--apply`, `codes --json` since v1.10.0) plus the OPTIONAL
  `explain <code>` (since v1.15.0, human and `--json` forms, unknown code →
  exit 2). Exit-code matrix honored since the v1.10.0 exit-code band, with
  the two registered deviations below.
- **L2 — Conformant (documented).** RepairLoopBench (`eval/README.md` in the
  main repository) is the reference instance of §3: 138 tasks (v1.16.0),
  dual verbatim capture, machine-gated prompts, multi-chain reference
  validation, black-box scoring, declared scope.

## Registered deviations (authoritative list)

Both deviations are registered in the authoritative clause-by-clause mapping —
[specs/acri/lom-conformance.md](https://github.com/lom-lang/lom/blob/main/specs/acri/lom-conformance.md)
in the main repository — which remains the single source for deviation
statements:

1. `pkg-expand` mixed failure path exits 1 (not ≥2): the path carries PKG
   diagnostic codes, treated as diagnostic semantics rather than tool
   failure.
2. The LSP protocol band exits 1: r58-locked protocol behavior, not part of
   the ACRI CLI surface.

## Evidence pointers

- Mapping document (clause ↔ behavior ↔ status):
  `specs/acri/lom-conformance.md` in the main repository.
- Reference consumer (specification §4, runnable):
  `specs/acri/consumer.py` in the main repository.
- Benchmark card: `eval/README.md` in the main repository.
- Version anchors: main-repository tags `v1.10.0` (β-2: `codes` outlet,
  `l2-fix/v2` position, exit-code band), `v1.15.0` (C4 native position
  dual-write + D5 `explain`; ACRI L0 native conformant), `v1.16.0`
  (benchmark growth to 138 tasks; `LEX000` `0:0`+`"none"` shape re-verified
  live at registration time).

## Suite status

The executable conformance suite is delivered (Conformance Batch 2+3+4,
2026-10-28; see [conformance/README.md](../conformance/README.md) for how to
run it). First machine run against Lom v1.16.0 (2026-10-28): **7
`conformant`, 5 `by-mapping`, 0 `non-conformant`**, C-03 `skipped`
(single-release run), C-12 `manual-pending` (manual tier) — consistent with
this registration's mappings and both registered deviations, which the suite
re-verified live (C-14). Note on C-04: the §1.2 enum-name case-normalization
mapping is a passthrough on v1.16.0 (emitted enums are already lowercase);
the mapping stays registered for older builds, so the probe reports
`by-mapping` while the mapping is on file.

# ACRI Conformance Suite — Probe Inventory (draft)

> **Status: draft inventory for Batch 2-3 engineering (see
> [README.md](README.md) "Engineering batches").** One row per probe:
> id / clause probed / method / expected result / machine-decidability.
> Machine-decidability is itself three-state: `machine` (fully decided by the
> runner), `machine+mapping` (decided by the runner once the implementation's
> registered mapping is applied — reported `by-mapping`), `manual` (audited
> by document review during registration, listed here for completeness).

## Probe table

| Id | Clause | Probe method | Expected | Decidability |
|---|---|---|---|---|
| C-01 | §2.1 envelope + §1.1 REQUIRED fields | Run `check --json` on the error probe; parse JSON; assert envelope keys `schema`/`file`/`ok`/`summary`/`diagnostics` present, and each diagnostic has `code`/`severity`/`message`/`file`/`position` with `severity` ∈ {`error`,`warning`} and `code` matching `<NS><NNN>` | All assertions hold | machine |
| C-02 | §1.1 `position` object | For every diagnostic in the C-01 run: `anchor` ∈ {`exact`, `name-first`, `none`}; `line`/`col` are integers; `≥1` when anchor ≠ `none`; `0` permitted when anchor = `none` (v0.2-draft erratum) | No fabricated coordinates; no anchor outside the enum | machine |
| C-03 | §1.1 code stability (cross-release) | Run the same probe set under two releases of the tool; compare the diagnostic code multisets | Multisets identical | machine (requires both binaries — runner takes two adapter manifests) |
| C-04 | §1.2 RepairSuggestion enums | Run `fix --plan --json` on the mixed probe; for each suggestion assert `confidence` ∈ {`high`,`medium`,`low`} and `action` ∈ {`insert`,`replace`,`delete`,`hint`} after the registered enum-name normalization (e.g. `High` → `high`) | All values in enum; normalization itself is a registered mapping | machine+mapping |
| C-05 | §1.3 AXIOM 1 (behavioral) | Snapshot the mixed probe file; run `fix --apply`; re-run `check --json`; diff. The probe must contain at least one Low or Medium suggestion and one hint-only suggestion touching distinct text | Only high-confidence non-hint suggestions took effect; Low/Medium/hint targets byte-identical to snapshot; never `fixed == bad` inverted (a file whose only suggestions are Low/Medium/hint is left unchanged) | machine |
| C-06 | §1.3 AXIOM 3 (plan side-effect-free) | Snapshot the error probe; run `fix --plan`; diff file bytes | Byte-identical | machine |
| C-07 | §2.1 REQUIRED command set | Probe `check --json`, `fix --plan --json`, `fix --apply`, `codes --json` through the adapter manifest; unrecognized command templates count as absent | All four present and parseable | machine |
| C-08 | §2.1 `codes` outlet closed loop | Parse `codes --json`; for each diagnostic observed in C-01, assert its `code` resolves in the table, with matching severity | Zero unresolved codes; severity agreement 100% | machine |
| C-09 | §2.2 exit-code matrix | Four runs: error probe → expect 1; warnings-only probe → expect 0; `fix --plan` on error probe → expect 0; nonexistent input path → expect ≥ 2 | All four cells match | machine |
| C-10 | §2.1 `explain <code>` (OPTIONAL) | If the command is registered: known code → rc 0 with non-empty output; unknown code → rc ≥ 2 | As stated; absent command → probe skipped, not failed | machine (conditional) |
| C-11 | Forward-compatibility (consumers ignore unknown fields) | Run the reference consumer (spec §4 shape) against the toolchain end-to-end; the consumer must complete without rejecting envelope extensions | Consumer run completes rc 0 | machine+mapping (consumer needs the adapter manifest) |
| C-12 | §3 L2 methodology (six clauses) | Document review of the implementation's published benchmark card (dual capture, synthesis declaration, multi-chain validation, black-box scoring, machine gate, scope honesty) | All six declared and evidenced in the card | manual |
| C-13 | `l2-fix/v2` position field (Lom extension surface) | Run the registered L2-fail probe through the L2 fix outlet; assert each plan carries the structured `position` object with `ln:cl`-derived line/col | Position present and well-formed per the registration mapping | machine (bound to Lom; other implementations skip) |
| C-14 | Registered deviations re-check | Re-run C-09 sub-cells named as registered deviations in `implementations/*.md` (e.g. Lom: `pkg-expand` mixed path stays 1; LSP band stays 1); assert the deviation still matches its registration, so registrations cannot rot silently | Observed behavior equals the registered deviation | machine+mapping |

## Notes

- Probes C-01…C-11, C-14 are implementation-neutral (driven through adapter
  manifests); C-13 is explicitly reference-implementation-bound and skipped
  for everyone else; C-12 is the only fully manual row and gates L2
  registration rather than emitting a pass/fail.
- Reporting follows the three-state vocabulary of [README.md](README.md)
  (`conformant` / `by-mapping` / `non-conformant`); `machine+mapping` probes
  can never report better than `by-mapping` for the mapped aspect.
- The runner (Batch 2+) emits one summary line per probe plus an aggregate
  three-state table; no partial credit, no averaging.

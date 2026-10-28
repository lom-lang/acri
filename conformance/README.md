# ACRI Conformance Suite

This directory holds the ACRI conformance suite — machine-checkable probes
that measure any ACRI L1 toolchain against the specification in `spec/`.
**Status: runner delivered.** The executable suite lives in
[suite/](suite/) (Python, standard library only); the probe inventory is
[suite-design.md](suite-design.md); implementations bind through adapter
manifests in [adapters/](adapters/) and supply their own probe files under
[probes/](probes/). The first run against the reference implementation
(Lom v1.16.0) reports 7 `conformant`, 5 `by-mapping`, 0 `non-conformant`
(C-03 `skipped` — single release; C-12 `manual-pending` — manual tier),
consistent with the registration in `implementations/lom.md`.

## Scope — the machine-checkable subset of L1

The suite covers the clauses of the specification that can be decided by
driving a CLI and inspecting its output. The initial probe set:

1. **Envelope completeness** — `check --json` emits the §2.1 envelope
   (`schema`/`file`/`ok`/`summary`/`diagnostics`) and every diagnostic carries
   the REQUIRED §1.1 fields (`code`/`severity`/`message`/`file`/`position`).
2. **Exit-code matrix** — the four §2.2 cells, measured behaviorally:
   error-severity diagnostics → 1; warnings-only or clean → 0;
   `fix --plan`/`fix --apply` completed → 0; tool-internal failure
   (e.g. unreadable input) → ≥ 2.
3. **`codes` outlet** — `codes --json` returns a machine-readable table, and
   every code observed in a real `check --json` run resolves against it
   (closed-loop bootstrap check).
4. **`l2-fix` position field** — (reference-implementation extension surface)
   the Lom `l2-fix/v2` envelope's structured position field, per the mapping
   registered in `implementations/lom.md`.
5. **AXIOM 1 behavioral test** — with a probe file whose suggestions span the
   confidence/action grid, `fix --apply` changes only what
   `confidence = "high" AND action ≠ "hint"` permits; a Low- or
   Medium-confidence suggestion is never auto-applied. This is a behavior
   test (run, apply, re-check, diff), not a documentation review.

Clauses that cannot be decided by driving the CLI (e.g. L2 benchmark
methodology, §3) are out of machine scope and are audited by document
review during registration.

## Reporting vocabulary — three states

Every probed clause reports exactly one of:

| State | Meaning |
|---|---|
| `conformant` | The toolchain satisfies the clause as written, natively. |
| `by-mapping` | The toolchain satisfies the clause via a registered mapping (e.g. enum-name case normalization, a legacy flat field dual-written alongside the ACRI object). The mapping must be documented in the implementation's entry under `implementations/`; the suite re-runs the probe through the mapping. |
| `non-conformant` | The clause is not satisfied. |

There is no partial credit and no fourth state; OPTIONAL clauses (§2.1
`explain`) report `conformant`/`non-conformant` only when present, and are
skipped (not failed) when absent.

## Probing method — any CLI, not just Lom

The suite binds to no language, runtime, or vendor (specification §0):

- **Process boundary only.** Probes drive the toolchain exclusively through
  its CLI via subprocess calls and parse stdout/exit codes. Nothing is
  imported from the implementation; no knowledge of the implementation's
  language is assumed.
- **Adapter manifest.** Each implementation under test provides a small
  manifest: command templates for `check --json`, `fix --plan`,
  `fix --apply`, `codes --json` (e.g. argument order), plus field addressing
  for its envelope. Probes are written against the manifest, not against
  Lom's flag spellings.
- **Implementation-owned probe files.** Because the suite cannot author
  source files in a language it does not know, each implementation supplies
  its own minimal probe set (a clean file, an error file, a warnings-only
  file, a mixed-suggestion file, an unreadable-input path). The suite
  specifies what each probe must exercise; the implementation provides the
  files; the runner verifies the probes actually trigger the expected
  conditions (e.g. the error file does produce an error-severity diagnostic).

## Usage

Run the suite against a registered implementation (Python 3.8+, standard
library only; no installation):

```
python conformance/suite/runner.py conformance/adapters/lom.json
```

- One line per probe (`C-xx = state`), then the aggregate three-state
  summary. Exit code: `0` no `non-conformant`; `1` at least one
  `non-conformant`; `2` setup/probe self-verification failure (no verdicts
  emitted).
- A Markdown artifact with per-probe evidence is written to
  `conformance/.tmp/report-<timestamp>.md` (gitignored). Run artifacts and
  mutated probe copies live in a per-run workspace under `conformance/.tmp/`
  and are removed afterwards — committed probe files are never mutated.
- Cross-release code-stability (C-03): pass a second, older adapter
  manifest: `--baseline conformance/adapters/lom-vX.json`. Without it C-03
  reports `skipped`.
- C-12 (§3 L2 methodology) is the manual tier: the runner emits
  `manual-pending` and never a machine pass/fail.
- Registering another toolchain: add `conformance/adapters/<tool>.json`
  (command templates + envelope field addressing + registered mappings +
  probe list; see the schema keys used in `adapters/lom.json`), supply
  `conformance/probes/<tool>/…` files that trigger the required conditions
  (the runner self-verifies them before probing), and register the results
  in `implementations/<tool>.md`.

## Engineering batches

The suite is built in batches:

- **Batch 1 (done)** — skeleton: scope (this README), probe inventory draft
  ([suite-design.md](suite-design.md)), and the first implementation
  registration (`implementations/lom.md`).
- **Batch 2 (done)** — runner core: adapter manifest schema
  (`adapters/lom.json` — command templates, envelope field addressing,
  registered mappings) + machine probes C-01/C-02/C-06/C-07/C-09 (envelope
  completeness, position object, plan side-effect-freedom, REQUIRED command
  set, exit-code matrix).
- **Batch 3 (done)** — behavioral probes: C-05 AXIOM 1 apply test (run,
  apply, re-check, diff on a probe spanning the confidence/action grid),
  C-08 `codes` closed loop, C-13 `l2-fix/v2` position field, C-14
  registered-deviations re-check (Lom `pkg-expand` rc 1, LSP band rc 1).
- **Batch 4 (done)** — reporter: three-state per-probe lines + aggregate
  summary + Markdown artifact (`conformance/.tmp/`, gitignored), and the
  full first run against the reference implementation (Lom v1.16.0),
  recorded above.

Layout: `suite/runner.py` (entry) · `suite/adapter.py` (manifest loader +
process-boundary driver) · `suite/probes.py` (C-01…C-14) ·
`suite/report.py` (three-state model + rendering) · `adapters/`
(implementation manifests) · `probes/<impl>/` (implementation-owned probe
files).

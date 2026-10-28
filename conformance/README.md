# ACRI Conformance Suite (planned)

This directory holds the ACRI conformance suite — machine-checkable probes
that measure any ACRI L1 toolchain against the specification in `spec/`.
**Status: skeleton.** This README fixes the scope, the reporting vocabulary,
and the probing method; the probe inventory is drafted in
[suite-design.md](suite-design.md); the executable runner arrives in a later
batch (see "Engineering batches" below).

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

## Engineering batches

The suite is built in batches; this repository first stands up the skeleton:

- **Batch 1 (this repository, current)** — skeleton: scope (this README),
  probe inventory draft ([suite-design.md](suite-design.md)), and the first
  implementation registration (`implementations/lom.md`). No executable
  runner yet.
- **Batch 2 (later)** — runner core: adapter manifest schema + the first
  machine probes (envelope completeness, exit-code matrix, plan
  side-effect-freedom).
- **Batch 3 (later)** — behavioral probes: AXIOM 1 apply test, `codes`
  closed loop, `l2-fix/v2` position field (against Lom as reference).
- **Batch 4 (later)** — reporter: three-state summary output (CLI + Markdown
  artifact) and a full first run against the reference implementation,
  published with the registration entry.

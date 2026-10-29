# ACRI — Agent-Compiler Repair Interface

**This repository is the home of the ACRI specification** — the standalone,
implementation-neutral "spec house", separate from any implementing project.

## What is ACRI

ACRI defines the interface between a compiler/toolchain and the AI agents
that consume its diagnostics and act on its repair suggestions. It is a
thin, deliberate contract: structured diagnostic objects, confidence-graded
repair suggestions governed by a safety axiom (auto-apply only
high-confidence, non-hint actions), a minimal CLI protocol with an exit-code
matrix, and a methodology for contamination-safe repair-loop benchmarks. The
reference implementation is the Lom language and toolchain; conformance
requires no adoption of Lom or of any particular language, runtime, or
vendor.

## Three layers

| Layer | Content |
|---|---|
| **L0 — Object model** (normative) | The `Diagnostic` and `RepairSuggestion` objects (§1.1/§1.2) and the three safety axioms (§1.3): AXIOM 1 auto-apply gate, AXIOM 2 cognitive-suggestion rule, AXIOM 3 plan/apply separation. |
| **L1 — CLI protocol** (normative) | The command set `check --json` / `fix --plan` / `fix --apply` / `codes` (plus OPTIONAL `explain`), the `check --json` envelope, the exit-code matrix, and the conformance levels (L0-conformant / L1-conformant / L2-documented). |
| **L2 — Repair-benchmark methodology** (informative) | Six clauses for a contamination-safe repair-loop benchmark: dual verbatim capture, synthesis declaration, multi-chain reference validation, black-box scoring, machine gate on prompts, scope honesty. Reference instance: RepairLoopBench. |

## Versioning

- **0.x drafts may revise freely between cuts**; 1.0 will be the first
  stable cut.
- Additive field/enum changes are **minor**; removal or semantic change of a
  REQUIRED field, or an axiom change, is **major**.
- **A numbered cut is immutable**: once a version is cut, its content never
  changes in place — any textual change, down to a typo, requires a new
  version number (errata ship as a new draft/cut; see `spec/`).
- Every cut is anchored by two carriers: a **git tag** for that version in
  this repository, and an entry in **`CHANGELOG.md`**. A version lacking
  either is not cut.

## Governance

- Current steward: **the Lom project & wytyKen**.
- The specification is **implementation-neutral** (§0 of the spec);
  stewardship of the Lom language and stewardship of the ACRI specification
  are separable, and a future transfer to a neutral foundation is
  explicitly not precluded (precedents: MCP and AGENTS.md → Linux
  Foundation-hosted Agentic AI Foundation, 2025-12).

## Repository layout

```
spec/                         # The specification itself
  acri-v0.1.md                # v0.1 — numbered cut, immutable (byte-identical to the main repo's cut)
  acri-v0.2-draft.md          # v0.2 errata draft (undecided; three [v0.2-draft]-tagged revisions)
conformance/                  # Conformance suite (runner delivered 2026-10-28)
  README.md                   # Scope, three-state reporting, probing method, batch plan
  suite-design.md             # Probe inventory (C-01…C-14)
  suite/                      # Executable runner (Python, standard library only)
  adapters/                   # Adapter manifests (lom.json = first/reference)
  probes/                     # Implementation-owned probe files (probes/lom/ = first set)
implementations/              # Implementation registrations
  lom.md                      # Lom (reference implementation) — L0/L1/L2 conformant since v1.15.0
mappings/                     # Adapter-source mappings (informative; never modify spec/)
  sarif.md                    # SARIF v2.1.0 → ACRI L0/L1 — adapter-author guide, field-checked against the OASIS spec
adopt/                        # Adoption aids for toolchain repos
  AGENTS.md.snippet           # Paste-ready AGENTS.md block (commands, exit codes, safety rules)
  README.md                   # What to paste where
CHANGELOG.md                  # Version carriers (one entry per cut)
LICENSE-SPEC                  # CC-BY-4.0 (spec text)
LICENSE-CODE                  # Apache-2.0 (code)
```

## How to conform

1. **Read the specification** — `spec/acri-v0.1.md` is the operative
   version. Map your toolchain's diagnostics, suggestions, CLI, and exit
   codes onto L0/L1; document any enum-name or field-shape mappings. If
   your tool already emits SARIF v2.1.0 (GCC 13+, Clang, most static
   analyzers), start from the verified mapping in `mappings/sarif.md`; to
   teach agents in your repo how to consume your interface, paste
   `adopt/AGENTS.md.snippet` into your `AGENTS.md`.
2. **Run the conformance suite** — write an adapter manifest for your CLI
   (see `conformance/adapters/lom.json` for the shape) plus your own probe
   files, then run `python conformance/suite/runner.py <manifest.json>`
   (delivered 2026-10-28; see `conformance/README.md`).
3. **Register**: open a PR adding `implementations/<your-tool>.md`
   (use `implementations/lom.md` as the template) stating your conformance
   levels, registered deviations, and evidence pointers.

## License

Dual-licensed by artifact type:

- **Specification text** (`spec/`, plus the descriptive documents in this
  repository): **Creative Commons Attribution 4.0 International
  (CC-BY-4.0)** — see `LICENSE-SPEC`.
- **Code** (the conformance runner and any scripts, when they land):
  **Apache License 2.0** — see `LICENSE-CODE`.

# ACRI TODO

> Maintenance ledger for this repository. Cross-workspace matters live in the
> workspace-local handbook (not in any public repo); this file tracks this
> repository's own items only. Operative spec: **v0.1** (v0.2-draft pending).

## Pending batches

- **v0.2 cut decision** — the v0.2 errata draft (three tagged revisions:
  anchor:none zero-coordinate sentinel, refreshed verbatim example, immutability
  + dual version carriers) awaits the user's cut/no-cut decision. If cut:
  refresh the §3 reference-instance counts (129 → current suite size) first
  (0.x drafts may revise freely before cutting), then tag + CHANGELOG entry.
- **Conformance C-03 cross-release probe** — implemented in the runner
  (dual-manifest comparison) but never exercised against two real releases;
  run when a second toolchain release is available.

## Observation points (event-triggered)

- **MCP spec watch** — if the MCP specification introduces diagnostics/repair
  primitives, re-evaluate the ecosystem position (see the ecosystem survey,
  2026-10-29: MCP currently has none; it is the sole structural long-term
  overlap threat).
- **SARIF TC watch** — SARIF revisions adding confidence-grading or
  apply-permission semantics would narrow the mapping gap documented in
  `mappings/sarif.md`.

## Done (recent)

- Conformance suite batches 2+3+4 delivered (runner + 14 probes + adapter
  manifest + probe set); first run vs the reference toolchain: zero
  non-conformant.
- Ecosystem mapping & adoption aids: `mappings/sarif.md` (SARIF 2.1.0 → ACRI
  L0/L1 adapter mapping) + `adopt/AGENTS.md.snippet`.

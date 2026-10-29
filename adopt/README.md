# adopt/ — adoption aids

Two paste-ready artifacts for toolchains that want to speak ACRI without
writing spec prose themselves:

- **`AGENTS.md.snippet`** — a Markdown block to paste into your repository's
  `AGENTS.md`. It tells any agent (Codex, Cursor, Jules, Gemini CLI, …) how
  to consume your toolchain's ACRI repair interface: the four commands, the
  exit-code semantics, the three safety axioms in one line each, and the
  consumption discipline. Replace the `<CHECK_CMD>` / `<FIX_PLAN_CMD>` /
  `<FIX_APPLY_CMD>` / `<CODES_CMD>` (and optional `<EXPLAIN_CMD>`)
  placeholders with your real commands, fill in the conformance-declaration
  sentence at the bottom, and delete the `explain` row if you do not ship
  the OPTIONAL command.
- **`../mappings/sarif.md`** — if your tool already emits SARIF v2.1.0
  (GCC 13+, Clang, …), that appendix maps it onto ACRI L0/L1 so a thin
  wrapper can front it with the commands above.

AGENTS.md is the lowest-cost distribution channel for ACRI conventions
(60k+ repositories already carry one); pasting this snippet is the whole
integration on the instruction side.

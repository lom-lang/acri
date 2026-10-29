# Mapping appendix: SARIF v2.1.0 → ACRI L0/L1

> **Status**: Informative adapter guidance — a guide for adapter authors. It
> is **not** part of the ACRI specification, does not modify `spec/` in any
> way, and creates no conformance obligations for existing implementations.
> The operative specification remains **ACRI v0.1**
> (`../spec/acri-v0.1.md`). One mapping decision below (`position` `0:0` +
> `"none"`) follows the `../spec/acri-v0.2-draft.md` erratum; adapters that
> declare strict-v0.1 conformance must register a deviation instead (see
> §3.3).
>
> **Verified source**: SARIF v2.1.0 OASIS Standard
> (<https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html>,
> OASIS, 2020-03-27). Every SARIF field name and quotation below was checked
> against that document on **2026-10-29**. GCC/Clang flags were checked
> against their current official manuals on the same date (§7).

## 1. Purpose

SARIF is the existing formal standard with the largest overlap against the
ACRI L0 object model: `result`'s four core fields correspond one-to-one to
the ACRI `Diagnostic`, and `fixes` provide a patch-style repair expression
equivalent to `RepairSuggestion`'s `action` + `payload`. SARIF, however, has
no confidence grading, no safety axioms, no CLI contract, and no
repair-benchmark methodology.

This appendix therefore treats SARIF **as an adapter source**: any tool that
can emit SARIF v2.1.0 (GCC 13+, Clang, GitHub code scanning exporters, most
static analyzers) can be connected to the ACRI consumption surface by a
wrapper that implements this mapping. Nothing here requires the SARIF
producer to change.

## 2. Terminology

- "Adapter" — a wrapper that consumes SARIF v2.1.0 log files and exposes the
  ACRI L0 objects (and, if it wraps a CLI, the L1 command set).
- Quotations are from the SARIF v2.1.0 spec with section numbers as `§n.m`.

## 3. L0 field correspondence (SARIF `result` → ACRI `Diagnostic`)

| ACRI field | SARIF source | Rule |
|---|---|---|
| `severity` | `result.level` | `error` → `error`; `warning` → `warning`; `note` → `warning` (or drop, per registered policy); absent/`none` with non-`fail` kind → drop (or `warning` per registered policy). See §3.1. |
| `message` | `result.message.text` | Direct copy; id-only messages resolved or honestly synthesized. See §3.2. |
| `file` | `result.locations[0].physicalLocation.artifactLocation.uri` | URI-to-path normalization; fallback to `analysisTarget` or the run's input. See §3.3. |
| `position` | `result.locations[0].physicalLocation.region.{startLine,startColumn}` | Both 1-based positive integers, same as ACRI; `anchor: "exact"`. No location → `anchor: "none"` (0:0 per the v0.2-draft erratum). See §3.3. |
| `code` | `result.ruleId`, or `ruleIndex` → `run.tool.driver.rules[i].id` | Adapter MUST normalize to `<NS><NNN>`. See §3.4. |
| `stage` | — (no counterpart) | Adapter MAY omit or set a fixed value (e.g. `static-analysis`). |
| `hint` | — (closest: `result.fixes[].description.text`) | Adapter MAY derive a one-line hint from the fix description, if present. |

### 3.1 `severity` ← `result.level`

SARIF spec (§3.27.10): "A result object MAY contain a property named `level`
whose value is one of a fixed set of strings that specify the severity level
of the result", with the values `error` ("a serious problem was found"),
`warning` ("a problem was found"), `note` ("a minor problem or an opportunity
to improve the code was found"), and `none` ("The concept of 'severity' does
not apply to this result because the `kind` property (§3.27.9) has a value
other than `'fail'`").

Two SARIF defaulting rules matter to adapters and are easy to miss:

- Kind default (§3.27.9): "If `kind` is absent, it SHALL default to
  `'fail'`." — so a bare `result` with no `level`/`kind` is a *failure*
  report, not a note.
- Level default (§3.27.10): for `kind` ≠ `'fail'`, "if `level` is absent, it
  SHALL default to `'none'`"; for `kind` = `'fail'` with `level` absent, the
  level is resolved through the rule's configuration override chain
  (`invocation.ruleConfigurationOverrides` →
  `reportingDescriptor.defaultConfiguration.level`), and "IF `level` has not
  yet been set THEN SET `level` to `'warning'`."

Mapping rules (ACRI `severity` is exactly `"error" | "warning"`, where
`error` blocks the build and `warning` does not):

| SARIF `level` (after defaulting) | ACRI `severity` | Rationale |
|---|---|---|
| `"error"` | `"error"` | Direct: serious problem ↔ blocks compilation/equivalent. |
| `"warning"` | `"warning"` | Direct. |
| `"note"` | `"warning"` (default) — or dropped, if the adapter's registered policy says so | ACRI has no tier below `warning`; a note does not block, which is exactly ACRI `warning` semantics. Dropping notes is a legitimate registered policy, silently swallowing them is not. |
| `"none"`, or `level` absent because `kind` ≠ `"fail"` (`pass` / `open` / `review` / …) | emit no `Diagnostic` (default) — or `"warning"` per registered policy | These results are not defect reports; mapping them as warnings would be noise. |

The adapter MUST record its note/non-fail policy in its mapping document
(the conformance-suite notion of a "registered mapping").

### 3.2 `message` ← `result.message.text`

SARIF (§3.27.11): "A result object SHALL contain a property named `message`
whose value is a message object (§3.11) that describes the result." The
`message` object itself (§3.11.2) only requires that "At least one of the
`text` (§3.11.8) or `id` (§3.11.10) properties SHALL be present", where
`text` (§3.11.8) is "a non-empty string containing a plain text message".

Rules:

1. `text` present → copy verbatim into ACRI `message`.
2. `text` absent, `id` present → the adapter SHOULD resolve the string from
   `run.tool.driver.rules[ruleIndex].messageStrings[id]` (applying
   `arguments` if present). If resolution is impossible, the adapter MUST
   NOT fabricate prose; it MUST emit an honest fallback such as
   `SARIF message id '<id>' (unresolved)` and register that behavior.
3. `markdown` present → ignore (SARIF §3.11.9 itself guarantees `text`
   accompanies `markdown`).

### 3.3 `file` / `position` ← `result.locations[0].physicalLocation`

SARIF (§3.27.12): "A result object SHOULD contain a property named
`locations` whose value is an array of zero or more location objects
(§3.28)". The `physicalLocation` (§3.28.3) is "a physicalLocation object
(§3.29) that identifies the file within which the location lies"; its
`artifactLocation.uri` (§3.4.3) is "a string containing a URI [RFC3986]
that specifies the location of the artifact". Inside `region` (§3.30),
`startLine` (§3.30.5) is "a positive integer equal to the line number of
the line containing the first character in the region", and `startColumn`
(§3.30.6) is "a positive integer equal to the column number of the first
character in the region"; "If `startColumn` is absent, it SHALL default to
1."

Rules:

1. `file` ← `locations[0].physicalLocation.artifactLocation.uri`, with URI
   normalization: strip the `file://` scheme, resolve relative references
   against `uriBaseId`/`originalUriBaseIds` when present. Multiple entries
   in `locations` (allowed by §3.27.12 for genuinely multi-location
   conditions): use `[0]` as the primary and MAY attach the rest as an
   adapter extension field.
2. `position` ← `{ "line": region.startLine, "col": region.startColumn,
   "anchor": "exact" }`. Both systems are 1-based positive integers — no
   off-by-one conversion. SARIF's defaulting ("If `startColumn` is absent,
   it SHALL default to 1") already yields an ACRI-legal value. A multi-line
   `region` has no ACRI counterpart; the adapter MAY attach
   `endLine`/`endColumn` as extension fields (ACRI consumers MUST ignore
   unknown fields).
3. **No usable location** (SARIF explicitly allows this — §3.27.12 NOTE 1:
   "In rare circumstances, it might not be possible to specify a location
   for a result"): emit `"position": { "line": 0, "col": 0, "anchor":
   "none" }` and set `file` to the best honest fallback in this order:
   `result.analysisTarget` URI → the adapter's declared analysis input → a
   literal non-fabricated placeholder registered in the mapping. This
   follows the `../spec/acri-v0.2-draft.md` §1.1 erratum (the `0:0`
   no-position sentinel). An adapter that declares strict v0.1 conformance
   cannot emit `0:0` under the v0.1 reading and MUST instead register this
   as a deviation; fabricating `1:1` is never acceptable (v0.1 §1.1:
   "`name-first` … MUST NOT be fabricated as `1:1`" — the honesty rule
   applies a fortiori to `none`).

### 3.4 `code` ← `ruleId` / `ruleIndex` → `rules[].id`

SARIF (§3.27.5): `ruleId` is "a hierarchical string (§3.5.4) whose leading
components specify the stable identifier of the rule that was evaluated to
produce the result. In addition to being stable, `ruleId` SHOULD be opaque."
(§3.27.6): `ruleIndex` is "the array index … of the [rule's
`reportingDescriptor`] within" the component's `rules` array — §3.19.23: "A
toolComponent object MAY contain a property named `rules` whose value is an
array of zero or more unique `reportingDescriptor` objects (§3.49)", reached
via `run.tool` (§3.14.6, "SHALL contain … a `tool` object (§3.18)") →
`.driver` (§3.18.2, "SHALL contain a property named `driver` whose value is
a `toolComponent` object (§3.19)"). Each `reportingDescriptor` (§3.49.3)
"SHALL contain a property named `id` whose value is a string. In the case of
a rule, `id` SHALL contain a stable identifier for the rule and SHOULD be
opaque" (spec example: `"CA2101"`).

**The normalization gap**: ACRI v0.1 §1.1 requires `code` to have the format
`<NS><NNN>` (namespace + digits); SARIF rule identifiers only have to be
stable and opaque — `"CA2101"`, `"cpp/unused-include"`, `"clang-diagnostic-
unused-variable"` are all legal SARIF and none is a legal ACRI code. The
normalization is therefore **the adapter's responsibility**, and it is a
MUST:

1. The adapter MUST map every SARIF rule identifier it emits to an ACRI
   `<NS><NNN>` code. Recommended scheme: reserve one namespace (or one per
   producer, e.g. `SRC`/`SCC`…) for SARIF-derived rules and assign digits
   deterministically from the SARIF identifier (stable hash or a checked-in
   allocation table). For hierarchical `ruleId`s, normalize the leading
   component only.
2. The SARIF-id → ACRI-code table MUST be stable across adapter releases
   (ACRI §1.1: "Codes MUST be stable across releases") and MUST be published
   through the `codes` command so it doubles as the namespace registry.
3. Resolution order: `ruleId` if present; else `ruleIndex` →
   `run.tool.driver.rules[ruleIndex].id`; if neither resolves (SARIF permits
   a `result` to carry only a `rule` object, or nothing), the adapter MUST
   assign a stable synthesized code and register the derivation rule in its
   mapping document.

### 3.5 Fields with no SARIF counterpart

`stage` and `hint` have no SARIF source. Adapters MAY synthesize them
(`stage: "static-analysis"`; `hint` ← the first `fixes[].description.text`)
or omit them — both are OPTIONAL in ACRI §1.1.

## 4. Exit-code matrix mapping (L1)

SARIF is a file format, not an interaction protocol, so the ACRI §2.2
exit-code matrix binds the **adapter's CLI**, not the SARIF producer. The
SARIF evidence available for the decision:

- §3.14.11: "A `run` object MAY contain a property named `invocations`
  whose value is an array of zero or more `invocation` objects (§3.20)".
- §3.20.14: "An `invocation` object SHALL contain a property named
  `executionSuccessful` whose value is a Boolean that is `true` if the
  engineering system that started the process knows that the analysis tool
  succeeded, and `false` if the engineering system knows that the tool
  failed." (Spec NOTE: "This property is needed because not all programs
  exit with an exit code of 0 on success and non-0 on failure.")
- §3.20.9: "an `invocation` object SHOULD contain a property named
  `exitCode` whose value is an integer specifying the process exit code."

Recommended adapter strategy (the column "ACRI §2.2 situation" is what the
adapter exits with):

| Condition observed by the adapter | ACRI §2.2 situation | Adapter exit |
|---|---|---|
| SARIF file unreadable / not valid JSON / not a SARIF log (adapter's own failure) | The tool itself failed | ≥ 2 |
| Any mapped `result` has ACRI `severity: "error"` | `check`: one or more error-severity diagnostics | 1 |
| Results are warnings/notes only, or none | `check`: warnings only, or clean | 0 |

Notes:

1. Decide from the **mapped results**, not from the producer's exit code:
  compiler exit-code conventions differ from ACRI's matrix (a compiler exits
  non-zero for ordinary diagnostics), so blindly forwarding
  `invocations[].exitCode` would misreport ordinary errors as tool failure.
2. `executionSuccessful: false` (or an `exitCode` that indicates crash-like
  failure under the producer's documented convention) SHOULD make the
  adapter skeptical of result completeness, but per the table above it maps
  to ≥ 2 only when the adapter itself cannot produce a trustworthy mapping
  (e.g. truncated log); otherwise report the mapped results and exit per
  their severities, optionally attaching an extension field noting the
  invocation state. Whichever policy is chosen, register it.

## 5. `fixes` → `RepairSuggestion`

### 5.1 The SARIF side, verified

- §3.27.30: "A `result` object MAY contain a property named `fixes` whose
  value is an array of zero or more unique `fix` objects (§3.55)."
- §3.55.1: "A `fix` object represents a proposed fix for the problem
  indicated by `theResult`. It specifies a set of artifacts to modify. For
  each artifact, it specifies regions to remove, and provides new content to
  insert."
- §3.56.3: "An `artifactChange` object SHALL contain a property named
  `replacements` whose value is an array of one or more `replacement`
  objects (§3.57) each of which represents the replacement of a single
  region of the artifact specified by the `artifactLocation` property
  (§3.56.2)."
- §3.57.3: "A `replacement` object SHALL contain a property named
  `deletedRegion` whose value is a `region` object (§3.30) specifying the
  region to delete. If the length of the region specified by
  `deletedRegion` is zero, then `deletedRegion` specifies an insertion
  point, and the SARIF consumer performing the replacement SHALL NOT remove
  any content."
- §3.57.4: "A `replacement` object MAY contain a property named
  `insertedContent` whose value is an `artifactContent` object (§3.3) that
  specifies the content to insert in place of the region specified by the
  `deletedRegion` property (or at the point specified by `deletedRegion`, if
  `deletedRegion` has a length of zero and therefore specifies an insertion
  point)."
- Appendix G (Informative) advises producers to "structure those fixes in
  such a way as to affect a minimal range of content" because it "maximizes
  the likelihood that an automated tool can safely apply multiple fixes to
  the same artifact" — guidance about patch *shape*, containing nothing
  about when a fix *may be applied*.

### 5.2 Mapping table

| ACRI `RepairSuggestion` | SARIF source | Rule |
|---|---|---|
| `code` | the owning `result`'s normalized code (§3.4) | Direct. |
| `action` | `replacement.deletedRegion` × `insertedContent` | zero-length `deletedRegion` + `insertedContent` → `insert`; non-zero `deletedRegion` + `insertedContent` → `replace`; non-zero `deletedRegion` without `insertedContent` → `delete`. Zero-length region without content is a no-op — drop. |
| `suggestion` | `fix.description.text` (§3.55.2, "SHOULD contain") | Direct when present; otherwise the adapter MUST synthesize a factual one-liner (e.g. `"replace <region> in <file> per SARIF fix"`) — never an invented rationale. |
| `payload` | `deletedRegion` + `insertedContent.text` + `artifactChange.artifactLocation.uri` | Implementation-defined shape per ACRI §1.2; recommended: `{"file": …, "region": {startLine, startColumn, endLine, endColumn}, "text": …}`. For multi-replacement fixes carry the full list (see granularity below). |
| `position` | the (single) `deletedRegion`'s start, or the insertion point | `anchor: "exact"`; when a fix carries several replacements and the payload holds the list, use the first replacement's position. |
| `confidence` | **no SARIF counterpart** | See §5.3 — MUST be declared by adapter policy; SARIF-derived fixes default to `medium`/`low`, never `high`. |

**Granularity**: one SARIF `fix` is the atomic unit a SARIF consumer would
apply (Appendix G's disjointness argument presumes whole-fix application).
The default is therefore **one `fix` → one `RepairSuggestion`**, with all
`artifactChanges[].replacements[]` carried in `payload`. An adapter MAY
instead split per replacement; if it does, it MUST register that choice
(splitting changes the auto-apply unit and can break atomicity).

### 5.3 Confidence policy (normative for adapters)

SARIF v2.1.0 has **no concept of confidence or applicability**: nothing in
the `fix` object, its `rule`, or Appendix G distinguishes a mechanical,
always-correct rewrite from a behavior-changing suggestion; `rank`
(§3.27.25) is a result-ordering value, not a repair-confidence grade.
ACRI's AXIOM 1 keys auto-apply on `confidence = "high"`, so the confidence
assignment made here is a **safety decision, not a formatting decision**.
The following clauses bind every adapter that maps SARIF `fixes`:

1. The adapter MUST declare a confidence policy in its mapping document —
   the fixed, registered answer to "what confidence do SARIF-derived
   fixes get?" — before exposing mapped fixes through `fix --plan`.
2. SARIF-derived fixes MUST NOT be mapped to `confidence: "high"` by
   default. Absent producer-side evidence, the default assignment is
   `"medium"` (a well-formed patch that still requires a human or an
   explicit gate before application) or `"low"`; `"high"` is never inferred
   from SARIF content alone.
3. An upgrade to `"high"` is permitted only through an explicit, registered
   policy — e.g. a per-rule allowlist backed by human-verified evidence for
   that rule's patches — and the allowlist itself MUST be published via the
   `codes` table or the adapter's mapping document. (This is the AXIOM 1 /
   AXIOM 2 alignment: SARIF cannot tell an adapter which fixes are safe to
   auto-apply, so the adapter must not pretend that it can.)
4. If the adapter implements `fix --apply`, it MUST enforce AXIOM 1 on the
   mapped grades exactly as it would for native suggestions — which, given
   clause 2, means SARIF-derived fixes are applied only when an explicit
   policy (clause 3) promoted them.

## 6. Coverage deltas

### 6.1 ACRI has, SARIF lacks (the adapter must supply)

| ACRI feature | Adapter obligation |
|---|---|
| Confidence grading (`high`/`medium`/`low`) | Declared policy per §5.3. |
| The three safety axioms (§1.3) | Enforced in the adapter's CLI (`fix --plan` side-effect-free; `fix --apply` gated per AXIOM 1; no auto-rewrite of cognitive notices). |
| L1 command set + exit-code matrix (§2.1/§2.2) | The adapter *is* the CLI surface; SARIF producers have none to offer. |
| `codes` machine-readable code table | Built from the SARIF-id → ACRI-code normalization table (§3.4). |
| L2 repair-benchmark methodology (§3) | Out of adapter scope; belongs to the adopting toolchain. |

### 6.2 SARIF has, ACRI lacks (ACRI consumers ignore)

`fingerprints`/`partialFingerprints` (§3.27.16, stable result identity for
tracking), `baselineState` (§3.27.24, new/unchanged versus a baseline run),
rule taxonomies (`toolComponent.taxa`), `rank` (§3.27.25), `codeFlows`,
`stacks`, `relatedLocations`, `occurrenceCount`, and the whole run-level
governance apparatus (version control provenance, baselining, conversion).
None of these has a slot in ACRI L0/L1; per the forward-compatibility axiom,
ACRI consumers MUST ignore unknown fields, and adapters MAY pass them
through as extension fields when their consumers want them. An adapter MUST
NOT silently overload ACRI fields to smuggle this content (e.g. encoding
`baselineState` into `message`).

## 7. Producer onboarding (one-liners)

Verified against the official manuals on 2026-10-29:

- **GCC 13+** — the GCC manual (`-fdiagnostics-format`): "FORMAT is
  `text`, `sarif-stderr` or `sarif-file`" and "The `sarif-stderr` and
  `sarif-file` formats both emit diagnostics in SARIF Version 2.1.0
  format":

  ```
  gcc -fdiagnostics-format=sarif-file -c bad.c        # writes bad.c.sarif
  ```

- **Clang** — the Clang User's Manual ("Formatting of Diagnostics"):
  `-fdiagnostics-format=sarif` "emit[s] diagnostics as a SARIF JSON
  document" on standard error; the manual notes "The SARIF diagnostic
  format is currently unstable" and shows this example (check the Clang
  version's manual before relying on the emitted shape):

  ```
  clang -fsyntax-only -fdiagnostics-format=sarif -Wno-sarif-format-unstable -fno-caret-diagnostics t.c 2> diagnostics.sarif
  ```

An adapter then consumes the produced log and exposes the ACRI surface. For
conformance registration, wrap the result per `../conformance/README.md`
(adapter manifest + probe files) and register in `implementations/` with
this file cited as the mapping basis.

## 8. Related documents

- `../spec/acri-v0.1.md` — the operative specification (all § references
  above).
- `../spec/acri-v0.2-draft.md` — the `0:0` no-position sentinel erratum used
  in §3.3.
- `../adopt/AGENTS.md.snippet` — paste-into-your-repo instructions that
  steer agents to the mapped ACRI surface.
- `../conformance/README.md` — how an adapter proves the mapping.

"""C-01..C-14 探测项实现（对照 conformance/suite-design.md 逐行）。

每个探测函数接收共享上下文 Ctx，返回 ProbeResult。全部经 adapter（进程
边界）驱动被测 CLI；所有判定基于 stdout/exit code/文件字节。

判定与三态的对应：
- 断言全部成立且无登记映射介入        -> conformant
- 断言成立但经由登记映射（manifest mappings / 登记 deviations）-> by-mapping
- 断言不成立                        -> non-conformant
- OPTIONAL 缺席 / 单版本首跑 / 非 Lom 实现 -> skipped
- C-12 人工档                       -> manual-pending
"""

import os
import re

from adapter import Adapter, SetupError  # noqa: F401  (re-export for convenience)
from report import (BY_MAPPING, CONFORMANT, MANUAL_PENDING, NON_CONFORMANT,
                    ProbeResult, SKIPPED)

CODE_RE = re.compile(r"^[A-Z0-9]*[A-Z][A-Z0-9]*[0-9]{3}$")  # <NS><NNN>
SEVERITIES = ("error", "warning")
CONFIDENCE_ENUM = ("high", "medium", "low")
ACTION_ENUM = ("insert", "replace", "delete", "hint")
ANCHOR_ENUM = ("exact", "name-first", "none")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class Ctx:
    """一轮运行中的共享上下文：adapter、工作目录与共享命令缓存。

    缓存原则：所有非破坏性命令在首次需要时执行并缓存（在任何 --apply
    变异之前完成），破坏性命令（apply）只在各自探针内对工作副本执行。
    """

    def __init__(self, adapter, workspace, baseline=None):
        self.adapter = adapter
        self.workspace = workspace
        self.baseline = baseline
        self._cache = {}

    # ------------------------------------------------------------ 基础设施

    def file(self, probe_name):
        """探针名（或 manifest 相对路径）-> 工作副本绝对路径。"""
        if probe_name in self.workspace_probe_files:
            return self.workspace_probe_files[probe_name]
        return os.path.normpath(os.path.join(self.workspace, probe_name))

    def check_run(self, probe_name):
        key = "check:" + probe_name
        if key not in self._cache:
            result, payload = self.adapter.run_json(
                "check_json", file=self.file(probe_name), cwd=self.workspace)
            self._cache[key] = (result, payload)
        return self._cache[key]

    def diagnostics(self, probe_name):
        _, payload = self.check_run(probe_name)
        a = self.adapter
        return payload[a.key("check", "diagnostics")] or []

    def plan_run(self, probe_name):
        key = "plan:" + probe_name
        if key not in self._cache:
            result, payload = self.adapter.run_json(
                "fix_plan", file=self.file(probe_name), cwd=self.workspace)
            self._cache[key] = (result, payload)
        return self._cache[key]

    def codes_run(self):
        if "codes" not in self._cache:
            result, payload = self.adapter.run_json("codes_json",
                                                    cwd=self.workspace)
            self._cache["codes"] = (result, payload)
        return self._cache["codes"]

    def unreadable_run(self):
        """不可读输入哨兵路径的 check 运行（rc>=2 的工具故障带）。"""
        if "unreadable" not in self._cache:
            result, payload = self.adapter.run_json(
                "check_json", file=self.file("unreadable_input"),
                cwd=self.workspace)
            self._cache["unreadable"] = (result, payload)
        return self._cache["unreadable"]

    def suggestions(self, probe_name):
        """plan 信封中的全部建议，统一成 (code, action, confidence, line) 字段组。

        code 取自该建议所属诊断（lom-fix/v1 的 plan.diagnostic.code）；
        line 取建议自身的行号（无行号的 positionless 建议为 None/0）。
        """
        _, payload = self.plan_run(probe_name)
        a = self.adapter
        plans = payload.get(a.key("plan", "list")) or []
        out = []
        for plan in plans:
            diag = plan.get(a.key("plan", "diagnostic")) or {}
            code = diag.get(a.key("plan", "code"))
            for fix in plan.get(a.key("plan", "suggestions")) or []:
                out.append({
                    "code": code,
                    "action": fix.get(a.key("plan", "action")),
                    "confidence": fix.get(a.key("plan", "confidence")),
                    "line": fix.get(a.key("plan", "line")),
                })
        return out

    def read_bytes(self, probe_name):
        with open(self.file(probe_name), "rb") as fh:
            return fh.read()

    def read_bytes_of(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def fresh_copy(self, probe_name, tag):
        """把探针源文件重新复制为工作目录下的 <tag>-<basename> 副本。

        用于需要保证文件未被此前探针变异的破坏性/字节敏感探测。
        """
        import shutil
        src = self.adapter.probe_path(self.probe_sources[probe_name])
        dst = os.path.join(self.workspace, "%s-%s" % (tag, os.path.basename(src)))
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copyfile(src, dst)
        return dst

    workspace_probe_files = None  # runner 注入：探针名 -> 工作副本绝对路径
    probe_sources = None          # runner 注入：探针名 -> manifest 登记的源路径


# ====================================================================
# C-01 §2.1 envelope + §1.1 REQUIRED fields
# ====================================================================

def probe_c01(ctx):
    a = ctx.adapter
    failures = []
    total_diag = 0
    schema_ids = set()
    for name in ("error", "mixed", "warnings_only", "clean"):
        result, payload = ctx.check_run(name)
        for logical in ("schema", "file", "ok", "summary", "diagnostics"):
            actual = a.key("check", logical)
            if actual not in payload:
                failures.append("%s: envelope key %r missing" % (name, actual))
        summary = payload.get(a.key("check", "summary")) or {}
        for logical in ("total", "errors", "warnings"):
            actual = a.key("summary", logical)
            if actual not in summary:
                failures.append("%s: summary key %r missing" % (name, actual))
        schema_ids.add(str(payload.get(a.key("check", "schema"))))
        for i, diag in enumerate(ctx.diagnostics(name)):
            total_diag += 1
            where = "%s#diag%d" % (name, i)
            for logical in ("code", "severity", "message", "file", "position"):
                actual = a.key("diagnostic", logical)
                if actual not in diag:
                    failures.append("%s: diagnostic field %r missing" % (where, actual))
            if a.key("diagnostic", "severity") in diag and \
                    diag[a.key("diagnostic", "severity")] not in SEVERITIES:
                failures.append("%s: severity %r outside enum" %
                                (where, diag[a.key("diagnostic", "severity")]))
            if a.key("diagnostic", "code") in diag and \
                    not CODE_RE.match(str(diag[a.key("diagnostic", "code")])):
                failures.append("%s: code %r fails <NS><NNN>" %
                                (where, diag[a.key("diagnostic", "code")]))
    state = NON_CONFORMANT if failures else CONFORMANT
    detail = ("%d diagnostics across 4 check runs; schema=%s"
              % (total_diag, ",".join(sorted(schema_ids))))
    if failures:
        detail = "; ".join(failures[:3]) + (" (+%d more)" % (len(failures) - 3) if len(failures) > 3 else "")
    evidence = []
    for name in ("error", "mixed", "warnings_only", "clean"):
        result, _ = ctx.check_run(name)
        evidence.append("check --json on %s: rc=%d" % (name, result.rc))
    return ProbeResult("C-01", "S2.1 envelope + S1.1 REQUIRED fields", state,
                       detail, evidence)


# ====================================================================
# C-02 §1.1 position object
# ====================================================================

def probe_c02(ctx):
    a = ctx.adapter
    failures = []
    anchor_counts = {}
    mapped_zero_sentinel = False
    total = 0
    for name in ("error", "mixed", "warnings_only", "clean"):
        for i, diag in enumerate(ctx.diagnostics(name)):
            total += 1
            where = "%s#diag%d" % (name, i)
            pos = diag.get(a.key("diagnostic", "position"))
            if not isinstance(pos, dict):
                failures.append("%s: position is not an object" % where)
                continue
            anchor = pos.get(a.key("position", "anchor"))
            anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
            if anchor not in ANCHOR_ENUM:
                failures.append("%s: anchor %r outside enum" % (where, anchor))
            line = pos.get(a.key("position", "line"))
            col = pos.get(a.key("position", "col"))
            if not (is_int(line) and is_int(col)):
                failures.append("%s: line/col not integers (%r,%r)" % (where, line, col))
                continue
            if anchor in ("exact", "name-first"):
                if line < 1 or col < 1:
                    failures.append("%s: anchor=%s but %d:%d < 1" % (where, anchor, line, col))
            elif anchor == "none" and (line < 1 or col < 1):
                # v0.1 严格读法禁止 0:0；登记 + v0.2-draft 勘误合法化 -> 映射面
                mapped_zero_sentinel = True

    # 不可读输入通道（LEX000 一类 positionless 信封）
    unreadable, unreadable_payload = ctx.unreadable_run()
    for i, diag in enumerate(unreadable_payload.get(a.key("check", "diagnostics")) or []):
        total += 1
        pos = diag.get(a.key("diagnostic", "position"))
        anchor = (pos or {}).get(a.key("position", "anchor"))
        line = (pos or {}).get(a.key("position", "line"))
        col = (pos or {}).get(a.key("position", "col"))
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
        if anchor not in ANCHOR_ENUM:
            failures.append("unreadable#diag%d: anchor %r outside enum" % (i, anchor))
        if not (is_int(line) and is_int(col)):
            failures.append("unreadable#diag%d: line/col not integers" % i)
        elif anchor == "none" and (line < 1 or col < 1):
            mapped_zero_sentinel = True

    if failures:
        state, detail = NON_CONFORMANT, "; ".join(failures[:3])
    elif mapped_zero_sentinel:
        state = BY_MAPPING
        detail = ("anchor=none with honest 0:0 observed (registered mapping; "
                  "v0.2-draft erratum)")
    else:
        state, detail = CONFORMANT, "no fabricated coordinates"
    anchor_summary = ", ".join("%s=%d" % kv for kv in sorted(anchor_counts.items(),
                                                             key=lambda kv: str(kv[0])))
    detail += "; %d positions (%s)" % (total, anchor_summary or "none")
    evidence = ["unreadable-input check: rc=%d" % unreadable.rc]
    return ProbeResult("C-02", "S1.1 position object", state, detail, evidence)


# ====================================================================
# C-03 §1.1 code stability (cross-release)
# ====================================================================

def probe_c03(ctx):
    if ctx.baseline is None:
        return ProbeResult(
            "C-03", "S1.1 code stability (cross-release)", SKIPPED,
            "single-release first run; re-run with --baseline <manifest> to "
            "compare diagnostic-code multisets across two releases")
    a = ctx.adapter
    b = ctx.baseline
    from collections import Counter
    failures = []
    for name in ("error", "mixed", "warnings_only", "clean"):
        _, payload_a = ctx.check_run(name)
        result_b, payload_b = b.run_json("check_json", file=ctx.file(name),
                                         cwd=ctx.workspace)
        codes_a = Counter(d[a.key("diagnostic", "code")] for d in
                          payload_a.get(a.key("check", "diagnostics")) or [])
        codes_b = Counter(d[b.key("diagnostic", "code")] for d in
                          payload_b.get(b.key("check", "diagnostics")) or [])
        if codes_a != codes_b:
            failures.append("%s: multiset drift %s vs %s" %
                            (name, dict(codes_a), dict(codes_b)))
    state = NON_CONFORMANT if failures else CONFORMANT
    detail = "code multisets identical across both releases" if not failures \
        else "; ".join(failures[:3])
    return ProbeResult("C-03", "S1.1 code stability (cross-release)", state, detail)


# ====================================================================
# C-04 §1.2 RepairSuggestion enums (after registered normalization)
# ====================================================================

def normalize_enum(adapter, value, field):
    """应用登记的枚举名归一化映射（当前登记：lowercase）。"""
    rule = ((adapter.manifest.get("mappings") or {})
            .get("enum_normalization") or {}).get("rule")
    if value is None:
        return None, False
    if rule == "lowercase" and isinstance(value, str) and not value.islower():
        return value.lower(), True
    return value, False


def probe_c04(ctx):
    a = ctx.adapter
    failures = []
    observed_conf = set()
    observed_act = set()
    normalization_applied = False
    sources = [("fix --plan", ctx.suggestions("mixed"))]

    ext = a.extension("l2_fix")
    if ext:
        result, payload = a.run_extension("l2_fix", file=ctx.file("l2_fail"),
                                          cwd=ctx.workspace)
        entries = payload.get(ext["envelope"]["list"]) or []
        l2 = []
        for e in entries:
            l2.append({"code": e.get(ext["envelope"]["code"]),
                       "action": e.get(ext["envelope"]["action"]),
                       "confidence": e.get(ext["envelope"]["confidence"]),
                       "line": None})
        sources.append(("l2-fix outlet", l2))

    for source, items in sources:
        for i, s in enumerate(items):
            where = "%s#sugg%d(%s)" % (source, i, s.get("code"))
            conf, mapped_c = normalize_enum(a, s.get("confidence"), "confidence")
            act, mapped_a = normalize_enum(a, s.get("action"), "action")
            normalization_applied = normalization_applied or mapped_c or mapped_a
            if conf not in CONFIDENCE_ENUM:
                failures.append("%s: confidence %r outside enum" % (where, conf))
            else:
                observed_conf.add(conf)
            if act not in ACTION_ENUM:
                failures.append("%s: action %r outside enum" % (where, act))
            else:
                observed_act.add(act)

    if failures:
        state, detail = NON_CONFORMANT, "; ".join(failures[:3])
    else:
        state = BY_MAPPING  # 判定面经过登记的枚举归一化映射
        detail = ("confidence{%s} action{%s} all in enum after registered "
                  "case normalization (passthrough on this build)"
                  % (",".join(sorted(observed_conf)),
                     ",".join(sorted(observed_act))))
    evidence = ["sources: %s" % ", ".join(s for s, _ in sources),
                "normalization actually rewrote a value: %s" % normalization_applied]
    return ProbeResult("C-04", "S1.2 RepairSuggestion enums", state, detail, evidence)


# ====================================================================
# C-05 §1.3 AXIOM 1 (behavioral)
# ====================================================================

def _diff_line_sets(before_bytes, after_bytes):
    return (before_bytes.decode("utf-8", "replace").splitlines(),
            after_bytes.decode("utf-8", "replace").splitlines())


def probe_c05(ctx):
    a = ctx.adapter
    failures = []
    evidence = []

    # 1) mixed 探针：网格前置（自证亦校验）
    planned = ctx.suggestions("mixed")
    high_nonhint = [s for s in planned
                    if s["confidence"] == "high" and s["action"] != "hint"]
    low_med = [s for s in planned if s["confidence"] in ("medium", "low")]
    hints = [s for s in planned if s["action"] == "hint"]
    if not high_nonhint or not low_med or not hints:
        return ProbeResult("C-05", "S1.3 AXIOM 1 (behavioral)", NON_CONFORMANT,
                           "probe precondition failed: confidence/action grid "
                           "not spanned (setup should have caught this)")

    snapshot = ctx.read_bytes("mixed")
    result, payload = a.run_json("fix_apply", file=ctx.file("mixed"),
                                 cwd=ctx.workspace)
    evidence.append("fix --apply on mixed copy: rc=%d, applied=%s" %
                    (result.rc, payload.get(a.key("apply", "applied"))))
    if result.rc != 0:
        failures.append("fix --apply rc=%d (expected 0)" % result.rc)

    changes = payload.get(a.key("apply", "changes")) or []
    planned_keys = {(s["code"], s["action"]) for s in high_nonhint}
    for ch in changes:
        key = (ch.get(a.key("apply", "change_code")),
               ch.get(a.key("apply", "change_action")))
        if key not in planned_keys:
            failures.append("applied change %r is not a planned high-confidence "
                            "non-hint fix" % (key,))
    applied_keys = {(ch.get(a.key("apply", "change_code")),
                     ch.get(a.key("apply", "change_action"))) for ch in changes}
    if applied_keys != planned_keys:
        failures.append("applied set %s != planned high non-hint set %s"
                        % (sorted(map(str, applied_keys)),
                           sorted(map(str, planned_keys))))

    after = ctx.read_bytes("mixed")
    before_lines, after_lines = _diff_line_sets(snapshot, after)
    # 2) 低/中置信或 hint 的目标行必须逐字仍在（对有行号的建议）
    for s in low_med + hints:
        line = s.get("line")
        if isinstance(line, int) and line and 0 < line <= len(before_lines):
            target = before_lines[line - 1]
            if target not in after_lines:
                failures.append("low/medium/hint target line %d %r altered"
                                % (line, target[:40]))
        evidence.append("guarded target %s(%s,%s) intact" %
                        (s["code"], s["action"], s["confidence"]))
    # 3) 复检：被应用码消失；低/中/hint 码仍在
    recheck_result, recheck = a.run_json("check_json", file=ctx.file("mixed"),
                                         cwd=ctx.workspace)
    remaining = [d.get(a.key("diagnostic", "code"))
                 for d in recheck.get(a.key("check", "diagnostics")) or []]
    for s in low_med + hints:
        if s["code"] not in remaining:
            failures.append("code %s (low/medium/hint suggestion) vanished "
                            "after apply" % s["code"])
    for (code, _act) in applied_keys:
        if code in remaining:
            failures.append("applied code %s still reported after apply" % code)
    evidence.append("re-check after apply: remaining=%s" % remaining)

    # 4) hint-only 探针：唯一建议为 low/hint -> 文件逐字节不变（fixed==bad 正向断言）
    hint_snapshot = ctx.read_bytes("hint_only")
    hint_result, hint_payload = a.run_json("fix_apply",
                                           file=ctx.file("hint_only"),
                                           cwd=ctx.workspace)
    hint_after = ctx.read_bytes("hint_only")
    unchanged = hint_snapshot == hint_after
    if hint_result.rc != 0:
        failures.append("hint-only apply rc=%d (expected 0)" % hint_result.rc)
    if not unchanged:
        failures.append("hint-only probe altered by apply (AXIOM 1 violation)")
    evidence.append("hint-only probe: applied=%s, byte-identical=%s" %
                    (hint_payload.get(a.key("apply", "applied")), unchanged))

    state = NON_CONFORMANT if failures else CONFORMANT
    detail = ("apply took exactly the high-confidence non-hint set %s; "
              "low/medium/hint targets intact; hint-only file byte-identical"
              % sorted(set("%s:%s" % kv for kv in planned_keys)))
    if failures:
        detail = "; ".join(failures[:3])
    return ProbeResult("C-05", "S1.3 AXIOM 1 (behavioral)", state, detail, evidence)


# ====================================================================
# C-06 §1.3 AXIOM 3 (plan side-effect-free)
# ====================================================================

def probe_c06(ctx):
    failures = []
    evidence = []
    # 在全新副本上真实运行一次 plan（不依赖缓存——此前 C-05 可能已变异工作副本）
    for name in ("error", "mixed", "warnings_only"):
        copy = ctx.fresh_copy(name, "c06")
        before = ctx.read_bytes_of(copy)
        result, _ = ctx.adapter.run_json("fix_plan", file=copy,
                                         cwd=ctx.workspace)
        after = ctx.read_bytes_of(copy)
        if before != after:
            failures.append("%s mutated by fix --plan" % name)
        evidence.append("fix --plan on fresh %s copy: rc=%d, byte-identical=%s"
                        % (name, result.rc, before == after))
    state = NON_CONFORMANT if failures else CONFORMANT
    detail = "plan left all probe files byte-identical" if not failures \
        else "; ".join(failures)
    return ProbeResult("C-06", "S1.3 AXIOM 3 (plan side-effect-free)", state,
                       detail, evidence)


# ====================================================================
# C-07 §2.1 REQUIRED command set
# ====================================================================

def probe_c07(ctx):
    a = ctx.adapter
    failures = []
    evidence = []
    required = ("check_json", "fix_plan", "fix_apply", "codes_json")
    for name in required:
        if a.command_template(name) is None:
            failures.append("command template %r absent from adapter manifest" % name)

    if "check_json" in a.manifest["commands"]:
        result, payload = ctx.check_run("clean")
        if result.rc != 0 or not payload.get(a.key("check", "ok"), False):
            failures.append("check --json: rc=%d ok=%s on clean probe"
                            % (result.rc, payload.get(a.key("check", "ok"))))
        evidence.append("check --json parses, clean probe rc=%d" % result.rc)
    if "fix_plan" in a.manifest["commands"]:
        result, payload = ctx.plan_run("warnings_only")
        if result.rc != 0 or a.key("plan", "list") not in payload:
            failures.append("fix --plan: rc=%d, plans list missing" % result.rc)
        evidence.append("fix --plan parses, warnings-only probe rc=%d" % result.rc)
    if "fix_apply" in a.manifest["commands"]:
        # 在 warnings-only 工作副本上真实驱动一次 --apply（副本可变异）
        result, payload = a.run_json("fix_apply", file=ctx.file("warnings_only"),
                                     cwd=ctx.workspace)
        if result.rc != 0:
            failures.append("fix --apply: rc=%d (expected 0)" % result.rc)
        evidence.append("fix --apply parses (lom-apply envelope), rc=%d, "
                        "applied=%s" % (result.rc,
                                        payload.get(a.key("apply", "applied"))))
    if "codes_json" in a.manifest["commands"]:
        result, payload = ctx.codes_run()
        listing = payload.get(a.key("codes", "list")) or []
        if result.rc != 0 or not listing:
            failures.append("codes --json: rc=%d, %d entries"
                            % (result.rc, len(listing)))
        evidence.append("codes --json parses, %d entries" % len(listing))

    state = NON_CONFORMANT if failures else CONFORMANT
    detail = "all four REQUIRED commands present and parseable" if not failures \
        else "; ".join(failures[:3])
    return ProbeResult("C-07", "S2.1 REQUIRED command set", state, detail, evidence)


# ====================================================================
# C-08 §2.1 codes outlet closed loop
# ====================================================================

def probe_c08(ctx):
    a = ctx.adapter
    _, codes_payload = ctx.codes_run()
    table = {}
    for entry in codes_payload.get(a.key("codes", "list")) or []:
        table[entry.get(a.key("codes", "code"))] = entry
    failures = []
    observed = set()
    for name in ("error", "mixed", "warnings_only"):
        for d in ctx.diagnostics(name):
            code = d.get(a.key("diagnostic", "code"))
            sev = d.get(a.key("diagnostic", "severity"))
            observed.add(code)
            if code not in table:
                failures.append("%s: code %r unresolved in codes table" % (name, code))
            elif table[code].get(a.key("codes", "severity")) != sev:
                failures.append("%s: code %r severity %r != table %r"
                                % (name, code, sev,
                                   table[code].get(a.key("codes", "severity"))))
    # 不可读输入通道也在闭合回路内（LEX000）
    _, unreadable = ctx.unreadable_run()
    for d in unreadable.get(a.key("check", "diagnostics")) or []:
        code = d.get(a.key("diagnostic", "code"))
        observed.add(code)
        if code not in table:
            failures.append("unreadable: code %r unresolved" % code)

    state = NON_CONFORMANT if failures else CONFORMANT
    detail = ("%d observed codes all resolve; severity agreement 100%%"
              % len(observed)) if not failures else "; ".join(failures[:3])
    evidence = ["observed codes: %s" % ", ".join(sorted(observed)),
                "table size: %d" % len(table)]
    return ProbeResult("C-08", "S2.1 codes outlet closed loop", state, detail,
                       evidence)


# ====================================================================
# C-09 §2.2 exit-code matrix
# ====================================================================

def probe_c09(ctx):
    failures = []
    evidence = []
    r_error, _ = ctx.check_run("error")
    r_warn, _ = ctx.check_run("warnings_only")
    r_clean, _ = ctx.check_run("clean")
    r_plan, _ = ctx.plan_run("error")
    r_unreadable, _ = ctx.unreadable_run()

    if r_error.rc != 1:
        failures.append("error probe rc=%d (expected 1)" % r_error.rc)
    if r_warn.rc != 0:
        failures.append("warnings-only probe rc=%d (expected 0)" % r_warn.rc)
    if r_clean.rc != 0:
        failures.append("clean probe rc=%d (expected 0)" % r_clean.rc)
    if r_plan.rc != 0:
        failures.append("fix --plan on error probe rc=%d (expected 0)" % r_plan.rc)
    if r_unreadable.rc < 2:
        failures.append("unreadable input rc=%d (expected >=2)" % r_unreadable.rc)

    evidence.append("error->%d, warnings-only->%d, clean->%d, plan->%d, "
                    "unreadable->%d" % (r_error.rc, r_warn.rc, r_clean.rc,
                                        r_plan.rc, r_unreadable.rc))
    state = NON_CONFORMANT if failures else CONFORMANT
    detail = "all matrix cells match" if not failures else "; ".join(failures)
    return ProbeResult("C-09", "S2.2 exit-code matrix", state, detail, evidence)


# ====================================================================
# C-10 §2.1 explain <code> (OPTIONAL)
# ====================================================================

def probe_c10(ctx):
    a = ctx.adapter
    opt = (a.manifest.get("optional") or {}).get("explain")
    if not opt or not opt.get("registered"):
        return ProbeResult("C-10", "S2.1 explain <code> (OPTIONAL)", SKIPPED,
                           "OPTIONAL command not registered — skipped, not failed")
    failures = []
    known = opt.get("known_code")
    unknown = opt.get("unknown_code")
    r_known, p_known = a.run_json("explain_json", code=known, cwd=ctx.workspace)
    if r_known.rc != 0:
        failures.append("explain %s rc=%d (expected 0)" % (known, r_known.rc))
    doc = p_known.get(a.key("explain", "doc"))
    if not doc:
        failures.append("explain %s: empty documentation" % known)
    r_unknown = a.run_command("explain_json", code=unknown, cwd=ctx.workspace)
    if r_unknown.rc < 2:
        failures.append("explain %s rc=%d (expected >=2)" % (unknown, r_unknown.rc))
    evidence = ["explain %s: rc=%d, doc %d chars" % (known, r_known.rc, len(doc or "")),
                "explain %s: rc=%d" % (unknown, r_unknown.rc)]
    state = NON_CONFORMANT if failures else CONFORMANT
    detail = "OPTIONAL command present: known->0 non-empty, unknown->>=2" \
        if not failures else "; ".join(failures)
    return ProbeResult("C-10", "S2.1 explain <code> (OPTIONAL)", state, detail,
                       evidence)


# ====================================================================
# C-11 forward-compatibility (spec S4 reference consumer)
# ====================================================================

def probe_c11(ctx):
    a = ctx.adapter
    failures = []
    plans_total = 0
    applicable = []
    resolved = []
    try:
        # 规范 §4 参考消费器形态，经 manifest 寻址逐字段驱动（进程边界）；
        # 消费器只按键取已知字段 = 忽略未知扩展字段（前向兼容公理）。
        _, codes_payload = ctx.codes_run()
        codes = {c[a.key("codes", "code")]: c
                 for c in codes_payload.get(a.key("codes", "list")) or []}
        _, check = ctx.check_run("error")
        for d in check.get(a.key("check", "diagnostics")) or []:
            code = d[a.key("diagnostic", "code")]
            resolved.append((code, codes.get(code, {})
                             .get(a.key("codes", "summary"), "?")))
        for probe in ("error", "mixed"):
            _, plan = ctx.plan_run(probe)
            for f in plan.get(a.key("plan", "list")) or []:
                plans_total += 1
                fixes = f.get(a.key("plan", "suggestions")) or []
                if not fixes:
                    continue
                conf, _ = normalize_enum(a, fixes[0].get(a.key("plan", "confidence")),
                                         "confidence")
                act, _ = normalize_enum(a, fixes[0].get(a.key("plan", "action")),
                                        "action")
                if conf == "high" and act != "hint":
                    applicable.append(f)
        if not resolved:
            failures.append("consumer resolved no diagnostics")
        if not applicable:
            failures.append("consumer found no applicable high non-hint fix")
    except (KeyError, TypeError, ValueError) as exc:
        failures.append("consumer aborted on envelope: %r" % exc)

    state = NON_CONFORMANT if failures else BY_MAPPING
    detail = ("reference consumer completed rc 0; %d applicable of %d plans "
              "across probes" % (len(applicable), plans_total)) \
        if not failures else "; ".join(failures[:3])
    evidence = ["resolved codes: %s" % ", ".join(c for c, _ in resolved)]
    return ProbeResult(
        "C-11", "forward-compatibility (S4 reference consumer)", state, detail,
        evidence)


# ====================================================================
# C-12 S3 L2 methodology — manual tier
# ====================================================================

def probe_c12(ctx):
    return ProbeResult(
        "C-12", "S3 L2 methodology (six clauses)", MANUAL_PENDING,
        "manual tier: audited by document review during registration; gates "
        "L2 registration, emits no machine pass/fail")


# ====================================================================
# C-13 l2-fix/v2 position field (Lom extension surface)
# ====================================================================

L2_LINE_RE = re.compile(
    r"^codegen error:(?:\s+(\d+):(\d+))?\s+\[([A-Z0-9]{2,8})\]")


def probe_c13(ctx):
    a = ctx.adapter
    ext = a.extension("l2_fix")
    if not ext:
        return ProbeResult("C-13", "l2-fix/v2 position field", SKIPPED,
                           "extension not registered for this implementation "
                           "(reference-implementation-bound probe)")
    result, payload = a.run_extension("l2_fix", file=ctx.file("l2_fail"),
                                      cwd=ctx.workspace)
    entries = payload.get(ext["envelope"]["list"]) or []
    pos_key = ext["envelope"]["position"]
    code_key = ext["envelope"]["code"]

    # 探针文本里的码行：带 ln:cl 与不带位置的两种形态
    with open(ctx.file("l2_fail"), "r", encoding="utf-8") as fh:
        probe_lines = fh.read().splitlines()
    expected = []
    for line in probe_lines:
        m = L2_LINE_RE.match(line)
        if m:
            ln, cl, code = m.group(1), m.group(2), m.group(3)
            expected.append((code,
                             (int(ln), int(cl)) if ln is not None else None))
    if not expected:
        return ProbeResult("C-13", "l2-fix/v2 position field", NON_CONFORMANT,
                           "l2-fail probe contains no parseable rejection lines")

    failures = []
    by_code = {}
    for e in entries:
        by_code.setdefault(e.get(code_key), []).append(e)
    for code, pos in expected:
        matched = by_code.get(code) or []
        if not matched:
            failures.append("rejection %s produced no entry" % code)
            continue
        for e in matched:
            if pos is not None:
                p = e.get(pos_key)
                if not isinstance(p, dict):
                    failures.append("%s: ln:cl line but entry lacks position" % code)
                elif not (is_int(p.get("line")) and is_int(p.get("col"))
                          and p["line"] >= 1 and p["col"] >= 1):
                    failures.append("%s: malformed position %r" % (code, p))
                elif (p["line"], p["col"]) != pos:
                    failures.append("%s: position %r != ln:cl %r" % (code, p, pos))
            else:
                if e.get(pos_key) is not None:
                    failures.append("%s: positionless rejection carries position %r"
                                    % (code, e.get(pos_key)))

    state = NON_CONFORMANT if failures else BY_MAPPING
    detail = ("%d entries; ln:cl-derived positions well-formed; positionless "
              "line honestly omits position (registered mapping)"
              % len(entries)) if not failures else "; ".join(failures[:3])
    evidence = ["l2-fix outlet rc=%d on l2-fail probe" % result.rc,
                "entries: %s" % ", ".join("%s%s" % (e.get(code_key),
                                                    e.get(pos_key) or "(no pos)")
                                          for e in entries)]
    return ProbeResult("C-13", "l2-fix/v2 position field", state, detail, evidence)


# ====================================================================
# C-14 registered deviations re-check
# ====================================================================

def lsp_exit_frame():
    import json as _json
    body = _json.dumps({"jsonrpc": "2.0", "method": "exit"})
    return ("Content-Length: %d\r\n\r\n" % len(body)).encode("ascii") + body.encode()


def probe_c14(ctx):
    a = ctx.adapter
    deviations = a.deviations()
    if not deviations:
        return ProbeResult("C-14", "registered deviations re-check", SKIPPED,
                           "no registered deviations in the adapter manifest")
    failures = []
    evidence = []
    for dev in deviations:
        dev_id = dev.get("id", "<unnamed>")
        template = dev.get("command")
        file_arg = None
        if dev.get("probe"):
            file_arg = ctx.file(dev["probe"])
        stdin_data = None
        if dev.get("stdin_mode") == "lsp_exit_notification":
            stdin_data = lsp_exit_frame()
        result = a.run(template, file=file_arg, cwd=ctx.workspace,
                       stdin_data=stdin_data)
        expect_rc = dev.get("expect_rc")
        ok = True
        if expect_rc is not None and result.rc != expect_rc:
            failures.append("%s: rc=%d, registration says %s"
                            % (dev_id, result.rc, expect_rc))
            ok = False
        regex = dev.get("expect_output_regex")
        if regex and not re.search(regex, result.text()):
            failures.append("%s: output lacks /%s/" % (dev_id, regex))
            ok = False
        evidence.append("%s: rc=%d%s" % (dev_id, result.rc,
                                         ", output matched" if regex else ""))

    state = NON_CONFORMANT if failures else BY_MAPPING
    detail = ("%d registered deviation(s) still match their registration"
              % len(deviations)) if not failures else "; ".join(failures)
    return ProbeResult("C-14", "registered deviations re-check", state, detail,
                       evidence)


ALL_PROBES = [
    ("C-01", probe_c01), ("C-02", probe_c02), ("C-03", probe_c03),
    ("C-04", probe_c04), ("C-05", probe_c05), ("C-06", probe_c06),
    ("C-07", probe_c07), ("C-08", probe_c08), ("C-09", probe_c09),
    ("C-10", probe_c10), ("C-11", probe_c11), ("C-12", probe_c12),
    ("C-13", probe_c13), ("C-14", probe_c14),
]

"""ACRI conformance suite — runner entry point.

用法：
    python conformance/suite/runner.py conformance/adapters/lom.json
    python conformance/suite/runner.py <manifest> --baseline <older-manifest>

零第三方依赖（仅标准库）。对被测工具链只经 adapter manifest 以子进程驱动
（stdout + exit code），不 import 实现。报告 artifact 落 conformance/.tmp/
（gitignored）。退出码：0 = 无 non-conformant；1 = 存在 non-conformant；
2 = 套件装配/探针自证失败（探测未发生）。
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter import Adapter, SetupError            # noqa: E402
from probes import ALL_PROBES, Ctx                 # noqa: E402
from report import (NON_CONFORMANT, render_console, write_artifact)  # noqa: E402

CONFORMANCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(CONFORMANCE_DIR, ".tmp")


def collect_probe_sources(adapter):
    """逻辑探针名 -> manifest 登记的 conformance/ 相对路径（或 sentinel 声明）。"""
    sources = {}
    for logical, entry in adapter.manifest["probes"].items():
        sources[logical] = entry
    ext = adapter.extension("l2_fix")
    if ext and ext.get("probe"):
        sources["l2_fail"] = ext["probe"]
    for dev in adapter.deviations():
        if dev.get("probe"):
            sources["deviation:" + dev.get("id", "?")] = dev["probe"]
        if dev.get("fixture"):
            sources["fixture:" + dev.get("id", "?")] = dev["fixture"]
    return sources


def prepare_workspace(adapter, stamp):
    """把全部探针按原相对结构复制进 conformance/.tmp/run-<stamp>/。

    sentinel 形（{"sentinel": "<path>"}）= 按定义不存在的路径：只注册
    工作目录下的对应路径，不复制（自证阶段断言其缺席）。
    """
    workspace = os.path.join(TMP_DIR, "run-%s" % stamp)
    os.makedirs(workspace, exist_ok=True)
    files = {}
    entries = list(collect_probe_sources(adapter).items())
    # 先复制目录型 fixture，再复制文件型条目（已随 fixture 就位的文件跳过）
    dir_first = sorted(entries, key=lambda kv: 0 if os.path.isdir(
        adapter.probe_path(kv[1]["sentinel"] if isinstance(kv[1], dict)
                           and "sentinel" in kv[1] else kv[1])) else 1)
    for logical, entry in dir_first:
        if isinstance(entry, dict) and "sentinel" in entry:
            rel = entry["sentinel"]
            files[logical] = os.path.normpath(os.path.join(workspace, rel))
            continue
        rel = entry
        src = adapter.probe_path(rel)
        if not os.path.exists(src):
            raise SetupError("probe source not found: %s (for %r)" % (src, logical))
        dst = os.path.normpath(os.path.join(workspace, rel))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            if os.path.exists(dst):
                files[logical] = dst
                continue  # 已由目录型 fixture 覆盖
            shutil.copyfile(src, dst)
        files[logical] = dst
    return workspace, files


def verify_probes(adapter, ctx):
    """探针自证：每支探针必须真实触发其预期条件（README 探测方法要求）。"""
    checks = []

    def record(name, ok, msg):
        checks.append((name, bool(ok), msg))

    a = adapter

    r, p = ctx.check_run("clean")
    diag = p.get(a.key("check", "diagnostics")) or []
    record("clean", r.rc == 0 and p.get(a.key("check", "ok")) is True
           and len(diag) == 0,
           "rc=%d ok=%s diagnostics=%d" % (r.rc, p.get(a.key("check", "ok")), len(diag)))

    r, p = ctx.check_run("error")
    diags = p.get(a.key("check", "diagnostics")) or []
    record("error", r.rc == 1 and any(
        d.get(a.key("diagnostic", "severity")) == "error" for d in diags),
        "rc=%d errors=%d" % (r.rc, sum(
            1 for d in diags
            if d.get(a.key("diagnostic", "severity")) == "error")))

    r, p = ctx.check_run("warnings_only")
    diags = p.get(a.key("check", "diagnostics")) or []
    has_warn = any(d.get(a.key("diagnostic", "severity")) == "warning" for d in diags)
    no_err = not any(d.get(a.key("diagnostic", "severity")) == "error" for d in diags)
    record("warnings_only", r.rc == 0 and has_warn and no_err,
           "rc=%d warnings=%d errors=%d" % (r.rc, len(diags),
                                            sum(1 for d in diags
                                                if d.get(a.key("diagnostic", "severity")) == "error")))

    planned = ctx.suggestions("mixed")
    high_codes = {s["code"] for s in planned
                  if s["confidence"] == "high" and s["action"] != "hint"}
    lowmed_codes = {s["code"] for s in planned
                    if s["confidence"] in ("medium", "low")}
    hint_codes = {s["code"] for s in planned if s["action"] == "hint"}
    record("mixed-grid", bool(high_codes and lowmed_codes and hint_codes
                              and not (high_codes & (lowmed_codes | hint_codes))),
           "high{%s} low-med{%s} hint{%s}" %
           (",".join(sorted(high_codes)), ",".join(sorted(lowmed_codes)),
            ",".join(sorted(hint_codes))))

    hint_planned = ctx.suggestions("hint_only")
    record("hint_only", bool(hint_planned) and not any(
        s["confidence"] == "high" and s["action"] != "hint" for s in hint_planned),
        "%d suggestions, none high-non-hint" % len(hint_planned))

    sentinel = ctx.file("unreadable_input")
    record("unreadable_input", not os.path.exists(sentinel),
           "sentinel path absent: %s" % sentinel)

    ext = adapter.extension("l2_fix")
    if ext:
        r, p = a.run_extension("l2_fix", file=ctx.file("l2_fail"),
                               cwd=ctx.workspace)
        entries = p.get(ext["envelope"]["list"]) or []
        record("l2_fail", r.rc == 0 and bool(entries),
               "rc=%d entries=%d" % (r.rc, len(entries)))

    for dev in adapter.deviations():
        if dev.get("probe"):
            src = adapter.probe_path(dev["probe"])
            record("deviation:" + dev.get("id", "?"), os.path.exists(src),
                   "fixture present: %s" % src)

    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ACRI conformance suite runner (stdlib only)")
    parser.add_argument("manifest", help="adapter manifest, e.g. conformance/adapters/lom.json")
    parser.add_argument("--baseline", default=None,
                        help="second adapter manifest (older release) for C-03 cross-release compare")
    parser.add_argument("--keep-workspace", action="store_true",
                        help="keep the run workspace under conformance/.tmp/")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        adapter = Adapter(args.manifest)
        baseline = Adapter(args.baseline) if args.baseline else None
    except SetupError as exc:
        print("setup error: %s" % exc)
        return 2

    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        workspace, files = prepare_workspace(adapter, stamp)
    except SetupError as exc:
        print("setup error: %s" % exc)
        return 2

    ctx = Ctx(adapter, workspace, baseline=baseline)
    ctx.workspace_probe_files = files
    ctx.probe_sources = collect_probe_sources(adapter)

    print("ACRI conformance suite")
    print("  adapter      : %s (%s)" % (adapter.manifest["implementation"],
                                        adapter.manifest_path))
    print("  binary       : %s" % adapter.binary)
    print("  tool version : %s" % adapter.tool_version())
    if baseline:
        print("  baseline     : %s (%s)" % (baseline.manifest["implementation"],
                                            baseline.manifest_path))
    print("  workspace    : %s" % workspace)

    checks = verify_probes(adapter, ctx)
    print("\nprobe self-verification: %d/%d ok" %
          (sum(1 for _, ok, _ in checks if ok), len(checks)))
    for name, ok, msg in checks:
        print("  [%s] %-16s %s" % ("ok" if ok else "FAIL", name, msg))
    if not all(ok for _, ok, _ in checks):
        print("\nsetup error: probes do not trigger their expected conditions; "
              "run aborted before any conformance verdict")
        return 2

    print()
    results = []
    for pid, fn in ALL_PROBES:
        try:
            result = fn(ctx)
        except SetupError as exc:
            from report import ProbeResult
            result = ProbeResult(pid, "(harness)", NON_CONFORMANT,
                                 "harness error: %s" % exc)
        results.append(result)

    print(render_console(results))

    header = [
        "- Date: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "- Adapter: `%s` (%s)" % (adapter.manifest["implementation"],
                                  adapter.manifest_path),
        "- Binary: `%s`" % adapter.binary,
        "- Tool version: `%s`" % adapter.tool_version(),
        "- Baseline: %s" % (baseline.manifest_path if baseline else "none (single release)"),
        "- Workspace: `%s`" % workspace,
        "- Probe self-verification: %d/%d ok" % (sum(1 for _, ok, _ in checks if ok),
                                                 len(checks)),
    ]
    artifact = write_artifact(TMP_DIR, results, header)
    print("report artifact: %s" % os.path.relpath(artifact, CONFORMANCE_DIR))

    if not args.keep_workspace:
        shutil.rmtree(workspace, ignore_errors=True)
        # apply 副作用目录（.lom/ 历史等）都在 workspace 内，随之一并清理

    return 1 if any(r.state == NON_CONFORMANT for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())

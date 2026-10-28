"""探测结果的三态模型与报告渲染（控制台 + Markdown artifact）。

三态词汇（README "Reporting vocabulary"）：conformant / by-mapping /
non-conformant；OPTIONAL 缺席或单版本首跑等 = skipped（不算失败）；
C-12 人工档 = manual-pending。
"""

import io
import os

CONFORMANT = "conformant"
BY_MAPPING = "by-mapping"
NON_CONFORMANT = "non-conformant"
SKIPPED = "skipped"
MANUAL_PENDING = "manual-pending"

STATES = (CONFORMANT, BY_MAPPING, NON_CONFORMANT, SKIPPED, MANUAL_PENDING)

# 行式输出时探针说明的顺序即 C-01..C-14 的固定次序
PROBE_ORDER = ["C-%02d" % i for i in range(1, 15)]


class ProbeResult:
    def __init__(self, pid, clause, state, detail="", evidence=None):
        self.pid = pid
        self.clause = clause
        self.state = state
        self.detail = detail or ""
        self.evidence = list(evidence or [])

    def line(self):
        return "%s = %s%s" % (self.pid, self.state,
                              ("  " + self.detail) if self.detail else "")


def summarize(results):
    counts = {}
    by_state = {}
    for r in results:
        counts[r.state] = counts.get(r.state, 0) + 1
        by_state.setdefault(r.state, []).append(r.pid)
    return counts, by_state


def render_console(results):
    buf = io.StringIO()
    for r in results:
        buf.write(r.line() + "\n")
    buf.write("\nsummary:\n")
    counts, by_state = summarize(results)
    for state in STATES:
        if state not in counts:
            continue
        ids = " ".join(by_state[state])
        buf.write("  %-15s %d   %s\n" % (state, counts[state], ids))
    return buf.getvalue()


def render_markdown(results, header_lines):
    counts, by_state = summarize(results)
    buf = io.StringIO()
    buf.write("# ACRI conformance run\n\n")
    for line in header_lines:
        buf.write("%s\n" % line)
    buf.write("\n## Probe results\n\n")
    buf.write("| Id | Clause | State | Detail |\n")
    buf.write("|---|---|---|---|\n")
    for r in results:
        detail = r.detail.replace("|", "\\|")
        buf.write("| %s | %s | `%s` | %s |\n" % (r.pid, r.clause, r.state, detail))
    buf.write("\n## Summary\n\n")
    buf.write("| State | Count | Probes |\n|---|---|---|\n")
    for state in STATES:
        if state not in counts:
            continue
        buf.write("| `%s` | %d | %s |\n" % (state, counts[state],
                                            " ".join(by_state[state])))
    buf.write("\n## Evidence\n")
    for r in results:
        if not r.evidence:
            continue
        buf.write("\n### %s — %s\n\n" % (r.pid, r.clause))
        for item in r.evidence:
            buf.write("- %s\n" % item)
    return buf.getvalue()


def write_artifact(directory, results, header_lines):
    """把 Markdown 报告落到 conformance/.tmp/（gitignored）。返回路径。"""
    os.makedirs(directory, exist_ok=True)
    import time
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(directory, "report-%s.md" % stamp)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_markdown(results, header_lines))
    return path

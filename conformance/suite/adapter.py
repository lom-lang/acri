"""Adapter manifest loader + process-boundary command driver.

套件与被测工具链的唯一耦合面：adapter manifest（JSON）。所有对被测 CLI 的
驱动都经此处以子进程完成（stdout + exit code），不 import 实现、不假设实现
语言——规范 §0 中立性的工程落点。

仅标准库。
"""

import json
import os
import subprocess

DEFAULT_TIMEOUT = 60  # 秒；每个子进程调用的上限


class SetupError(Exception):
    """套件侧装配错误（manifest 缺字段、二进制不可用、探针不自证等）。

    与 non-conformant 严格区分：装配错误意味着探测没有发生。
    """


class ProcResult:
    """一次子进程调用的完整记录（进程边界证据）。"""

    def __init__(self, argv, rc, stdout, stderr, timed_out=False):
        self.argv = argv
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    def text(self):
        return (self.stdout or "") + (self.stderr or "")

    def describe(self):
        return "rc=%d argv=%s" % (self.rc, " ".join(self.argv))


class Adapter:
    """被测工具链的 manifest 绑定。"""

    def __init__(self, manifest_path):
        self.manifest_path = os.path.abspath(manifest_path)
        if not os.path.isfile(self.manifest_path):
            raise SetupError("adapter manifest not found: %s" % manifest_path)
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as fh:
                self.manifest = json.load(fh)
        except ValueError as exc:
            raise SetupError("adapter manifest is not valid JSON: %s" % exc)

        for key in ("schema", "implementation", "binary", "commands", "envelope", "probes"):
            if key not in self.manifest:
                raise SetupError("adapter manifest missing required key: %s" % key)
        if not self.manifest["schema"].startswith("acri-adapter/"):
            raise SetupError("unsupported adapter manifest schema: %r" % self.manifest["schema"])

        # 相对路径一律相对 conformance/ 目录（manifest 位于 conformance/adapters/）
        self.base_dir = os.path.dirname(os.path.dirname(self.manifest_path))
        self.binary = self._resolve_path(self.manifest["binary"])
        if not os.path.isfile(self.binary):
            raise SetupError("binary not found: %s" % self.binary)
        self.version_output = None

    # ---------------------------------------------------------------- 路径

    def _resolve_path(self, path):
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(self.base_dir, path))

    def probe_path(self, rel):
        """manifest 中登记的探针源路径（仓内 conformance/ 相对）。"""
        return self._resolve_path(rel)

    def command_template(self, name):
        return self.manifest["commands"].get(name)

    def extension(self, name):
        return (self.manifest.get("extensions") or {}).get(name)

    def deviations(self):
        return self.manifest.get("deviations") or []

    # ---------------------------------------------------------------- 信封寻址

    def key(self, group, logical, required=True):
        """把逻辑字段名翻译成该实现信封里的实际键名。"""
        env = self.manifest["envelope"]
        mapping = env.get(group)
        if mapping is None:
            if required:
                raise SetupError("manifest envelope missing group: %s" % group)
            return None
        actual = mapping.get(logical)
        if actual is None and required:
            raise SetupError("manifest envelope[%s] missing field: %s" % (group, logical))
        return actual

    # ---------------------------------------------------------------- 执行

    def build_argv(self, template, file=None, code=None):
        argv = []
        for part in template:
            part = part.replace("{bin}", self.binary)
            if file is not None:
                part = part.replace("{file}", file)
            if code is not None:
                part = part.replace("{code}", code)
            argv.append(part)
        return argv

    def run(self, template, file=None, code=None, cwd=None, stdin_data=None,
            timeout=DEFAULT_TIMEOUT):
        """执行一次命令模板，返回 ProcResult（UTF-8 解码）。"""
        argv = self.build_argv(template, file=file, code=code)
        try:
            proc = subprocess.run(
                argv,
                input=stdin_data,
                cwd=cwd,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ProcResult(argv, -1, "", "timeout after %ss" % timeout, timed_out=True)
        except OSError as exc:
            raise SetupError("failed to execute %s: %s" % (self.binary, exc))
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        return ProcResult(argv, proc.returncode, out, err)

    def run_command(self, name, file=None, code=None, cwd=None, stdin_data=None,
                    timeout=DEFAULT_TIMEOUT):
        template = self.command_template(name)
        if template is None:
            raise SetupError("adapter manifest has no command template: %s" % name)
        return self.run(template, file=file, code=code, cwd=cwd,
                        stdin_data=stdin_data, timeout=timeout)

    def run_json(self, name, file=None, code=None, cwd=None,
                 timeout=DEFAULT_TIMEOUT):
        result = self.run_command(name, file=file, code=code, cwd=cwd,
                                  timeout=timeout)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            raise SetupError(
                "command %r did not emit parseable JSON on stdout (rc=%d): %.200s"
                % (name, result.rc, result.stdout))
        return result, payload

    def run_extension(self, ext_name, file=None, cwd=None,
                      timeout=DEFAULT_TIMEOUT):
        """执行 manifest extensions 里登记的扩展出口（如 l2fix）。"""
        ext = self.extension(ext_name)
        if not ext:
            raise SetupError("extension not registered: %s" % ext_name)
        result = self.run(ext["command"], file=file, cwd=cwd, timeout=timeout)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            raise SetupError(
                "extension %r did not emit parseable JSON on stdout (rc=%d): %.200s"
                % (ext_name, result.rc, result.stdout))
        return result, payload

    def tool_version(self):
        if self.version_output is None:
            template = self.manifest.get("version_command") or ["{bin}", "--version"]
            result = self.run(template, timeout=30)
            self.version_output = (result.stdout or result.stderr).strip()
        return self.version_output

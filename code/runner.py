"""Run one manifest-defined CLI input in a fresh directory."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ASSERTION = re.compile(r"Assertion failed:\s*(.+)", re.IGNORECASE)
SANITIZER = re.compile(r"(?:ERROR|SUMMARY): (AddressSanitizer|UndefinedBehaviorSanitizer): ([^\r\n]+)")
WINDOWS_CRASHES = {0xC0000005, 0xC000001D, 0xC0000094, 0xC00000FD,
                   0xC0000409, 0x40000015, 0x80000003}


@dataclass
class Result:
    kind: str
    code: int | None
    stdout: str
    stderr: str
    signature: str = ""
    coverage: frozenset = frozenset()
    elapsed_ms: int = 0


class Target:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.config = json.loads((self.directory / "target.json").read_text(encoding="utf-8"))
        self.command = self.config["command"]
        if not isinstance(self.command, list) or not self.command or not all(
            isinstance(arg, str) and arg for arg in self.command
        ):
            raise ValueError("command must be a nonempty array of argument strings")
        self.timeout = float(self.config.get("timeout_seconds", 2))
        if not 0 < self.timeout <= 120:
            raise ValueError("timeout_seconds must be greater than 0 and at most 120")
        self.reject = set(self.config.get("reject_exit_codes", []))
        self.mode = self.config.get("mode", "bytes")
        if self.mode not in {"bytes", "jq-script", "json"}:
            raise ValueError(f"unknown input mode: {self.mode}")
        self.extension = {"bytes": ".bin", "jq-script": ".jq", "json": ".json"}[self.mode]
        self.seeds = self.directory / self.config.get("seeds", "seeds")
        self.version = self.config.get("version", "unspecified")
        if os.name == "nt":
            import ctypes
            # Prevent child crash dialogs from interrupting unattended runs.
            kernel = ctypes.windll.kernel32
            kernel.SetErrorMode(kernel.GetErrorMode() | 0x0001 | 0x0002 | 0x8000)

    def run(self, data):
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="jq-fuzz-") as work:
            work = Path(work)
            sample = work / ("input" + self.extension)
            sample.write_bytes(data)
            trace = work / "edges.txt"
            argv = [arg.replace("{target}", str(self.directory)).replace("{input}", str(sample))
                    for arg in self.command]
            stdin = data if self.config.get("stdin", False) else b""
            env = dict(os.environ, FUZZ_COVERAGE_FILE=str(trace))
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            with (work / "stdout").open("w+b") as out, (work / "stderr").open("w+b") as err:
                try:
                    proc = subprocess.run(argv, input=stdin, cwd=work, env=env, stdout=out,
                                          stderr=err, timeout=self.timeout, **kwargs)
                except subprocess.TimeoutExpired:
                    result = Result("timeout", None, read_output(out), read_output(err))
                except OSError as exc:
                    result = Result("launch_error", None, "", str(exc))
                else:
                    stdout, stderr = read_output(out), read_output(err)
                    kind, signature = classify(proc.returncode, stderr, self.reject)
                    result = Result(kind, proc.returncode, stdout, stderr, signature)
            if trace.exists():
                result.coverage = frozenset(trace.read_text(encoding="ascii").split())
            result.elapsed_ms = round((time.monotonic() - start) * 1000)
            return result


def read_output(stream):
    stream.seek(0)
    data = stream.read(65537)
    text = data[:65536].decode("utf-8", errors="replace")
    return text + ("\n[output truncated]" if len(data) > 65536 else "")


def classify(code, stderr, reject, windows=None):
    if code == 0:
        return "ok", ""
    match = SANITIZER.search(stderr)
    if match:
        detail = match[2].split(" on address", 1)[0].split(" at ", 1)[0]
        frame = next((line.split(" in ", 1)[1].strip() for line in stderr.splitlines()
                      if re.match(r"\s*#\d+\s+", line) and " in " in line
                      and "jq" in line.lower()), "")
        return "crash", f"{match[1]}: {detail}" + (f" | {frame}" if frame else "")
    match = ASSERTION.search(stderr)
    if match:
        return "crash", "assert: " + match[1].strip()
    windows = os.name == "nt" if windows is None else windows
    if windows and (code & 0xFFFFFFFF) in WINDOWS_CRASHES:
        return "crash", f"Windows exception 0x{code & 0xFFFFFFFF:08X}"
    if not windows and code in {-4, -5, -6, -7, -8, -11}:
        return "crash", f"POSIX signal {-code}"
    if code in reject:
        return "rejected", ""
    return "exit_error", ""

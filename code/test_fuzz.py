import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import mutate
from fuzz import minimize
from mutate import MAX_INPUT, cases
from runner import Result, Target, classify
from suite import compare


def make_target(test, command, **config):
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    path = Path(directory.name)
    (path / "target.json").write_text(
        json.dumps({"command": command, "timeout_seconds": 5, **config}), encoding="utf-8")
    return Target(path)


class DetectorTests(unittest.TestCase):
    def test_standard_compile_error_is_expected(self):
        self.assertEqual(classify(3, "jq: syntax error", {3}, windows=True), ("rejected", ""))

    def test_application_diagnostic_does_not_override_exit_status(self):
        for message in ("Assertion failed: application message", "==123==ERROR: AddressSanitizer: text"):
            with self.subTest(message=message):
                self.assertEqual(classify(5, message, {5}, windows=True), ("rejected", ""))

    def test_asan_diagnostic_requires_instrumented_target(self):
        message = "==123==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x123"
        self.assertEqual(classify(1, message, set(), windows=False), ("exit_error", ""))
        self.assertEqual(classify(1, message, set(), windows=False, address_sanitizer=True),
                         ("crash", "AddressSanitizer: heap-buffer-overflow"))

    def test_windows_abort_with_assertion(self):
        kind, sig = classify(0xC0000409, "Assertion failed: some check", {3}, windows=True)
        self.assertEqual((kind, sig), ("crash", "assert: some check"))

    def test_posix_abort(self):
        self.assertEqual(classify(-6, "", set(), windows=False), ("crash", "POSIX signal 6"))

    def test_ordinary_nonzero_is_separate(self):
        self.assertEqual(classify(9, "", {3}, windows=False), ("exit_error", ""))

    def test_shrink_preserves_signature(self):
        class Dummy:
            def run(self, data):
                signature = "wanted" if b"AB" in data else "different"
                return Result("crash", 1, "", "", signature)

        reduced, attempts = minimize(Dummy(), b"abcABdef", "wanted", limit=40)
        self.assertEqual(reduced, b"AB")
        self.assertLessEqual(attempts, 40)

    def test_seeded_mutation_is_reproducible(self):
        a = cases([b"def f: .; f"], "jq-script", "structured", random.Random(7))
        b = cases([b"def f: .; f"], "jq-script", "structured", random.Random(7))
        self.assertEqual([next(a) for _ in range(20)], [next(b) for _ in range(20)])


class RunnerTests(unittest.TestCase):
    def test_assertion_text_with_normal_exit_is_not_a_crash(self):
        target = make_target(self, [sys.executable, "-c",
                                    "import sys; print('Assertion failed: app', file=sys.stderr);"
                                    " sys.exit(5)"], reject_exit_codes=[5])
        result = target.run(b"")
        self.assertEqual((result.kind, result.code), ("rejected", 5))

    def test_abort_is_reported_with_an_exception_status(self):
        target = make_target(self, [sys.executable, "-c", "import os; os.abort()"])
        result = target.run(b"")
        self.assertEqual(result.kind, "crash")
        self.assertTrue(result.signature)

    def test_missing_binary_is_launch_error(self):
        target = make_target(self, ["{target}/no-such-binary"])
        self.assertEqual(target.run(b"").kind, "launch_error")

    def test_timeout_is_not_a_crash(self):
        target = make_target(self, [sys.executable, "-c", "import time; time.sleep(5)"],
                             timeout_seconds=0.5)
        self.assertEqual(target.run(b"").kind, "timeout")

    def test_directory_with_spaces_and_chinese(self):
        parent = tempfile.TemporaryDirectory()
        self.addCleanup(parent.cleanup)
        path = Path(parent.name) / "\u6d4b\u8bd5 \u76ee\u5f55"
        path.mkdir()
        (path / "target.json").write_text(json.dumps(
            {"command": [sys.executable, "-c", "print('ok')"]}), encoding="utf-8")
        result = Target(path).run(b"")
        self.assertEqual((result.kind, result.stdout.strip()), ("ok", "ok"))

    def test_large_output_is_truncated(self):
        target = make_target(self, [sys.executable, "-c", "print('x' * 70000)"])
        result = target.run(b"")
        self.assertIn("[output truncated]", result.stdout)
        self.assertLess(len(result.stdout), 65600)

    def test_extra_arguments_are_appended(self):
        target = make_target(self, [sys.executable, "-c", "import sys; print(sys.argv[1])"])
        self.assertEqual(target.run(b"", ["hello"]).stdout.strip(), "hello")

    def test_auxiliary_files_are_written(self):
        target = make_target(self, [sys.executable, "-c", "print(open('aux.txt').read())"])
        self.assertEqual(target.run(b"", files={"aux.txt": "payload"}).stdout.strip(), "payload")

    def test_stdin_is_delivered_when_configured(self):
        target = make_target(self, [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
                             stdin=True)
        self.assertEqual(target.run(b"abcde").stdout.strip(), "5")


class MutationTests(unittest.TestCase):
    def test_oversized_seed_is_rejected_before_any_run(self):
        with self.assertRaises(ValueError):
            cases([b"x" * (MAX_INPUT + 1)], "bytes", "bytes", random.Random(1))

    def test_seed_at_limit_is_accepted(self):
        generator = cases([b"x" * MAX_INPUT], "bytes", "bytes", random.Random(1))
        self.assertEqual(len(next(generator)), MAX_INPUT)
        for _ in range(30):
            self.assertLessEqual(len(next(generator)), MAX_INPUT)

    def test_generation_stops_after_repeated_oversized_mutations(self):
        oversized = b"x" * (MAX_INPUT + 1)
        with mock.patch.object(mutate, "byte_mutation", return_value=oversized):
            generator = cases([b"seed"], "bytes", "bytes", random.Random(1))
            next(generator)
            with self.assertRaises(ValueError):
                next(generator)


class ConfirmationTests(unittest.TestCase):
    def test_flaky_crash_is_reported_as_unconfirmed(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        target = Path(workspace.name) / "target"
        (target / "seeds").mkdir(parents=True)
        (target / "seeds" / "seed.bin").write_bytes(b"payload")
        script = target / "flaky.py"
        script.write_text(
            "import os, pathlib, sys\n"
            "counter = pathlib.Path(__file__).with_name('count')\n"
            "n = int(counter.read_text()) if counter.exists() else 0\n"
            "counter.write_text(str(n + 1))\n"
            "if n in (1, 2):\n"
            "    os.abort()\n"
            "sys.exit(0)\n", encoding="utf-8")
        (target / "target.json").write_text(json.dumps({
            "version": "flaky", "command": [sys.executable, str(script)],
            "mode": "bytes", "seeds": "seeds", "timeout_seconds": 10,
        }), encoding="utf-8")
        out = Path(workspace.name) / "out"
        cli = Path(__file__).with_name("fuzz.py")
        proc = subprocess.run([sys.executable, str(cli), "run", str(target),
                               "--strategy", "bytes", "--budget", "3", "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["bugs"], [])
        self.assertEqual(len(summary["unconfirmed"]), 1)
        self.assertIsNone(summary["seconds_to_first_crash"])
        self.assertFalse((out / "bug-001").exists())
        report = json.loads((out / "unstable-001" / "report.json").read_text(encoding="utf-8"))
        self.assertFalse(report["confirmed"])
        self.assertEqual(report["status"], "unstable")


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)

    def write_run(self, name, version, records):
        path = self.root / name
        path.mkdir()
        (path / "summary.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        with (path / "cases.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
        return path

    @staticmethod
    def record(key, versions=None):
        record = {"id": key, "category": "normal",
                  "actual": {"kind": "ok", "exit": 0, "stdout": "x"}}
        if versions:
            record["versions"] = versions
        return record

    def test_missing_case_fails_the_comparison(self):
        old = self.write_run("old", "jq 1.8.0", [self.record("a"), self.record("b")])
        new = self.write_run("new", "jq 1.8.0", [self.record("a")])
        out = self.root / "comparison.json"
        status = compare(SimpleNamespace(old=str(old), new=str(new), out=str(out)))
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_from_new"], ["b"])

    def test_version_specific_case_is_not_treated_as_missing(self):
        old = self.write_run("old", "jq 1.8.0",
                             [self.record("a"), self.record("b", ["jq 1.8.0"])])
        new = self.write_run("new", "jq 1.8.1", [self.record("a")])
        out = self.root / "comparison.json"
        status = compare(SimpleNamespace(old=str(old), new=str(new), out=str(out)))
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertTrue(result["complete"])
        self.assertEqual(result["version_specific"], [{"id": "b", "only_in": "old"}])


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

from fuzz import minimize
from mutate import cases
from runner import Result, Target, classify


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


if __name__ == "__main__":
    unittest.main()

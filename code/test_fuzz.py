import random
import unittest

from fuzz import minimize
from mutate import cases
from runner import Result, classify


class DetectorTests(unittest.TestCase):
    def test_standard_compile_error_is_expected(self):
        self.assertEqual(classify(3, "jq: syntax error", {3}, windows=True), ("rejected", ""))

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


if __name__ == "__main__":
    unittest.main()

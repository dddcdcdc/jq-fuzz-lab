"""Check that jq sorts integer arrays correctly and that sorting is idempotent."""
import argparse
import json
from pathlib import Path
import platform
import random
from runner import PLATFORM_VERSION, Target


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("target")
parser.add_argument("--seed", type=int, default=19)
parser.add_argument("--count", type=int, default=50)
parser.add_argument("--out", required=True)
args = parser.parse_args()
target = Target(args.target)
rng = random.Random(args.seed)
violations = []
arrays = [[], [0], [3, -1, 3, 0], [2**31 - 1, -(2**31), 0]]
arrays.extend([rng.choices(range(-200, 201), k=rng.randrange(40)) for _ in range(args.count)])
for values in arrays:
    case = json.dumps(values).encode("utf-8")
    first = target.run(case)
    if first.kind != "ok":
        violations.append({"input": values, "stage": "first", "kind": first.kind, "error": first.stderr})
        continue
    second = target.run(first.stdout.encode("utf-8"))
    if second.kind != "ok":
        violations.append({"input": values, "stage": "second", "kind": second.kind, "error": second.stderr})
        continue
    try:
        actual, repeated = json.loads(first.stdout), json.loads(second.stdout)
    except ValueError:
        violations.append({"input": values, "stage": "decode", "output": first.stdout})
        continue
    if actual != sorted(values) or repeated != actual:
        violations.append({"input": values, "actual": actual, "repeated": repeated})
report = {"platform_version": PLATFORM_VERSION, "version": target.version,
          "target_sha256": target.sha256, "seed": args.seed, "cases": len(arrays),
          "passed": len(arrays) - len(violations), "violations": violations,
          "environment": {"python": platform.python_version(), "platform": platform.platform()}}
Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"Sort property checks: {report['passed']}/{report['cases']}")
raise SystemExit(bool(violations))

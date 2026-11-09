"""Execute the deterministic case corpus and record every case outcome.

Two actions:

  run      execute targets/jq-cases/cases.jsonl against one build
  compare  list cases whose observable behaviour differs between two runs
"""
import argparse
from collections import Counter, defaultdict
import json
import platform
from pathlib import Path
import sys
import time

from runner import PLATFORM_VERSION, Target


def normalize(text):
    # Windows builds of the reference target terminate lines with CRLF.
    return text.replace("\r\n", "\n")


def display_path(binary):
    """Report the binary relative to the repository when it lives inside it."""
    try:
        return Path(binary).resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix()
    except ValueError:
        return binary


def check(case, result):
    expect = case["expect"]
    failures = []
    if "kind" in expect and result.kind != expect["kind"]:
        failures.append(f"kind: expected {expect['kind']}, got {result.kind}")
    if result.code != expect["exit"]:
        failures.append(f"exit: expected {expect['exit']}, got {result.code}")
    if "stdout" in expect and normalize(result.stdout) != normalize(expect["stdout"]):
        failures.append("stdout differs")
    for needle in expect.get("stderr_contains", []):
        if needle.lower() not in result.stderr.lower():
            failures.append(f"stderr lacks {needle!r}")
    return failures


def run(args):
    target = Target(args.target)
    if args.binary:
        target.use_binary(args.binary)
    if args.version:
        target.version = args.version
    corpus = target.directory / "cases.jsonl"
    cases = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line]
    cases = [case for case in cases if "versions" not in case or target.version in case["versions"]]
    if args.category:
        cases = [case for case in cases if case["category"] in args.category]
    if not cases:
        raise ValueError("no case matches the selected filters")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    counts = defaultdict(Counter)
    records, failed = [], []
    for case in cases:
        result = target.run(case["stdin"].encode("utf-8"), case["argv"], case.get("files"))
        failures = check(case, result)
        counts[case["category"]]["total"] += 1
        counts[case["category"]]["passed" if not failures else "failed"] += 1
        record = {
            "id": case["id"], "category": case["category"], "argv": case["argv"],
            "stdin": case["stdin"], "files": case.get("files", {}),
            "expected": case["expect"],
            "actual": {"kind": result.kind, "exit": result.code,
                       "stdout": normalize(result.stdout),
                       "stderr": result.stderr[:400], "elapsed_ms": result.elapsed_ms},
            "passed": not failures, "failures": failures,
        }
        if case.get("versions"):
            record["versions"] = case["versions"]
        records.append(record)
        if failures:
            failed.append(record)
            print(f"[fail] {case['id']}: {'; '.join(failures)}", flush=True)
    with (out / "cases.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "platform_version": PLATFORM_VERSION,
        "version": target.version,
        "target_sha256": target.sha256,
        "binary": display_path(target.command[0].replace("{target}", str(target.directory))),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "cases": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "by_category": {name: dict(counter) for name, counter in sorted(counts.items())},
        "failures": [record["id"] for record in failed],
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    print(f"[suite] {summary['version']}: {summary['passed']}/{summary['cases']} passed "
          f"in {summary['elapsed_seconds']}s", flush=True)
    for name, counter in summary["by_category"].items():
        print(f"  {name:12} {counter.get('passed', 0)}/{counter.get('total', 0)}", flush=True)
    return 0 if not failed else 1


def compare(args):
    old_dir, new_dir = Path(args.old), Path(args.new)
    old_summary = json.loads((old_dir / "summary.json").read_text(encoding="utf-8"))
    new_summary = json.loads((new_dir / "summary.json").read_text(encoding="utf-8"))
    old_cases = load_cases(old_dir / "cases.jsonl")
    new_cases = load_cases(new_dir / "cases.jsonl")
    old_ids, new_ids = set(old_cases), set(new_cases)
    shared = sorted(old_ids & new_ids)
    differences = []
    for key in shared:
        before, after = old_cases[key]["actual"], new_cases[key]["actual"]
        changed = {field: {"from": before[field], "to": after[field]}
                   for field in ("kind", "exit", "stdout") if before[field] != after[field]}
        if changed:
            differences.append({"id": key, "category": old_cases[key]["category"],
                                "difference": changed})
    version_specific, missing, added = [], [], []
    for key in sorted(old_ids - new_ids):
        record = old_cases[key]
        if record.get("versions") and new_summary["version"] not in record["versions"]:
            version_specific.append({"id": key, "only_in": "old"})
        else:
            missing.append(key)
    for key in sorted(new_ids - old_ids):
        record = new_cases[key]
        if record.get("versions") and old_summary["version"] not in record["versions"]:
            version_specific.append({"id": key, "only_in": "new"})
        else:
            added.append(key)
    result = {
        "old": old_summary["version"], "new": new_summary["version"],
        "cases_run": {"old": len(old_ids), "new": len(new_ids)},
        "shared_cases": len(shared),
        "differences": len(differences), "cases": differences,
        "missing_from_new": missing, "added_in_new": added,
        "version_specific": version_specific,
        "complete": not missing and not added,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(f"[compare] {result['old']} vs {result['new']}: "
          f"{result['differences']} difference(s) in {result['shared_cases']} shared cases; "
          f"missing {len(missing)}, added {len(added)}, "
          f"version-specific {len(version_specific)}")
    for item in differences:
        print(f"  [diff] {item['id']}: {item['difference']}")
    for key in missing:
        print(f"  [missing] {key}: present in old run only")
    for key in added:
        print(f"  [added] {key}: present in new run only")
    return 0 if not differences and result["complete"] else 1


def load_cases(path):
    return {json.loads(line)["id"]: json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run_parser = actions.add_parser("run", help="execute the case corpus")
    run_parser.add_argument("target")
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--binary", help="run the corpus with another build")
    run_parser.add_argument("--version", help="label for the build used by --binary")
    run_parser.add_argument("--category", nargs="+", help="restrict to these categories")
    compare_parser = actions.add_parser("compare", help="diff two run summaries")
    compare_parser.add_argument("old")
    compare_parser.add_argument("new")
    compare_parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        return run(args) if args.action == "run" else compare(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())

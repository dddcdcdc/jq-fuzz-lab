"""Command-line runner, fuzzer, minimizer and replay tool."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import platform
import random
import sys
import time

from mutate import cases
from runner import PLATFORM_VERSION, Target


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def result_json(result):
    return {**asdict(result), "coverage": sorted(result.coverage)}


def minimize(target, data, signature, limit=100):
    size = 2
    attempts = 0
    while len(data) and attempts < limit:
        width = (len(data) + size - 1) // size
        for start in range(0, len(data), width):
            candidate = data[:start] + data[start + width:]
            attempts += 1
            result = target.run(candidate)
            if result.kind == "crash" and result.signature == signature:
                data, size = candidate, max(2, size - 1)
                break
            if attempts >= limit:
                return data, attempts
        else:
            if size >= len(data):
                break
            size = min(len(data), size * 2)
    return data, attempts


def report(target, out, number, data, result, iteration):
    out.mkdir()
    original = out / ("original" + target.extension)
    original.write_bytes(data)
    reduced, attempts = minimize(target, data, result.signature)
    minimized = out / ("minimized" + target.extension)
    minimized.write_bytes(reduced)
    confirmation = target.run(reduced)
    confirmed = confirmation.kind == "crash" and confirmation.signature == result.signature
    if not confirmed:
        reduced = data
        minimized.write_bytes(data)
        confirmation = target.run(data)
        confirmed = confirmation.kind == "crash" and confirmation.signature == result.signature
    metadata = {
        "id": number, "target_version": target.version, "found_at": iteration,
        "status": "confirmed" if confirmed else "unstable",
        "confirmed": confirmed,
        "original_bytes": len(data), "minimized_bytes": len(reduced),
        "minimizer_executions": attempts, "original": result_json(result),
        "confirmation": result_json(confirmation),
        "input_file": minimized.name,
        "replay": "python code/fuzz.py replay <target-dir> <path-to-minimized-input>",
    }
    write_json(out / "report.json", metadata)
    (out / "stderr.txt").write_text(result.stderr, encoding="utf-8", newline="")
    if confirmed:
        print(f"  [shrink] {len(data)} -> {len(reduced)} bytes ({attempts} trials)", flush=True)
    else:
        print("  [unstable] final confirmation did not reproduce the crash", flush=True)
    return metadata


def fuzz(args, target):
    seeds = sorted(path for path in target.seeds.iterdir() if path.is_file())
    pool = [path.read_bytes() for path in seeds]
    if not pool:
        raise ValueError("seed corpus is empty")
    control = target.run(pool[0])
    if control.kind != "ok":
        raise ValueError(f"the first seed must succeed: {control.kind} {control.stderr.strip()}")
    if args.strategy == "guided" and not control.coverage:
        raise ValueError("guided mode requires an instrumented target with edge coverage")
    if args.budget < len(pool):
        raise ValueError("budget must cover the initial corpus")
    generated = cases(pool, target.mode, args.strategy, random.Random(args.seed))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    coverage, findings, unstable = set(), {}, {}
    results = Counter()
    first_crash = None
    print(f"[run] {target.version} | {target.mode} | {args.strategy} | "
          f"seed={args.seed} | budget={args.budget}", flush=True)
    for iteration in range(1, args.budget + 1):
        data = next(generated)
        result = target.run(data)
        if result.kind == "launch_error":
            raise ValueError(result.stderr)
        results[result.kind] += 1
        new_edges = result.coverage - coverage
        coverage.update(result.coverage)
        if args.strategy == "guided" and new_edges and result.kind in {"ok", "rejected"}:
            if data not in pool:
                pool.append(data)
        if (result.kind == "crash" and result.signature not in findings
                and result.signature not in unstable):
            confirmation = target.run(data)
            if confirmation.kind != "crash" or confirmation.signature != result.signature:
                unstable[result.signature] = {"found_at": iteration}
                print(f"[unstable] case {iteration}: {result.signature} "
                      f"(not reproducible)", flush=True)
            else:
                number = len(findings) + 1
                directory = out / f"bug-{number:03}"
                found_after = round(time.monotonic() - started, 2)
                info = report(target, directory, number, data, result, iteration)
                if info["confirmed"]:
                    if first_crash is None:
                        first_crash = found_after
                    print(f"[crash #{number}] case {iteration}: {result.signature}", flush=True)
                    findings[result.signature] = info
                else:
                    name = f"unstable-{len(unstable) + 1:03}"
                    unstable[result.signature] = {"found_at": iteration, "report": name}
                    directory.rename(out / name)
        if iteration % 25 == 0 or iteration == args.budget:
            print(f"[progress] {iteration}/{args.budget} | crash runs={results['crash']} | "
                  f"unique={len(findings)} | edges={len(coverage)}", flush=True)
    summary = {
        "platform_version": PLATFORM_VERSION,
        "version": target.version, "target_sha256": target.sha256,
        "mode": target.mode, "strategy": args.strategy,
        "seed": args.seed, "executions": args.budget, "outcomes": dict(results),
        "coverage_edges": len(coverage) if coverage else None,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "seconds_to_first_crash": first_crash,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "bugs": [{"signature": signature, "found_at": info["found_at"], "id": info["id"]}
                 for signature, info in findings.items()],
        "unconfirmed": [{"signature": signature, "found_at": info["found_at"],
                         "report": info.get("report")}
                        for signature, info in unstable.items()],
    }
    write_json(out / "summary.json", summary)
    detail = f"{len(findings)} reproducible bug(s)"
    if unstable:
        detail += f", {len(unstable)} unconfirmed"
    print(f"[done] {detail}; summary: {out / 'summary.json'}", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run", help="fuzz a directory with target.json")
    run.add_argument("target")
    run.add_argument("--strategy", choices=["bytes", "structured", "guided"], default="structured")
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--budget", type=int, default=150)
    run.add_argument("--out", required=True)
    replay = commands.add_parser("replay", help="run one saved input")
    replay.add_argument("target")
    replay.add_argument("input")
    replay.add_argument("--out", help="write a JSON record")
    args = parser.parse_args()
    try:
        target = Target(args.target)
        if args.action == "run":
            return fuzz(args, target)
        result = target.run(Path(args.input).read_bytes())
        print(f"[replay] {target.version} | {result.kind} | exit={result.code}")
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())
        if args.out:
            write_json(Path(args.out), result_json(result))
        return 0 if result.kind in {"ok", "rejected", "crash"} else 2
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())

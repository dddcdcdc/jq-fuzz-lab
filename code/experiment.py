"""Repeat byte and structure-aware tests under equal input budgets."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("target")
parser.add_argument("--budget", type=int, default=100)
parser.add_argument("--seeds", type=int, nargs="+", default=[7, 17, 37])
parser.add_argument("--out", required=True)
parser.add_argument("--guided", action="store_true")
args = parser.parse_args()
out = Path(args.out)
out.mkdir(parents=True)
cli = Path(__file__).with_name("fuzz.py")
rows = []
strategies = ["bytes", "structured"] + (["guided"] if args.guided else [])
for seed in args.seeds:
    for strategy in strategies:
        directory = out / f"{strategy}-{seed}"
        subprocess.run([sys.executable, str(cli), "run", args.target, "--strategy", strategy,
                        "--seed", str(seed), "--budget", str(args.budget), "--out", str(directory)],
                       check=True)
        data = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        rows.append({
            "strategy": strategy, "seed": seed, "budget": args.budget,
            "ok": data["outcomes"].get("ok", 0), "rejected": data["outcomes"].get("rejected", 0),
            "crash_runs": data["outcomes"].get("crash", 0),
            "timeout": data["outcomes"].get("timeout", 0),
            "exit_error": data["outcomes"].get("exit_error", 0),
            "unique_confirmed": len(data["bugs"]), "first_case": min(
                (bug["found_at"] for bug in data["bugs"]), default=None),
            "seconds_to_first_crash": data["seconds_to_first_crash"],
            "elapsed_seconds": data["elapsed_seconds"],
            "coverage_edges": data["coverage_edges"],
            "target_sha256": data["target_sha256"],
        })
with (out / "comparison.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

aggregate = {}
for strategy in strategies:
    group = [row for row in rows if row["strategy"] == strategy]
    firsts = [row["first_case"] for row in group if row["first_case"] is not None]
    aggregate[strategy] = {
        "runs": len(group),
        "runs_with_crash": sum(1 for row in group if row["unique_confirmed"]),
        "first_case_mean": round(statistics.mean(firsts), 2) if firsts else None,
        "first_case_median": statistics.median(firsts) if firsts else None,
        "first_case_min": min(firsts) if firsts else None,
        "first_case_max": max(firsts) if firsts else None,
        "crash_runs_total": sum(row["crash_runs"] for row in group),
        "seconds_mean": round(statistics.mean(row["elapsed_seconds"] for row in group), 2),
    }
(out / "aggregate.json").write_text(json.dumps({
    "budget": args.budget, "seeds": args.seeds, "strategies": aggregate,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(aggregate, ensure_ascii=False, indent=2))

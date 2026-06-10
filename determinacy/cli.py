"""determinacy run <config.toml> [--tier N] [--limit K] [--workers W] [--out DIR]

Pipeline: load tasks (adapter) -> materialize cases -> coverage screen (tier 1) ->
airtight witnesses (tier 2) -> tiered report. Tier 3 (graded-patch) is documented in the
README and left to the bench's own harness; this CLI runs tiers 1-2 (the agent-only + grep tiers).
"""
import argparse, pathlib, sys
from .config import load_config
from .adapter import load_tasks
from .materialize import materialize
from . import coverage, witness, plurality, refute, report, receipts


def main(argv=None):
    ap = argparse.ArgumentParser(prog="determinacy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="audit a benchmark")
    r.add_argument("config")
    r.add_argument("--tier", type=int, default=2, help="highest tier to run (1=coverage, 2=airtight)")
    r.add_argument("--limit", type=int, default=None, help="cap number of tasks (smoke test)")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--out", default=None, help="output dir (default runs/<name>)")
    r.add_argument("--no-clone", action="store_true", help="tier 2 without codebase grep (downgrades airtight)")
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    out = pathlib.Path(a.out or f"runs/{cfg['name']}")
    cases = out / "cases"
    cache = out / ".cache" / "repos"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[determinacy] {cfg['name']}: loading tasks via {cfg['source']}")
    tasks = load_tasks(cfg, limit=a.limit)
    ids = materialize(tasks, cases)
    print(f"[determinacy] materialized {len(ids)} cases -> {cases}")

    print(f"[determinacy] tier 1 coverage screen (agent={cfg['agent']!r})")
    recs = coverage.run(cases, cfg["agent"], out, workers=a.workers)
    amb = sum(r["verdict"] == "AMBIGUOUS" for r in recs)
    print(f"[determinacy]   {amb}/{len(recs)} AMBIGUOUS (>=1 grep-verified GAP)")

    if a.tier >= 2:
        print(f"[determinacy] tier 2a airtight witnesses (clone+grep)")
        counts = witness.run(cases, cfg["agent"], out, cache, do_clone=not a.no_clone, workers=a.workers)
        print(f"[determinacy]   airtight={counts['airtight']} "
              f"prose-affirmative={counts['prose-affirmative']} hypothesis={counts['hypothesis']}")
        if not a.no_clone:
            print(f"[determinacy] tier 2b codebase-plurality (clone+grep, multiplicity)")
            ncand = plurality.run(cases, cfg["agent"], out, cache, workers=a.workers)
            print(f"[determinacy]   {ncand} plural candidates")
            print(f"[determinacy] tier 2c comparability refutation (the quality gate)")
            ref = refute.run(cases, cfg["agent"], workers=a.workers)
            print(f"[determinacy]   plural survived={ref['survived']} dropped(cherry-pick)={ref['dropped']}")

    summary = report.build_report(out, cases, cfg["name"])
    nr = receipts.write_all(cases, out)
    print(f"[determinacy] wrote {nr} per-problem receipts (cases/<id>/RECEIPT.md)")
    print(f"[determinacy] DONE. claimable spine = {summary.get('spine', summary['airtight'])} "
          f"({summary['airtight']} airtight + {summary.get('plural', 0)} plural); "
          f"coverage screen {summary['behavior_gap_pct']:.1f}% behavior-level. "
          f"See {out}/REPORT.md and {out}/CLAIMS.md")


if __name__ == "__main__":
    sys.exit(main())

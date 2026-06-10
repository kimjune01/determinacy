"""Aggregate the run into a tiered REPORT.md + a CLAIMS.md (one row per airtight witness)."""
import json, math, pathlib, re


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def build_report(out_dir, cases_dir, name):
    out_dir, cases_dir = pathlib.Path(out_dir), pathlib.Path(cases_dir)
    recs = []
    for jf in (out_dir / "judge").glob("*.json"):
        try:
            r = json.loads(jf.read_text())
            if r.get("in_gold_total", 0) > 0:
                recs.append(r)
        except Exception:
            pass
    n = len(recs)
    amb = [r for r in recs if r["n_gap"] > 0]
    beh = sum(r["in_gold_total"] for r in recs)
    gap = sum(r["n_gap"] for r in recs)

    airtight, hyps = [], 0
    for d in cases_dir.iterdir():
        if (d / "AMBIGUITY_WITNESS.md").exists():
            t = (d / "AMBIGUITY_WITNESS.md").read_text()
            if "class: **airtight**" in t:
                m = re.search(r"constant `([^`]+)`", t)
                airtight.append((d.name, m.group(1) if m else "?"))
        elif (d / "AMBIGUITY_HYPOTHESIS.md").exists():
            hyps += 1
    alo, ahi = wilson(len(airtight), n)

    R = [f"# Determinacy report -- {name}", "",
         f"Cases with >=1 graded behavior: **{n}**.  Graded behaviors total: **{beh}**.", "",
         "| tier | what it measures | rate | trust |", "|---|---|---|---|",
         f"| 0 screen (coverage, case-level) | >=1 prose-silent behavior | "
         f"{len(amb)}/{n} = {100*len(amb)/n:.1f}% | loose upper bound |",
         f"| 1 coverage (behavior-level) | prose-silent graded behaviors (grep-verified) | "
         f"{gap}/{beh} = {100*gap/beh:.1f}% | upper bound (over-flags) |",
         f"| **2 airtight (mechanical spine)** | constant absent from prose+codebase (clone+grep) | "
         f"**{len(airtight)}/{n} = {100*len(airtight)/n:.1f}%** (Wilson95 {100*alo:.1f}-{100*ahi:.1f}) | "
         f"**claimable** |",
         f"| hypotheses | prose-affirmative + codebase, raters-pending | {hyps} | not claimed |", "",
         "Tiers 0-1 over-flag (parametrized behaviors, convention-resolved silence) and are disclosed as "
         "upper bounds. Only tier 2 survives a hostile reader. See `CLAIMS.md` for the certified spine.", ""]
    (out_dir / "REPORT.md").write_text("\n".join(R) + "\n")

    C = [f"# CLAIMS -- {name}: airtight witnesses (mechanical spine)", "",
         "Each row: the hidden test grades a discriminating constant absent from the prose AND the "
         "codebase at base_commit (clone + ripgrep), present only in gold+test. Re-runnable; no model "
         "judgment in the verdict.", "",
         "| case | discriminating constant | witness | receipts |", "|---|---|---|---|"]
    for case, const in sorted(airtight):
        rel = f"cases/{case}"
        C.append(f"| `{case}` | `{const[:60]}` | [witness]({rel}/AMBIGUITY_WITNESS.md) | "
                 f"[spec]({rel}/spec.md) · [gold]({rel}/gold.diff) · [test]({rel}/hidden_test.diff) |")
    (out_dir / "CLAIMS.md").write_text("\n".join(C) + "\n")
    return {"n": n, "behavior_gap_pct": 100 * gap / beh if beh else 0,
            "airtight": len(airtight), "hypotheses": hyps}

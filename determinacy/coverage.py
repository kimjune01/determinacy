"""Tier 1 -- coverage screen. For each behavior the hidden test checks, the agent cites
the verbatim prose clause that determines it (or null) AND the verbatim gold snippet that
implements it (or null). We VERIFY both citations against the actual text, then:

  GAP          = tested AND in-gold AND not-covered  -> the test grades what the prose never stated
  COVERED      = tested AND in-gold AND covered
  OUT_OF_SCOPE = not in gold (pre-existing scaffolding)

Citations are grep-verified, so a GAP is checkable, not a vibe. (Generalized from
swebench-pro-audit/tools/judge_pool.py.)
"""
import json, re, pathlib, concurrent.futures as cf
from .agent import run_agent, extract_json

PROMPT = """You are a benchmark determinacy auditor detecting "mindreading": behaviors a solver could
only produce by guessing the author's unstated intent. You are given the task PROBLEM (the prose a solver
receives), the GOLD PATCH (accepted solution), the HIDDEN TEST, and the FAIL_TO_PASS list.

For EACH distinct behavior the hidden test asserts (a specific value, timing, ordering, exception, shape,
or when-to-act decision), output:
- "test": the behavior, concrete.
- "covering_prose": the VERBATIM clause from the PROBLEM that determines it, copied EXACTLY; or null.
- "gold_anchor": a short VERBATIM snippet from the GOLD PATCH (a changed line/identifier) that implements
  this behavior, copied EXACTLY; or null if the gold does not implement it.

Both citations are checked against the actual text; invention is rejected. A behavior is determined only
if derivable from the quoted prose ALONE. Do NOT use anything you recall about this repo. Enumerate
specific constants (delays, counts), exception types, and decision points.

Output your FINAL message as ONLY this JSON:
{"rows": [{"test": "...", "covering_prose": "..."|null, "gold_anchor": "..."|null}, ...]}

=== PROBLEM (prose) ===
{spec}

=== GOLD PATCH ===
{gold}

=== FAIL_TO_PASS ===
{f2p}

=== HIDDEN TEST ===
{test}
"""


def aggr(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split())


def cited(quote, ntext, tok):
    a = aggr(quote)
    if not a:
        return False
    if a in ntext:
        return True
    qt = [w for w in a.split() if len(w) > 3]
    return bool(qt) and sum(w in tok for w in qt) / len(qt) >= 0.85


def classify(rows, spec, gold):
    nspec, ngold = aggr(spec), aggr(gold)
    st = set(w for w in nspec.split() if len(w) > 3)
    gt = set(w for w in ngold.split() if len(w) > 3)
    for r in rows:
        in_gold = bool(r.get("gold_anchor")) and cited(r["gold_anchor"], ngold, gt)
        in_prose = bool(r.get("covering_prose")) and cited(r["covering_prose"], nspec, st)
        r["in_gold"] = in_gold
        r["status"] = "OUT_OF_SCOPE" if not in_gold else ("COVERED" if in_prose else "GAP")
    return rows


def find_line(text, quote):
    q = aggr(quote)
    if not q:
        return None
    head = " ".join(q.split()[:6])
    for i, ln in enumerate(text.splitlines(), 1):
        if head and head in aggr(ln):
            return i
    return None


def _read(d, name, n=None):
    p = d / name
    t = p.read_text() if p.exists() else ""
    return t[:n] if n else t


def judge(case_dir, agent_cmd, out_dir):
    d = pathlib.Path(case_dir)
    short = d.name
    spec, gold = _read(d, "spec.md"), _read(d, "gold.diff")
    test, f2p = _read(d, "hidden_test.diff", 12000), _read(d, "fail_to_pass.txt", 2000)
    prompt = (PROMPT.replace("{spec}", spec[:9000]).replace("{gold}", gold[:14000])
              .replace("{f2p}", f2p).replace("{test}", test))
    raw = run_agent(agent_cmd, prompt)
    (out_dir / "judge").mkdir(parents=True, exist_ok=True)
    (out_dir / "judge" / f"{short}.last.txt").write_text(raw)
    parsed = extract_json(raw)
    rows = parsed.get("rows", []) if parsed else []
    ok = parsed is not None
    classify(rows, spec, gold)
    gap = sum(r["status"] == "GAP" for r in rows)
    cov = sum(r["status"] == "COVERED" for r in rows)
    oos = sum(r["status"] == "OUT_OF_SCOPE" for r in rows)
    rec = {"case": short, "ok": ok,
           "verdict": "ERROR" if not ok else ("AMBIGUOUS" if gap else "ENTAILED"),
           "in_gold_total": cov + gap, "n_covered": cov, "n_gap": gap,
           "n_out_of_scope": oos, "rows": rows}
    (out_dir / "judge" / f"{short}.json").write_text(json.dumps(rec, indent=1))
    write_table(d, rec, out_dir)
    return rec


def write_table(d, rec, out_dir):
    short = rec["case"]
    spec_txt, gold_txt = _read(d, "spec.md"), _read(d, "gold.diff")
    rel = f"../cases/{short}"
    L = [f"# Coverage attribution: {short}", "",
         f"- verdict: **{rec['verdict']}**  ({rec['n_covered']}/{rec['in_gold_total']} in-gold "
         f"behaviors covered; **{rec['n_gap']} GAP** = mindreading; {rec['n_out_of_scope']} out-of-scope)",
         f"- receipts: [`spec.md`]({rel}/spec.md) · [`gold.diff`]({rel}/gold.diff) · "
         f"[`hidden_test.diff`]({rel}/hidden_test.diff)",
         "- A **GAP** is a behavior the gold implements and the test checks, but no prose clause states.",
         "", "| test behavior | covering clause (prose) | implemented in gold |", "|---|---|---|"]
    order = {"GAP": 0, "COVERED": 1, "OUT_OF_SCOPE": 2}
    for r in sorted(rec["rows"], key=lambda r: order.get(r["status"], 3)):
        t = (r.get("test") or "").replace("|", "\\|")[:140]
        cp, ga = r.get("covering_prose"), r.get("gold_anchor")
        prose = ""
        if r["status"] == "COVERED" and cp:
            ln = find_line(spec_txt, cp)
            prose = f"[`{cp[:80]}`]({rel}/spec.md{'#L'+str(ln) if ln else ''})"
        gold = "_(not in gold)_" if r["status"] == "OUT_OF_SCOPE" else ""
        if r["status"] != "OUT_OF_SCOPE" and ga:
            ln = find_line(gold_txt, ga)
            gold = f"[`{ga[:80]}`]({rel}/gold.diff{'#L'+str(ln) if ln else ''})"
        L.append(f"| {t} | {prose} | {gold} |")
    (out_dir / "attribution").mkdir(parents=True, exist_ok=True)
    (out_dir / "attribution" / f"{short}.md").write_text("\n".join(L) + "\n")


def run(cases_dir, agent_cmd, out_dir, workers=10, slugs=None):
    cases_dir, out_dir = pathlib.Path(cases_dir), pathlib.Path(out_dir)
    dirs = [cases_dir / s for s in slugs] if slugs else \
        [d for d in cases_dir.iterdir() if d.is_dir()]
    recs = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for rec in ex.map(lambda d: judge(d, agent_cmd, out_dir), dirs):
            recs.append(rec)
    return recs

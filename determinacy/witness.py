"""Tier 2 -- airtight witness (the mechanical spine). For each AMBIGUOUS case the agent
proposes the single strongest witness over the GAP behaviors and classifies it:

  airtight          -- pinned by an ARBITRARY CONSTANT present only in gold+test
  prose-affirmative -- the prose explicitly describes the alternative reading R2
  codebase / borderline -- a convention might bind (HYPOTHESIS; never auto-claimed)

The agent only PROPOSES. We then VERIFY mechanically: airtight is claimable ONLY when the
discriminating constant is absent from the prose AND absent from the codebase at base_commit
(cached git checkout + ripgrep). Absent from both, present only in gold+test -> airtight, PROVEN.
Everything else -> AMBIGUITY_HYPOTHESIS.md, counted in no claimable rate.

(Generalized from swebench-pro-audit/tools/witness.py. The `-e` separator in in_codebase is load-
bearing: a constant like `-1` must not be parsed as a ripgrep flag, or absence is vacuously certified.)
"""
import json, re, shutil, subprocess, pathlib, concurrent.futures as cf
from .agent import run_agent, extract_json
from . import coverage as cov

PROMPT = """You are a benchmark determinacy auditor. A screen found GAP behaviors in this task:
behaviors the HIDDEN TEST checks and the GOLD PATCH implements, but that NO prose requirement states.
Pick the SINGLE strongest ambiguity witness among the GAPs and classify it.

Definitions (be strict):
- "airtight": pinned by an ARBITRARY CONSTANT (a specific number, string literal, count, delay, key
  name, class/identifier) a solver could NOT derive from the prose -- a free authorial choice. Give the
  EXACT constant token as it appears in gold+test.
- "prose-affirmative": the prose EXPLICITLY describes a DIFFERENT, equally-faithful contract R2 than the
  one the test pins. Quote the verbatim prose clause supporting R2.
- "codebase": the rule might be set by a codebase convention, not the prose (a hypothesis).
- "borderline": a single plausible reading might bind.

Output ONLY this JSON:
{
 "test_behavior": "the GAP behavior, concrete",
 "klass": "airtight"|"prose-affirmative"|"codebase"|"borderline",
 "constant": "the arbitrary constant token (airtight only; else null)",
 "r2_prose_clause": "verbatim prose clause supporting the alternative (prose-affirmative only; else null)",
 "gold_anchor": "verbatim snippet from GOLD PATCH implementing the test-pinned reading R1",
 "test_assertion": "verbatim snippet from HIDDEN TEST that discriminates R1 from R2",
 "R1": "the reading the test pins (one sentence)",
 "R2": "a prose-faithful alternative a from-prose engineer could ship (one sentence)",
 "why_R2_fails": "why R2 fails the test assertion (one sentence)"
}
Copy all quoted snippets EXACTLY. Do NOT use anything you recall about this repo.

=== PROBLEM (prose) ===
{spec}
=== GOLD PATCH ===
{gold}
=== HIDDEN TEST ===
{test}
=== GAP BEHAVIORS (screen) ===
{gaps}
"""


def clone_at(repo, commit, cache):
    dst = pathlib.Path(cache) / repo.replace("/", "__")
    marker = dst / ".checked_out"
    if marker.exists() and marker.read_text().strip() == commit:
        return dst
    dst.mkdir(parents=True, exist_ok=True)
    try:
        if not (dst / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=dst, check=True)
            subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"],
                           cwd=dst, check=True)
        f = subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", commit],
                           cwd=dst, capture_output=True, text=True)
        if f.returncode != 0:
            subprocess.run(["git", "fetch", "-q", "origin"], cwd=dst, capture_output=True, text=True)
        co = subprocess.run(["git", "checkout", "-q", "-f", commit], cwd=dst,
                            capture_output=True, text=True)
        if co.returncode != 0:
            return None
        marker.write_text(commit)
        return dst
    except Exception:
        return None


def _signatures(const):
    sigs = [const]
    m = re.match(r"[\[\]\s\"']*([A-Za-z0-9_:\-./]{6,}?)(?:[,$%{}\s]|$)", const)
    if m and m.group(1) != const and len(m.group(1)) >= 6:
        sigs.append(m.group(1))
    return [s for s in dict.fromkeys(sigs) if s]


def in_codebase(tree, const):
    """True if the constant occurs in the tree (excluding tests). `-e` is mandatory so a leading-dash
    constant (e.g. -1) is treated as a pattern, not a flag -- else absence is vacuously certified."""
    if not const:
        return False
    rg = shutil.which("rg")
    for sig in _signatures(const):
        if rg:
            r = subprocess.run([rg, "-l", "--fixed-strings", "-g", "!*test*", "-g", "!*spec*",
                                "-e", sig, str(tree)], capture_output=True, text=True)
        else:
            r = subprocess.run(["grep", "-rIl", "--exclude=*test*", "-e", sig, str(tree)],
                               capture_output=True, text=True)
        if r.stdout.strip():
            return True
    return False


def draft(case_dir, agent_cmd, out_dir):
    d = pathlib.Path(case_dir)
    short = d.name
    jf = pathlib.Path(out_dir) / "judge" / f"{short}.json"
    if not jf.exists():
        return {"case": short, "skip": "no coverage json"}
    rec = json.loads(jf.read_text())
    gaps = [r for r in rec.get("rows", []) if r.get("status") == "GAP"]
    if not gaps:
        return {"case": short, "skip": "no GAP"}
    spec, gold = cov._read(d, "spec.md"), cov._read(d, "gold.diff")
    test = cov._read(d, "hidden_test.diff", 12000)
    gaptxt = "\n".join(f"- {g['test']}  [gold: {g.get('gold_anchor')}]" for g in gaps)
    prompt = (PROMPT.replace("{spec}", spec[:9000]).replace("{gold}", gold[:14000])
              .replace("{test}", test).replace("{gaps}", gaptxt[:3000]))
    raw = run_agent(agent_cmd, prompt)
    (pathlib.Path(out_dir) / "judge" / f"{short}.witness.last.txt").write_text(raw)
    cand = extract_json(raw)
    if not cand:
        return {"case": short, "skip": "agent parse fail"}
    return {"case": short, "dir": str(d), "cand": cand, "spec": spec, "gold": gold, "test": test}


def verify(res, do_clone, cache):
    if "cand" not in res:
        return res
    d = pathlib.Path(res["dir"])
    c = res["cand"]
    spec, gold, test = res["spec"], res["gold"], res["test"]
    gt = set(w for w in cov.aggr(gold).split() if len(w) > 3)
    tt = set(w for w in cov.aggr(test).split() if len(w) > 3)
    res["gold_ok"] = bool(c.get("gold_anchor")) and cov.cited(c["gold_anchor"], cov.aggr(gold), gt)
    res["test_ok"] = bool(c.get("test_assertion")) and cov.cited(c["test_assertion"], cov.aggr(test), tt)
    verdict = "hypothesis"
    if c.get("klass") == "airtight":
        const = (c.get("constant") or "").strip()
        in_prose = bool(const) and const.lower() in spec.lower()
        res["const_in_prose"] = in_prose
        res["const_in_codebase"] = None
        if const and not in_prose and res["gold_ok"] and res["test_ok"] and do_clone:
            meta = json.loads((d / "meta.json").read_text())
            tree = clone_at(meta["repo"], meta["base_commit"], cache) if meta.get("base_commit") else None
            if tree is not None:
                inc = in_codebase(tree, const)
                res["const_in_codebase"] = inc
                if inc is False:
                    verdict = "airtight"
    elif c.get("klass") == "prose-affirmative":
        clause = c.get("r2_prose_clause")
        st = set(w for w in cov.aggr(spec).split() if len(w) > 3)
        if clause and cov.cited(clause, cov.aggr(spec), st) and res["gold_ok"] and res["test_ok"]:
            verdict = "prose-affirmative"  # still a hypothesis at render time (see render)
    res["verdict"] = verdict
    return res


def render(res):
    d = pathlib.Path(res["dir"])
    short = d.name
    c, v = res["cand"], res["verdict"]
    proven = v == "airtight"   # only airtight (codebase-grep-certified) is auto-PROVEN
    title = "Ambiguity witness" if proven else "Ambiguity HYPOTHESIS (not claimed)"
    L = [f"# {title} -- {short}", "",
         f"- class: **{v}** ({'PROVEN -- mechanical spine' if proven else 'disciplined hypothesis'})",
         "", "## The graded behavior", c.get("test_behavior", ""),
         f"- test assertion: `{c.get('test_assertion')}`",
         "", "## Two readings; the test pins one",
         f"- **R1 (test-pinned / gold):** {c.get('R1','')}  gold: `{c.get('gold_anchor')}`",
         f"- **R2 (prose-faithful alternative):** {c.get('R2','')}", ""]
    if proven:
        L += ["## Why airtight",
              f"The discriminating constant `{c.get('constant')}` appears nowhere a solver reads: "
              f"absent from the prose and from the codebase at base_commit (ripgrep), present only in "
              f"gold+test. A reviewer re-runs the grep and concedes.", ""]
    else:
        L += [f"## Status: HYPOTHESIS ({v})",
              "Not mechanically certified as underdetermination; flagged for independent raters. "
              "**Not counted in the claimable spine.**", ""]
    L += [f"## Why R2 fails the test", c.get("why_R2_fails", ""), "",
          "_agent proposed; anchors mechanically verified against the committed gold/test/prose._"]
    name = "AMBIGUITY_WITNESS.md" if proven else "AMBIGUITY_HYPOTHESIS.md"
    (d / name).write_text("\n".join(L) + "\n")
    return v


def run(cases_dir, agent_cmd, out_dir, cache, do_clone=True, workers=8, slugs=None):
    cases_dir = pathlib.Path(cases_dir)
    if slugs is None:
        slugs = []
        for jf in sorted((pathlib.Path(out_dir) / "judge").glob("*.json")):
            try:
                if json.loads(jf.read_text()).get("verdict") == "AMBIGUOUS":
                    slugs.append(jf.stem)
            except Exception:
                pass
    dirs = [str(cases_dir / s) for s in slugs]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:   # draft in parallel
        drafts = list(ex.map(lambda d: draft(d, agent_cmd, out_dir), dirs))
    counts = {"airtight": 0, "prose-affirmative": 0, "hypothesis": 0, "skip": 0}
    for res in drafts:                                       # verify+clone SERIALLY (checkout races)
        if "cand" not in res:
            counts["skip"] += 1
            continue
        verify(res, do_clone, cache)
        counts[render(res)] = counts.get(render(res), 0) + 1
    return counts

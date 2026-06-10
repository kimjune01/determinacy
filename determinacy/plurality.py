"""Tier 2b -- codebase-plurality (multiplicity evidence). For a GAP case the agent didn't certify
airtight, the agent proposes the discriminating choice + >=2 live, comparable, conflicting precedents
in the repo at base_commit. Python verifies each snippet exists in a non-test/vendor/dead path (grep).
>=2 verified, distinct files, distinct "ways" -> a *candidate* codebase-plural witness.

This is multiplicity evidence: the codebase itself makes the choice >=2 ways while the prose is silent,
so a from-codebase solver could land on either. The pointers (path + verbatim snippet) are mechanical;
whether they GENUINELY conflict is then certified by `refute.py` (the comparability pass). A raw candidate
is NOT claimable until it survives that pass.

(Generalized from swebench-pro-audit/tools/codebase_ambiguity.py; reads repo/base_commit from meta.json.)
"""
import json, re, shutil, subprocess, pathlib, concurrent.futures as cf
from .agent import run_agent, extract_json
from . import coverage as cov, witness as wit

EXCLUDE = re.compile(r"(^|/)(tests?|testing|__tests__|spec|specs|examples?|example|vendor|"
                     r"node_modules|third_party|deprecated|legacy|\.git|fixtures?|mocks?|testdata)(/|$)", re.I)

PROMPT = """You are auditing whether a benchmark task pins a choice the CODEBASE leaves open. A screen
found a GAP: the hidden test checks a behavior the gold implements but no prose requirement states.

Decide if the codebase ALREADY does this discriminating thing in MORE THAN ONE WAY. If a solver reading
the codebase would find two (or more) established, CURRENT, comparable precedents that make this choice
differently, the choice is underdetermined and the test arbitrarily pins one.

Find >=2 such precedents in the repo (working tree at this commit). For each give the file path and a
SHORT verbatim code snippet (copy exactly) showing the choice made that way. STRICT:
- precedents must be LIVE production code -- NOT under any test/spec/example/vendor/deprecated/fixture path.
- they must be COMPARABLE -- the same kind of decision in a similar context.
- if the codebase is actually CONSISTENT (one way, or differences not comparable), return
  "consistent": true and an empty precedents list. Do not manufacture a conflict.

Output ONLY: {"discriminating_choice":"...", "consistent": true|false,
 "precedents":[{"path":"...","snippet":"...","way":"which convention this shows"}, ...]}

=== PROSE ===
{spec}
=== GOLD PATCH ===
{gold}
=== HIDDEN TEST ===
{test}
=== GAP behavior (screen) ===
{gap}
=== REPO FILE LIST (sample) ===
{files}
"""


def grep_path(tree, snippet):
    """A non-excluded repo-relative path containing the snippet, else None. `-e` so a leading-dash
    snippet is a pattern, not a flag."""
    rg = shutil.which("rg")
    snip = snippet.strip().splitlines()[0].strip() if snippet.strip() else ""
    if len(snip) < 6:
        return None
    if rg:
        r = subprocess.run([rg, "-l", "--fixed-strings", "-e", snip, str(tree)], capture_output=True, text=True)
    else:
        r = subprocess.run(["grep", "-rIl", "-e", snip, str(tree)], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        rel = str(pathlib.Path(line).relative_to(tree)) if str(tree) in line else line
        if not EXCLUDE.search(rel):
            return rel
    return None


def _first_gap(out_dir, sid):
    jf = pathlib.Path(out_dir) / "judge" / f"{sid}.json"
    if not jf.exists():
        return ""
    for r in json.loads(jf.read_text()).get("rows", []):
        if r.get("status") == "GAP":
            return f"{r['test']}  [gold: {r.get('gold_anchor')}]"
    return ""


def run_case(case_dir, agent_cmd, out_dir, cache):
    d = pathlib.Path(case_dir)
    meta = json.loads((d / "meta.json").read_text())
    if not meta.get("base_commit"):
        return f"{d.name}: no base_commit"
    tree = wit.clone_at(meta["repo"], meta["base_commit"], cache)
    if tree is None:
        return f"{d.name}: clone failed"
    files = subprocess.run(["bash", "-lc", f"cd {tree} && git ls-files | grep -viE "
                            f"'(test|spec|example|vendor|node_modules|fixture|mock|testdata)' | head -400"],
                           capture_output=True, text=True).stdout
    spec, gold = cov._read(d, "spec.md"), cov._read(d, "gold.diff")
    test = cov._read(d, "hidden_test.diff", 8000)
    prompt = (PROMPT.replace("{spec}", spec[:7000]).replace("{gold}", gold[:9000])
              .replace("{test}", test).replace("{gap}", _first_gap(out_dir, d.name)[:400])
              .replace("{files}", files[:6000]))
    cand = extract_json(run_agent(agent_cmd, prompt))
    if not cand or cand.get("consistent") or not cand.get("precedents"):
        return f"{d.name}: consistent / no conflict"
    verified = []
    for p in cand["precedents"]:
        rel = grep_path(tree, p.get("snippet", ""))
        if rel:
            verified.append({**p, "verified_path": rel})
    ways = {v.get("way", "") for v in verified}
    files_ = {v["verified_path"] for v in verified}
    ok = len(verified) >= 2 and len(files_) >= 2 and len(ways) >= 2
    res = {"slug": d.name, "choice": cand.get("discriminating_choice"),
           "n_verified": len(verified), "verified": verified, "ok": ok}
    (d / "codebase_ambiguity.json").write_text(json.dumps(res, indent=1))
    if ok:
        _render(d, res, meta)
        if (d / "AMBIGUITY_HYPOTHESIS.md").exists():
            (d / "AMBIGUITY_HYPOTHESIS.md").unlink()
        return f"{d.name}: CANDIDATE codebase-plural ({len(verified)} precedents)"
    return f"{d.name}: only {len(verified)} verified -> stays hypothesis"


def _render(d, res, meta):
    L = [f"# Ambiguity witness -- {d.name}  (codebase-plurality)", "",
         f"- class: **codebase-plural** (candidate -- pending comparability refutation)",
         f"- repo `{meta['repo']}` @ `{meta['base_commit'][:10]}`", "",
         "## The underdetermined choice", res.get("choice", ""), "",
         "## The codebase makes the choice >=2 conflicting live ways (prose silent)",
         "Point at the precedents; the plurality is the evidence:"]
    for i, v in enumerate(res["verified"], 1):
        L += [f"{i}. `{v['verified_path']}` -- {v.get('way','')}",
              f"   ```\n   {(v.get('snippet') or '').strip()[:300]}\n   ```"]
    L += ["", "_agent proposed; each precedent grep-verified verbatim at base_commit in a live "
          "(non-test/vendor/dead) path. Genuine-conflict certification: see comparability pass._"]
    (d / "AMBIGUITY_WITNESS.md").write_text("\n".join(L) + "\n")


def run(cases_dir, agent_cmd, out_dir, cache, workers=6, slugs=None):
    cases_dir = pathlib.Path(cases_dir)
    if slugs is None:
        # codebase-convention candidates = AMBIGUOUS cases without an airtight witness
        slugs = [d.name for d in cases_dir.iterdir() if d.is_dir()
                 and (d / "AMBIGUITY_HYPOTHESIS.md").exists()
                 and not (d / "codebase_ambiguity.json").exists()]
    # group by repo; cases within a repo run serially (shared clone dir, re-checkout hazard)
    groups = {}
    for s in slugs:
        repo = json.loads((cases_dir / s / "meta.json").read_text()).get("repo", "?")
        groups.setdefault(repo, []).append(s)
    n_cand = 0

    def worker(items):
        c = 0
        for s in items:
            msg = run_case(cases_dir / s, agent_cmd, out_dir, cache)
            if "CANDIDATE" in msg:
                c += 1
        return c
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        n_cand = sum(ex.map(worker, groups.values()))
    return n_cand

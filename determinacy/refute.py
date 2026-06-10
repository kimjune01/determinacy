"""Tier 2c -- comparability refutation (the quality gate for plurality). A raw codebase-plural
candidate cites >=2 grep-verified precedents, but the *claim that they genuinely conflict* is
contestable: superficially-similar precedents (different decisions that look alike) are cherry-picks,
not underdetermination. An independent pass asks exactly that narrow existence question.

  comparable=true  -> the precedents are the same semantic decision made plural ways -> codebase-plural
                      WITNESS stands (claimable).
  comparable=false -> different decisions/contexts -> dropped to hypothesis (codebase-plural-contested).

This measurably improves quality: on the reference audit it cut raw plurality roughly in half.
(Generalized from swebench-pro-audit/tools/comparability_check.py.)
"""
import json, re, pathlib, concurrent.futures as cf
from .agent import run_agent, extract_json

PROMPT = """You verify whether cited code precedents constitute GENUINE comparable plurality: the SAME
semantic decision made more than one way in comparable live contexts, versus different decisions that
merely look similar. This is an existence check, not a judgment about which is better.

The discriminating choice: {choice}

Cited precedents (each is real, live, non-test code at the same commit):
{precedents}

Are these the SAME semantic decision (the same kind of validation / status-selection / default), made
differently in comparable contexts -- so a developer choosing how to do THIS decision faces a genuinely
plural codebase? Or are they DIFFERENT decisions / situations that only resemble each other (e.g. "404
for a missing file" vs "403 for a traversal attempt" are different situations, not plural conventions
for one choice)?

Output ONLY: {"comparable": true|false, "why": "one sentence"}"""


def _is_plural_candidate(d):
    w = d / "AMBIGUITY_WITNESS.md"
    return w.exists() and "class: **codebase-plural**" in w.read_text()


def check(case_dir, agent_cmd):
    d = pathlib.Path(case_dir)
    ca = d / "codebase_ambiguity.json"
    if not ca.exists():
        return d.name, None
    obj = json.loads(ca.read_text())
    prec = obj.get("verified", [])
    pretext = "\n".join(f"- {p.get('verified_path')}: {p.get('way','')}\n    {(p.get('snippet') or '')[:160]}"
                        for p in prec)
    j = extract_json(run_agent(agent_cmd, PROMPT.replace("{choice}", str(obj.get("choice", "")))
                               .replace("{precedents}", pretext[:4000])))
    if not j:
        return d.name, None
    comp = bool(j.get("comparable"))
    obj["comparability_verified"] = comp
    obj["comparability_why"] = j.get("why")
    ca.write_text(json.dumps(obj, indent=1))
    wf, hf = d / "AMBIGUITY_WITNESS.md", d / "AMBIGUITY_HYPOTHESIS.md"
    if comp:
        body = wf.read_text() if wf.exists() else ""
        body = body.replace("(candidate -- pending comparability refutation)",
                            "(PROVEN -- comparability verified)")
        wf.write_text(body.rstrip() + "\n\n## Comparability verified\n"
                      f"Same semantic decision in comparable live context (existence proof of genuine "
                      f"plurality): {j.get('why')}\n")
        return d.name, True
    note = (f"# Ambiguity HYPOTHESIS (codebase-plural, NOT comparable -- dropped) -- {d.name}\n\n"
            "- class: **codebase-plural-contested** (NOT claimed)\n"
            f"- The cited precedents are not genuine comparable plurality: {j.get('why')}. A plurality "
            "existence proof requires the SAME decision; this is a cherry-pick, not underdetermination.\n")
    hf.write_text(note)
    if wf.exists():
        wf.unlink()
    return d.name, False


def run(cases_dir, agent_cmd, workers=6):
    cases_dir = pathlib.Path(cases_dir)
    slugs = [d for d in cases_dir.iterdir() if d.is_dir() and _is_plural_candidate(d)]
    survived = dropped = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for name, verdict in ex.map(lambda d: check(d, agent_cmd), slugs):
            if verdict is True:
                survived += 1
            elif verdict is False:
                dropped += 1
    return {"survived": survived, "dropped": dropped}

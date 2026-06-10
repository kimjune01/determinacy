"""One receipt-grade artifact PER PROBLEM. Every case -- entailed, hypothesis, or airtight --
gets a self-contained cases/<id>/RECEIPT.md: the verdict, the tier evidence, links to the raw
materials, and (for airtight) a copy-paste command a skeptic runs to re-verify the grep himself.
"""
import json, re, pathlib


def _coverage(out_dir, sid):
    jf = pathlib.Path(out_dir) / "judge" / f"{sid}.json"
    if not jf.exists():
        return None
    try:
        return json.loads(jf.read_text())
    except Exception:
        return None


def write_receipt(case_dir, out_dir):
    d = pathlib.Path(case_dir)
    sid = d.name
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    repo, base = meta.get("repo"), meta.get("base_commit")
    cov = _coverage(out_dir, sid)

    airtight = const = None
    klass = "entailed"
    if (d / "AMBIGUITY_WITNESS.md").exists() and "class: **airtight**" in (d / "AMBIGUITY_WITNESS.md").read_text():
        airtight = True
        m = re.search(r"constant `([^`]+)`", (d / "AMBIGUITY_WITNESS.md").read_text())
        const = m.group(1) if m else None
        klass = "airtight"
    elif (d / "AMBIGUITY_HYPOTHESIS.md").exists():
        t = (d / "AMBIGUITY_HYPOTHESIS.md").read_text()
        m = re.search(r"class: \*\*([\w-]+)\*\*", t)
        klass = f"hypothesis ({m.group(1)})" if m else "hypothesis"
    elif cov and cov.get("verdict") == "AMBIGUOUS":
        klass = "ambiguous (unwitnessed)"

    verdict = {"airtight": "AIRTIGHT (claimable -- mechanical spine)"}.get(
        klass, "ENTAILED (every graded behavior has a covering clause)"
        if klass == "entailed" else f"NOT CLAIMED ({klass})")

    L = [f"# Receipt -- {sid}", "",
         f"- repo: `{repo}` @ `{(base or '')[:12]}`",
         f"- **verdict: {verdict}**", ""]
    if cov:
        L += [f"## Tier 1 -- coverage (grep-verified)",
              f"{cov['n_covered']}/{cov['in_gold_total']} graded behaviors covered by a prose clause; "
              f"**{cov['n_gap']} GAP** (test grades it, gold implements it, prose silent). "
              f"Full table: [`attribution/{sid}.md`](../../attribution/{sid}.md).", ""]
    if airtight and const:
        L += ["## Tier 2 -- airtight (mechanical)",
              f"The hidden test grades the discriminating constant `{const}`, which is **absent from the "
              f"prose and from the codebase** at `{(base or '')[:12]}`, present only in gold+test. "
              "Re-verify it yourself:", "",
              "```bash",
              f"git clone https://github.com/{repo}.git /tmp/{sid} && cd /tmp/{sid} && git checkout {base}",
              f"rg --fixed-strings -g '!*test*' -e {_shq(const)}   # expect: no matches (absent)",
              "```",
              "[witness](AMBIGUITY_WITNESS.md)", ""]
    elif "hypothesis" in klass:
        L += ["## Tier 2 -- not certified",
              f"Flagged `{klass}` by the screen but not mechanically certifiable as underdetermination "
              "(convention may bind, or the alternative is the agent's judgment). Counted in no claimable "
              "rate. [hypothesis](AMBIGUITY_HYPOTHESIS.md)", ""]
    L += ["## Materials", f"[spec.md](spec.md) · [gold.diff](gold.diff) · [hidden_test.diff](hidden_test.diff)"]
    (d / "RECEIPT.md").write_text("\n".join(L) + "\n")
    return klass


def _shq(s):
    return "'" + (s or "").replace("'", "'\\''") + "'"


def write_all(cases_dir, out_dir):
    cases_dir = pathlib.Path(cases_dir)
    n = 0
    for d in cases_dir.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            write_receipt(d, out_dir)
            n += 1
    return n

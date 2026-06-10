"""Write canonical Tasks into the case-dir interchange the instruments read:
cases/<instance_id>/{spec.md, gold.diff, test.diff, hidden_test.diff, fail_to_pass.txt, meta.json}.
meta.json carries repo + base_commit so the airtight tier can clone without re-reading the dataset.
"""
import json, pathlib


def _stats(diff):
    diff = diff or ""
    files = len([l for l in diff.splitlines() if l.startswith("+++ b/")])
    loc = len([l for l in diff.splitlines()
               if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))])
    return {"files": files, "loc": loc, "words": len(diff.split())}


def materialize(tasks, cases_dir):
    cases_dir = pathlib.Path(cases_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        sid = t["instance_id"]
        d = cases_dir / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.md").write_text(t.get("problem_statement") or "")
        (d / "gold.diff").write_text(t.get("gold_patch") or "")
        test = t.get("test_patch") or ""
        (d / "test.diff").write_text(test)
        (d / "hidden_test.diff").write_text(test)          # instruments expect this name
        (d / "fail_to_pass.txt").write_text("\n".join(t.get("fail_to_pass") or []))
        (d / "instance_id.txt").write_text(sid)
        (d / "meta.json").write_text(json.dumps({
            "instance_id": sid,
            "repo": t.get("repo"),
            "base_commit": t.get("base_commit"),
            "f2p_count": len(t.get("fail_to_pass") or []),
            "gold_stats": _stats(t.get("gold_patch")),
        }, indent=1))
    return sorted(p.name for p in cases_dir.iterdir() if p.is_dir())

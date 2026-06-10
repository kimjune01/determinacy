"""Normalize any SWE-bench-shaped dataset into canonical Task dicts via the field-map."""
import json, pathlib


def _get(row, dotted):
    cur = row
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _rows(cfg):
    src = cfg["source"]
    if src.get("local"):
        for line in pathlib.Path(src["local"]).read_text().splitlines():
            if line.strip():
                yield json.loads(line)
    else:
        from datasets import load_dataset
        ds = load_dataset(src["hf_dataset"], split=src.get("split", "test"))
        yield from ds


def load_tasks(cfg, limit=None):
    fm = cfg["fields"]
    out = []
    for row in _rows(cfg):
        t = {k: _get(row, fm[k]) for k in fm}
        if not t.get("instance_id"):
            continue
        t["fail_to_pass"] = t.get("fail_to_pass") or []
        if isinstance(t["fail_to_pass"], str):
            t["fail_to_pass"] = [t["fail_to_pass"]]
        out.append(t)
        if limit and len(out) >= limit:
            break
    return out

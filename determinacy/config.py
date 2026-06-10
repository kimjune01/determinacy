"""Load a benchmark field-map config (TOML). A bench is fully described by:
an `agent` CLI command, a `[source]` (HF dataset+split or a local jsonl), and a
`[fields]` map from canonical names to the bench's column names (dotted paths ok).
"""
import pathlib
try:
    import tomllib
except ModuleNotFoundError:  # py<3.11
    import tomli as tomllib

CANONICAL = ["instance_id", "problem_statement", "gold_patch", "test_patch",
             "fail_to_pass", "repo", "base_commit"]


def load_config(path):
    cfg = tomllib.loads(pathlib.Path(path).read_text())
    cfg.setdefault("agent", "codex exec -")
    src = cfg.get("source", {})
    if "hf_dataset" not in src and "local" not in src:
        raise ValueError("config [source] needs hf_dataset (+ split) or local (jsonl path)")
    fields = cfg.get("fields", {})
    missing = [f for f in CANONICAL if f not in fields]
    if missing:
        raise ValueError(f"config [fields] missing: {missing}")
    cfg["name"] = cfg.get("name") or pathlib.Path(path).stem
    return cfg

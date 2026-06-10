# determinacy

**A determinacy auditor for SWE-bench-shaped coding benchmarks.** Point it at any benchmark whose tasks look like `{problem_statement, gold patch, test_patch, FAIL_TO_PASS, repo, base_commit}` and it tells you what fraction of the graded behaviors the task *spec actually determines* — with grep-certified receipts for the cases where the hidden test grades something the prose never stated.

A binary pass/fail benchmark credits (or faults) an agent for reproducing one maintainer's unstated choice. When the issue text underdetermines the fix, the hidden test pins one of several faithful readings, and the score becomes a **specification lottery**. You cannot separate *capability shortfall* from *spec shortfall* without auditing determinacy. This tool does that audit, and — crucially — it distinguishes the part you can prove from the part that is just a model's opinion.

> **Anybody can run a vibe check.** Two API calls and an LLM will hand you a scary "30% of tasks are ambiguous" number. That number is worthless — LLM raters over-flag, counting ordinary engineering latitude as ambiguity. The point of this tool is the **mechanical spine**: receipts a skeptic re-runs without trusting any rater.

## What you bring

A **SOTA coding agent on the CLI** (e.g. `codex exec -`, `claude -p`). The tool shells out to it for the judgment-shaped steps and (optionally) to generate alternate patches. Set it once in your config:

```toml
agent = "codex exec --model gpt-5.5 -"
```

It also needs `git` and `ripgrep` (`rg`) for the mechanical tiers.

## The tiers (report all; never flatten)

| tier | what it asks | evidence | trust |
|---|---|---|---|
| **0 · screen** | does the *prose alone* leave ≥2 incompatible faithful designs? | two blind agent raters, AND-gated | **vibe** — candidate finder only |
| **1 · coverage** | is each graded behavior covered by a verbatim prose clause? | per-behavior table, citations **grep-verified** | upper bound (over-flags) |
| **2 · airtight** | is the discriminating constant absent from prose **and** codebase? | clone `repo@base_commit` + `rg`; constant lives only in gold+test | **mechanical spine — claimable, re-runnable** |
| **3 · graded-patch** | does a prose-faithful *alternate* patch fail the official grader? | your agent writes Design B; run the bench's own harness | **strongest** (needs the harness) |

Tier 2 is the headline: zero model judgment in the verdict. A reviewer clones the repo, greps the constant, finds it absent, and concedes — the benchmark grades a value the issue never specified and the codebase never established.

## Quickstart

```bash
uv run determinacy run examples/swebench-rebench.toml             # tiers 1-2 (the grep-backed tiers)
uv run determinacy run examples/swebench-rebench.toml --limit 5   # smoke test on 5 tasks
uv run determinacy run examples/swebench-rebench.toml --tier 1    # coverage only (no cloning)
```

The CLI runs the **grep-backed tiers (1 coverage, 2 airtight)** — the ones worth running. Tier 0 (the LLM-rater vibe) is the thing this tool exists to replace, so it doesn't bother; tier 3 (graded-patch) needs the benchmark's own execution harness and is left to it (your agent writes Design B, the bench's grader judges it).

**The output is a receipt-grade artifact for every problem in the set** — not just the flagged ones. Outputs to `runs/<bench>/`:
- **`cases/<id>/RECEIPT.md`** — one self-contained receipt per problem: the verdict (entailed / airtight / hypothesis), the tier evidence, links to the materials, and — for airtight cases — a **copy-paste `git clone` + `rg` command a skeptic runs to re-verify the absence himself**.
- `attribution/<id>.md` — per-case coverage table (every graded behavior → clause or GAP, citations grep-verified)
- `cases/<id>/{spec.md, gold.diff, hidden_test.diff, meta.json}` — the raw materials each receipt points at
- `cases/<id>/AMBIGUITY_WITNESS.md` — the airtight argument, for certified cases
- `CLAIMS.md` — one row per certified witness (the mechanical spine), Pro-style
- `REPORT.md` — tiered rates with Wilson CIs

## Configuring a new benchmark

A benchmark is a TOML field-map. See `examples/` for SWE-rebench, SWE-bench Pro, SWE-bench Verified:

```toml
agent = "codex exec --model gpt-5.5 -"

[source]
hf_dataset = "nebius/SWE-rebench-leaderboard"   # or local = "tasks.jsonl"
split = "2026_03"

[fields]
instance_id       = "instance_id"
problem_statement = "problem_statement"
gold_patch        = "patch"
test_patch        = "test_patch"
fail_to_pass      = "FAIL_TO_PASS"
repo              = "repo"
base_commit       = "base_commit"
```

Any field can be a dotted path (`meta.llm_score`) for nested columns.

## Worked reference

[`kimjune01/swebench-pro-audit`](https://github.com/kimjune01/swebench-pro-audit) is a full 728-task determinacy audit built with this method (the instruments here are generalized from it): the admissibility spec, the seven-label witness grid, the mechanical-spine-vs-hypothesis discipline, and ~700 per-case receipts. Read it for the methodology in depth; this tool packages the pipeline to point at any bench.

## The discipline (why the tiers matter)

The screens over-flag. A test that parametrizes one behavior 11 ways generates 11 "GAP" rows that are really one determined decision; a general prose principle covers specifics a per-row grep won't match. So tiers 0–1 are **upper bounds**, disclosed as such, never the claim. Only tier 2 (and 3) survive a hostile reader. The output reports every tier with its trust level — the value is knowing *which fraction is provable*, which is exactly the thing nobody bothers to separate.

Positive-evidence-only: a behavior is called airtight on a *present* constant absent from the sources, never on failure-to-find. Where neither airtight nor a graded-patch is available, the case stays a labeled hypothesis — counted in no claimable rate.

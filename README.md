# determinacy

**A determinacy auditor for SWE-bench-shaped coding benchmarks.** Point it at any benchmark whose tasks look like `{problem_statement, gold patch, test_patch, FAIL_TO_PASS, repo, base_commit}` and it tells you what fraction of the graded behaviors the task *spec actually determines*, with grep-certified receipts for the cases where the hidden test grades something the issue never stated.

Concretely: it extracts the behaviors the hidden test grades, checks each against the issue text, and certifies the underspecified ones with receipts a skeptic re-runs. Today `determinacy run` automates coverage, airtight certification, codebase-plurality, and the refutation that hardens it; the graded-patch and answer-key tiers need the benchmark's own execution harness and are left to it.

> **Anybody can run a vibe check.** Two API calls and an LLM hand you a scary "30% of tasks are ambiguous." That number is worthless: LLM raters over-flag, counting ordinary engineering latitude as ambiguity. The point of this tool is the **mechanical spine**, a smaller provable floor that a skeptic re-runs without trusting any rater.

## Motivation

A binary benchmark scores an agent for reproducing one maintainer's choices. When the issue underdetermines the fix (and a GitHub issue, being a discussion rather than a spec, very often does), the hidden test arbitrarily pins one of several faithful readings, and a correct fix scores zero. This **specification lottery** silently conflates *capability shortfall* (the agent couldn't solve a determinate task) with *spec shortfall* (the task didn't determine its answer), which no leaderboard separates. The catch is that the audit is itself easy to fake: ask an LLM "is this ambiguous?" and you get a big, useless number. So the real problem is separating what you can **prove** from what is just a model's opinion. See [`discussion.md`](discussion.md) for the full argument and the determinacy-weighted scoring it implies.

## Quickstart

```bash
uv run determinacy run examples/swebench-rebench.toml             # tiers 1-2 (the grep-backed tiers)
uv run determinacy run examples/swebench-rebench.toml --limit 5   # smoke test on 5 tasks
uv run determinacy run examples/swebench-rebench.toml --tier 1    # coverage only (no cloning)
```

You bring a SOTA coding agent on the CLI (`codex exec -`, `claude -p`, …), plus `git` and `ripgrep`. The agent is consulted only to *propose*; the verdicts are settled by a grep, a grader, or a pointer you check yourself.

## Example: one airtight claim

`tobymao__sqlglot-7479`. The issue asks the parser to handle `AI.EMBED(...)`. The hidden test asserts:

```python
assert isinstance(ast.expressions[0].expression, exp.AIEmbed)
```

So the benchmark grades a specific AST class name, `AIEmbed`. The issue never names it, and neither does the codebase. Verify the absence yourself:

```bash
git clone https://github.com/tobymao/sqlglot && cd sqlglot && git checkout 38357253
rg --fixed-strings -g '!*test*' -e AIEmbed   # no matches: nowhere a solver could read it
```

`AIEmbed` lives only in the gold patch and the test. A faithful parser that named the node `AIEmbedding` or `BigQueryEmbed` is scored wrong. That is the whole claim, and it took one grep. The tool writes exactly this as `cases/tobymao__sqlglot-7479/RECEIPT.md`.

## Output: a receipt per problem

The output is a **receipt-grade artifact for every problem in the set**, not just the flagged ones. Under `runs/<bench>/`:

- **`cases/<id>/RECEIPT.md`**: the verdict and its **pointer-checkable receipt**. For airtight, a copy-paste `git clone` + `rg` that returns no matches; for codebase-plural, the **≥2 `path:line` precedents** that conflict. Settling the case is reading two lines, not re-reading the repo.
- `attribution/<id>.md`: the coverage table (every graded behavior → clause or GAP, grep-verified).
- `cases/<id>/AMBIGUITY_WITNESS.md`: the airtight or plurality argument, for certified cases.
- `CLAIMS.md`: one row per certified witness (the mechanical spine).
- `REPORT.md`: tiered rates with Wilson CIs.

## Configuring a new benchmark

A benchmark is a TOML field-map. See `examples/` for SWE-rebench, SWE-bench Verified, SWE-bench Pro:

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

## Classifications

Two levels. Per **behavior** (the coverage screen labels every graded behavior on the finite test grid); per **case** (the strongest witness over its GAPs sets the case verdict). The label sets the **witness burden**, exactly what a skeptic needs to accept it, and whether it is **claimable** or a **hypothesis**.

### Per behavior

| label | the graded behavior is… | how it's settled |
|---|---|---|
| `COVERED` | determined by a verbatim prose clause | the clause is cited and grep-verified in the spec |
| `GAP` | tested + implemented in gold + **no** covering prose | both anchors grep-verified; the prose silence is the signal |
| `OUT_OF_SCOPE` | not in the gold patch (pre-existing scaffolding) | the gold anchor doesn't verify; dropped |

### Per case

| verdict | meaning | witness burden | status |
|---|---|---|---|
| `ENTAILED` | every graded behavior has a covering clause | none (no GAP) | determinate, not a defect |
| **`AIRTIGHT`** | the test pins an **arbitrary constant** absent from prose **and** codebase, present only in gold+test | clone + `rg`: the constant is nowhere a solver reads | **claimable** (mechanical spine) |
| `PROSE-AFFIRMATIVE` | the prose explicitly describes a *different* faithful contract R2 than the test pins | the R2 clause verifies verbatim, but whether it *entails* R2 is the agent's read | hypothesis (raters-pending) |
| **`CODEBASE-PLURAL`** | the codebase makes the choice **≥2 conflicting live ways**, prose silent | **pointers to the ≥2 precedent lines** (`path:line` ×2, grep-verified, live paths), comparability refutation-confirmed | **claimable** (spine) |
| `BORDERLINE` | a single relevant convention, but no ≥2 conflicting precedents to point at | nothing short of a graded patch settles it | **hypothesis** |

**The claimable spine is positive, pointer-checkable evidence: `AIRTIGHT` (absence, one grep), `CODEBASE-PLURAL` (multiplicity, two line pointers), and graded-patch (the bench's own grader rejects a faithful R2).** Each settles the case with a pointer a skeptic checks in seconds: a grep result, two `path:line`s, or a grade, never by re-reading the codebase, never by a rating. That checkability cost *is* the line between a claim and a vibe: a vibe makes the reader re-read the whole repo to confirm it; a receipt points at the two lines that settle it. Everything that cannot produce such a pointer (`PROSE-AFFIRMATIVE`, `BORDERLINE`) stays a **disciplined hypothesis**: labeled, receipted, counted in **no** claimable rate. Three properties keep the spine honest.

- **Positive-evidence-only.** A case is airtight on a *present* constant shown absent from the sources, never on failure-to-find a convention. Where you can neither certify airtight nor exhibit a conflict, the verdict stays a hypothesis; we do not convert our own ignorance into a benchmark indictment.
- **Screens over-flag, and we say so.** A test that parametrizes one decision across 11 inputs yields 11 GAP rows that are really one determined behavior; a general prose principle covers specifics a per-row grep won't match. So the coverage rate is an **upper bound**, disclosed as such; the claimable spine is the floor. On SWE-rebench `2026_03` the gap was stark: the screen flags ~30% of behaviors prose-silent, but the spine that survives a hostile reader is **~14%** (6% airtight plus 8% refutation-survived plurality; raw plurality was 17%, the comparability pass halved it). The screen is the scare number; the spine is the claim.
- **A single pass is a floor, not a ceiling.** The agent proposes one witness per case, so any one run surfaces only *some* of the airtight cases; different runs find different ones (two passes over `2026_03` certified 7 and 9, overlapping but not identical). The grep verdict never varies, so re-running only **grows** the certified spine and can never admit a false one: the gate can be under-fed, never fooled. Report the rate as "**≥ N**, each independently verifiable," and union successive passes toward the true set. This is why the number is reproducible *as a lower bound* even though the agent is not deterministic.

## Method

Determinacy auditing is a funnel: **find candidates** (the coverage screen, grep-verified GAPs), **certify the spine** (airtight absence-evidence and codebase-plurality multiplicity-evidence, the latter refutation-hardened), then **report**. The agent only proposes; every claim rests on a check you re-run. Two further tiers (graded-patch, and the gold-passes-own-verifier answer-key axis) need the benchmark's execution harness and are left to it.

Full pipeline, all nine phases with the certification rules and the agent-proposes/verdict-is-checked contract: **[`method.md`](method.md)**.

## Worked reference

[`kimjune01/swebench-pro-audit`](https://github.com/kimjune01/swebench-pro-audit) is a full 728-task determinacy audit built with this method: the admissibility spec, the full witness grid, the mechanical-spine-vs-hypothesis discipline, the two-precedent codebase rule, and ~700 per-case receipts. Read it for the methodology in depth; this tool packages that pipeline to point at any bench.

# Method: the full pipeline

Determinacy auditing is not one screen. It is a funnel that drives candidates through progressively harder certifications, claiming only what survives. The full method was developed over the [reference audit](https://github.com/kimjune01/swebench-pro-audit) of 728 tasks. `[tool]` marks what `determinacy run` automates today; the rest is the reference pipeline, some of it requiring the benchmark's own execution harness.

**What you bring:** a SOTA coding agent on the CLI (`codex exec -`, `claude -p`, …), plus `git` and `ripgrep`. The tool shells out to your agent for the judgment-shaped steps (proposing candidates and refuting them). A model never *sets* a verdict; it only proposes what a grep, a grader, or a pointer you check yourself then settles.

## Find candidates

1. **Adapt + materialize** `[tool]`. A TOML field-map normalizes any HF dataset (or jsonl) into `cases/<id>/{spec.md, gold.diff, hidden_test.diff, meta.json}`. `meta.json` carries `repo` and `base_commit` so certification can clone without re-reading the dataset.
2. **Coverage pass** `[tool]`. Label **every** behavior the hidden test grades (the finite set behind `FAIL_TO_PASS`). For each, the agent cites the verbatim prose clause that determines it and the verbatim gold snippet that implements it; **both citations are checked against the actual text.** Verified-in-gold plus no-covering-clause is a **GAP**. (Complete labeling, not found examples.)
3. **Divergence axis.** A separate prose-only rater pass: would competent engineers converge on the test-passing design from the prose alone? This is the screen "rate." Reported, never claimed.

## Certify the spine (mechanical, claimable): positive evidence, never a rating

4. **Airtight** `[tool]`. *Absence* evidence: the discriminating constant is absent from the prose **and** from the codebase at `base_commit` (clone + `rg`), present only in gold+test. A solver has nowhere to read it. One grep, re-runnable.
5. **Codebase-plurality.** *Multiplicity* evidence: the codebase itself makes the choice ≥2 conflicting ways while the prose is silent, so a from-codebase solver could land on either. Each precedent is grep-verified in a live (non-test, non-vendor, non-dead) path. The pointers are mechanical, but the *claim that they genuinely conflict* (rather than being superficially similar) is a real risk, so raw promotion is only a **candidate**, certified only by surviving the adversarial refutation in step 7. After that, the surviving precedents are the evidence: you point at the two lines, the conflict has already withstood a hostile refuter, and there is nothing left to re-litigate.
6. **Graded-patch** *(needs the bench harness)*. Your agent writes the alternate faithful patch R2; a blind two-rater gate confirms R2 is prose-faithful; the benchmark's **own grader** runs R2 and rejects it. The strongest receipt: a faithful fix the bench scores wrong.

## Harden and cross-check

7. **Two-expert adversarial refutation.** One model constructs a split; an independent cross-family refuter tries to kill it; only survivors count, with inter-rater κ and an advocate recall pass for missed splits. This step measurably improves quality: it separates a genuine conflict from a superficial one, and on the reference audit it cut raw codebase-plurality roughly in half (the superficially-similar "conflicts" die here). A plurality candidate is not claimable until it survives this pass.
8. **Answer-key axis (gold-passes-own-verifier)** *(needs the harness)*. Run every gold through the official grader under an isolation protocol (parallel, then re-run each non-pass alone) so a flake is never logged as a defect. Gold that fails its own grader is `KNOWN_BAD`.
9. **Upstream receipts.** Backlink each case to its real PR; surface where a human *dictated* the graded choice in review (the construct-validity smoking gun).

## Report `[tool]`

A self-contained `RECEIPT.md` per problem, a `CLAIMS.md` of certified witnesses, a tiered `REPORT.md`; mechanical spine separated from disciplined hypotheses; negative controls.

The discipline through all of it is one rule: **the agent only ever *proposes*; every claimable verdict rests on a check a skeptic re-runs**: a grep, a grader, or a conflict whose precedents you read and whose comparability survived independent refutation. A screen is a candidate; a claim is a receipt.

See the [`Classifications`](README.md#classifications) table in the README for the per-behavior and per-case label taxonomy and the three honesty properties.

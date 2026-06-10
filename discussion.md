# Discussion: why audit determinacy, and what the number means

## The specification lottery

A binary pass/fail benchmark scores an agent's patch by running a hidden test. That credits — or faults — the agent for reproducing **one maintainer's choices**. When the issue text underdetermines the fix, several genuinely faithful implementations exist, and the hidden test arbitrarily pins one. An otherwise-correct fix scores zero because it made a different defensible choice than the gold author. We call that a **specification lottery**.

It is not a rare edge case. The prose a solver actually receives is, in most SWE benchmarks, a raw GitHub issue — a *discussion*, not a spec. Issues routinely pose open questions ("should this be an error instead?"), float multiple resolutions, and leave the discriminating constant — a class name, a key, an exact message, a sentinel value — entirely to the author. The maintainer privately knows which one they merged; the solver, given only the issue, cannot derive it. That private knowledge is the construct-validity failure, not a rescue.

## The confound the leaderboard hides

The headline number conflates two things a benchmark consumer must keep apart:

- **capability shortfall** — the agent couldn't solve a *determinate* task. This shrinks as models improve.
- **spec shortfall** — the task didn't determine its own answer. No model fixes this; the information isn't in the prose to derive.

A single resolve rate cannot tell you which wall a given failure hit. So every reported score silently **credits the harness with whatever determinacy the prose happened to supply, and faults it for whatever the prose withheld.** Two harnesses with identical capability can rank differently purely on how lucky their tasks' prose was. A determinacy audit measures the spec term independently, so the shortfall becomes attributable.

## What to do about it (the constructive half)

Auditing is diagnosis; the prescription is a scoring change. Instead of a boolean, score each instance as the fraction of the new behaviors it achieves net of regressions:

> `score = clamp01( (FAIL_TO_PASS passed − PASS_TO_PASS regressed) / FAIL_TO_PASS introduced )`

computable today from any harness's per-test output. Read `1 − score` as residual work a maintainer must still do — the production value the agent provided. Paired with a determinacy label, the residual splits the way that matters: on a **determinate** task it is *capability residual*, which a better model erases; on a **divergent** task it is *specification residual*, which no model erases, because the choice has to come from a human.

Put together, the float reads as one quantity — **the automation a task admits**, which factors as *the determinacy the prose affords × the capability of the model and harness.* A fully determinate task has an automation ceiling of one, so its score is pure capability. A divergent task tops out below one even for a perfect harness, and the remainder is not failure but **elicitation**: the correct behavior of an agent against underspecified prose is to implement everything the spec determines and leave the unstated choice for review. You cannot factor that product from the score alone — which is exactly why the determinacy label has to be measured separately, and why this tool exists.

So the recommendation that falls out of any audit with a non-trivial divergent fraction is the same one regardless of the bench: **score determinacy-weighted, and publish the divergent set** so consumers can score on the determinate subset, or at least know which residual is spec-missing rather than capability-missing.

## Why the measurement is the hard part

The trap is that the audit *itself* is trivial to fake. Ask an LLM "is this task ambiguous?" and you get a large, alarming, useless number — it flags every micro-choice ordinary convention resolves. LLM raters over-flag by a wide margin, and a test that parametrizes one decision across many inputs inflates the count further. A scary "30% ambiguous" headline from a rater is worth nothing, and it discredits the real finding underneath it.

So the entire design problem is **separating what you can prove from what is just a model's opinion**, and reporting them as different things. This tool's answer is to use the model only to *propose*, and to establish every claimable verdict *mechanically*: a coverage GAP is a citation grep-verified against the actual text; an airtight verdict is the discriminating constant shown — by a clone and a ripgrep a reviewer re-runs — to be absent from everywhere a solver reads. The screens (the LLM-shaped tiers) are reported as upper bounds; the grep-certified spine is the claim. The value of the tool is not the big number — anyone's LLM produces that. It is knowing *which fraction is provable*.

## Scope and honesty

- **Positive-evidence-only.** A case is called underdetermined on a *present* constant shown absent from the sources, never on failure-to-find a convention. Where neither airtight nor a graded patch is available, the verdict stays a labeled hypothesis — counted in no claimable rate. We do not convert our own ignorance into a benchmark indictment.
- **This is an evaluation-design claim, not a maintainer-intent claim.** The audit shows the *presented prose* underdetermines the graded answer under blind evaluation — which is exactly the agent-facing condition. It does not claim maintainers lacked intent, nor that every faithful alternative deserves equal credit. The recommendation (weight by determinacy, publish the divergent set) follows from the former alone.
- **The screens over-flag, by design.** Coverage prose-silence is an upper bound; only the airtight floor (and a graded-patch, where the harness allows it) survives a hostile reader. On SWE-rebench `2026_03`, the two diverged sharply: ~30% of graded behaviors prose-silent, ~6% airtight-certifiable. The gap between those two numbers is the whole point of measuring carefully.

# timsim Sample Designer — onboarding & visualization design

> **Revision 2** — incorporates a Codex review (`SAMPLE_DESIGNER_UX.codex-review.md`). The review's
> load-bearing correction: don't teach a tidy, instrument-like causal story before timsim models
> those causes. Make the truth *inspectable*, but distinguish the three kinds of truth (below).

Companion to `SAMPLE_DESIGNER.md` (the built QC slice). This is about the **next layer**: making the
GUI legible to a **newcomer who does not yet know what timsim is or what to do with it.** The current
UI works for someone who already has the mental model; it does not *teach* the model.

## The problem

The built slice (Sample → Sample preparation → Replicates & variance → Review & generate) is correct
and runnable, but every screen assumes the user already knows what timsim is (a generator of synthetic
runs with known truth, not an analysis tool), what they are building (a sample that fans out into
runs), what the knobs mean physically (load in ng, occupancy, missed cleavages, CV), and what to *do*
with the outputs. A newcomer hits a wall of correct-but-unexplained controls.

## North star (revised)

> **Help a scientist specify, inspect, and validate a synthetic experiment with known truth.**

The "known truth" is the differentiator over a real instrument — but it is the *through-line*, not a
mandate to bolt a ground-truth readout onto every control. And it is not one thing. The whole design
rests on keeping **three kinds of truth visually distinct**, because conflating them is exactly how a
simulator GUI teaches wrong intuition:

| Kind | What it is | Example in this slice | How to show it |
|---|---|---|---|
| **Specified** | What the user dials in | load 200 ng, biological CV 15%, occupancy 0.5 | the controls; a summary bar |
| **Realized** | What the sim stochastically drew | realized biological CV 9.5%; the actual per-replicate amounts | results, labelled "measured from the run" |
| **Observed** | What a downstream tool would report | DIA-NN's IDs / quant / FDR | *out of scope here* — needs the render + a search |

This slice produces **specified** and **realized** truth; it does **not** produce **observed** results
(no `.d`, no search). The UI must never let a visual imply an *observed* consequence (detection,
coverage, FDR) that the model has not computed.

## Ideas, grouped by lever

### 1. Frame it up front + a worked example (explanation + guidance) — *now the top priority*

- **A one-screen "what is this?"**: *"timsim manufactures synthetic mass-spec runs with known truth.
  Describe a sample; get runs you can feed to DIA-NN / Spectronaut and check how well they recover what
  you put in."* 3-icon diagram (sample → runs → your search tool). Dismissible; re-openable via `?`.
- **A "Load example QC experiment" path** *(added per review — the biggest onboarding gap)*: opens a
  *completed, inspectable* 3-bio × 2-tech run with short annotations — what was specified, what varied
  across biological replicates, what the outputs mean, what gets compared downstream. The panel
  *explains*; the example gives a **safe first success** before the newcomer configures anything.
- **Trust boundaries, stated explicitly** *(added per review)*: which values are specified vs realized;
  which mechanisms are modeled now vs not (detectability, ionization, acquisition are **not** yet);
  and that synthetic truth is for benchmarking/calibration, not proof a real sample behaves the same.

### 2. Show what you're building (visualization)

- **The experiment sheet** *(highest-value — teaches the tool's output model fastest)*. Biological
  replicates as *vials*, resolving to the run count. Label it **"biological samples → technical
  runs"** rather than leaning on syringe/injection imagery (the technical-replicate model is
  "same material, measured again," and this slice does not yet render those measurements). Editing 3×2
  redraws it. Makes **Sample ≠ Run** obvious with no prose.
- **The abundance / dynamic-range curve** *(reframed for honesty)*. Show the rank-ordered **specified
  molecular amounts** (label the axis "amount, amol"); the load shifts the absolute scale. Describe
  dynamic range as an **input property of the sample you built**, *not* a coverage or detectability
  prediction. **No detection-limit line** — detectability is not modeled in this slice, and a line
  would teach "above = detected," the worst proteomics intuition. A distinctly-labelled "simulated
  detectability" overlay is a *future* addition, only once the model computes it.
- **A digestion preview** *(labelled illustrative)*. One **real example protein** ("illustrative
  molecule," not proteome-wide yield) with K/R sites marked, visibly separating theoretical tryptic
  products, missed-cleavage products, and what the length filter *removes* — so it is clear
  **max length is a post-digestion filter, not a physical digestion parameter.**
- **Occupancy → modform bar** *(corrected)*. For a **single** site at occupancy *p*: a two-segment bar,
  unmodified (1−*p*) vs modified (*p*). Only for a **multi-site** peptide do 0/1/2+ modified forms
  appear, and then only under a clearly-labelled **independent-site approximation**. Also state that
  `max-N-variable-mods` is a search-engine enumeration cap, not a biological occupancy mechanism.
- **(Later — needs precursors/render) the m/z × 1/K₀ cloud** via the embedded `tims-viewer`: a
  **simulated precursor feature space**, not "as the instrument sees it."

### 3. Make the flow legible (flow)

- A **persistent live "sample summary" bar** (always visible): `HeLa · 3 bio × 2 tech = 6 runs ·
  200 ng · trypsin · 2 mods`. The newcomer never loses the thread of the whole thing while editing one
  part. This is the specified-truth anchor.
- A light **pipeline-style spine** (`Proteome → Digest → Modify → Design → Generate`) as a *conceptual*
  model of what is being built — **not** presented as the literal necroflow DAG. Keep cache feedback
  **subtle** ("ready" / "needs update"), never a lesson in invalidation.

### 4. Explain in place (explanations)

- **Interpreted review/results cards, not raw numbers** — and they must show **specified vs realized
  side by side**: "biological CV — set 15% / measured 9.5% (from the run's replicate amounts)," with a
  small gauge and a **"what next"** line.
- **The downstream handoff, stated concretely** *(sharpened per review)*: "Generate the runs + export
  the **truth table** → analyze with your tool → compare IDs, quantities, and CV against truth." Note
  that **real FDR evaluation needs a defined truth-match criterion** — do not imply a single "recovery
  score."
- **Contextual "Why change this?"** near the few consequential controls (load, occupancy, replicates,
  CV) — *not* a full hover-glossary on every term (that becomes tooltip confetti).

## Priority order (revised per review)

1. **Upfront framing + a runnable worked example** — orient, and a safe first success.
2. **Experiment sheet + persistent summary bar** — teaches the output model; fastest to "what will
   Generate make?"
3. **Interpreted results cards with specified-vs-realized** — closes the loop honestly.
4. **Abundance / dynamic-range curve (no threshold)** — domain-rich but cognitively expensive; it is
   not the fastest route to a first generation, so it comes after the above.

Contextual explanations (§4) ride along with each.

## Deliberately deferred

- Detectability/coverage overlays, and the m/z × 1/K₀ instrument view (need precursors/CCS + render).
- Any experiment type beyond single-sample QC.
- Any step-gating "wizard" — steps stay hints, not gates; the visuals teach along the way.
- Cache/DAG process education in the UI.

## Resolved (was: open questions)

1. North star → *specify, inspect, validate*, with specified/realized/observed kept distinct.
2. First visualization → the **experiment sheet** (teaches the output model, prevents the worst
   novice confusion), ahead of the abundance curve.
3. Honesty fixes → **drop the detection-limit line**; **correct the single-site modform bar**.
4. The spine is a conceptual model only; do not foreground cache dots or the literal DAG.
5. Onboarding needs a **worked, explorable example** in addition to the framing panel.

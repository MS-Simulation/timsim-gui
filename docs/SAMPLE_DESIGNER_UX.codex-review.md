# Codex review — Sample Designer onboarding & visualization design

Reviewer framing: proteomics domain expert + specialist in software for non-programmer scientists.

---

**Overall:** strong direction, but the doc risks teaching an overly tidy, instrument-like causal story
before timsim actually models all of those causes. Make the generated truth inspectable — but
distinguish **specified truth**, **realized simulated truth**, and **downstream observed results.**

**1. North star.** "Make the manufactured ground truth visible at every step" is right as a
*differentiator*, too absolute as the *product principle*. A newcomer's first need is "what am I
creating, what will it produce, and why would I use it?" Revise to: *"Help scientists specify,
inspect, and validate a synthetic experiment with known truth."* This makes room for a clean form and
for the specified/realized distinction, and stops implying every knob has a visible ground-truth
consequence.

**2. Visualizations — honesty and intuition.**
- *Experiment sheet:* best and most honest — it explains that one biological design expands into
  replicate runs. Avoid syringes if they imply an injection model the simulator may not have; label
  "biological samples → technical runs".
- *Rank-abundance curve:* the **detection-limit line is scientifically dishonest in this slice.**
  Detectability/ionization/acquisition/interference/search are not modeled, so there is no defensible
  detection limit; the line teaches "above = detected," the exact wrong proteomics intuition. Show the
  distribution as **specified molecular amount**; let load shift the absolute scale; describe dynamic
  range as an **input property of the sample, not a coverage prediction.** Add a distinctly-labelled
  "simulated detectability" overlay only once the model supports it.
- *Digestion preview:* good, if it uses a real example sequence labelled "illustrative molecule" and
  visibly separates theoretical tryptic products / missed-cleavage products / filters / retained
  amount — otherwise users infer max length is a physical digestion parameter rather than a
  post-digestion filter.
- *Occupancy → modform bar:* misleading as written. A **single site** has only unmodified vs
  modified. "unmodified / singly / doubly" needs ≥2 independently modifiable sites, site-specific
  occupancies, and an independence assumption. Start with a one-site two-segment bar; for multi-site
  show a labelled "independent-site approximation". Make clear `max-N-variable-mods` is an enumeration
  cap, not a biological mechanism.
- *m/z × 1/K₀ cloud:* correctly deferred; don't call it "as the instrument sees it" — it is a
  simulated precursor feature space.

**3. Prioritization.** The **experiment sheet moves a newcomer fastest** — it answers "what will
Generate make?" The summary bar is scaffolding, not teaching. Revised tranche: (1) upfront framing +
a **runnable worked example**; (2) experiment sheet + persistent summary; (3) interpreted
review/results cards with **specified-vs-realized** values; (4) rank-abundance curve, no threshold.
The curve is domain-rich but cognitively expensive — not the fastest route to a first success.

**4. Missing onboarding.** A dismissible explainer is not enough. Add a **"Load example QC
experiment"** path opening a completed, inspectable 3-bio × 2-tech design with annotations. Add
explicit **trust boundaries**: which values are user-specified vs stochastic realized; which
mechanisms are modeled now vs not; that synthetic truth is for benchmarking/calibration, not proof a
real sample behaves identically. The DIA-NN/Spectronaut loop needs a concrete handoff ("generate runs
+ export truth table → analyze → compare IDs/quant/CV/—when applicable—FDR against truth"), and
**true FDR needs a defined truth-match criterion** — don't imply a single "compare recovery" score.

**5. Premature / over-engineered.** The **cache-status interpretation in the spine is premature** —
newcomers don't need necroflow's invalidation model; keep it subtle ("updates needed"/"ready"), not
process education. The live rank curve is premature if it only exists to make a polished chart from a
large peptide-quantity output — ship it once its semantics are sound. A full glossary risks "tooltip
confetti"; prefer a small set of contextual "why change this?" near consequential controls.

**Answers to the open questions.**
1. Right direction, but revise to inspectable *specified and realized* truth — not truth at every step.
2. Experiment sheet first; it teaches the output model and prevents the most consequential confusion.
3. Yes — omit the detection-limit line now; fix the modform single-site/multi-site logic.
4. The spine is fine as a conceptual model; don't present it as the literal DAG or foreground cache dots.
5. Needs a worked, explorable example in addition to the panel — the panel explains, the example
   establishes confidence and a safe first success.

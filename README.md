# Redrob — Intelligent Candidate Discovery & Ranking

Ranks the top 100 candidates from a 100K pool against the **Senior AI Engineer
(Founding Team)** job description, best-fit first, with grounded per-candidate
reasoning.

**▶ Live demo:** https://redrob-siddh.streamlit.app

## Reproduce

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

Runs in **~2 min on a CPU-only 16 GB machine** (verified on an 8-core Ryzen 7 —
well within the 5-minute limit), no network, no GPU.
Accepts `.jsonl` or `.jsonl.gz`. Output passes `validate_submission.py` as-is.

```bash
python validate_submission.py submission.csv   # -> "Submission is valid."
```

## Live sandbox / demo

**Live app → https://redrob-siddh.streamlit.app**

An interactive dashboard runs the **same ranker** on a small sample and makes
every decision visible: the six-signal decomposition per candidate (radar), the
behavioral multiplier, itemized penalties, plain-English honeypot explanations,
and a side-by-side of *naive keyword ranking vs. this system* — including a
"traps intercepted" view (where a keyword matcher ranks each stuffer/honeypot vs.
where this system floors it).

```bash
pip install -r requirements.txt
streamlit run app.py
```

Loads a curated 40-candidate showcase by default (strong matches + every trap
type), a **random unfiltered 400-profile slice** of the real pool (anti-cherry-pick),
the organizer's 50-profile sample, or your own `.jsonl` upload. You can **filter it
like a recruiter** (location / experience / must-have skill), **search any candidate**,
open the **raw source profile to verify every claim**, and read a **"proven at scale"**
panel measured on the full 100K run (68.8% of the pool is non-engineering noise; a
naive keyword ranker would seat 96 traps incl. 10 honeypots in its top 100 — this
system: 0). The demo imports `rank.py`'s exact scoring functions — **one source of
truth, no logic re-implemented.**

**Deploy as the submission's mandatory sandbox link** (both platforms read
`requirements.txt`; entry point is `app.py`):

- **Streamlit Community Cloud** — push to GitHub → [share.streamlit.io](https://share.streamlit.io)
  → select the repo, main file `app.py` → Deploy.
- **HuggingFace Spaces** — create a Space (SDK: *Streamlit*), push these files,
  and set `sdk: streamlit` / `app_file: app.py` in the Space README front-matter.

The curated showcase is regenerated from the pool with
`python make_showcase.py --candidates ./candidates.jsonl`.

## The problem, stated honestly

The pool is adversarial by design:

- **~70% of profiles are non-engineering titles** (HR Manager, Accountant,
  Mechanical Engineer …) carrying AI skills. Skill names are distributed almost
  uniformly across the pool (~12K occurrences each), so a skill list is *noise*.
  A keyword/embedding matcher ranks these stuffers at the top — that is the trap.
- **~80 honeypots** with internally impossible profiles (tenure > company age,
  "expert" in skills used 0 months, overlapping job dates). >10% honeypots in the
  top 100 is an automatic disqualification.
- **Planted decoys**: e.g. ~150 "AI Research Engineer" profiles exist precisely
  because the JD *rejects* pure-research backgrounds.

The genuinely relevant title cluster is tiny — single digits of "Senior AI
Engineer," a few hundred ML Engineers. The JD itself says it expects ~10 strong
matches, not thousands.

## Why not embeddings?

A dense-embedding-cosine ranker is the obvious move and the wrong one here: it
rewards keyword density, walks into the stuffer/honeypot traps, is slow to
reproduce, and is hard to defend ("the model decided"). The scoring metric
(`0.50·NDCG@10 + 0.30·NDCG@50 + 0.15·MAP + 0.05·P@10`) puts **half the weight on
the top 10**, so the entire game is getting the very top right and keeping traps
out — a structural-reasoning problem, not a similarity problem.

So the core ranker is **rules + TF-IDF**: fully offline, CPU, deterministic,
reproducible inside their Stage-3 Docker, and auditable line by line. Dense
embeddings can be added as an *optional precompute* re-ranker, but they are not
load-bearing.

## How it works (JD input → ranked output)

```
candidates.jsonl
   │  stream-parse 100K profiles → structured features + text blob
   ▼
TF-IDF(corpus)  ── cosine ──►  semantic_fit  vs JD-intent query
   │
   ▼  per candidate, six sub-scores in [0,1]:
        role        title gate: real ML/AI eng titles high; non-tech titles → 0
        career      career_history describes ranking/search/recsys at product cos
        semantic    TF-IDF cosine to JD intent (catches buzzword-free Tier-5s)
        skill       trust-weighted: endorsements × duration × proficiency ×
                    on-platform assessment; off-target CV/speech down-weighted
        experience  peak 6–8 yrs, soft 5–9, hard penalty outside; product>services
        location    Pune/Noida/India-relocatable high; outside-India strong penalty
   │
   ▼  base = Σ wᵢ·scoreᵢ
      score = base × behavior_multiplier − penalties
      behavior_multiplier: response rate, recency, interview completion,
                           recruiter saves, open-to-work, verification
      penalties: title-chaser, pure-services career, research-only, over-seniority
   │
   ▼  HONEYPOT gate → floor;  non-tech role gate → floor
   ▼  round(score,4), sort by (−score, candidate_id) → top 100 + reasoning
submission.csv
```

### The decisive signals

1. **Role gate.** A Marketing Manager with 9 AI skills scores ~0 on `role`,
   which is 28% of the base and gated — no skill list rescues it. This alone
   defeats the keyword-stuffer pool.
2. **Trust-weighted skills.** A skill counts only in proportion to endorsements,
   months used, proficiency, and (where present) the candidate's on-platform
   assessment score. "Expert in 10 skills, 0 endorsements, 0 months" contributes
   nothing — which is also a honeypot signature.
3. **Honeypot detector.** Seven independent plausibility checks (tenure vs
   experience, skill duration vs career length, expert-with-zero-use, reversed
   education dates, overlapping jobs). We do **not** hard-code honeypot IDs — we
   detect the contradictions a careful human reviewer would catch. Result: **0
   honeypots in the top 100.**
4. **Behavioral availability.** A perfect-on-paper candidate who has ghosted
   recruiters and gone dark is, for hiring, unavailable — multiplied down.

## Explainability

Every row carries reasoning generated **only from fields present in that
candidate's profile** — title, years, up-to-three corroborated relevant skills,
a real product-company role from their history, and live engagement signals.
Nothing is invented; a skill is never named in the reasoning unless it appears in
the candidate's own skill list with real corroboration. This is what prevents the
hallucinated / templated / rank-contradicting reasoning the rubric penalizes.

## Files

| file | purpose |
|---|---|
| `rank.py` | the ranker (single command, end-to-end) — and the importable scoring API |
| `app.py` | interactive sandbox dashboard (the demo / sandbox link) |
| `make_showcase.py` | regenerates the curated demo sample from the pool |
| `make_pool_sample.py` / `pool_sample.jsonl` | random, unfiltered 400-profile slice of the pool (anti-cherry-pick demo input) |
| `make_evidence.py` / `pool_stats.json` | full-pool measured stats for the demo's "proven at scale" panel |
| `showcase_candidates.jsonl` | 40 real profiles covering every trap type (demo input) |
| `sample_candidates.json` | organizer's 50-profile sample (demo input) |
| `requirements.txt` | deps — core ranker (scikit-learn, numpy) + demo (streamlit, plotly) |
| `submission_metadata.yaml` | portal metadata mirror |
| `validate_submission.py` | organizer's format validator (bundled) |
| `submission.csv` | the top-100 output |

## Tunables (all explicit, in `rank.py`)

Component weights `W`, title tiers `TITLE_TIERS`, skill groups `SKILL_GROUPS`,
preferred cities, services-firm list, and the JD intent query are all named
constants at the top of the file — every ranking decision traces back to one of
them. No hidden state, no learned weights to explain away.

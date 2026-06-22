#!/usr/bin/env python3
"""Offline, CPU-only ranker for the Senior AI Engineer JD. Structural multi-signal
scoring with a role gate and an honeypot floor over a 100K candidate pool -> top-100 CSV.

    python rank.py --candidates ./candidates.jsonl --out ./submission.csv
"""

import argparse, csv, json, math, re, sys, datetime
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# --- JD encoding: tunable knobs derived from the job description -------------

TITLE_TIERS = {
    1.00: ["senior ai engineer", "staff machine learning", "lead ai engineer",
           "senior machine learning engineer", "applied ml engineer",
           "senior nlp engineer", "search engineer", "recommendation systems"],
    0.90: ["ml engineer", "machine learning engineer", "ai engineer",
           "nlp engineer", "senior software engineer (ml)"],
    0.78: ["data scientist", "senior data scientist", "applied scientist",
           "senior applied scientist"],
    0.62: ["backend engineer", "data engineer", "analytics engineer",
           "software engineer", "senior software engineer", "full stack",
           "cloud engineer", "devops engineer", "platform engineer"],
    0.30: ["frontend engineer", "mobile developer", "java developer",
           ".net developer", "qa engineer", "data analyst"],
    0.45: ["ai research engineer", "research scientist"],   # research-only risk
    0.40: ["ai specialist", "junior ml engineer"],          # vague / too junior
}
# Non-engineering titles -> hard zero on role (the keyword-stuffer pool).
NONTECH_TITLES = {
    "business analyst", "hr manager", "mechanical engineer", "accountant",
    "project manager", "customer support", "operations manager",
    "content writer", "sales executive", "civil engineer", "graphic designer",
    "marketing manager", "product manager",
}

# Relevant skills grouped by weight; off-target (CV/speech) tracked separately.
SKILL_GROUPS = {
    "core_retrieval": (1.00, {
        "embeddings", "sentence-transformers", "bge", "e5", "vector search",
        "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
        "elasticsearch", "rag", "retrieval", "semantic search", "ann"}),
    "ranking_eval": (0.95, {
        "learning to rank", "ltr", "xgboost", "lightgbm", "ndcg", "ranking",
        "recommendation systems", "recommender", "information retrieval"}),
    "nlp_llm": (0.85, {
        "nlp", "llm", "fine-tuning llms", "lora", "qlora", "peft",
        "transformers", "huggingface", "prompt engineering"}),
    "ml_foundation": (0.70, {
        "machine learning", "deep learning", "pytorch", "tensorflow",
        "scikit-learn", "mlops", "model deployment", "feature engineering"}),
    "eng_foundation": (0.55, {
        "python", "spark", "airflow", "sql", "docker", "kubernetes",
        "aws", "gcp", "data pipelines", "etl"}),
    "offtarget": (0.0, {
        "image classification", "speech recognition", "tts", "computer vision",
        "robotics", "object detection", "ocr", "asr"}),
}
PROFICIENCY_W = {"beginner": 0.4, "intermediate": 0.7, "advanced": 0.9, "expert": 1.0}

# Services firms penalized when they make up a candidate's whole career.
SERVICES_FIRMS = {"tcs", "infosys", "wipro", "accenture", "cognizant",
                  "capgemini", "tech mahindra", "hcl", "mindtree", "ltimindtree",
                  "deloitte", "kpmg", "pwc", "ey"}

PREFERRED_CITIES = {"pune", "noida", "hyderabad", "bangalore", "bengaluru",
                    "mumbai", "delhi", "gurgaon", "gurugram", "ncr"}

# JD intent text used as the TF-IDF query.
JD_QUERY = """
senior ai engineer founding team owning ranking retrieval and matching systems.
production experience with embeddings based retrieval sentence transformers bge e5,
vector databases pinecone weaviate qdrant milvus faiss opensearch elasticsearch hybrid search.
shipped end to end ranking search or recommendation system to real users at scale.
strong python, evaluation frameworks ndcg mrr map offline online ab testing.
applied machine learning at product companies not pure services or research.
embedding drift index refresh retrieval quality regression. llm re-ranking fine tuning lora.
""".lower()

W = dict(role=0.28, career=0.22, semantic=0.15, skill=0.16, experience=0.13, location=0.06)

HONEYPOT_FLOOR = 0.001
DQ_FLOOR = 0.02


# --- per-candidate feature extraction ----------------------------------------

def _norm(s): return (s or "").strip().lower()

def title_score(c):
    """Best title tier across current + past roles; non-tech current title caps low."""
    titles = [_norm(c["profile"]["current_title"])]
    titles += [_norm(j["title"]) for j in c["career_history"]]
    cur = titles[0]
    if cur in NONTECH_TITLES:
        # small rescue only if a strong past eng title exists
        best_hist = 0.0
        for t in titles[1:]:
            for tier, names in TITLE_TIERS.items():
                if any(nm in t for nm in names):
                    best_hist = max(best_hist, tier)
        return min(0.25, best_hist * 0.3)
    best = 0.0
    for t in titles:
        for tier, names in TITLE_TIERS.items():
            if any(nm in t for nm in names):
                best = max(best, tier)
    return best

def skill_score(c):
    """Relevant-skill match, trust-weighted by endorsements, duration, proficiency and
    on-platform assessment so keyword stuffing fails. Off-target skills don't count."""
    assessments = c["redrob_signals"].get("skill_assessment_scores", {}) or {}
    rel, offt = 0.0, 0.0
    for s in c["skills"]:
        nm = _norm(s["name"])
        endorse = min(s.get("endorsements", 0) / 30.0, 1.0)
        dur = min(s.get("duration_months", 0) / 36.0, 1.0)
        prof = PROFICIENCY_W.get(s.get("proficiency", "beginner"), 0.4)
        assess = assessments.get(s["name"], assessments.get(nm, None))
        trust = (0.45 * prof + 0.30 * endorse + 0.25 * dur)
        if assess is not None:
            trust = 0.6 * trust + 0.4 * (assess / 100.0)
        matched_grp = None
        for grp, (gw, names) in SKILL_GROUPS.items():
            if nm in names or any(nm == n or n in nm for n in names):
                matched_grp = grp; break
        if matched_grp == "offtarget":
            offt += trust
        elif matched_grp:
            rel += SKILL_GROUPS[matched_grp][0] * trust
    raw = rel / 4.0                        # ~4 strong relevant skills saturates
    raw = min(raw, 1.0)
    if offt > rel + 1.0:                   # wrong-domain (CV/speech) profile
        raw *= 0.4
    return raw

def experience_score(c):
    """Peak 6-8 yrs, soft 5-9, penalized outside; product exposure adds, services doesn't."""
    y = c["profile"]["years_of_experience"]
    if 6 <= y <= 8:      band = 1.0
    elif 5 <= y <= 9:    band = 0.85
    elif 4 <= y < 5:     band = 0.65
    elif 9 < y <= 11:    band = 0.55
    elif 11 < y <= 13:   band = 0.35
    elif 3 <= y < 4:     band = 0.4
    else:                band = 0.15
    comps = [_norm(j["company"]) for j in c["career_history"]]
    inds  = [_norm(j["industry"]) for j in c["career_history"]]
    n = max(len(comps), 1)
    services = sum(1 for cm in comps if cm in SERVICES_FIRMS)
    product = sum(1 for ind in inds if ind in ("ai/ml", "saas", "software",
                  "fintech", "edtech", "e-commerce", "food delivery",
                  "product", "internet"))
    prod_ratio = product / n
    return min(1.0, band * (0.7 + 0.3 * prod_ratio))

def location_score(c):
    loc = _norm(c["profile"]["location"])
    country = _norm(c["profile"]["country"])
    relocate = c["redrob_signals"].get("willing_to_relocate", False)
    if any(city in loc for city in PREFERRED_CITIES):
        return 1.0
    if country == "india":
        return 0.85 if relocate else 0.55
    return 0.25 if relocate else 0.05      # outside India: no visa sponsorship

def behavior_multiplier(c, ref_date):
    """Availability/engagement modifier ~[0.55, 1.12] from response rate, recency,
    interview completion, recruiter saves, open-to-work and verification."""
    s = c["redrob_signals"]
    resp = s.get("recruiter_response_rate", 0.0)
    try:
        la = datetime.date.fromisoformat(s["last_active_date"])
        days = (ref_date - la).days
    except Exception:
        days = 180
    recency = max(0.0, 1.0 - days / 180.0)
    interview = s.get("interview_completion_rate", 0.0)
    saved = min(s.get("saved_by_recruiters_30d", 0) / 40.0, 1.0)
    open_w = 1.0 if s.get("open_to_work_flag") else 0.7
    verified = (s.get("verified_email") and s.get("verified_phone"))
    m = (0.40 * resp + 0.25 * recency + 0.20 * interview + 0.15 * saved)
    m = 0.55 + 0.5 * m
    m *= open_w
    if verified: m *= 1.05
    return min(m, 1.12)

def penalty_reasons(c):
    """JD red flags as an itemized (label, amount) list."""
    out = []
    hist = c["career_history"]
    short = sum(1 for j in hist if j["duration_months"] < 20)
    if len(hist) >= 3 and short >= 3:
        out.append(("title-chaser: 3+ short stints (<20 mo)", 0.10))
    comps = [_norm(j["company"]) for j in hist]
    if comps and all(cm in SERVICES_FIRMS for cm in comps):
        out.append(("pure-services career: every employer a services firm", 0.15))
    txt = _norm(c["profile"]["summary"])
    if c["profile"]["years_of_experience"] < 4 and "langchain" in txt and "retrieval" not in txt:
        out.append(("recent-LangChain-only, no retrieval depth", 0.08))
    if ("research" in _norm(c["profile"]["current_title"])
            and not any(k in txt for k in ("production", "deployed", "shipped", "users"))):
        out.append(("research-only: no production language in summary", 0.06))
    if c["profile"]["years_of_experience"] > 12:
        out.append(("over-seniority: >12 yrs (role wants a hands-on IC)", 0.12))
    return out


def penalties(c):
    return sum(amt for _, amt in penalty_reasons(c))


# --- honeypot / implausibility detector (floored to ~0) ----------------------

def honeypot_flags(c):
    """List the internal contradictions that mark an impossible (honeypot) profile."""
    flags = []
    p = c["profile"]; y = p["years_of_experience"]
    hist = c["career_history"]
    total_mo = sum(j["duration_months"] for j in hist)
    if total_mo / 12.0 > y + 4:
        flags.append("tenure_exceeds_experience")
    if any(j["duration_months"] / 12.0 > y + 1.5 for j in hist):
        flags.append("job_longer_than_career")
    for s in c["skills"]:
        if s.get("duration_months", 0) / 12.0 > y + 1.0:
            flags.append("skill_duration_exceeds_career"); break
    if any(s.get("proficiency") in ("expert", "advanced")
           and s.get("duration_months", 1) == 0 for s in c["skills"]):
        flags.append("expert_zero_duration")
    experts = [s for s in c["skills"] if s.get("proficiency") == "expert"]
    if len(experts) >= 6 and sum(s.get("endorsements", 0) for s in experts) <= 2:
        flags.append("expert_no_endorsements")
    for e in c.get("education", []):
        if e.get("end_year") and e.get("start_year") and e["end_year"] < e["start_year"]:
            flags.append("education_dates_reversed"); break
    try:
        starts = [datetime.date.fromisoformat(j["start_date"]) for j in hist if j.get("start_date")]
        career_span = (datetime.date(2026, 6, 1) - min(starts)).days / 365.0 if starts else y
        if total_mo / 12.0 > career_span + 3:
            flags.append("overlapping_jobs")
    except Exception:
        pass
    return flags


# --- reasoning (built only from fields present in the profile) ----------------

def make_reasoning(c, comps):
    p = c["profile"]; s = c["redrob_signals"]
    title = p["current_title"]; y = p["years_of_experience"]
    rel = []
    for sk in c["skills"]:
        nm = _norm(sk["name"])
        for grp, (gw, names) in SKILL_GROUPS.items():
            if grp != "offtarget" and gw >= 0.7 and (nm in names or any(n in nm for n in names)):
                if sk.get("endorsements", 0) >= 3 or sk.get("duration_months", 0) >= 12:
                    rel.append(sk["name"])
                break
    rel = list(dict.fromkeys(rel))[:3]
    loc = p["location"]
    bits = [f"{title}, {y:.1f} yrs"]
    if rel:
        bits.append("corroborated skills: " + ", ".join(rel))
    prod = next((j for j in c["career_history"]
                 if _norm(j["industry"]) in ("ai/ml", "saas", "software", "fintech",
                 "edtech", "e-commerce", "internet", "food delivery")), None)
    if prod:
        bits.append(f"product exp at {prod['company']} ({prod['industry']})")
    bits.append(f"{loc}")
    bits.append(f"resp {s.get('recruiter_response_rate',0):.2f}, "
                f"saved {s.get('saved_by_recruiters_30d',0)}")
    txt = "; ".join(bits) + "."
    return txt[:240]


# --- pipeline (importable: the demo ranks via the same functions) ------------

def build_blob(c):
    """Lowercased headline + summary + career descriptions + skill names."""
    p = c["profile"]
    return " ".join([p["headline"], p["summary"],
                     " ".join(j["description"] for j in c["career_history"]),
                     " ".join(s["name"] for s in c["skills"])]).lower()


def load_candidates(path):
    """Stream-parse a .jsonl(.gz) pool into (candidates, blobs, ref_date), where
    ref_date is the latest last_active_date (recency is measured relative to it)."""
    cands, texts = [], []
    opener = (lambda p: __import__("gzip").open(p, "rt", encoding="utf-8")) \
        if str(path).endswith(".gz") else (lambda p: open(p, encoding="utf-8"))
    ref_date = datetime.date(2000, 1, 1)
    with opener(path) as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            cands.append(c)
            texts.append(build_blob(c))
            try:
                la = datetime.date.fromisoformat(c["redrob_signals"]["last_active_date"])
                if la > ref_date:
                    ref_date = la
            except Exception:
                pass
    return cands, texts, ref_date


def semantic_fit(texts, min_df=3):
    """TF-IDF cosine of each blob vs the JD query, normalized to [0,1]; min_df
    relaxes on tiny samples so the vocabulary does not collapse."""
    md = min_df if len(texts) >= 50 else 1
    vec = TfidfVectorizer(max_features=40000, ngram_range=(1, 2),
                          stop_words="english", sublinear_tf=True, min_df=md)
    X = vec.fit_transform(texts)
    q = vec.transform([JD_QUERY])
    sem = linear_kernel(q, X).ravel()
    return sem / (sem.max() + 1e-9)


def score_candidate(c, sem_i, ref_date):
    """Score one candidate, returning each intermediate value (sub-scores,
    multiplier, penalty, gate). Score math matches the CLI path."""
    hp = honeypot_flags(c)
    comps = dict(
        role=title_score(c), career=0.0, semantic=float(sem_i),
        skill=skill_score(c), experience=experience_score(c),
        location=location_score(c),
    )
    # career fit: keyword corroboration of ranking/search/recsys work + semantic
    carblob = " ".join(j["description"].lower() for j in c["career_history"])
    career_kw = sum(k in carblob for k in
                    ("ranking", "retrieval", "search", "recommend",
                     "embedding", "vector", "relevance", "matching"))
    comps["career"] = min(1.0, 0.25 * career_kw) * 0.6 + comps["semantic"] * 0.4

    base = sum(W[k] * comps[k] for k in W)
    mult = behavior_multiplier(c, ref_date)
    pen = penalties(c)
    score = base * mult - pen
    pre_gate = score

    gate = None
    if hp:
        score = HONEYPOT_FLOOR
        gate = "honeypot"
    if comps["role"] < 0.05:               # non-tech title, no eng rescue
        score = min(score, DQ_FLOOR)
        if gate is None:
            gate = "role_gate"

    return dict(cid=c["candidate_id"], comps=comps, base=base, mult=mult,
                penalty=pen, pre_gate_score=pre_gate,
                score=round(max(score, 0.0), 4), hp=hp, gate=gate)


def rank_all(cands, texts, ref_date, min_df=3, sem=None):
    """Score and sort all candidates best-first. Sort key (-rounded_score,
    candidate_id) matches the validator's ordering rule."""
    if sem is None:
        sem = semantic_fit(texts, min_df=min_df)
    scored = [dict(score_candidate(c, float(sem[i]), ref_date), idx=i)
              for i, c in enumerate(cands)]
    scored.sort(key=lambda d: (-d["score"], d["cid"]))
    return scored


# --- CLI entry point ---------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topk", type=int, default=100)
    args = ap.parse_args()

    print("[1/5] loading candidates …", file=sys.stderr)
    cands, texts, ref_date = load_candidates(args.candidates)
    print(f"      {len(cands)} candidates. recency ref = {ref_date}", file=sys.stderr)

    print("[2/5] TF-IDF semantic fit …", file=sys.stderr)
    sem = semantic_fit(texts)

    print("[3/5] structured scoring …", file=sys.stderr)
    scored = rank_all(cands, texts, ref_date, sem=sem)

    print("[4/5] ranking …", file=sys.stderr)
    top = scored[:args.topk]

    hp_in_top = sum(1 for d in top if d["hp"])
    print(f"      honeypots in top {args.topk}: {hp_in_top} "
          f"({100*hp_in_top/len(top):.1f}%)", file=sys.stderr)

    print("[5/5] writing CSV …", file=sys.stderr)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, d in enumerate(top, 1):
            reasoning = make_reasoning(cands[d["idx"]], d["comps"])
            w.writerow([d["cid"], rank, f'{d["score"]:.4f}', reasoning])
    print(f"done -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

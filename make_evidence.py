#!/usr/bin/env python3
"""Write pool_stats.json — measured stats from ranking the full 100K pool (pool
composition, top-100 properties, naive-keyword baseline). Precomputed because the
hosted sandbox can't ship the 465 MB pool.

    python make_evidence.py --candidates ./candidates.jsonl --out ./pool_stats.json
"""
import argparse, json, statistics
from collections import Counter
import rank


def rel_skill_count(c, thresh=0.70):
    n = 0
    for s in c["skills"]:
        nm = rank._norm(s["name"])
        for grp, (gw, names) in rank.SKILL_GROUPS.items():
            if grp != "offtarget" and gw >= thresh and (nm in names or any(x in nm for x in names)):
                n += 1
                break
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", default="pool_stats.json")
    args = ap.parse_args()

    print("ranking full pool (~2 min) …")
    cands, texts, ref = rank.load_candidates(args.candidates)
    scored = rank.rank_all(cands, texts, ref)
    by_idx = {d["idx"]: d for d in scored}
    top = scored[:100]

    nontech = sum(1 for c in cands if rank._norm(c["profile"]["current_title"]) in rank.NONTECH_TITLES)
    hp_flagged = sum(1 for d in scored if d["hp"])

    top_titles = Counter(cands[d["idx"]]["profile"]["current_title"] for d in top)
    top_scores = [d["score"] for d in top]
    yrs = [cands[d["idx"]]["profile"]["years_of_experience"] for d in top]
    india = sum(1 for d in top if rank._norm(cands[d["idx"]]["profile"]["country"]) == "india")

    # naive keyword baseline: rank purely by relevant-skill count
    naive_order = sorted(range(len(cands)), key=lambda i: -rel_skill_count(cands[i]))
    naive_top = set(naive_order[:100])
    floor_set = {d["idx"] for d in scored if d["hp"] or d["gate"] == "role_gate"}
    naive_traps = len(naive_top & floor_set)
    naive_hp = sum(1 for i in naive_top if by_idx[i]["hp"])

    stats = {
        "pool_size": len(cands),
        "pool_nontech_pct": round(100 * nontech / len(cands), 1),
        "pool_honeypot_flagged": hp_flagged,
        "top100": {
            "honeypots": sum(1 for d in top if d["hp"]),
            "india_pct": round(100 * india / len(top)),
            "median_years": round(statistics.median(yrs), 1),
            "score_min": round(min(top_scores), 3),
            "score_max": round(max(top_scores), 3),
            "distinct_titles": len(top_titles),
            "top_titles": top_titles.most_common(10),
        },
        "naive_baseline": {
            "traps_in_top100": naive_traps,
            "honeypots_in_top100": naive_hp,
        },
        "runtime_note": "Ranked all 100,000 profiles on CPU (no GPU, no network) in ~2 min.",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))
    print(f"\nwrote -> {args.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Write showcase_candidates.jsonl — a small curated slice of the pool covering each
demo category (strong, stuffer, honeypot, research, services-only, off-target,
outside-India, adjacent). Records are real and unedited; the dashboard re-derives
all labels live, so this only samples representative profiles.

    python make_showcase.py --candidates ./candidates.jsonl --out ./showcase_candidates.jsonl
"""
import argparse, json, random
import rank

SEED = 7
PER = dict(strong=12, honeypot=6, stuffer=6, research=3,
           services=3, offtarget=3, outside_india=3, adjacent=4)


def rel_skill_count(c):
    n = 0
    for s in c["skills"]:
        nm = rank._norm(s["name"])
        for grp, (gw, names) in rank.SKILL_GROUPS.items():
            if grp != "offtarget" and gw >= 0.85 and (
                    nm in names or any(x in nm for x in names)):
                n += 1
                break
    return n


def is_services_only(c):
    comps = [rank._norm(j["company"]) for j in c["career_history"]]
    return bool(comps) and all(cm in rank.SERVICES_FIRMS for cm in comps)


def is_offtarget(c):
    off = rel = 0
    for s in c["skills"]:
        nm = rank._norm(s["name"])
        for grp, (gw, names) in rank.SKILL_GROUPS.items():
            if nm in names or any(x in nm for x in names):
                if grp == "offtarget":
                    off += 1
                elif gw >= 0.7:
                    rel += 1
                break
    return off >= 3 and off > rel


def categorize(c, d, pos):
    """First-match-wins category bucket for a candidate, or None."""
    title = rank._norm(c["profile"]["current_title"])
    country = rank._norm(c["profile"]["country"])
    if pos < PER["strong"] and not d["hp"]:
        return "strong"
    if d["hp"]:
        return "honeypot"
    if d["gate"] == "role_gate" and rel_skill_count(c) >= 5:
        return "stuffer"
    if "research" in title:
        return "research"
    if is_services_only(c):
        return "services"
    if is_offtarget(c):
        return "offtarget"
    if country and country != "india":
        return "outside_india"
    if 150 <= pos < 700 and d["comps"]["role"] >= 0.6 and country == "india":
        return "adjacent"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", default="showcase_candidates.jsonl")
    args = ap.parse_args()

    print("loading + ranking full pool (one-time, ~2 min) …")
    cands, texts, ref = rank.load_candidates(args.candidates)
    scored = rank.rank_all(cands, texts, ref)

    buckets = {k: [] for k in PER}
    for pos, d in enumerate(scored):
        c = cands[d["idx"]]
        cat = categorize(c, d, pos)
        if cat:
            buckets[cat].append((c, d, pos))

    # honeypots: prefer variety across distinct flag types
    seen_flag, hp_div = set(), []
    for c, d, pos in buckets["honeypot"]:
        key = d["hp"][0]
        if key not in seen_flag:
            seen_flag.add(key)
            hp_div.append((c, d, pos))
    for tup in buckets["honeypot"]:
        if tup not in hp_div:
            hp_div.append(tup)
    buckets["honeypot"] = hp_div

    rng = random.Random(SEED)
    chosen, summary = [], []
    for cat, n in PER.items():
        pool = buckets[cat]
        if cat not in ("strong", "honeypot"):
            rng.shuffle(pool)
        pick = pool[:n]
        chosen.extend(pick)
        summary.append((cat, len(pool), len(pick)))

    uniq = {c["candidate_id"]: c for c, d, pos in chosen}
    out = [uniq[k] for k in sorted(uniq)]
    with open(args.out, "w", encoding="utf-8") as f:
        for c in out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nwrote {len(out)} candidates -> {args.out}\n")
    print(f"{'category':16} {'available':>10} {'picked':>7}")
    for cat, avail, pick in summary:
        print(f"{cat:16} {avail:>10} {pick:>7}")
    print("\nexamples by category:")
    for cat, n in PER.items():
        for c, d, pos in buckets[cat][:2]:
            p = c["profile"]
            flag = ("HP:" + ",".join(d["hp"][:2])) if d["hp"] else f"score={d['score']}"
            print(f"  [{cat:13}] {c['candidate_id']}  {p['current_title'][:34]:34}  "
                  f"{p['years_of_experience']}y  {p['country'][:12]:12} {flag}")


if __name__ == "__main__":
    main()

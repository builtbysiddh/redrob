#!/usr/bin/env python3
"""Write pool_sample.jsonl — a random, unfiltered slice of the pool (real, unedited
records) so the ranker can be demoed on unbiased data rather than a curated set.

    python make_pool_sample.py --candidates ./candidates.jsonl --out ./pool_sample.jsonl --n 400
"""
import argparse, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", default="pool_sample.jsonl")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    with open(args.candidates, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip()]
    pick = random.Random(args.seed).sample(lines, min(args.n, len(lines)))
    with open(args.out, "w", encoding="utf-8") as f:
        for ln in pick:
            f.write(ln if ln.endswith("\n") else ln + "\n")
    print(f"wrote {len(pick)} random profiles -> {args.out}")

if __name__ == "__main__":
    main()

"""P2-02 entry point at the path named in ROADMAP §4. The implementation is `nawa.data_verify`.

    python data_pipeline/atlas/verify.py check candidates.jsonl --out results.jsonl
    python data_pipeline/atlas/verify.py bench --seed 2026
"""

from nawa.data_verify import main

if __name__ == "__main__":
    main()

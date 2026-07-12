# Data Directory

Structure:

- `raw/`: input corpora (license-clean). Place `.txt` or `.jsonl` files.
- `processed/`: normalized and sharded text files for tokenizer training/eval.
- `manifest.json`: machine-readable list of corpora, licenses, and attribution.
- `LICENSES.md`: human-readable license statements.

Guidelines:

- Only include corpora with permissive licenses suitable for tokenizer training.
- Avoid sensitive/PII content. Use the preparation script to strip emails/URLs.
- Keep shards ~5–50MB per file for efficient tokenizer training.

Scripts:

- `scripts/data/prepare_corpora.py` — normalize, dedupe, shard, and produce manifest.

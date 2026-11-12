import os
import re
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # transformers is optional; imported lazily at runtime
    from transformers import PreTrainedTokenizerBase

# A plain Hugging Face repo id: "owner/name". No local paths, URLs, or extra segments.
_REPO_ID = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# Built-in allowlist: the one tokenizer the /complete API documents as its example.
# Operators add more with ALLOWED_TOKENIZERS (comma-separated repo ids).
DEFAULT_ALLOWED_TOKENIZERS = frozenset({"UW/OLMo2-8B-SuperBPE-t180k"})

MAX_CACHED = 8

_lock = threading.Lock()  # guards _cache only; never held while downloading
_cache: "OrderedDict[str, PreTrainedTokenizerBase]" = OrderedDict()


class TokenizerNotAllowedError(ValueError):
    """The requested tokenizer id is malformed or not on the allowlist."""


def _allowed_ids() -> set[str]:
    extra = {p.strip() for p in os.getenv("ALLOWED_TOKENIZERS", "").split(",") if p.strip()}
    return set(DEFAULT_ALLOWED_TOKENIZERS) | extra


def validate_tokenizer_id(repo_id: str) -> str:
    """Return repo_id if it is a plain repo id on the allowlist, else raise."""
    owner, _, name = repo_id.partition("/")
    if (
        not _REPO_ID.fullmatch(repo_id)
        or owner.strip(".") == ""
        or name.strip(".") == ""
        or owner.startswith(".")
    ):
        raise TokenizerNotAllowedError("tokenizer_id must be a Hugging Face repo id: owner/name")
    if repo_id not in _allowed_ids():
        raise TokenizerNotAllowedError("tokenizer_id is not on the allowed tokenizer list")
    return repo_id


def _load_tokenizer(repo_id: str) -> "PreTrainedTokenizerBase":
    try:
        from transformers import AutoTokenizer  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Tokenizers unavailable: install transformers (and sentencepiece if needed)"
        ) from e

    # Prefer slow tokenizer to avoid rust wheels.
    # bandit B615 (unpinned download) stays suppressed for a reason that holds: repo_id has
    # already passed validate_tokenizer_id (owner/name shape plus an operator allowlist), so
    # the caller cannot choose the repository. No revision is pinned, so a listed repo can
    # still change upstream; trust_remote_code is off, so only tokenizer files are fetched.
    tok = AutoTokenizer.from_pretrained(repo_id, use_fast=False)  # nosec B615
    return tok


def get_tokenizer(repo_id: str) -> "PreTrainedTokenizerBase":
    validate_tokenizer_id(repo_id)
    with _lock:
        if repo_id in _cache:
            _cache.move_to_end(repo_id)
            return _cache[repo_id]
    # Download outside the lock so a slow fetch does not block other callers.
    tok = _load_tokenizer(repo_id)
    with _lock:
        _cache[repo_id] = tok
        _cache.move_to_end(repo_id)
        while len(_cache) > MAX_CACHED:
            _cache.popitem(last=False)
    return tok


def estimate_tokenization_metrics(
    text: str, tokenizer_id: str | None
) -> tuple[int, float, float] | None:
    """
    Estimate token counts using the provided tokenizer repo id.

    Returns (num_tokens, bytes_per_token, tokens_per_byte) or None if no tokenizer_id.
    """
    if not tokenizer_id:
        return None
    tok = get_tokenizer(tokenizer_id)
    enc = tok(
        text, add_special_tokens=False, return_attention_mask=False, return_token_type_ids=False
    )
    ids = enc.get("input_ids", [])
    total_tokens = len(ids)
    total_bytes = len(text.encode("utf-8")) if text else 0
    if total_tokens == 0 or total_bytes == 0:
        return (total_tokens, 0.0, 0.0)
    bpt = total_bytes / total_tokens
    tpb = total_tokens / total_bytes
    return (total_tokens, bpt, tpb)

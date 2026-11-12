"""Embedding generator for semantic caching with sentence-transformers."""

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # optional "embeddings" extra; imported lazily at runtime
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings for semantic search using sentence-transformers.

    Features:
    - Local embedding generation (no API calls)
    - 384-dimensional vectors (all-MiniLM-L6-v2)
    - Lazy model loading for fast startup
    - Thread-safe singleton pattern
    - Normalized vectors for cosine similarity
    """

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: str = "cpu"
    ) -> None:
        """
        Initialize embedding generator.

        Args:
            model_name: Hugging Face model identifier
            device: Device to run model on ('cpu', 'cuda', 'mps')
        """
        self.model_name = model_name
        self.device = device
        self._model = None  # Lazy loaded

        logger.info(f"EmbeddingGenerator initialized (model={model_name}, device={device})")

    @property
    def model(self) -> "SentenceTransformer":
        """
        Lazy-load the sentence transformer model.

        Returns:
            SentenceTransformer model
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name, device=self.device)
                logger.info(f"Model loaded successfully on {self.device}")

            except ImportError as e:
                # Optional extra: callers decide how loudly to report it (the cost tracker
                # logs it once and skips caching), so don't log an error on every call here.
                raise ImportError(
                    "sentence-transformers is required for semantic caching "
                    "(install the 'embeddings' extra)"
                ) from e

            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise

        return self._model

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            384-dimensional embedding vector (list of floats)

        Raises:
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        # Normalize text (same as cache normalization)
        normalized_text = " ".join(text.split())

        try:
            # Generate embedding
            embedding = self.model.encode(
                normalized_text,
                convert_to_numpy=True,
                normalize_embeddings=True,  # L2 normalization for cosine similarity
            )

            # Convert to list for JSON serialization
            return embedding.tolist()

        except ImportError:
            raise  # optional extra missing; reported by the caller
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts (batched).

        Args:
            texts: List of input texts

        Returns:
            List of 384-dimensional embedding vectors

        Raises:
            ValueError: If texts list is empty
        """
        if not texts:
            raise ValueError("Cannot generate embeddings for empty list")

        # Normalize all texts
        normalized_texts = [" ".join(text.split()) for text in texts]

        try:
            # Batch encode for efficiency
            embeddings = self.model.encode(
                normalized_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=32,  # Process 32 at a time
                show_progress_bar=len(normalized_texts) > 100,  # Show progress for large batches
            )

            # Convert to list of lists
            return [emb.tolist() for emb in embeddings]

        except ImportError:
            raise  # optional extra missing; reported by the caller
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """
        Get the dimensionality of the embeddings.

        Returns:
            Embedding vector dimension (384 for all-MiniLM-L6-v2)
        """
        # Force model load to get dimension
        return self.model.get_sentence_embedding_dimension()

    def cosine_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Note: Embeddings are already L2-normalized, so cosine similarity
        is just the dot product.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0.0 to 1.0)

        Raises:
            ValueError: If embeddings have different dimensions
        """
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Embedding dimensions don't match: {len(embedding1)} vs {len(embedding2)}"
            )

        # Dot product of normalized vectors = cosine similarity
        similarity = sum(a * b for a, b in zip(embedding1, embedding2, strict=False))

        # Clamp to [0, 1] range (numerical precision)
        return max(0.0, min(1.0, similarity))

    def warmup(self) -> None:
        """
        Warm up the model by generating a test embedding.

        Useful for pre-loading the model at startup to avoid
        cold start latency on first request.
        """
        logger.info("Warming up embedding model...")
        try:
            self.generate_embedding("warmup test")
            logger.info("Model warmup complete")
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")


# ==================== GLOBAL INSTANCE ====================

_embedding_generator: EmbeddingGenerator | None = None


@lru_cache(maxsize=1)
def get_embedding_generator(
    model_name: str | None = None, device: str | None = None
) -> EmbeddingGenerator:
    """
    Get global EmbeddingGenerator instance (singleton).

    Args:
        model_name: Override default model (from EMBEDDING_MODEL env var)
        device: Override device (from EMBEDDING_DEVICE env var or auto-detect)

    Returns:
        EmbeddingGenerator instance
    """
    global _embedding_generator

    if _embedding_generator is None:
        # Get config from environment
        default_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        default_device = os.getenv("EMBEDDING_DEVICE", _detect_device())

        final_model = model_name or default_model
        final_device = device or default_device

        _embedding_generator = EmbeddingGenerator(model_name=final_model, device=final_device)

        logger.info("Global EmbeddingGenerator created")

    return _embedding_generator


def _detect_device() -> str:
    """
    Auto-detect best device for embeddings.

    Returns:
        'cuda', 'mps', or 'cpu'
    """
    try:
        import torch

        if torch.cuda.is_available():
            logger.info("CUDA detected, using GPU for embeddings")
            return "cuda"
        elif torch.backends.mps.is_available():
            logger.info("MPS (Apple Silicon) detected, using GPU for embeddings")
            return "mps"
        else:
            logger.info("No GPU detected, using CPU for embeddings")
            return "cpu"

    except ImportError:
        logger.info("PyTorch not available, defaulting to CPU")
        return "cpu"


def close_embedding_generator() -> None:
    """Release embedding model from memory (cleanup on shutdown)."""
    global _embedding_generator

    if _embedding_generator:
        _embedding_generator._model = None
        _embedding_generator = None
        logger.info("EmbeddingGenerator closed and memory released")

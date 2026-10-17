"""
Swappable embedding providers, all producing L2-normalised 1024-dim vectors.

- bge:    BAAI/bge-large-en-v1.5 via sentence-transformers (local, no API cost)
- openai: text-embedding-3-small with dimensions=1024 (hosted)
- hash:   feature-hashing of words, bigrams and character trigrams. No model,
          no network — for tests and offline demos. Captures lexical overlap only.

Each provider carries its own similarity calibration because raw cosine scales
differ wildly between models (BGE rarely goes below ~0.5; hashing rarely above ~0.6).
"""

import asyncio
import hashlib
import itertools
import logging
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import settings
from app.models.embedding import VECTOR_DIM

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Calibration:
    # Raw cosine → 0-100 relevance: (sim - floor) / (ceiling - floor)
    floor: float
    ceiling: float
    # Skill-to-skill similarity thresholds for semantic skill matching
    skill_match: float
    skill_partial: float
    # Chunk relevance labels
    high: float
    medium: float

    def to_score(self, similarity: float) -> float:
        value = (similarity - self.floor) / (self.ceiling - self.floor)
        return round(max(0.0, min(1.0, value)) * 100, 1)


class Embedder(ABC):
    name: str
    calibration: Calibration

    @abstractmethod
    def _embed(self, texts: list[str], *, is_query: bool) -> list[list[float]]: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed, texts, is_query=False)

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed, texts, is_query=True)


class BGEEmbedder(Embedder):
    name = "bge"
    calibration = Calibration(floor=0.55, ceiling=0.86, skill_match=0.86, skill_partial=0.79, high=0.78, medium=0.68)
    _QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - depends on optional deps
            raise RuntimeError(
                "EMBEDDING_PROVIDER=bge requires `pip install -r requirements-ml.txt`."
            ) from e
        model_name = model_name or "BAAI/bge-large-en-v1.5"
        logger.info("Loading embedding model %s (downloads ~1.3 GB on first run)...", model_name)
        self._model = SentenceTransformer(model_name)
        logger.info("Embedding model loaded.")

    def _embed(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        if is_query:
            texts = [self._QUERY_INSTRUCTION + t for t in texts]
        vectors = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vectors]


class OpenAIEmbedder(Embedder):
    name = "openai"
    calibration = Calibration(floor=0.18, ceiling=0.62, skill_match=0.72, skill_partial=0.58, high=0.5, medium=0.38)
    _URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, model_name: str | None = None) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY.")
        self._model = model_name or "text-embedding-3-small"
        self._client = httpx.Client(
            timeout=60.0, headers={"Authorization": f"Bearer {settings.openai_api_key}"}
        )

    def _embed(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            batch = [t[:8000] or " " for t in texts[i : i + 96]]
            resp = self._client.post(
                self._URL, json={"model": self._model, "input": batch, "dimensions": VECTOR_DIM}
            )
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in data)
        return out


class HashEmbedder(Embedder):
    name = "hash"
    calibration = Calibration(floor=0.04, ceiling=0.42, skill_match=0.78, skill_partial=0.55, high=0.3, medium=0.15)
    _WORD = re.compile(r"[a-z0-9+#.]+")

    def _features(self, text: str) -> dict[str, float]:
        from app.services.skills import canonicalize

        words = [w.strip(".") for w in self._WORD.findall(text.lower())]
        words = [w for w in words if w and w not in _STOPWORDS]
        feats: dict[str, float] = {}
        for w in words:
            feats["w:" + canonicalize(w).lower()] = feats.get("w:" + canonicalize(w).lower(), 0) + 1.0
            padded = f"#{w}#"
            for j in range(len(padded) - 2):
                key = "c:" + padded[j : j + 3]
                feats[key] = feats.get(key, 0) + 0.25
        for a, b in itertools.pairwise(words):
            feats[f"b:{a} {b}"] = feats.get(f"b:{a} {b}", 0) + 0.5
        return feats

    def _embed(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * VECTOR_DIM
            for feat, weight in self._features(text).items():
                digest = hashlib.blake2b(feat.encode(), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % VECTOR_DIM
                sign = 1.0 if digest[4] & 1 else -1.0
                vec[idx] += sign * (1.0 + math.log(weight)) if weight >= 1 else sign * weight
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


_STOPWORDS = {
    "a", "an", "and", "the", "of", "to", "in", "on", "for", "with", "at", "by", "from", "as", "is",
    "are", "was", "were", "be", "been", "or", "that", "this", "it", "its", "we", "you", "our", "your",
    "will", "can", "have", "has", "had", "into", "using", "use", "used", "etc", "also", "such",
}


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    provider = settings.embedding_provider
    if provider == "bge":
        return BGEEmbedder(settings.embedding_model)
    if provider == "openai":
        return OpenAIEmbedder(settings.embedding_model)
    return HashEmbedder()


def cosine(a: list[float], b: list[float]) -> float:
    """Vectors are L2-normalised, so cosine is the dot product."""
    return float(sum(x * y for x, y in zip(a, b, strict=False)))

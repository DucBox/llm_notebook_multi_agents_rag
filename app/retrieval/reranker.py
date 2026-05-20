import asyncio
from functools import lru_cache

from FlagEmbedding import FlagReranker

from app.config import settings


@lru_cache(maxsize=1)
def _load_model() -> FlagReranker:
    return FlagReranker(settings.RERANKER_MODEL, use_fp16=settings.RERANKER_USE_FP16)


async def rerank(query: str, texts: list[str]) -> list[float]:
    """Return normalized relevance scores (0-1) for each (query, text) pair."""
    model = _load_model()
    pairs = [[query, text] for text in texts]
    loop = asyncio.get_event_loop()
    scores: list[float] = await loop.run_in_executor(
        None,
        lambda: model.compute_score(pairs, normalize=True),
    )
    return scores if isinstance(scores, list) else [scores]

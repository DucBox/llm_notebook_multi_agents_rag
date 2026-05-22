import httpx

from app.embeddings.providers.base import BaseEmbeddingProvider


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, base_url: str, model: str = "nomic-embed-text", dimension: int = 768):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        last_exc = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self._base_url}/api/embed",
                        json={"model": self._model, "input": texts},
                    )
                    resp.raise_for_status()
                    return resp.json()["embeddings"]
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc

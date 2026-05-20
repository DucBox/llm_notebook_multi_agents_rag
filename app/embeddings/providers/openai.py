from openai import AsyncOpenAI

from app.embeddings.providers.base import BaseEmbeddingProvider


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimension: int = 1536):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            input=texts,
            model=self._model,
        )
        # OpenAI returns embeddings in the same order as input
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

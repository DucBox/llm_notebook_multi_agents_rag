from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension this provider produces."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

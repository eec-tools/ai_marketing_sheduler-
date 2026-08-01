from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class for AI providers. Add new providers by implementing this interface."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Generate text content from a prompt."""
        ...

    @abstractmethod
    async def generate_image(self, prompt: str, size: str = "square") -> bytes:
        """Generate an image from a prompt. Returns raw bytes."""
        ...

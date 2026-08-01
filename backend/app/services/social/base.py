from abc import ABC, abstractmethod


class SocialPlatform(ABC):
    """Abstract base for social media platforms. Add new platforms by implementing this interface."""

    @abstractmethod
    async def publish_post(self, caption: str, image_url: str) -> dict:
        """Publish a post. Returns platform response with post ID."""
        ...

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Verify the access token is still valid."""
        ...

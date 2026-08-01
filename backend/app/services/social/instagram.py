import httpx
from app.services.social.base import SocialPlatform


class InstagramService(SocialPlatform):
    """Instagram Graph API publishing service."""

    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, ig_user_id: str):
        self.access_token = access_token
        self.ig_user_id = ig_user_id

    async def verify_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.GRAPH_URL}/{self.ig_user_id}",
                params={"fields": "id,name", "access_token": self.access_token}
            )
            return resp.status_code == 200

    async def publish_post(self, caption: str, image_url: str = None) -> dict:
        """Publish to Instagram using two-step container + publish flow."""
        if not image_url:
            raise ValueError("Instagram requires an image URL")

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Create media container
            container_resp = await client.post(
                f"{self.GRAPH_URL}/{self.ig_user_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.access_token
                }
            )
            container_resp.raise_for_status()
            container_id = container_resp.json().get("id")

            # Step 2: Publish the container
            publish_resp = await client.post(
                f"{self.GRAPH_URL}/{self.ig_user_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.access_token
                }
            )
            publish_resp.raise_for_status()
            post_id = publish_resp.json().get("id")

        return {"platform_post_id": post_id, "status": "published"}

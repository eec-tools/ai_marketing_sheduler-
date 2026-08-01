import httpx
from app.services.social.base import SocialPlatform


class LinkedInService(SocialPlatform):
    """LinkedIn posting service using the LinkedIn API v2."""

    API_BASE = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str, person_urn: str):
        self.access_token = access_token
        self.person_urn = person_urn  # urn:li:person:{id}
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    async def verify_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/userinfo", headers=self.headers)
            return resp.status_code == 200

    async def upload_image(self, image_url: str) -> str:
        """Upload image to LinkedIn and return asset URN."""
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Register upload
            register_resp = await client.post(
                f"{self.API_BASE}/assets?action=registerUpload",
                headers=self.headers,
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": self.person_urn,
                        "serviceRelationships": [{
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }]
                    }
                }
            )
            register_data = register_resp.json()
            upload_url = register_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset = register_data["value"]["asset"]

            # Step 2: Download image and upload it
            if image_url.startswith("data:"):
                import base64
                header, encoded = image_url.split(",", 1)
                img_content = base64.b64decode(encoded)
            else:
                img_resp = await client.get(image_url)
                img_content = img_resp.content

            await client.put(
                upload_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                content=img_content
            )

        return asset

    async def publish_post(self, caption: str, image_url: str = None) -> dict:
        """Publish a post to LinkedIn."""
        async with httpx.AsyncClient(timeout=30) as client:
            post_data = {
                "author": self.person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": caption},
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
            }

            if image_url:
                asset = await self.upload_image(image_url)
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "description": {"text": "Post image"},
                    "media": asset,
                    "title": {"text": ""}
                }]

            resp = await client.post(
                f"{self.API_BASE}/ugcPosts",
                headers=self.headers,
                json=post_data
            )
            resp.raise_for_status()
            return {"platform_post_id": resp.headers.get("x-restli-id", ""), "status": "published"}

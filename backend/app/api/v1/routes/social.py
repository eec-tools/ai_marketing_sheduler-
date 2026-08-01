from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid, secrets, httpx

from app.core.database import get_db
from app.core.security import encrypt_value, decrypt_value
from app.core.config import settings
from app.models.models import User, ConnectedAccount
from app.schemas.schemas import ConnectedAccountOut, OAuthUrlResponse, MessageResponse
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/social", tags=["Social Accounts"])

# In-memory state store (use Redis in production)
_oauth_states: dict = {}


@router.get("", response_model=List[ConnectedAccountOut])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ConnectedAccount).where(ConnectedAccount.user_id == current_user.id))
    return result.scalars().all()


# ─── LinkedIn ─────────────────────────────────────────────────────────────────

@router.get("/linkedin/auth-url", response_model=OAuthUrlResponse)
async def linkedin_auth_url(current_user: User = Depends(get_current_user)):
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = current_user.id

    scope = "openid profile email w_member_social"
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={settings.LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
        f"&scope={scope}"
        f"&state={state}"
    )
    return OAuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    user_id = _oauth_states.pop(state, None)
    if not user_id:
        raise HTTPException(400, "Invalid OAuth state")

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange LinkedIn token")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Get profile info
        profile_resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        profile = profile_resp.json()

    # Upsert connected account
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.platform == "linkedin"
        )
    )
    account = result.scalar_one_or_none()

    if account:
        account.access_token = encrypt_value(access_token)
        account.platform_user_id = profile.get("sub")
        account.platform_username = profile.get("name")
        account.status = "connected"
    else:
        account = ConnectedAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            platform="linkedin",
            access_token=encrypt_value(access_token),
            platform_user_id=profile.get("sub"),
            platform_username=profile.get("name"),
            status="connected"
        )
        db.add(account)

    await db.commit()
    username = profile.get("name") or "User"
    return HTMLResponse(content=f"""
    <html>
    <head><title>LinkedIn Connected</title></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; text-align: center; padding: 40px; background: #f8fafc;">
        <div style="max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="font-size: 48px; margin-bottom: 16px;">🎉</div>
            <h2 style="color: #0f172a; margin: 0 0 8px 0;">LinkedIn Connected!</h2>
            <p style="color: #64748b; font-size: 14px; margin: 0 0 20px 0;">Welcome, <strong>{username}</strong>. You can now publish right from your dashboard.</p>
            <div style="color: #16a34a; font-weight: 500; font-size: 13px;">Closing popup window...</div>
        </div>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'SOCIAL_CONNECTED', platform: 'linkedin' }}, '*');
            }}
            setTimeout(() => window.close(), 1500);
        </script>
    </body>
    </html>
    """)


@router.delete("/linkedin", response_model=MessageResponse)
async def disconnect_linkedin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.platform == "linkedin"
        )
    )
    account = result.scalar_one_or_none()
    if account:
        await db.delete(account)
    return MessageResponse(message="LinkedIn disconnected")

from pydantic import BaseModel
class PageIdUpdate(BaseModel):
    page_id: str

@router.patch("/{platform}/page", response_model=ConnectedAccountOut)
async def update_platform_page_id(
    platform: str,
    req: PageIdUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.platform == platform
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, f"{platform.capitalize()} account not connected")
    
    account.platform_page_id = req.page_id if req.page_id.strip() else None
    await db.commit()
    await db.refresh(account)
    return account


# ─── Instagram ────────────────────────────────────────────────────────────────

@router.get("/instagram/auth-url", response_model=OAuthUrlResponse)
async def instagram_auth_url(current_user: User = Depends(get_current_user)):
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = current_user.id

    scope = "instagram_basic,instagram_content_publish,pages_show_list"
    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth"
        f"?client_id={settings.INSTAGRAM_CLIENT_ID}"
        f"&redirect_uri={settings.INSTAGRAM_REDIRECT_URI}"
        f"&scope={scope}"
        f"&state={state}"
        f"&response_type=code"
    )
    return OAuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/instagram/callback")
async def instagram_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    user_id = _oauth_states.pop(state, None)
    if not user_id:
        raise HTTPException(400, "Invalid OAuth state")

    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": settings.INSTAGRAM_CLIENT_ID,
                "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
                "redirect_uri": settings.INSTAGRAM_REDIRECT_URI,
                "code": code,
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange Instagram token")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Get Instagram Business Account automatically via /me/accounts
        accounts_resp = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"fields": "instagram_business_account,name", "access_token": access_token}
        )
        accounts_data = accounts_resp.json().get("data", [])
        insta_account_id = None
        insta_username = "Instagram Account"

        for page in accounts_data:
            if page.get("instagram_business_account"):
                insta_account_id = page["instagram_business_account"].get("id")
                insta_username = page.get("name", "Instagram Business")
                break

        if not insta_account_id:
            # Fallback to basic profile ID if no business account linked
            me_resp = await client.get(
                "https://graph.facebook.com/v19.0/me",
                params={"fields": "id,name", "access_token": access_token}
            )
            profile = me_resp.json()
            insta_account_id = profile.get("id")
            insta_username = profile.get("name")

    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.platform == "instagram"
        )
    )
    account = result.scalar_one_or_none()

    if account:
        account.access_token = encrypt_value(access_token)
        account.platform_user_id = insta_account_id
        account.platform_username = insta_username
        account.status = "connected"
    else:
        account = ConnectedAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            platform="instagram",
            access_token=encrypt_value(access_token),
            platform_user_id=insta_account_id,
            platform_username=insta_username,
            status="connected"
        )
        db.add(account)

    await db.commit()
    username = profile.get("name") or "Account"
    return HTMLResponse(content=f"""
    <html>
    <head><title>Instagram Connected</title></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; text-align: center; padding: 40px; background: #f8fafc;">
        <div style="max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="font-size: 48px; margin-bottom: 16px;">🎉</div>
            <h2 style="color: #0f172a; margin: 0 0 8px 0;">Instagram Connected!</h2>
            <p style="color: #64748b; font-size: 14px; margin: 0 0 20px 0;">Connected account: <strong>{username}</strong></p>
            <div style="color: #16a34a; font-weight: 500; font-size: 13px;">Closing popup window...</div>
        </div>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'SOCIAL_CONNECTED', platform: 'instagram' }}, '*');
            }}
            setTimeout(() => window.close(), 1500);
        </script>
    </body>
    </html>
    """)


@router.delete("/instagram", response_model=MessageResponse)
async def disconnect_instagram(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.platform == "instagram"
        )
    )
    account = result.scalar_one_or_none()
    if account:
        await db.delete(account)
    return MessageResponse(message="Instagram disconnected")

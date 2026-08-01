"""
Professional Social Media Card Generator
Uses Pillow to render pixel-perfect, branded image cards.
Supports custom logos, brand colors, and 3 templates.
No external API required — 100% free.
"""
import io
import base64 as _b64
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

FONT_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REGULAR = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

SIZE_MAP = {
    "square":    (1080, 1080),
    "portrait":  (1080, 1920),
    "landscape": (1920, 1080),
}


def _load_font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fetch_logo(logo_url: str, target_size: int = 120) -> Image.Image | None:
    """Fetch logo from a URL or base64 data URI, return square RGBA Pillow image."""
    if not logo_url:
        return None
    try:
        # Handle base64 data URIs: data:image/png;base64,xxxx
        if logo_url.startswith("data:"):
            header, data = logo_url.split(",", 1)
            img_bytes = _b64.b64decode(data)
        else:
            import urllib.request
            with urllib.request.urlopen(logo_url, timeout=5) as r:
                img_bytes = r.read()

        logo = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # Make it square by padding, then resize
        max_dim = max(logo.size)
        square = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        offset = ((max_dim - logo.size[0]) // 2, (max_dim - logo.size[1]) // 2)
        square.paste(logo, offset, logo)
        logo = square.resize((target_size, target_size), Image.LANCZOS)
        return logo
    except Exception:
        return None


def _paste_logo(img: Image.Image, logo: Image.Image, x: int, y: int):
    """Paste logo onto card with alpha compositing."""
    if logo is None:
        return
    try:
        if img.mode != "RGBA":
            img_rgba = img.convert("RGBA")
        else:
            img_rgba = img
        img_rgba.paste(logo, (x, y), logo)
        # Convert back to RGB if needed
        if img.mode == "RGB":
            rgb = Image.new("RGB", img_rgba.size, (255, 255, 255))
            rgb.paste(img_rgba, mask=img_rgba.split()[3])
            img.paste(rgb)
        else:
            img.paste(img_rgba)
    except Exception:
        pass


def _extract_search_keywords(query: str) -> str:
    """
    Extract meaningful visual keywords from a topic or headline string.
    Removes stopwords and returns a concise search string.
    """
    if not query or not isinstance(query, str):
        return "business professional"
    
    # Common English stopwords and abstract terms less useful for photo search
    stopwords = {
        "a", "an", "the", "and", "or", "for", "in", "of", "to", "is", "are", "that",
        "with", "on", "at", "by", "our", "your", "we", "it", "from", "as", "be",
        "how", "why", "what", "when", "where", "who", "will", "can", "should",
        "must", "do", "does", "did", "have", "has", "had", "this", "these", "those",
        "about", "into", "through", "during", "before", "after", "above", "below",
        "up", "down", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "all", "any", "both", "each", "few", "more", "most",
        "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "s", "t", "just", "don", "now", "d", "ll", "m", "o",
        "re", "ve", "y", "scale", "boost", "grow", "growing", "make", "take", "get",
        "using", "used", "uses"
    }
    
    import re
    # Strip punctuation and split
    words = re.findall(r'[a-zA-Z]{3,}', query.lower())
    keywords = [w for w in words if w not in stopwords]
    
    # Take up to 4 most relevant keywords
    return " ".join(keywords[:4]) if keywords else "business office"


def _fetch_background_photo(query: str, W: int, H: int) -> Image.Image | None:
    """
    Multi-tier keyword photo fetcher using web scraping + reliable fallbacks:
    - Tier 1A: Bing Images web scraping (extracts direct high-res image URLs)
    - Tier 1B: Flickr Public Tag Feed search (no API key required)
    - Tier 2: Picsum Photos fallback (high-res stable seed fallback)
    Returns a PIL Image resized to WxH, or None on complete failure.
    """
    import httpx, re, urllib.parse, hashlib, logging

    search_query = _extract_search_keywords(query)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # Helper to download and validate image bytes into a resized RGB PIL Image
    def _download_and_process(img_url: str, client: httpx.Client) -> Image.Image | None:
        try:
            r = client.get(img_url, headers=headers, timeout=6)
            if r.status_code == 200 and len(r.content) > 5000:
                photo = Image.open(io.BytesIO(r.content)).convert("RGB")
                photo = photo.resize((W, H), Image.LANCZOS)
                return photo
        except Exception:
            pass
        return None

    with httpx.Client(timeout=8, follow_redirects=True) as client:
        # ─── TIER 1A: Bing Images Web Scraper ────────────────────────────────
        try:
            bing_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(search_query)}&first=1"
            res = client.get(bing_url, headers=headers)
            if res.status_code == 200:
                # Find direct image URLs inside murl JSON fields or HTML encoded strings
                urls = re.findall(r'\"murl\":\"(https?://[^\"]+)\"', res.text) or \
                       re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', res.text)
                
                # Filter out suspicious or tiny icons, prefer jpg/png
                valid_urls = [u for u in urls if any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png"))][:4]
                for u in valid_urls:
                    photo = _download_and_process(u, client)
                    if photo:
                        logging.info(f"Successfully scraped Bing image for query '{search_query}'")
                        return photo
        except Exception as e:
            logging.debug(f"Bing scraper attempt failed: {e}")

        # ─── TIER 1B: Flickr Public Tag Feed Scraper ─────────────────────────
        try:
            # Flickr public feed accepts comma-separated tags
            flickr_tags = ",".join(search_query.split()[:3])
            flickr_url = f"https://www.flickr.com/services/feeds/photos_public.gne?tags={urllib.parse.quote(flickr_tags)}&format=json&nojsoncallback=1"
            res = client.get(flickr_url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])[:4]
                for item in items:
                    # Replace _m.jpg (small thumbnail) with _b.jpg (large 1024px version)
                    img_url = item.get("media", {}).get("m", "").replace("_m.jpg", "_b.jpg")
                    if img_url:
                        photo = _download_and_process(img_url, client)
                        if photo:
                            logging.info(f"Successfully scraped Flickr image for query '{search_query}'")
                            return photo
        except Exception as e:
            logging.debug(f"Flickr feed attempt failed: {e}")

        # ─── TIER 2: Picsum Photos Fallback ──────────────────────────────────
        try:
            seed = int(hashlib.md5(search_query.encode()).hexdigest(), 16) % 1000
            picsum_url = f"https://picsum.photos/seed/{seed}/{W}/{H}"
            res = client.get(picsum_url, headers=headers)
            if res.status_code == 200 and len(res.content) > 5000:
                photo = Image.open(io.BytesIO(res.content)).convert("RGB")
                photo = photo.resize((W, H), Image.LANCZOS)
                logging.info(f"Used Picsum fallback for query '{search_query}'")
                return photo
        except Exception as e:
            logging.warning(f"All background photo fetches failed: {e}")

    # Tier 3: Returns None so templates fall back to solid brand gradients
    return None



def _apply_overlay(img: Image.Image, primary: tuple, style: str = "dark") -> Image.Image:
    """
    Apply a semi-transparent overlay so text stays readable over a photo.
    Returns a new RGB image with overlay applied.
    """
    overlay = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(overlay)

    if style == "dark":
        # Dark gradient overlay from bottom-heavy
        for y in range(img.size[1]):
            t = y / img.size[1]
            # More opaque at bottom, lighter at top
            alpha = int(100 + 120 * t)
            draw.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, alpha))
    elif style == "brand":
        # Brand-color tinted overlay
        r, g, b = primary
        alpha = 175
        draw.rectangle([0, 0, img.size[0], img.size[1]], fill=(r, g, b, alpha))
    elif style == "split":
        # Dark bottom half
        H = img.size[1]
        draw.rectangle([0, H // 2, img.size[0], H], fill=(0, 0, 0, 190))
        draw.rectangle([0, 0, img.size[0], H // 2], fill=(0, 0, 0, 80))

    img_rgba = img.convert("RGBA")
    composited = Image.alpha_composite(img_rgba, overlay)
    return composited.convert("RGB")


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _darken(rgb, factor=0.5):
    return tuple(max(0, int(c * factor)) for c in rgb)


def _lighten(rgb, factor=1.5):
    return tuple(min(255, int(c * factor)) for c in rgb)


def _blend(c1, c2, t):
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textlength(test, font=font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ─── TEMPLATE 1: Professional Dark ────────────────────────────────────────────
def _render_professional(W, H, headline, topic, brand_name, cta, primary, secondary, logo=None):
    # Try to get a real stock photo background from Unsplash
    bg_query = f"{topic or headline} business professional"
    photo = _fetch_background_photo(bg_query, W, H)

    if photo:
        # Apply dark overlay so text is readable
        img = _apply_overlay(photo, primary, style="dark")
    else:
        # Fallback: solid dark gradient
        img = Image.new("RGB", (W, H))
        draw_bg = ImageDraw.Draw(img)
        dark_top, dark_bot = (8, 12, 24), (18, 26, 50)
        for y in range(H):
            t = y / H
            draw_bg.line([(0, y), (W, y)], fill=_blend(dark_top, dark_bot, t))

    draw = ImageDraw.Draw(img, "RGBA")

    # Top accent bar
    bar_h = max(10, H // 100)
    draw.rectangle([0, 0, W, bar_h], fill=primary)

    # Logo + Brand name row
    logo_size = max(72, H // 14)
    row_y = bar_h + 36
    col_x = 60
    if logo:
        logo_img = _fetch_logo(logo, logo_size) if isinstance(logo, str) else logo
        if logo_img:
            _paste_logo(img, logo_img, col_x, row_y)
            col_x += logo_size + 18

    font_brand = _load_font(FONT_BOLD, max(30, H // 34))
    draw = ImageDraw.Draw(img)  # redraw after paste
    brand_y = row_y + (logo_size - font_brand.size) // 2 if logo else row_y
    draw.text((col_x, brand_y), (brand_name or "YOUR BRAND").upper(), font=font_brand, fill=primary)

    # Headline
    h_size = max(76, H // 12) if len(headline) < 40 else max(58, H // 16)
    font_h = _load_font(FONT_BOLD, h_size)
    lines = _wrap_text(headline.upper(), font_h, W - 120, draw)
    line_gap = int(h_size * 0.28)
    total_h = len(lines) * (h_size + line_gap)
    start_y = (H - total_h) // 2 - int(H * 0.04)

    for i, line in enumerate(lines):
        y = start_y + i * (h_size + line_gap)
        draw.text((62, y + 4), line, font=font_h, fill=(0, 0, 0, 100))  # shadow
        draw.text((60, y), line, font=font_h, fill=(255, 255, 255))

    # Underline accent
    ul_y = start_y + total_h + 22
    draw.rectangle([60, ul_y, 60 + 220, ul_y + 6], fill=primary)

    # Subtext
    if topic:
        font_sub = _load_font(FONT_REGULAR, max(30, H // 34))
        sub_lines = _wrap_text(topic, font_sub, W - 120, draw)[:3]
        sub_y = ul_y + 40
        for sl in sub_lines:
            draw.text((60, sub_y), sl, font=font_sub, fill=(175, 195, 220, 210))
            sub_y += int(font_sub.size * 1.5)

    # CTA bar
    cta_h = max(95, H // 10)
    draw.rectangle([0, H - cta_h, W, H], fill=primary)
    font_cta = _load_font(FONT_BOLD, max(30, H // 34))
    cta_text = cta or "Learn More →"
    draw.text((60, H - cta_h + (cta_h - font_cta.size) // 2), cta_text, font=font_cta, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


# ─── TEMPLATE 2: Minimal Clean ────────────────────────────────────────────────
def _render_minimal(W, H, headline, topic, brand_name, cta, primary, secondary, logo=None):
    # Get stock photo for a soft blurred background
    bg_query = f"{topic or headline} minimal clean modern"
    photo = _fetch_background_photo(bg_query, W, H)

    if photo:
        # Blur + bright overlay so it feels minimal/light
        photo_blur = photo.filter(ImageFilter.GaussianBlur(18))
        img = _apply_overlay(photo_blur, primary, style="brand")
        # Blend with white for a light feel
        white = Image.new("RGB", (W, H), (255, 255, 255))
        img = Image.blend(img, white, alpha=0.55)
    else:
        img = Image.new("RGB", (W, H), (250, 250, 252))

    draw = ImageDraw.Draw(img, "RGBA")

    # Light subtle grid lines
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(235, 235, 242, 60))

    # Left accent strip
    strip_w = max(18, W // 55)
    draw.rectangle([0, 0, strip_w, H], fill=primary)

    # Top decorative corner
    for i in range(5):
        r = (i + 1) * 50
        draw.arc([W - r - 80, -r, W + r - 80, r + 80], start=90, end=180,
                 fill=(*primary, 15 + i * 8), width=2)

    # Logo + Brand name row
    logo_size = max(64, H // 16)
    lx = strip_w + 55
    ly = 55
    if logo:
        logo_img = _fetch_logo(logo, logo_size) if isinstance(logo, str) else logo
        if logo_img:
            _paste_logo(img, logo_img, lx, ly)
            lx += logo_size + 16

    draw = ImageDraw.Draw(img)
    font_brand = _load_font(FONT_BOLD, max(28, H // 38))
    brand_y = ly + (logo_size - font_brand.size) // 2 if logo else ly
    draw.text((lx, brand_y), (brand_name or "YOUR BRAND").upper(), font=font_brand, fill=primary)

    # Headline
    h_size = max(82, H // 11) if len(headline) < 35 else max(62, H // 14)
    font_h = _load_font(FONT_BOLD, h_size)
    max_w = W - strip_w - 110
    lines = _wrap_text(headline, font_h, max_w, draw)
    gap = int(h_size * 0.25)
    total_h = len(lines) * (h_size + gap)
    start_y = (H - total_h) // 2 - int(H * 0.03)

    for i, line in enumerate(lines):
        y = start_y + i * (h_size + gap)
        draw.text((strip_w + 55, y), line, font=font_h, fill=(20, 24, 38))

    # Underline
    ul_y = start_y + total_h + 20
    draw.rectangle([strip_w + 55, ul_y, strip_w + 55 + 130, ul_y + 7], fill=primary)

    # Subtext
    if topic:
        font_sub = _load_font(FONT_REGULAR, max(28, H // 36))
        sub_lines = _wrap_text(topic, font_sub, max_w, draw)[:3]
        sub_y = ul_y + 35
        for sl in sub_lines:
            draw.text((strip_w + 55, sub_y), sl, font=font_sub, fill=(100, 110, 130, 220))
            sub_y += int(font_sub.size * 1.5)

    # CTA pill button
    font_cta = _load_font(FONT_BOLD, max(28, H // 36))
    cta_text = cta or "Discover More →"
    cta_w = int(draw.textlength(cta_text, font=font_cta)) + 70
    cx = strip_w + 55
    cy = H - 105
    draw.rounded_rectangle([cx, cy, cx + cta_w, cy + font_cta.size + 28], radius=35, fill=primary)
    draw.text((cx + 35, cy + 14), cta_text, font=font_cta, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


# ─── TEMPLATE 3: Corporate Split ──────────────────────────────────────────────
def _render_corporate(W, H, headline, topic, brand_name, cta, primary, secondary, logo=None):
    # Photo on right panel, solid color on left
    bg_query = f"{topic or headline} office corporate business"
    photo = _fetch_background_photo(bg_query, W, H)

    if photo:
        base = photo.copy()
    else:
        base = Image.new("RGB", (W, H), (255, 255, 255))

    img = base
    draw = ImageDraw.Draw(img, "RGBA")

    # Left panel
    split = int(W * 0.40)
    draw.polygon([(0, 0), (split + int(W * 0.07), 0),
                  (split - int(W * 0.03), H), (0, H)], fill=primary)

    # Left panel texture
    light = _lighten(primary, 1.3)
    for i in range(0, split + 100, 55):
        draw.line([(i, 0), (i - 55, H)], fill=(*light, 20))

    # Logo on left panel (top)
    logo_size = max(70, H // 14)
    lx, ly = 50, 55
    if logo:
        logo_img = _fetch_logo(logo, logo_size) if isinstance(logo, str) else logo
        if logo_img:
            _paste_logo(img, logo_img, lx, ly)
            lx += logo_size + 16
            ly += (logo_size - max(32, H // 32)) // 2

    draw = ImageDraw.Draw(img)
    font_brand = _load_font(FONT_BOLD, max(32, H // 32))
    brand_lines = _wrap_text((brand_name or "YOUR BRAND").upper(), font_brand, split - 80, draw)
    by = ly
    for bl in brand_lines:
        draw.text((lx, by), bl, font=font_brand, fill=(255, 255, 255, 230))
        by += int(font_brand.size * 1.3)    

    # Left panel decorative circles
    dark_p = _darken(primary, 0.65)
    draw.ellipse([-100, H - 300, 220, H + 100], fill=(*dark_p, 80))

    # Topic tag on left panel
    if topic:
        font_tag = _load_font(FONT_REGULAR, max(24, H // 44))
        tag_lines = _wrap_text(topic[:60], font_tag, split - 80, draw)[:3]
        ty = H - 190
        for tl in tag_lines:
            draw.text((50, ty), tl, font=font_tag, fill=(255, 255, 255, 165))
            ty += int(font_tag.size * 1.45)

    # Right panel headline
    right_x = split + int(W * 0.08)
    right_w = W - right_x - 60
    h_size = max(70, H // 12) if len(headline) < 35 else max(54, H // 16)
    font_h = _load_font(FONT_BOLD, h_size)
    h_lines = _wrap_text(headline, font_h, right_w, draw)
    gap = int(h_size * 0.28)
    total_h = len(h_lines) * (h_size + gap)
    start_y = (H - total_h) // 2 - int(H * 0.03)

    for i, line in enumerate(h_lines):
        y = start_y + i * (h_size + gap)
        draw.text((right_x, y), line, font=font_h, fill=(18, 22, 40))

    ul_y = start_y + total_h + 22
    draw.rectangle([right_x, ul_y, right_x + 110, ul_y + 6], fill=primary)

    # CTA
    font_cta = _load_font(FONT_BOLD, max(28, H // 36))
    cta_text = cta or "Get in Touch →"
    draw.text((right_x, H - 110), cta_text, font=font_cta, fill=primary)

    # Right edge accent
    draw.rectangle([W - 14, 0, W, H], fill=primary)

    # Right panel: darken the photo where headline sits
    if photo:
        right_x_start = int(W * 0.43)
        fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fade)
        fd.rectangle([right_x_start, 0, W, H], fill=(0, 0, 0, 130))
        img_rgba = img.convert("RGBA")
        img = Image.alpha_composite(img_rgba, fade).convert("RGB")
        draw = ImageDraw.Draw(img)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


# ─── PUBLIC ENTRY POINT ───────────────────────────────────────────────────────
def generate_card(
    headline: str,
    topic: str = "",
    brand_name: str = "Your Brand",
    cta: str = "Learn More →",
    primary_color: str = "#2563EB",
    secondary_color: str = "#64748B",
    style: str = "professional",
    size: str = "square",
    logo_url: str = None,
) -> bytes:
    """
    Generate a professional social media image card using Pillow.
    Returns PNG bytes. No API key required.

    Args:
        logo_url: Optional URL or base64 data URI of your brand logo.
                  Accepts http/https URLs and data:image/... URIs.
    """
    W, H = SIZE_MAP.get(size, (1080, 1080))
    primary = _hex_to_rgb(primary_color or "#2563EB")
    secondary = _hex_to_rgb(secondary_color or "#64748B")

    headline = (headline or "Your Headline Here").strip()
    topic = (topic or "").strip()
    brand_name = (brand_name or "Your Brand").strip()
    cta = (cta or "Learn More →").strip()

    # Pre-fetch the logo once so all templates share the same object
    logo_size = max(80, H // 13)
    logo_img = _fetch_logo(logo_url, logo_size) if logo_url else None

    if style == "minimal":
        return _render_minimal(W, H, headline, topic, brand_name, cta, primary, secondary, logo=logo_img)
    elif style == "corporate":
        return _render_corporate(W, H, headline, topic, brand_name, cta, primary, secondary, logo=logo_img)
    else:
        return _render_professional(W, H, headline, topic, brand_name, cta, primary, secondary, logo=logo_img)

# ─── LOGO COMPOSITOR (for AI-generated images) ────────────────────────────────
def composite_logo_on_image(
    image_data: str | bytes,
    logo_url: str,
    position: str = "top-left",
    logo_size_pct: float = 0.12,
    padding_pct: float = 0.04,
) -> str:
    """
    Composite the brand logo on top of any existing image (AI-generated or otherwise).
    Returns a base64 data URI string.

    Args:
        image_data: Either a base64 data URI string (data:image/...;base64,...) or raw bytes.
        logo_url:   Brand logo as a URL or base64 data URI.
        position:   One of: "top-left", "top-right", "bottom-left", "bottom-right"
        logo_size_pct: Logo size as fraction of image width (default 12%)
        padding_pct:   Padding from edges as fraction of image width (default 4%)
    Returns:
        A data URI string with the logo composited on top.
    """
    import base64 as _b64_local

    # ── Decode the base image ──────────────────────────────────────────────────
    if isinstance(image_data, str):
        if image_data.startswith("data:"):
            _, raw = image_data.split(",", 1)
            img_bytes = _b64_local.b64decode(raw)
        else:
            img_bytes = _b64_local.b64decode(image_data)
    else:
        img_bytes = image_data

    try:
        base_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except Exception:
        # If we can't open the image, return unchanged
        if isinstance(image_data, str):
            return image_data
        return f"data:image/png;base64,{_b64_local.b64encode(img_bytes).decode()}"

    W, H = base_img.size
    logo_px = max(64, int(W * logo_size_pct))
    pad = max(24, int(W * padding_pct))

    # ── Load and resize the logo ───────────────────────────────────────────────
    logo_img = _fetch_logo(logo_url, logo_px)
    if logo_img is None:
        # Nothing to composite; return original unchanged
        if isinstance(image_data, str):
            return image_data
        return f"data:image/png;base64,{_b64_local.b64encode(img_bytes).decode()}"

    # ── Determine position ─────────────────────────────────────────────────────
    lw, lh = logo_img.size
    if position == "top-right":
        x, y = W - lw - pad, pad
    elif position == "bottom-left":
        x, y = pad, H - lh - pad
    elif position == "bottom-right":
        x, y = W - lw - pad, H - lh - pad
    else:  # top-left (default)
        x, y = pad, pad

    # ── Add a subtle white "backing pill" for logo visibility on any background
    backing_pad = 10
    backing = Image.new("RGBA", (lw + backing_pad * 2, lh + backing_pad * 2), (255, 255, 255, 200))
    # Paste backing
    base_img.paste(backing, (x - backing_pad, y - backing_pad), backing)

    # ── Paste the actual logo ──────────────────────────────────────────────────
    base_img.paste(logo_img, (x, y), logo_img)

    # ── Encode back to base64 data URI ────────────────────────────────────────
    buf = io.BytesIO()
    final = base_img.convert("RGB")
    final.save(buf, format="JPEG", quality=90, optimize=True)
    encoded = _b64_local.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


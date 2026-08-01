from PIL import Image
import io
import re


class ImageReviewService:
    """
    Reviews generated images for quality before publishing.
    Uses Pillow for heuristic checks.
    """

    MIN_WIDTH = 600
    MIN_HEIGHT = 600
    MIN_BRIGHTNESS = 30   # 0-255 scale
    MAX_BRIGHTNESS = 230
    VALID_ASPECT_RATIOS = {
        "square": (0.9, 1.1),      # ~1:1
        "portrait": (0.5, 0.65),   # ~9:16
        "landscape": (1.7, 1.9),   # ~16:9
    }

    def review(self, image_bytes: bytes, expected_size: str = "square") -> dict:
        """
        Run heuristic image review.
        Returns: {"result": "PASS"|"FAIL", "issues": [...], "score": 0-10}
        """
        issues = []

        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            return {"result": "FAIL", "issues": [f"Cannot open image: {e}"], "score": 0}

        width, height = img.size

        # Check minimum dimensions
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            issues.append(f"Image too small: {width}x{height}px (minimum {self.MIN_WIDTH}x{self.MIN_HEIGHT})")

        # Check aspect ratio
        ratio = width / height
        expected_range = self.VALID_ASPECT_RATIOS.get(expected_size, (0.9, 1.1))
        if not (expected_range[0] <= ratio <= expected_range[1]):
            issues.append(f"Aspect ratio {ratio:.2f} doesn't match expected {expected_size}")

        # Check brightness (not too dark or too light)
        if img.mode != "RGB":
            img = img.convert("RGB")

        grayscale = img.convert("L")
        import statistics
        pixels = list(grayscale.getdata())
        avg_brightness = statistics.mean(pixels)

        if avg_brightness < self.MIN_BRIGHTNESS:
            issues.append(f"Image too dark (brightness: {avg_brightness:.0f})")
        elif avg_brightness > self.MAX_BRIGHTNESS:
            issues.append(f"Image too bright/washed out (brightness: {avg_brightness:.0f})")

        # Check file size (should be > 10KB to ensure actual content)
        if len(image_bytes) < 10_000:
            issues.append("Image file size too small — may be corrupted or empty")

        score = max(0, 10 - (len(issues) * 3))
        result = "PASS" if not issues else "FAIL"

        return {
            "result": result,
            "issues": issues,
            "score": score,
            "width": width,
            "height": height,
            "brightness": round(avg_brightness, 1),
            "file_size_kb": round(len(image_bytes) / 1024, 1)
        }

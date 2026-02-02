import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageOps
from scipy import ndimage

# Initialize PaddleOCR once at module level (lazy loading)
_ocr_instance = None


def _get_ocr():
    """Get or create the PaddleOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
    return _ocr_instance

# Timer region containing both RTA and IGT lines (top-right)
# Format: (left, top, right, bottom) as percentages of image dimensions
DEFAULT_TIMER_REGION = (0.80, 0.01, 0.995, 0.11)


def crop_timer_region(
    image: Image.Image,
    region: tuple[float, float, float, float] = DEFAULT_TIMER_REGION,
) -> Image.Image:
    """Crop the timer region from the frame."""
    width, height = image.size
    left = int(width * region[0])
    top = int(height * region[1])
    right = int(width * region[2])
    bottom = int(height * region[3])
    return image.crop((left, top, right, bottom))


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.

    The timer overlay has two lines:
    - RTA (cyan): high G and B, lower R
    - IGT (yellow/gold): high R and G, lower B

    Pipeline: color extraction -> dilate -> scale -> invert
    """
    arr = np.array(image)
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)

    # Cyan mask (RTA): high G and B, lower R
    cyan_mask = (g > 180) & (b > 180) & (r < 180)

    # Yellow mask (IGT): high R and G, lower B
    yellow_mask = (r > 150) & (g > 150) & (b < 200) & (r + g > 350)

    # Combine both color masks
    combined_mask = cyan_mask | yellow_mask

    # Dilate to connect fragmented pixels
    dilated = ndimage.binary_dilation(combined_mask, iterations=1)
    dilated_img = Image.fromarray((dilated * 255).astype(np.uint8))

    # Scale up with LANCZOS for smoothing
    scaled = dilated_img.resize(
        (dilated_img.width * 3, dilated_img.height * 3), Image.Resampling.LANCZOS
    )

    # Threshold and invert (black text on white background for Tesseract)
    arr2 = np.array(scaled)
    inverted = 255 - (arr2 > 128) * 255

    # Add padding
    padded = ImageOps.expand(
        Image.fromarray(inverted.astype(np.uint8)), border=20, fill=255
    )

    return padded


def extract_timer_text(image: Image.Image) -> str:
    """Run PaddleOCR on the preprocessed image."""
    ocr = _get_ocr()
    # PaddleOCR expects numpy array or file path
    img_array = np.array(image)
    result = ocr.ocr(img_array, cls=False)

    if not result or not result[0]:
        return ""

    # Extract text from all detected regions, sorted by y-position
    lines = []
    for line in result[0]:
        bbox, (text, confidence) = line
        y_pos = bbox[0][1]  # Top-left y coordinate
        lines.append((y_pos, text))

    # Sort by y position and join
    lines.sort(key=lambda x: x[0])
    return "\n".join(text for _, text in lines)


def _fix_ocr_text(text: str) -> str:
    """Fix common OCR misreads for this specific pixel timer font."""
    fixed = text.upper()

    # Fix punctuation
    for old, new in [("-", ":"), (";", ":"), ("'", ":"), (",", ".")]:
        fixed = fixed.replace(old, new)

    # Fix digit misreads
    for old, new in [
        ("O", "0"),
        ("D", "0"),
        ("Q", "0"),
        ("U", "0"),
        ("I", "1"),
        ("L", "1"),
        ("|", "1"),
        ("J", "1"),
        ("Z", "2"),
        ("E", "3"),
        ("A", "4"),
        ("H", "4"),
        ("S", "5"),
        ("G", "6"),
        ("B", "8"),
        ("P", "9"),
    ]:
        fixed = fixed.replace(old, new)

    return fixed


@dataclass
class TimerResult:
    """Result from timer OCR with both RTA and IGT values."""

    rta: Optional[int]  # First time found (cyan RTA line)
    igt: Optional[int]  # Second time found (yellow IGT line), None if not detected

    @property
    def timer(self) -> Optional[int]:
        """Return IGT if available, else RTA (backwards compatible)."""
        return self.igt if self.igt is not None else self.rta


def parse_timer_detailed(text: str) -> TimerResult:
    """
    Parse both RTA and IGT from OCR text.

    Returns a TimerResult with both values for inspection.
    """
    fixed = _fix_ocr_text(text)

    # Find all time patterns MM:SS
    times = re.findall(r"(\d{1,2}):(\d{2})", fixed)

    valid_times = []
    for mins_str, secs_str in times:
        mins, secs = int(mins_str), int(secs_str)
        # Fix likely 6x or 8x -> 0x misread for minutes
        # (the pixel font's 0 often OCRs as 6 or 8)
        if mins >= 60:
            mins = mins % 10
        if secs < 60:
            valid_times.append(mins * 60 + secs)

    rta = valid_times[0] if len(valid_times) >= 1 else None
    igt = valid_times[1] if len(valid_times) >= 2 else None
    return TimerResult(rta=rta, igt=igt)


def parse_timer(text: str) -> Optional[int]:
    """
    Parse timer from OCR text.

    Looks for time patterns (MM:SS), preferring IGT (second time found).
    Falls back to RTA (first time) if IGT not readable.
    Returns timer value in seconds, or None if parsing fails.
    """
    result = parse_timer_detailed(text)
    return result.timer


def format_timer(seconds: int) -> str:
    """Format seconds as MM:SS."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def read_timer_from_frame(
    frame_path: str,
    region: tuple[float, float, float, float] = DEFAULT_TIMER_REGION,
) -> Optional[int]:
    """
    Read the timer from a stream frame.

    Returns timer value in seconds, or None if OCR fails.
    Prefers IGT but falls back to RTA if IGT is unreadable.
    """
    result = read_timer_from_frame_detailed(frame_path, region)
    return result.timer


def read_timer_from_frame_detailed(
    frame_path: str,
    region: tuple[float, float, float, float] = DEFAULT_TIMER_REGION,
) -> TimerResult:
    """
    Read the timer from a stream frame with detailed RTA/IGT breakdown.

    Returns TimerResult with both RTA and IGT values for inspection.
    """
    image = Image.open(frame_path)
    cropped = crop_timer_region(image, region)
    processed = preprocess_image(cropped)
    text = extract_timer_text(processed)
    return parse_timer_detailed(text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ocr.py <frame_path> [region_left,top,right,bottom]")
        sys.exit(1)

    frame_path = sys.argv[1]
    region = DEFAULT_TIMER_REGION

    if len(sys.argv) > 2:
        parts = sys.argv[2].split(",")
        region = tuple(float(p) for p in parts)

    timer_seconds = read_timer_from_frame(frame_path, region)

    if timer_seconds is not None:
        print(f"Timer: {format_timer(timer_seconds)} ({timer_seconds} seconds)")
    else:
        print("Failed to read timer from frame")

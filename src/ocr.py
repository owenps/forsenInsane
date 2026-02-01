import re
from typing import Optional

import pytesseract
from PIL import Image, ImageOps

# Timer region containing both RTA and IGT lines (top-right)
# Format: (left, top, right, bottom) as percentages of image dimensions
DEFAULT_TIMER_REGION = (0.80, 0.02, 0.995, 0.10)


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

    Pipeline: grayscale -> threshold -> invert -> scale up
    """
    # Convert to grayscale
    gray = ImageOps.grayscale(image)

    # Lower threshold to capture bright timer text and preserve colons
    threshold = 95
    binary = gray.point(lambda p: 255 if p > threshold else 0)

    # Invert so we get black text on white background (better for Tesseract)
    inverted = ImageOps.invert(binary)

    # Scale up for better OCR (use NEAREST to preserve pixel font)
    scaled = inverted.resize((inverted.width * 4, inverted.height * 4), Image.Resampling.NEAREST)

    return scaled


def extract_timer_text(image: Image.Image) -> str:
    """Run Tesseract OCR on the preprocessed image."""
    # psm 11 = sparse text, works better with this pixel font
    config = "--psm 11"
    text = pytesseract.image_to_string(image, config=config)
    return text.strip()


def _fix_ocr_digits(text: str) -> str:
    """Fix common OCR misreads for this specific pixel timer font."""
    # Based on observed OCR errors: 0 reads as A/G/B/O, etc.
    replacements = {
        'O': '0', 'o': '0', 'Q': '0', 'D': '0',
        'A': '0', 'G': '0',  # 0 often misread as A or G in this font
        'B': '0', 'b': '0',  # 0 also misread as B
        'I': '1', 'l': '1', 'i': '1', '|': '1',
        'Z': '2', 'z': '2',
        'S': '5', 's': '5',
        'g': '9', 'q': '9',
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def parse_timer(text: str) -> Optional[int]:
    """
    Parse IGT timer from OCR text.

    Looks for time patterns (MM:SS), handling common OCR errors.
    Returns timer value in seconds, or None if parsing fails.
    """
    # First fix common OCR digit misreads
    fixed = _fix_ocr_digits(text)

    # Find all time patterns MM:SS in the fixed text
    times = re.findall(r"(\d{1,2}):(\d{2})", fixed)

    if len(times) >= 2:
        # Second time is likely IGT (RTA is first, IGT is second)
        minutes = int(times[1][0])
        seconds = int(times[1][1])
        if seconds < 60:
            return minutes * 60 + seconds

    if times:
        # Fallback to first/only time found
        minutes = int(times[0][0])
        seconds = int(times[0][1])
        if seconds < 60:
            return minutes * 60 + seconds

    return None


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
    Read the IGT timer from a stream frame.

    Returns timer value in seconds, or None if OCR fails.
    """
    image = Image.open(frame_path)
    cropped = crop_timer_region(image, region)
    processed = preprocess_image(cropped)
    text = extract_timer_text(processed)
    return parse_timer(text)


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

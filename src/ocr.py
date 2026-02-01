"""OCR processing for reading the IGT timer from stream frames."""

import re
from typing import Optional

import pytesseract
from PIL import Image, ImageFilter, ImageOps

# Default timer region (top-right area, needs calibration for forsen's overlay)
# Format: (left, top, right, bottom) as percentages of image dimensions
DEFAULT_TIMER_REGION = (0.75, 0.02, 0.98, 0.08)


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

    Pipeline: grayscale -> scale up -> threshold -> invert -> cleanup
    """
    # Convert to grayscale
    gray = ImageOps.grayscale(image)

    # Scale up for better OCR (Tesseract works better with larger text)
    scaled = gray.resize((gray.width * 3, gray.height * 3), Image.Resampling.LANCZOS)

    # Apply threshold to create binary image
    threshold = 180
    binary = scaled.point(lambda p: 255 if p > threshold else 0)

    # Light cleanup
    cleaned = binary.filter(ImageFilter.MedianFilter(size=3))

    return cleaned


def extract_timer_text(image: Image.Image) -> str:
    """Run Tesseract OCR on the preprocessed image."""
    config = "--psm 7 -c tessedit_char_whitelist=0123456789:"
    text = pytesseract.image_to_string(image, config=config)
    return text.strip()


def parse_timer(text: str) -> Optional[int]:
    """
    Parse timer text (MM:SS or M:SS) to total seconds.

    Returns None if parsing fails.
    """
    # Match patterns like "10:23", "9:45", "1:23:45"
    match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if not match:
        return None

    groups = match.groups()
    if groups[2] is not None:
        # H:MM:SS format
        hours = int(groups[0])
        minutes = int(groups[1])
        seconds = int(groups[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        # MM:SS format
        minutes = int(groups[0])
        seconds = int(groups[1])
        return minutes * 60 + seconds


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

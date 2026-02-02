"""Unit tests for OCR timer detection."""

import os
from pathlib import Path

import pytest

from src.ocr import (
    TimerResult,
    _fix_ocr_text,
    format_timer,
    parse_timer,
    parse_timer_detailed,
    read_timer_from_frame,
    read_timer_from_frame_detailed,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFormatTimer:
    def test_format_simple(self):
        assert format_timer(0) == "0:00"
        assert format_timer(60) == "1:00"
        assert format_timer(90) == "1:30"

    def test_format_double_digits(self):
        assert format_timer(600) == "10:00"
        assert format_timer(867) == "14:27"


class TestFixOcrText:
    def test_punctuation_fixes(self):
        assert ":" in _fix_ocr_text("03-47")
        assert ":" in _fix_ocr_text("03;47")
        assert ":" in _fix_ocr_text("03'47")

    def test_digit_fixes(self):
        # O -> 0
        assert "0" in _fix_ocr_text("O3:47")
        # I -> 1
        assert "1" in _fix_ocr_text("I0:00")


class TestParseTimer:
    def test_parse_clean_time(self):
        assert parse_timer("RTA: 03:47.246") == 227  # 3*60 + 47
        assert parse_timer("IGT: 10:30.000") == 630  # 10*60 + 30

    def test_parse_with_ocr_errors(self):
        # Common OCR error: 0 read as 6
        assert parse_timer("RTA: 63:47.246") == 227  # 63 % 10 = 3

    def test_parse_two_times_returns_second(self):
        # When both RTA and IGT are found, return IGT (second time)
        result = parse_timer("RTA: 03:47.246\nIGT: 03:28.022")
        assert result == 208  # IGT: 3*60 + 28

    def test_parse_single_time_fallback(self):
        # When only one time found, use it
        assert parse_timer("RTA: 10:30.000") == 630

    def test_parse_no_time(self):
        assert parse_timer("no time here") is None
        assert parse_timer("") is None


class TestParseTimerDetailed:
    def test_parse_both_times(self):
        result = parse_timer_detailed("RTA: 03:47.246\nIGT: 03:28.022")
        assert result.rta == 227  # 3*60 + 47
        assert result.igt == 208  # 3*60 + 28
        assert result.timer == 208  # Should return IGT

    def test_parse_single_time(self):
        result = parse_timer_detailed("RTA: 10:30.000")
        assert result.rta == 630
        assert result.igt is None
        assert result.timer == 630  # Falls back to RTA

    def test_parse_no_time(self):
        result = parse_timer_detailed("no time here")
        assert result.rta is None
        assert result.igt is None
        assert result.timer is None


class TestReadTimerFromFrame:
    """
    Integration tests using real frame captures.

    Add new frames to tests/fixtures/ with naming convention:
    frame_MM_SS_rta_MM_SS_igt.jpg

    These tests verify the full OCR pipeline works with actual stream frames.
    Tests focus on IGT detection since that's what we care about for alerts.
    """

    @pytest.fixture
    def frame_03_47(self):
        """Frame with RTA: 03:47.246, IGT: 03:28.022"""
        path = FIXTURES_DIR / "frame_03_47_rta_03_28_igt.jpg"
        if not path.exists():
            pytest.skip(f"Test fixture not found: {path}")
        return str(path)

    @pytest.fixture
    def frame_02_24(self):
        """Frame with RTA: 02:24.428, IGT: 02:24.497"""
        path = FIXTURES_DIR / "frame_02_24_rta_02_24_igt.jpg"
        if not path.exists():
            pytest.skip(f"Test fixture not found: {path}")
        return str(path)

    @pytest.fixture
    def frame_03_38(self):
        """Frame with RTA: 03:38.725, IGT: 03:17.122"""
        path = FIXTURES_DIR / "frame_03_38_rta_03_17_igt.jpg"
        if not path.exists():
            pytest.skip(f"Test fixture not found: {path}")
        return str(path)

    def test_frame_03_47_igt(self, frame_03_47):
        """Expected IGT: 208s (3:28)"""
        result = read_timer_from_frame_detailed(frame_03_47)
        assert result.igt is not None, "Failed to detect IGT"
        assert 198 <= result.igt <= 218, f"IGT {result.igt}s not close to expected 208s"

    def test_frame_02_24_igt(self, frame_02_24):
        """Expected IGT: 144s (2:24). RTA is also 2:24 so either value is acceptable."""
        result = read_timer_from_frame_detailed(frame_02_24)
        # In this frame RTA ≈ IGT, so getting .timer is sufficient
        timer = result.timer
        assert timer is not None, "Failed to detect any timer"
        assert 134 <= timer <= 154, f"Timer {timer}s not close to expected 144s"

    def test_frame_03_38_igt(self, frame_03_38):
        """Expected IGT: 197s (3:17)"""
        result = read_timer_from_frame_detailed(frame_03_38)
        assert result.igt is not None, "Failed to detect IGT"
        assert 187 <= result.igt <= 207, f"IGT {result.igt}s not close to expected 197s"


# Convenience function to run tests directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

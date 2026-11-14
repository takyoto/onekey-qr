"""Tests for decode_qr_codes() using QR images generated with OpenCV."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from onekey_qr import decode_qr_codes


def make_qr(text: str, scale: int = 8, border: int = 40) -> np.ndarray:
    """Return a BGR image of a QR code encoding `text`, with a white margin."""
    qr = cv2.QRCodeEncoder.create().encode(text)
    qr = cv2.resize(qr, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    qr = cv2.copyMakeBorder(qr, border, border, border, border, cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)


def side_by_side(*images: np.ndarray) -> np.ndarray:
    """Place images horizontally on a white canvas (pads to the tallest one)."""
    height = max(img.shape[0] for img in images)
    padded = [
        cv2.copyMakeBorder(img, 0, height - img.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        for img in images
    ]
    return np.hstack(padded)


def test_decodes_single_qr_code():
    img = make_qr("OneKey QR test")

    assert decode_qr_codes(img) == ["OneKey QR test"]


def test_decodes_multiple_qr_codes():
    img = side_by_side(make_qr("first"), make_qr("second"))

    # Detection order is not guaranteed
    assert sorted(decode_qr_codes(img)) == ["first", "second"]


def test_removes_duplicate_qr_codes():
    img = side_by_side(make_qr("same"), make_qr("same"))

    assert decode_qr_codes(img) == ["same"]


def test_returns_empty_list_when_no_qr_code():
    img = np.full((400, 400, 3), 255, dtype=np.uint8)

    assert decode_qr_codes(img) == []


@pytest.mark.parametrize("scale", [3, 4, 6, 8, 10])
def test_decodes_qr_code_on_screen_sized_image(scale):
    # A QR code of various sizes placed on a large screenshot-like canvas.
    # scale=6 is missed by detectAndDecodeMulti alone (regression check for the fallback).
    canvas = np.full((1080, 1920, 3), 240, dtype=np.uint8)
    qr = make_qr("on screen", scale=scale)
    canvas[300 : 300 + qr.shape[0], 900 : 900 + qr.shape[1]] = qr

    assert decode_qr_codes(canvas) == ["on screen"]

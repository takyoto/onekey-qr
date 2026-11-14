"""Tests for the scan flow, with screen capture, clipboard and notifications replaced by fakes."""

from __future__ import annotations

import queue
import sys

import numpy as np
import pytest

import onekey_qr


@pytest.fixture
def fakes(monkeypatch):
    """Replace OS-dependent parts and record what the scan flow does."""
    calls = {"copied": [], "notified": []}

    monkeypatch.setattr(onekey_qr, "capture_all_monitors", lambda: np.zeros((10, 10, 3), np.uint8))
    monkeypatch.setattr(onekey_qr.pyperclip, "copy", lambda text: calls["copied"].append(text))
    monkeypatch.setattr(onekey_qr, "notify", lambda title, message: calls["notified"].append(message))

    def set_decoded(texts):
        monkeypatch.setattr(onekey_qr, "decode_qr_codes", lambda img: list(texts))

    calls["set_decoded"] = set_decoded
    return calls


def test_single_qr_code_is_copied(fakes):
    fakes["set_decoded"](["OneKey QR test"])

    onekey_qr.scan_and_copy()

    assert fakes["copied"] == ["OneKey QR test"]
    assert fakes["notified"] == ["Copied: OneKey QR test"]


def test_multiple_qr_codes_are_copied_one_per_line(fakes):
    fakes["set_decoded"](["first", "second"])

    onekey_qr.scan_and_copy()

    assert fakes["copied"] == ["first\nsecond"]
    assert fakes["notified"] == ["Copied 2 items:\nfirst\nsecond"]


def test_clipboard_is_untouched_when_no_qr_code(fakes):
    fakes["set_decoded"]([])

    onekey_qr.scan_and_copy()

    assert fakes["copied"] == []
    assert fakes["notified"] == ["No QR code found"]


def test_errors_are_reported_instead_of_raised(fakes, monkeypatch):
    def broken_capture():
        raise RuntimeError("capture failed")

    monkeypatch.setattr(onekey_qr, "capture_all_monitors", broken_capture)

    onekey_qr.scan_and_copy()  # must not raise, so the worker thread keeps running

    assert fakes["copied"] == []
    assert fakes["notified"] == ["Error: capture failed"]


def test_repeated_hotkey_presses_queue_at_most_one_scan(monkeypatch):
    requests = queue.Queue(maxsize=1)
    monkeypatch.setattr(onekey_qr, "_requests", requests)

    for _ in range(5):
        onekey_qr.on_hotkey()

    assert requests.qsize() == 1


def test_notify_falls_back_to_console_without_notification_libraries(monkeypatch, capsys):
    # Setting a module to None in sys.modules makes importing it fail
    monkeypatch.setitem(sys.modules, "win11toast", None)
    monkeypatch.setitem(sys.modules, "plyer", None)

    onekey_qr.notify("OneKey QR", "hello")

    assert capsys.readouterr().out == "[OneKey QR] hello\n"

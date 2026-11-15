"""Tests for hotkey parsing and registration with Windows (RegisterHotKey)."""

from __future__ import annotations

import ctypes
import queue

import pytest

import onekey_qr
from onekey_qr import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN

# An unusual combination that no app is likely to use, so registering it in tests
# doesn't clash with the desktop the tests run on
TEST_HOTKEY = "ctrl+alt+shift+f24"


@pytest.mark.parametrize(
    ("hotkey", "expected"),
    [
        ("windows+shift+q", (MOD_WIN | MOD_SHIFT, ord("Q"))),
        ("Win + Shift + Q", (MOD_WIN | MOD_SHIFT, ord("Q"))),
        ("ctrl+alt+1", (MOD_CONTROL | MOD_ALT, ord("1"))),
        ("control+f1", (MOD_CONTROL, 0x70)),
        ("f24", (0, 0x87)),
        ("scroll lock", (0, 0x91)),
        ("pause", (0, 0x13)),
    ],
)
def test_parse_hotkey(hotkey, expected):
    assert onekey_qr.parse_hotkey(hotkey) == expected


@pytest.mark.parametrize("hotkey", ["", "shift+", "ctrl+shift", "hyper+q", "f25", "win+ä"])
def test_parse_hotkey_rejects_unknown_keys(hotkey):
    with pytest.raises(ValueError):
        onekey_qr.parse_hotkey(hotkey)


def test_hotkey_already_in_use_is_reported():
    onekey_qr.register_hotkey(TEST_HOTKEY, hotkey_id=100)
    try:
        with pytest.raises(onekey_qr.HotkeyError, match="already used"):
            onekey_qr.register_hotkey(TEST_HOTKEY, hotkey_id=101)
    finally:
        onekey_qr.unregister_hotkey(100)

    # Once released, the combination can be registered again
    onekey_qr.register_hotkey(TEST_HOTKEY, hotkey_id=101)
    onekey_qr.unregister_hotkey(101)


def test_wm_hotkey_message_requests_a_scan(monkeypatch):
    requests = queue.Queue(maxsize=1)
    monkeypatch.setattr(onekey_qr, "_requests", requests)

    onekey_qr.pump_messages()  # Makes sure this thread has a message queue
    user32 = ctypes.windll.user32
    thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
    assert user32.PostThreadMessageW(thread_id, onekey_qr.WM_HOTKEY, onekey_qr.HOTKEY_ID, 0)

    onekey_qr.pump_messages()

    assert requests.qsize() == 1


def test_other_hotkey_ids_are_ignored(monkeypatch):
    requests = queue.Queue(maxsize=1)
    monkeypatch.setattr(onekey_qr, "_requests", requests)

    onekey_qr.pump_messages()
    user32 = ctypes.windll.user32
    thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
    assert user32.PostThreadMessageW(thread_id, onekey_qr.WM_HOTKEY, onekey_qr.HOTKEY_ID + 1, 0)

    onekey_qr.pump_messages()

    assert requests.qsize() == 0

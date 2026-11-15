"""
OneKey QR: press the hotkey (default: Win+Shift+Q) to read QR codes on screen
and copy them to the clipboard.

Usage:
    python onekey_qr.py

See README.md for installation, configuration, and notes.
"""

from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes

import mss
import numpy as np
import pyperclip
import zxingcpp

HOTKEY = "windows+shift+q"
APP_NAME = "OneKey QR"

# --- Win32 hotkey API -------------------------------------------------------
# The hotkey is registered with Windows (RegisterHotKey), the same way Windows'
# own shortcuts such as Win+Shift+S work: the OS consumes the key press, so the
# keys are not passed on to the foreground app (no stray "Q" is typed).

HOTKEY_ID = 1

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # Holding the keys down does not repeat the hotkey

WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_MODIFIERS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}

# Virtual-key codes for named keys. Letters, digits and F1-F24 are computed.
_NAMED_KEYS = {
    "space": 0x20,
    "pause": 0x13,
    "scroll lock": 0x91,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "page up": 0x21,
    "page down": 0x22,
}

# A private WinDLL instance, so the argtypes below don't affect ctypes.windll
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.MsgWaitForMultipleObjects.argtypes = [
    wintypes.DWORD,
    ctypes.POINTER(wintypes.HANDLE),
    wintypes.BOOL,
    wintypes.DWORD,
    wintypes.DWORD,
]
_user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD


class HotkeyError(Exception):
    """The hotkey could not be registered."""

# mss >= 10.2 renamed mss.mss to mss.MSS; fall back for older versions
_MSS = getattr(mss, "MSS", None) or mss.mss

# Scan requests from the hotkey. maxsize=1 drops presses while a scan is pending,
# so repeated presses don't queue up multiple scans.
_requests: queue.Queue[None] = queue.Queue(maxsize=1)


def notify(title: str, message: str) -> None:
    """Show a toast notification. Falls back to console output if no library is available."""
    print(f"[{title}] {message}")
    try:
        from win11toast import notify as toast_notify

        toast_notify(title, message, app_id=APP_NAME)
    except Exception:
        try:
            from plyer import notification

            notification.notify(title=title, message=message, app_name=APP_NAME, timeout=3)
        except Exception:
            pass


def capture_all_monitors() -> np.ndarray:
    """Capture all monitors at once and return a BGRA image."""
    with _MSS() as sct:
        # monitors[0] is the virtual screen spanning all monitors
        shot = sct.grab(sct.monitors[0])
        return np.array(shot)  # BGRA


def decode_qr_codes(img: np.ndarray) -> list[str]:
    """Decode every QR code in the image and return a de-duplicated list of strings.

    `img` is a BGRA (screen capture), BGR or grayscale array.
    QR Code, Micro QR Code and rMQR Code are recognized.
    """
    if img.ndim == 3 and img.shape[2] == 4:
        # Pass the BGRA capture as-is (no color conversion needed)
        img = zxingcpp.ImageView(img, img.shape[1], img.shape[0], zxingcpp.ImageFormat.BGRA)

    results: list[str] = []
    for barcode in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode):
        if barcode.valid and barcode.text and barcode.text not in results:
            results.append(barcode.text)
    return results


def parse_hotkey(hotkey: str) -> tuple[int, int]:
    """Convert a hotkey such as "windows+shift+q" to (modifier flags, virtual-key code)."""
    *modifier_names, key = [part.strip().lower() for part in hotkey.split("+")]

    modifiers = 0
    for name in modifier_names:
        if name not in _MODIFIERS:
            raise ValueError(f"Unknown modifier key in hotkey {hotkey!r}: {name!r}")
        modifiers |= _MODIFIERS[name]

    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())  # VK codes for A-Z and 0-9 match their ASCII codes
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1  # VK_F1 = 0x70
    else:
        raise ValueError(f"Unknown key in hotkey {hotkey!r}: {key!r}")
    return modifiers, vk


def register_hotkey(hotkey: str, hotkey_id: int = HOTKEY_ID) -> None:
    """Register the hotkey with Windows for the calling thread.

    WM_HOTKEY messages are posted to the calling thread's message queue, so the
    same thread must run pump_messages(). Raises HotkeyError on failure.
    """
    modifiers, vk = parse_hotkey(hotkey)
    if not _user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk):
        error = ctypes.get_last_error()
        if error == ERROR_HOTKEY_ALREADY_REGISTERED:
            raise HotkeyError(
                f"{hotkey.upper()} is already used by Windows or another app. "
                "Change HOTKEY in onekey_qr.py."
            )
        raise HotkeyError(f"Could not register {hotkey.upper()}: {ctypes.FormatError(error)}")


def unregister_hotkey(hotkey_id: int = HOTKEY_ID) -> None:
    _user32.UnregisterHotKey(None, hotkey_id)


def pump_messages() -> None:
    """Handle every message waiting in this thread's queue, without blocking."""
    msg = wintypes.MSG()
    while _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            on_hotkey()


def run_message_loop() -> None:
    """Wait for hotkey presses until Ctrl+C."""
    while True:
        pump_messages()
        # Wait with a timeout instead of blocking in GetMessageW: Python can only
        # raise KeyboardInterrupt (Ctrl+C) once the Win32 call returns.
        _user32.MsgWaitForMultipleObjects(0, None, False, 500, QS_ALLINPUT)


def on_hotkey() -> None:
    # Hand the work to the worker thread so the message loop is not blocked
    try:
        _requests.put_nowait(None)
    except queue.Full:
        pass  # A scan is already pending


def worker() -> None:
    # All scans and notifications run on this single long-lived thread.
    # Calling win11toast (WinRT) from a new thread for each scan crashed the
    # process with an access violation on the second scan.
    while True:
        _requests.get()
        scan_and_copy()


def scan_and_copy() -> None:
    try:
        img = capture_all_monitors()
        texts = decode_qr_codes(img)

        if not texts:
            notify(APP_NAME, "No QR code found")
            return

        joined = "\n".join(texts)
        pyperclip.copy(joined)
        if len(texts) == 1:
            notify(APP_NAME, f"Copied: {texts[0]}")
        else:
            notify(APP_NAME, f"Copied {len(texts)} items:\n{joined}")
    except Exception as e:
        notify(APP_NAME, f"Error: {e}")


def main() -> None:
    try:
        register_hotkey(HOTKEY)
    except (ValueError, HotkeyError) as e:
        notify(APP_NAME, f"Error: {e}")
        raise SystemExit(1)

    threading.Thread(target=worker, daemon=True).start()
    print(f"{APP_NAME} is running: press {HOTKEY.upper()} to read QR codes (Ctrl+C to quit)")
    try:
        run_message_loop()
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        # Windows also releases the hotkey when the process exits
        unregister_hotkey()


if __name__ == "__main__":
    main()

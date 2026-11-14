"""
OneKey QR: press the hotkey (default: Win+Shift+Q) to read QR codes on screen
and copy them to the clipboard.

Usage:
    python onekey_qr.py

See README.md for installation, configuration, and notes.
"""

from __future__ import annotations

import queue
import threading

import cv2
import keyboard
import mss
import numpy as np
import pyperclip

HOTKEY = "windows+shift+q"
APP_NAME = "OneKey QR"

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
    """Capture all monitors at once and return a BGR image usable by OpenCV."""
    with _MSS() as sct:
        # monitors[0] is the virtual screen spanning all monitors
        shot = sct.grab(sct.monitors[0])
        img = np.array(shot)  # BGRA
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def decode_qr_codes(img: np.ndarray) -> list[str]:
    """Decode every QR code in the image and return a de-duplicated list of strings."""
    detector = cv2.QRCodeDetector()
    results: list[str] = []

    def collect(target: np.ndarray) -> None:
        ok, texts, _points, _ = detector.detectAndDecodeMulti(target)
        if not ok or not any(texts):
            # detectAndDecodeMulti misses some codes (depending on their size)
            # that the single-code detector can read, so fall back to it
            text, _points, _ = detector.detectAndDecode(target)
            texts = (text,)
        for t in texts:
            if t and t not in results:
                results.append(t)

    collect(img)

    # If nothing was found, retry on a grayscale version
    if not results:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        collect(gray)

    return results


def on_hotkey() -> None:
    # Hand the work to the worker thread so the keyboard hook is not blocked
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
    threading.Thread(target=worker, daemon=True).start()
    keyboard.add_hotkey(HOTKEY, on_hotkey)
    print(f"{APP_NAME} is running: press {HOTKEY.upper()} to read QR codes (Ctrl+C to quit)")
    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    main()

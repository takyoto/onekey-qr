# OneKey QR

[![CI](https://github.com/takyoto/onekey-qr/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/takyoto/onekey-qr/actions/workflows/test.yml)

English | [日本語](README.ja.md)

**Read QR codes on your PC screen as easily as with your phone — just press one hotkey.**

Scanning a QR code takes a single tap on a smartphone, but on a PC it usually means pulling out your phone and pointing it at the monitor. OneKey QR runs in the background: press `Win+Shift+Q` and it reads the QR codes shown on your screen and copies their contents to the clipboard.

- Searches for QR codes across all of your monitors
- Reads every QR code on the screen if there is more than one
- Shows a toast notification with the copied content when it's done

## Requirements

- Windows 11
- Python 3.10 or later

## Installation

```
pip install -r requirements.txt
```

These libraries are used:

| Library | Purpose |
|---|---|
| keyboard | Listens for the hotkey system-wide |
| mss | Captures the screen (all monitors) |
| opencv-python / numpy | Detects and decodes QR codes |
| pyperclip | Copies the result to the clipboard |
| win11toast | Shows toast notifications |

## Usage

1. Start the script.

   ```
   python onekey_qr.py
   ```

   On startup, the console shows:

   ```
   OneKey QR is running: press WINDOWS+SHIFT+Q to read QR codes (Ctrl+C to quit)
   ```

2. Display the QR code you want to read on the screen.
3. Press `Win+Shift+Q`.
4. When the toast notification appears, paste the result with `Ctrl+V`.
5. To quit, press `Ctrl+C` in the console where the script is running.

### Results

| Situation | Clipboard contents | Notification |
|---|---|---|
| One QR code | Its content | `Copied: (content)` |
| Multiple QR codes | All contents, one per line | `Copied N items: (list of contents)` |
| None found | Unchanged | `No QR code found` |

## Changing the hotkey

Edit `HOTKEY` near the top of `onekey_qr.py`.

```python
HOTKEY = "windows+shift+q"
```

When choosing a hotkey, check **whether the combinations you might trigger partway through, if you press the keys in the wrong order, are harmful**.
For example, with `Ctrl+Alt+Q`, pressing Q before Alt sends `Ctrl+Q`, which closes some applications.

| Example | Notes |
|---|---|
| `"windows+shift+q"` | Default. The only partial combinations are `Win+Q` (search) and `Shift+Q` (typing a Q) |
| `"scroll lock"` / `"pause"` | Safe single keys, but many laptops don't have them |

## Notes

- Screen captures are processed in memory. No image files are saved.
- The `keyboard` library monitors key input system-wide. The hotkey may not respond while an application running with administrator privileges is in the foreground. In that case, run the script as administrator as well.
- QR codes that are too small or partly hidden may not be readable. Zoom in and try again.
- If `win11toast` is not installed, the script tries `plyer` for notifications. If neither is available, it only prints the result to the console.
- If no toast notification appears, check your Windows notification settings. The QR code is still read and copied, and the result is printed to the console.
  - **Settings → System → Notifications**: make sure **Notifications** is turned on.
  - Make sure **Do not disturb** (Windows 11) or **Focus assist** (Windows 10) is off.
  - In the app list on the same page, make sure the sender app (such as Windows PowerShell or Python) is not turned off.

## Development

Install the development dependencies and run the tests:

```
pip install -r requirements-dev.txt
pytest
```

The tests cover QR code decoding (using QR images generated with OpenCV) and the scan flow (with screen capture, clipboard and notifications replaced by fakes). The hotkey, actual screen capture and toast notifications depend on the Windows desktop, so check them manually.

## License

[MIT License](LICENSE) © 2026 Takuto Yamane

QR Code is a registered trademark of DENSO WAVE INCORPORATED.

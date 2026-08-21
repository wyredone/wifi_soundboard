# WiFi Soundboard

A local-network soundboard that lets phones and computers trigger audio playback on a Windows host.

## Windows setup

1. Install Python 3.10 or newer and enable **Add Python to PATH**.
2. Run `setup.bat`.
3. Put `.mp3`, `.wav`, or `.ogg` files in the `sounds` folder.
4. Run `start_soundboard.bat` to launch the native Windows Server Control Center.
5. On another device connected to the same trusted Wi-Fi network, open `http://HOST-IP:8080`.

## Windows Server Control Center

The desktop control center starts and stops the LAN server, displays the live LAN URL and QR code,
shows connected devices, and provides Kick and persistent Block actions. It also includes admission
control, server bind/port settings, a system-tray controller, and a live JSONL audit log. Settings and
blocklists are stored in `%LOCALAPPDATA%\WiFiSoundboard`.

Use `start_server_control.bat` to launch it directly. `run.py` remains available for headless web-only
operation and troubleshooting.

The sound list refreshes every five seconds. Renamed display labels are stored only in the current browser and do not rename files.

If `YourMomDrops.zip` is present in the project root, the application safely imports all MP3, WAV,
and OGG files into `sounds` on startup. Category folders in the archive are flattened, existing files
are preserved, and non-audio metadata is ignored.

## Firewall

If another device cannot connect, allow Python through Windows Defender Firewall on **Private networks only**. This app has no user authentication, so do not expose port 8080 to the internet or an untrusted network.

## Development

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest
python run.py
```

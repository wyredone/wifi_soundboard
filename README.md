# WiFi Soundboard

A local-network soundboard that lets phones and computers trigger audio playback on a Windows host.

## Windows setup

1. Install Python 3.10 or newer and enable **Add Python to PATH**.
2. Run `setup.bat`.
3. Put `.mp3`, `.wav`, or `.ogg` files in the `sounds` folder.
4. Run `start_soundboard.bat`.
5. On another device connected to the same trusted Wi-Fi network, open `http://HOST-IP:8080`.

The sound list refreshes every five seconds. Renamed display labels are stored only in the current browser and do not rename files.

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

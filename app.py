import hashlib
import threading
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename
from admin_state import admin_state

try:
    import pygame
except ImportError:  # Allows the UI and tests to start before audio dependencies exist.
    pygame = None


BASE_DIR = Path(__file__).resolve().parent
SOUND_DIR = BASE_DIR / "sounds"
ASSET_ARCHIVE = BASE_DIR / "wifi_soundboard_assets.zip"
ASSET_DIR = BASE_DIR / ".runtime_assets"
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg"}
SOUND_DIR.mkdir(exist_ok=True)


def ensure_assets():
    """Extract the bundled design system once, without trusting archive paths."""
    marker = ASSET_DIR / ".ready"
    if marker.exists() or not ASSET_ARCHIVE.exists():
        return
    ASSET_DIR.mkdir(exist_ok=True)
    root = ASSET_DIR.resolve()
    with zipfile.ZipFile(ASSET_ARCHIVE) as archive:
        for member in archive.infolist():
            target = (ASSET_DIR / member.filename).resolve()
            if root not in target.parents and target != root:
                continue
            archive.extract(member, ASSET_DIR)
    marker.touch()


ensure_assets()

app = Flask(__name__)
audio_lock = threading.RLock()
audio_ready = False
audio_error = "Audio system has not been initialized."
_current_volume: float = 1.0
_sound_cache: dict = {}  # filepath str -> pygame.mixer.Sound


@app.before_request
def register_client():
    if request.path.startswith(("/static/", "/assets/")):
        return None
    device_id = request.headers.get("X-Device-ID", "").strip()[:128]
    if not device_id:
        return None  # initial page load establishes the browser ID in JavaScript
    ip = request.remote_addr or "unknown"
    name = request.headers.get("X-Device-Name", "Browser")[:80]
    if not admin_state.is_allowed(device_id, ip):
        return jsonify(error="This device is not authorized by the server administrator"), 403
    admin_state.observe(device_id, ip, name, request.user_agent.string[:300])


def initialize_audio():
    global audio_ready, audio_error
    with audio_lock:
        if audio_ready:
            return True
        if pygame is None:
            audio_error = "Pygame is not installed. Run setup.bat."
            return False
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)  # allow up to 16 sounds to overlap
            audio_ready = True
            audio_error = ""
        except Exception as exc:
            audio_error = f"Audio device unavailable: {exc}"
        return audio_ready


def sound_id(filename):
    # 128-bit (32 hex chars) keeps collision probability negligible even for large sound libraries.
    return hashlib.sha256(filename.encode("utf-8")).hexdigest()[:32]


def get_available_sounds():
    sounds = []
    for path in sorted(SOUND_DIR.iterdir(), key=lambda item: item.name.casefold()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            sounds.append(
                {
                    "id": sound_id(path.name),
                    "name": path.stem.replace("_", " ").replace("-", " ").title(),
                    "file": path.name,
                }
            )
    return sounds


def find_sound(sound_identifier):
    return next(
        (sound for sound in get_available_sounds() if sound["id"] == sound_identifier),
        None,
    )


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Soundboard</title>
    <style>
        :root { --bg:#0f172a; --card:#1e293b; --text:#f8fafc; --muted:#94a3b8; --active:#22c55e; --danger:#ef4444; --border:#334155; }
        * { box-sizing: border-box; }
        body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text); margin:0; padding:20px; display:flex; flex-direction:column; align-items:center; }
        header,.grid { width:100%; max-width:800px; }
        h1 { margin:0 0 15px; font-size:1.8rem; text-align:center; }
        .controls { display:flex; gap:12px; flex-wrap:wrap; align-items:center; background:var(--card); padding:15px; border:1px solid var(--border); border-radius:12px; margin-bottom:20px; }
        input[type="text"] { flex:1; min-width:190px; padding:10px 12px; border-radius:8px; border:1px solid var(--border); background:var(--bg); color:var(--text); font-size:1rem; }
        .volume { display:flex; align-items:center; gap:8px; }
        button { border:1px solid var(--border); border-radius:8px; background:var(--bg); color:var(--text); padding:9px 12px; cursor:pointer; }
        button:hover { border-color:var(--active); }
        .stop:hover { border-color:var(--danger); }
        .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:15px; }
        .sound-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer; min-height:110px; transition:transform .1s,background-color .2s; }
        .sound-card:active { transform:scale(.96); }
        .sound-card.playing { background:rgba(34,197,94,.15); border-color:var(--active); }
        .sound-name { font-size:1.1rem; font-weight:600; text-align:center; margin-bottom:10px; overflow-wrap:anywhere; }
        .rename { color:var(--muted); font-size:.8rem; padding:4px 8px; border:0; background:transparent; }
        #status { color:var(--muted); margin-top:15px; font-size:.9rem; text-align:center; }
        #status.error { color:#fca5a5; }
        .empty { grid-column:1/-1; text-align:center; color:var(--muted); }
    </style>
</head>
<body>
    <header>
        <h1>WiFi Soundboard</h1>
        <div class="controls">
            <input type="text" id="search" placeholder="Search sounds..." aria-label="Search sounds">
            <div class="volume"><label for="volume">Volume</label><input type="range" id="volume" min="0" max="100" value="100"></div>
            <button id="refresh" type="button">Refresh</button>
            <button id="stop" class="stop" type="button">Stop</button>
        </div>
    </header>
    <main class="grid" id="grid"></main>
    <div id="status">Connecting...</div>
    <script>
        const grid = document.getElementById('grid');
        const statusNode = document.getElementById('status');
        const searchNode = document.getElementById('search');
        let sounds = [];
        let activeId = null;
        let refreshTimer;

        function setStatus(message, isError = false) {
            statusNode.textContent = message;
            statusNode.classList.toggle('error', isError);
        }

        async function api(url, options = {}) {
            const response = await fetch(url, options);
            let data = {};
            try { data = await response.json(); } catch (_) {}
            if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
            return data;
        }

        function visibleSounds() {
            const query = searchNode.value.trim().toLowerCase();
            return sounds.filter(sound => (localStorage.getItem(`name_${sound.id}`) || sound.name).toLowerCase().includes(query));
        }

        function render() {
            grid.replaceChildren();
            const items = visibleSounds();
            if (!items.length) {
                const empty = document.createElement('p');
                empty.className = 'empty';
                empty.textContent = sounds.length ? 'No matching sounds.' : 'No sound files found in the sounds folder.';
                grid.appendChild(empty);
                return;
            }
            for (const sound of items) {
                const card = document.createElement('div');
                card.className = `sound-card${activeId === sound.id ? ' playing' : ''}`;
                card.dataset.soundId = sound.id;
                card.tabIndex = 0;
                card.setAttribute('role', 'button');
                const name = document.createElement('div');
                name.className = 'sound-name';
                name.textContent = localStorage.getItem(`name_${sound.id}`) || sound.name;
                const rename = document.createElement('button');
                rename.className = 'rename';
                rename.type = 'button';
                rename.textContent = 'Rename on this device';
                rename.addEventListener('click', event => { event.stopPropagation(); renameSound(sound); });
                card.addEventListener('click', () => playSound(sound.id));
                card.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); playSound(sound.id); } });
                card.append(name, rename);
                grid.appendChild(card);
            }
        }

        function renameSound(sound) {
            const current = localStorage.getItem(`name_${sound.id}`) || sound.name;
            const updated = prompt('Display name on this device:', current);
            if (updated && updated.trim()) { localStorage.setItem(`name_${sound.id}`, updated.trim()); render(); }
        }

        async function fetchSounds(quiet = false) {
            try {
                const latest = await api('/api/sounds');
                if (JSON.stringify(latest) !== JSON.stringify(sounds)) { sounds = latest; render(); }
                if (!quiet) setStatus(`Connected · ${sounds.length} sound${sounds.length === 1 ? '' : 's'}`);
            } catch (error) { setStatus(`${error.message} · retrying`, true); }
        }

        async function playSound(id) {
            try {
                await api(`/api/play/${encodeURIComponent(id)}`, {method:'POST'});
                activeId = id; render(); setStatus('Playing');
            } catch (error) { activeId = null; render(); setStatus(error.message, true); }
        }

        async function stopSound() {
            try { await api('/api/stop', {method:'POST'}); activeId = null; render(); setStatus('Stopped'); }
            catch (error) { setStatus(error.message, true); }
        }

        async function pollPlayback() {
            try { const data = await api('/api/status'); if (!data.playing && activeId) { activeId = null; render(); } }
            catch (_) {}
        }

        searchNode.addEventListener('input', render);
        document.getElementById('refresh').addEventListener('click', () => fetchSounds());
        document.getElementById('stop').addEventListener('click', stopSound);
        document.getElementById('volume').addEventListener('input', async event => {
            try { await api('/api/volume', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({volume:Number(event.target.value)/100})}); }
            catch (error) { setStatus(error.message, true); }
        });
        fetchSounds();
        refreshTimer = setInterval(() => fetchSounds(true), 5000);
        setInterval(pollPlayback, 500);
    </script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(ASSET_DIR, filename)


@app.get("/api/sounds")
def api_sounds():
    return jsonify(get_available_sounds())


@app.post("/api/upload")
def upload_sound():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="Choose an audio file to upload"), 400
    filename = secure_filename(uploaded.filename)
    if not filename or Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return jsonify(error="Only MP3, WAV, and OGG files are supported"), 400
    destination = SOUND_DIR / filename
    if destination.exists():
        return jsonify(error="A sound with that filename already exists"), 409
    uploaded.save(destination)
    sound = next(item for item in get_available_sounds() if item["file"] == filename)
    return jsonify(status="uploaded", sound=sound), 201


@app.post("/api/play/<sound_identifier>")
def play_sound(sound_identifier):
    sound = find_sound(sound_identifier)
    if sound is None:
        return jsonify(error="Sound not found"), 404
    if not initialize_audio():
        return jsonify(error=audio_error), 503
    filepath = str(SOUND_DIR / sound["file"])
    try:
        with audio_lock:
            pygame.mixer.stop()  # exclusive playback: one sound at a time
            if filepath not in _sound_cache:
                _sound_cache[filepath] = pygame.mixer.Sound(filepath)
            snd = _sound_cache[filepath]
            snd.set_volume(_current_volume)
            snd.play()
        return jsonify(status="playing", id=sound_identifier)
    except Exception as exc:
        return jsonify(error=f"Unable to play sound: {exc}"), 500


@app.post("/api/stop")
def stop_sound():
    if not initialize_audio():
        return jsonify(error=audio_error), 503
    with audio_lock:
        pygame.mixer.stop()  # stops all active channels
    return jsonify(status="stopped")


@app.get("/api/status")
def playback_status():
    if not audio_ready:
        return jsonify(playing=False, audio_ready=False, error=audio_error)
    with audio_lock:
        playing = bool(pygame.mixer.get_busy())
    return jsonify(playing=playing, audio_ready=True)


@app.post("/api/volume")
def set_volume():
    global _current_volume
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="A JSON request body is required"), 400
    try:
        volume = float(data["volume"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Volume must be a number from 0.0 to 1.0"), 400
    if not 0.0 <= volume <= 1.0:
        return jsonify(error="Volume must be from 0.0 to 1.0"), 400
    if not initialize_audio():
        return jsonify(error=audio_error), 503
    with audio_lock:
        _current_volume = volume
        for snd in _sound_cache.values():
            snd.set_volume(volume)
    return jsonify(status="success", volume=volume)

import os
from flask import Flask, jsonify, request, render_template_string
import pygame

app = Flask(__name__)

# Initialize Pygame Mixer for instant audio playback & interruption
pygame.mixer.init()

# Ensure sound directory exists
SOUND_DIR = os.path.join(os.path.dirname(__file__), "sounds")
if not os.path.exists(SOUND_DIR):
    os.makedirs(SOUND_DIR)

def get_available_sounds():
    """Dynamically scan the sounds directory for supported audio formats."""
    sounds = []
    supported_extensions = ('.mp3', '.wav', '.ogg')
    
    if os.path.exists(SOUND_DIR):
        for filename in sorted(os.listdir(SOUND_DIR)):
            if filename.lower().endswith(supported_extensions):
                # Create a unique ID from the filename (without extension)
                file_id = os.path.splitext(filename)[0]
                # Create a clean display name (capitalize, replace underscores/hyphens with spaces)
                display_name = file_id.replace('_', ' ').replace('-', ' ').title()
                
                sounds.append({
                    "id": file_id,
                    "name": display_name,
                    "file": filename
                })
    return sounds

# Embedded HTML/JS Dashboard Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Soundboard (Python Prototype)</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --active-color: #22c55e;
            --border-color: #334155;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        header {
            width: 100%;
            max-width: 800px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin-bottom: 25px;
        }
        h1 { margin: 0; font-size: 1.8rem; text-align: center; }
        .controls-bar {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            background: var(--card-bg);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }
        input[type="text"] {
            flex: 1;
            min-width: 200px;
            padding: 10px 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-color);
            color: var(--text-color);
            font-size: 1rem;
        }
        .volume-control { display: flex; align-items: center; gap: 10px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 15px;
            width: 100%;
            max-width: 800px;
        }
        .sound-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.1s ease, background-color 0.2s ease;
            user-select: none;
            min-height: 100px;
        }
        .sound-card:active { transform: scale(0.96); }
        .sound-card.playing {
            background-color: rgba(34, 197, 94, 0.15);
            border-color: var(--active-color);
        }
        .sound-name { font-size: 1.1rem; font-weight: 600; text-align: center; margin-bottom: 10px; }
        .rename-btn {
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 0.8rem;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
        }
        .rename-btn:hover { color: var(--text-color); background: rgba(255, 255, 255, 0.05); }
        #status { font-size: 0.85rem; color: #94a3b8; margin-top: 15px; }
    </style>
</head>
<body>
    <header>
        <h1>WiFi Soundboard (Auto-Scan)</h1>
        <div class="controls-bar">
            <input type="text" id="searchInput" placeholder="Search sounds..." oninput="filterSounds()">
            <div class="volume-control">
                <label for="volumeSlider">Volume:</label>
                <input type="range" id="volumeSlider" min="0" max="100" value="100" oninput="updateVolume(this.value)">
            </div>
        </div>
    </header>

    <div class="grid" id="soundGrid"></div>
    <div id="status">Connecting to server...</div>

    <script>
        let sounds = [];

        async function fetchSounds() {
            try {
                const response = await fetch('/api/sounds');
                sounds = await response.json();
                renderSounds(sounds);
                document.getElementById('status').innerText = 'Connected (Auto-synced)';
            } catch (error) {
                document.getElementById('status').innerText = 'Connection lost. Retrying...';
                setTimeout(fetchSounds, 2000);
            }
        }

        function renderSounds(soundArray) {
            const grid = document.getElementById('soundGrid');
            grid.innerHTML = '';
            if (soundArray.length === 0) {
                grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #94a3b8;">No sound files found in the /sounds folder!</p>';
                return;
            }
            soundArray.forEach(sound => {
                const card = document.createElement('div');
                card.className = 'sound-card';
                card.id = `card-${sound.id}`;
                const customName = localStorage.getItem(`name_${sound.id}`) || sound.name;

                card.innerHTML = `
                    <div class="sound-name" id="name-${sound.id}">${customName}</div>
                    <button class="rename-btn" onclick="event.stopPropagation(); renameSound('${sound.id}')">Rename</button>
                `;
                card.onclick = () => playSound(sound.id);
                grid.appendChild(card);
            });
        }

        async function playSound(id) {
            const card = document.getElementById(`card-${id}`);
            card.classList.add('playing');
            try {
                await fetch(`/api/play/${id}`, { method: 'POST' });
            } catch (error) {
                console.error('Failed to trigger sound', error);
            }
            setTimeout(() => card.classList.remove('playing'), 300);
        }

        function filterSounds() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filtered = sounds.filter(sound => {
                const currentName = (localStorage.getItem(`name_${sound.id}`) || sound.name).toLowerCase();
                return currentName.includes(query);
            });
            renderSounds(filtered);
        }

        function renameSound(id) {
            const currentNameElement = document.getElementById(`name-${id}`);
            const newName = prompt('Enter a new name for this sound:', currentNameElement.innerText);
            if (newName && newName.trim() !== '') {
                localStorage.setItem(`name_${id}`, newName.trim());
                currentNameElement.innerText = newName.trim();
            }
        }

        async function updateVolume(val) {
            await fetch('/api/volume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ volume: val / 100 })
            });
        }

        fetchSounds();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/sounds')
def get_sounds():
    # Automatically scans folder on every fetch so you can drop files in without restarting
    return jsonify(get_available_sounds())

@app.route('/api/play/<sound_id>', methods=['POST'])
def play_sound(sound_id):
    sounds = get_available_sounds()
    sound = next((s for s in sounds if s["id"] == sound_id), None)
    
    if not sound:
        return jsonify({"error": "Sound not found"}), 404
    
    file_path = os.path.join(SOUND_DIR, sound["file"])
    if not os.path.exists(file_path):
        return jsonify({"error": f"File missing on disk: {sound['file']}"}), 404

    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        return jsonify({"status": "playing", "id": sound_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/volume', methods=['POST'])
def set_volume():
    data = request.json
    volume = float(data.get("volume", 1.0))
    pygame.mixer.music.set_volume(volume)
    return jsonify({"status": "success", "volume": volume})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
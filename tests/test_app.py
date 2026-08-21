import app as soundboard
import zipfile


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"WiFi Soundboard" in response.data
    assert "wsb_device_id=" in response.headers.get("Set-Cookie", "")
    assert b"app.js?v=7" in response.data
    assert b"app.css?v=3" in response.data


def test_card_favorite_is_centered_below_play_control():
    styles = (soundboard.BASE_DIR / "static" / "app.css").read_text(encoding="utf-8")
    rule = ".sound-pad>.favorite{position:absolute;left:50%;bottom:9px;top:auto;transform:translateX(-50%)"
    assert rule in styles
    assert ".sound-pad{padding-bottom:48px}" in styles


def test_mobile_scale_controls_persist_on_device():
    page = (soundboard.BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    script = (soundboard.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    styles = (soundboard.BASE_DIR / "static" / "app.css").read_text(encoding="utf-8")
    assert 'id="scaleDown"' in page
    assert 'id="scaleUp"' in page
    assert "wifiSoundboardScale" in script
    assert "storageSet('wifiSoundboardScale'" in script
    assert "--board-scale" in styles


def test_mobile_script_has_insecure_lan_id_fallback():
    script = (soundboard.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert "function createId()" in script
    assert "Math.random()" in script
    assert "crypto.randomUUID();" not in script


def test_mobile_browser_is_registered(client):
    soundboard.admin_state.clients.clear()
    response = client.get("/", headers={"User-Agent": "Mozilla/5.0 iPhone Mobile"})
    assert response.status_code == 200
    clients = soundboard.admin_state.active_clients()
    assert len(clients) == 1
    assert clients[0]["name"] == "Mobile Browser"


def test_blocked_cookie_is_rejected(client):
    soundboard.admin_state.clients.clear()
    response = client.get("/")
    device_id = next(iter(soundboard.admin_state.clients))
    soundboard.admin_state.blocked_devices.add(device_id)
    try:
        blocked = client.get("/api/sounds")
        assert blocked.status_code == 403
    finally:
        soundboard.admin_state.blocked_devices.discard(device_id)


def test_sound_ids_are_unique_for_same_stem(tmp_path, monkeypatch):
    (tmp_path / "alert.mp3").touch()
    (tmp_path / "alert.wav").touch()
    monkeypatch.setattr(soundboard, "SOUND_DIR", tmp_path)
    sounds = soundboard.get_available_sounds()
    assert len(sounds) == 2
    assert len({sound["id"] for sound in sounds}) == 2


def test_sound_id_is_32_chars():
    assert len(soundboard.sound_id("airhorn.mp3")) == 32


def test_default_drops_are_flattened_into_sounds(tmp_path, monkeypatch):
    archive = tmp_path / "drops.zip"
    destination = tmp_path / "sounds"
    destination.mkdir()
    with zipfile.ZipFile(archive, "w") as drops:
        drops.writestr("Drops/Category/hello.mp3", b"audio")
        drops.writestr("Drops/README.md", b"ignore")
    monkeypatch.setattr(soundboard, "DROPS_ARCHIVE", archive)
    monkeypatch.setattr(soundboard, "SOUND_DIR", destination)
    assert soundboard.ensure_default_sounds() == 1
    assert (destination / "hello.mp3").read_bytes() == b"audio"
    assert soundboard.ensure_default_sounds() == 0


def test_ymh_sounds_are_identified_from_bundled_archive(tmp_path, monkeypatch):
    archive = tmp_path / "YourMomDrops.zip"
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    (sounds / "hello.mp3").touch()
    (sounds / "other.mp3").touch()
    with zipfile.ZipFile(archive, "w") as drops:
        drops.writestr("YourMomDrops/Category/hello.mp3", b"audio")
    monkeypatch.setattr(soundboard, "DROPS_ARCHIVE", archive)
    monkeypatch.setattr(soundboard, "SOUND_DIR", sounds)
    available = {sound["file"]: sound for sound in soundboard.get_available_sounds()}
    assert available["hello.mp3"]["ymh"] is True
    assert available["other.mp3"]["ymh"] is False


def test_default_app_includes_persistent_ymh_board():
    script = (soundboard.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert "{id:'ymh',name:'YMH',pads:[],system:true}" in script
    assert "if(sound.ymh&&!ymhAssigned.has(sound.id))" in script


def test_unknown_sound_returns_404(client):
    response = client.post("/api/play/not-a-real-id")
    assert response.status_code == 404


def test_volume_requires_json(client):
    response = client.post("/api/volume")
    assert response.status_code == 400


def test_volume_rejects_invalid_values(client):
    for value in (-0.1, 1.1, "loud"):
        response = client.post("/api/volume", json={"volume": value})
        assert response.status_code == 400


def test_valid_volume(monkeypatch, client):
    monkeypatch.setattr(soundboard, "initialize_audio", lambda: True)
    response = client.post("/api/volume", json={"volume": 0.5})
    assert response.status_code == 200
    assert response.get_json()["volume"] == 0.5
    assert soundboard._current_volume == 0.5


class FakeSound:
    def __init__(self, filepath):
        self.filepath = filepath
        self.volume = 1.0

    def set_volume(self, v):
        self.volume = v

    def play(self):
        pass


class FakeMixer:
    Sound = FakeSound

    @staticmethod
    def init():
        pass

    @staticmethod
    def set_num_channels(n):
        pass

    @staticmethod
    def stop():
        pass

    @staticmethod
    def get_busy():
        return False


class FakePygame:
    mixer = FakeMixer()


import pytest


@pytest.fixture
def client():
    soundboard.app.config.update(TESTING=True)
    return soundboard.app.test_client()

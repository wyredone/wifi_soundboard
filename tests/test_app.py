import app as soundboard


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"WiFi Soundboard" in response.data


def test_sound_ids_are_unique_for_same_stem(tmp_path, monkeypatch):
    (tmp_path / "alert.mp3").touch()
    (tmp_path / "alert.wav").touch()
    monkeypatch.setattr(soundboard, "SOUND_DIR", tmp_path)
    sounds = soundboard.get_available_sounds()
    assert len(sounds) == 2
    assert len({sound["id"] for sound in sounds}) == 2


def test_sound_id_is_32_chars():
    assert len(soundboard.sound_id("airhorn.mp3")) == 32


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

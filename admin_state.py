import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WiFiSoundboard"
try:
    APP_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    APP_DIR = Path.cwd() / ".runtime_data"
    APP_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DIR / "settings.json"
AUDIT_FILE = APP_DIR / "audit.jsonl"


@dataclass
class Client:
    device_id: str
    ip: str
    name: str
    user_agent: str
    connected_at: float
    last_seen: float
    requests: int = 1


class AdminState:
    def __init__(self):
        self.lock = threading.RLock()
        self.clients = {}
        self.blocked_devices = set()
        self.blocked_ips = set()
        self.kicked_devices = set()
        self.accept_connections = True
        self.settings = self._load_settings()
        self.blocked_devices.update(self.settings.get("blocked_devices", []))
        self.blocked_ips.update(self.settings.get("blocked_ips", []))
        self.accept_connections = self.settings.get("accept_connections", True)

    def _load_settings(self):
        defaults = {"schema": 1, "host": "0.0.0.0", "port": 8080,
                    "start_minimized": False, "close_to_tray": True,
                    "accept_connections": True, "blocked_devices": [], "blocked_ips": []}
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if data.get("schema") == 1:
                defaults.update(data)
        except (OSError, ValueError, TypeError):
            pass
        return defaults

    def save(self):
        with self.lock:
            self.settings.update({"accept_connections": self.accept_connections,
                                  "blocked_devices": sorted(self.blocked_devices),
                                  "blocked_ips": sorted(self.blocked_ips)})
            temp = SETTINGS_FILE.with_suffix(".tmp")
            temp.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
            temp.replace(SETTINGS_FILE)

    def audit(self, action, **details):
        row = {"timestamp": time.time(), "action": action, **details}
        with self.lock:
            with AUDIT_FILE.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def observe(self, device_id, ip, name, user_agent):
        now = time.time()
        with self.lock:
            client = self.clients.get(device_id)
            if client:
                client.last_seen = now
                client.requests += 1
                client.ip, client.name, client.user_agent = ip, name, user_agent
            else:
                client = Client(device_id, ip, name, user_agent, now, now)
                self.clients[device_id] = client
                self.audit("client_connected", device_id=device_id, ip=ip, name=name)

    def is_allowed(self, device_id, ip):
        with self.lock:
            return (self.accept_connections and device_id not in self.blocked_devices
                    and device_id not in self.kicked_devices and ip not in self.blocked_ips)

    def active_clients(self, max_age=15):
        cutoff = time.time() - max_age
        with self.lock:
            return [asdict(c) for c in self.clients.values() if c.last_seen >= cutoff]

    def kick(self, device_id):
        with self.lock:
            self.kicked_devices.add(device_id)
            client = self.clients.pop(device_id, None)
        self.audit("client_kicked", device_id=device_id, ip=client.ip if client else "")

    def block(self, device_id, block_ip=False):
        with self.lock:
            client = self.clients.pop(device_id, None)
            self.blocked_devices.add(device_id)
            if block_ip and client:
                self.blocked_ips.add(client.ip)
        self.save()
        self.audit("client_blocked", device_id=device_id, ip=client.ip if client else "", block_ip=block_ip)

    def unblock_all(self):
        with self.lock:
            self.blocked_devices.clear(); self.blocked_ips.clear(); self.kicked_devices.clear()
        self.save(); self.audit("blocklist_cleared")


admin_state = AdminState()

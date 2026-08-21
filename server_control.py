import io
import socket
import sys
import threading
import time
from pathlib import Path

import qrcode
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QSystemTrayIcon, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget)
from waitress import create_server

from admin_state import AUDIT_FILE, admin_state
from app import ASSET_DIR, SOUND_DIR, app, initialize_audio


def lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80)); value = sock.getsockname()[0]; sock.close()
        return value
    except OSError:
        return "127.0.0.1"


class ManagedServer:
    def __init__(self):
        self.server = None; self.thread = None

    @property
    def running(self): return bool(self.thread and self.thread.is_alive())

    def start(self, host, port):
        if self.running: return
        initialize_audio()
        self.server = create_server(app, host=host, port=port, threads=8)
        self.thread = threading.Thread(target=self.server.run, name="wifi-soundboard-server", daemon=True)
        self.thread.start(); admin_state.audit("server_started", host=host, port=port)

    def stop(self):
        if self.server:
            self.server.close(); admin_state.audit("server_stopped")
        self.server = None; self.thread = None


class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__(); self.server = ManagedServer()
        self.setWindowTitle("WiFi Soundboard — Server Control Center")
        self.resize(1120, 720); self.setMinimumSize(900, 600)
        icon = ASSET_DIR / "icons/app/wifi_soundboard.ico"
        if icon.exists(): self.setWindowIcon(QIcon(str(icon)))
        self._build(); self._tray(); self._load_theme()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000)
        if admin_state.settings.get("start_minimized"): QTimer.singleShot(0, self.hide)
        self.start_server()

    def _load_theme(self):
        theme = ASSET_DIR / "theme/neon.qss"
        if theme.exists(): QApplication.instance().setStyleSheet(theme.read_text(encoding="utf-8"))
        else: QApplication.instance().setStyleSheet("QWidget{background:#080a12;color:#f7f8ff} QPushButton{padding:8px}")

    def _build(self):
        root = QWidget(); outer = QVBoxLayout(root); outer.setContentsMargins(22,18,22,18)
        head = QHBoxLayout(); logo = QLabel(); pix = QPixmap(str(ASSET_DIR/"logo/logo_lockup_1600.png")); logo.setPixmap(pix.scaledToWidth(300,Qt.SmoothTransformation)); head.addWidget(logo)
        head.addStretch(); self.status = QLabel("● STARTING"); self.status.setObjectName("statusLabel"); head.addWidget(self.status); outer.addLayout(head)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs); self.setCentralWidget(root)
        self._dashboard(); self._clients(); self._settings(); self._logs()

    def _dashboard(self):
        page=QWidget(); layout=QVBoxLayout(page); row=QHBoxLayout()
        self.start_btn=QPushButton("Stop Server"); self.start_btn.clicked.connect(self.toggle_server); row.addWidget(self.start_btn)
        open_btn=QPushButton("Open Web Soundboard"); open_btn.clicked.connect(self.open_web); row.addWidget(open_btn)
        folder=QPushButton("Open Sounds Folder"); folder.clicked.connect(lambda: __import__('os').startfile(SOUND_DIR)); row.addWidget(folder); row.addStretch(); layout.addLayout(row)
        self.url=QLineEdit(); self.url.setReadOnly(True); layout.addWidget(QLabel("LAN ADDRESS")); layout.addWidget(self.url)
        self.qr=QLabel(); self.qr.setAlignment(Qt.AlignCenter); self.qr.setMinimumHeight(260); layout.addWidget(self.qr)
        self.summary=QLabel(); self.summary.setAlignment(Qt.AlignCenter); layout.addWidget(self.summary); self.tabs.addTab(page,"Dashboard")

    def _clients(self):
        page=QWidget(); layout=QVBoxLayout(page); toolbar=QHBoxLayout()
        self.accept=QCheckBox("Accept incoming connections"); self.accept.setChecked(admin_state.accept_connections); self.accept.toggled.connect(self.set_admission); toolbar.addWidget(self.accept)
        clear=QPushButton("Clear Blocklist"); clear.clicked.connect(self.clear_blocks); toolbar.addWidget(clear); toolbar.addStretch(); layout.addLayout(toolbar)
        self.client_table=QTableWidget(0,7); self.client_table.setHorizontalHeaderLabels(["Device","IP Address","Connected","Last Seen","Requests","Kick","Block"]); self.client_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); layout.addWidget(self.client_table)
        self.tabs.addTab(page,"Connected Clients")

    def _settings(self):
        page=QWidget(); form=QFormLayout(page); self.host=QLineEdit(admin_state.settings["host"]); self.port=QSpinBox(); self.port.setRange(1024,65535); self.port.setValue(admin_state.settings["port"])
        self.close_tray=QCheckBox(); self.close_tray.setChecked(admin_state.settings["close_to_tray"]); form.addRow("Bind address",self.host); form.addRow("Port",self.port); form.addRow("Close window to tray",self.close_tray)
        save=QPushButton("Save Settings"); save.clicked.connect(self.save_settings); form.addRow(save); form.addRow(QLabel("Restart the server after changing the bind address or port.")); self.tabs.addTab(page,"Settings")

    def _logs(self):
        page=QWidget(); layout=QVBoxLayout(page); self.log=QTextEdit(); self.log.setReadOnly(True); layout.addWidget(self.log); self.tabs.addTab(page,"Activity Log")

    def _tray(self):
        self.tray=QSystemTrayIcon(self.windowIcon(),self); menu=__import__('PySide6.QtWidgets',fromlist=['QMenu']).QMenu()
        show=QAction("Show Server Control",self); show.triggered.connect(self.restore); menu.addAction(show)
        toggle=QAction("Start / Stop Server",self); toggle.triggered.connect(self.toggle_server); menu.addAction(toggle)
        quit_action=QAction("Exit WiFi Soundboard",self); quit_action.triggered.connect(self.exit_app); menu.addAction(quit_action); self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason:self.restore() if reason==QSystemTrayIcon.DoubleClick else None); self.tray.show()

    def current_url(self): return f"http://{lan_ip()}:{self.port.value()}"
    def start_server(self):
        try: self.server.start(self.host.text().strip(),self.port.value()); self.make_qr()
        except Exception as exc: QMessageBox.critical(self,"Server start failed",str(exc))
    def toggle_server(self): self.server.stop() if self.server.running else self.start_server(); self.refresh()
    def open_web(self): __import__('webbrowser').open(self.current_url())
    def make_qr(self):
        image=qrcode.make(self.current_url()); data=io.BytesIO(); image.save(data,format="PNG"); pix=QPixmap(); pix.loadFromData(data.getvalue()); self.qr.setPixmap(pix.scaled(230,230,Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def set_admission(self,value): admin_state.accept_connections=value; admin_state.save(); admin_state.audit("admission_changed",enabled=value)
    def clear_blocks(self):
        if QMessageBox.question(self,"Clear blocklist","Allow all previously kicked and blocked devices?")==QMessageBox.Yes: admin_state.unblock_all(); self.refresh()
    def kick(self,device_id): admin_state.kick(device_id); self.refresh()
    def block(self,device_id):
        if QMessageBox.question(self,"Block device","Block this device and its current IP address?")==QMessageBox.Yes: admin_state.block(device_id,True); self.refresh()
    def save_settings(self):
        admin_state.settings.update({"host":self.host.text().strip(),"port":self.port.value(),"close_to_tray":self.close_tray.isChecked()}); admin_state.save(); QMessageBox.information(self,"Settings saved","Settings saved. Restart the server to apply network changes.")
    def refresh(self):
        running=self.server.running; self.status.setText("● ONLINE" if running else "● OFFLINE"); self.start_btn.setText("Stop Server" if running else "Start Server"); self.url.setText(self.current_url()); clients=admin_state.active_clients(); self.summary.setText(f"{len(clients)} connected device{'s' if len(clients)!=1 else ''}  •  {len(admin_state.blocked_devices)} blocked")
        self.client_table.setRowCount(len(clients)); now=time.time()
        for row,c in enumerate(clients):
            values=[c['name'],c['ip'],time.strftime('%H:%M:%S',time.localtime(c['connected_at'])),f"{int(now-c['last_seen'])}s ago",str(c['requests'])]
            for col,value in enumerate(values): self.client_table.setItem(row,col,QTableWidgetItem(value))
            kick=QPushButton("Kick"); kick.clicked.connect(lambda _,d=c['device_id']:self.kick(d)); self.client_table.setCellWidget(row,5,kick)
            block=QPushButton("Block"); block.clicked.connect(lambda _,d=c['device_id']:self.block(d)); self.client_table.setCellWidget(row,6,block)
        try: self.log.setPlainText("\n".join(AUDIT_FILE.read_text(encoding="utf-8").splitlines()[-250:])); self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        except OSError: pass
    def closeEvent(self,event):
        if self.close_tray.isChecked(): event.ignore(); self.hide(); self.tray.showMessage("WiFi Soundboard","Server control is still running in the tray.")
        else: self.exit_app()
    def restore(self): self.show(); self.raise_(); self.activateWindow()
    def exit_app(self): self.server.stop(); self.tray.hide(); QApplication.quit()


if __name__=="__main__":
    qt=QApplication(sys.argv); qt.setQuitOnLastWindowClosed(False); window=ControlCenter(); window.show(); sys.exit(qt.exec())

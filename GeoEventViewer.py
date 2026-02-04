import sys
import requests
import sqlite3
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMainWindow, QScrollArea, QFrame, 
                             QPushButton, QCalendarWidget, QDialog)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView
import resources_rc

# --- CONFIGURAÇÕES ---
VERSAO = "🌏 GEO EVENT VIEWER v3.9"
DEV_INFO = "Desenvolvido por: Daniel Boechat || Engenharia de Software"

# --- PERSISTÊNCIA (SQLITE) ---
class DBManager:
    def __init__(self):
        self.conn = sqlite3.connect("historico.db")
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, tipo_orig TEXT, mag TEXT, loc TEXT, prof REAL, 
                hora TEXT, data TEXT, lat REAL, lon REAL, categoria TEXT,
                UNIQUE(ts, loc)
            )
        """)
        self.conn.commit()

    def salvar_evento(self, ev):
        data_str = datetime.now().strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO eventos (ts, tipo_orig, mag, loc, prof, hora, data, lat, lon, categoria)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ev.ts, ev.tipo_orig, str(ev.mag), ev.loc, ev.prof, ev.hora, data_str, ev.lat, ev.lon, ev.categoria))
            self.conn.commit()
        except: pass

    def buscar_historico(self, cat, data):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM eventos WHERE categoria = ? AND data = ? ORDER BY ts DESC", (cat, data))
        return cursor.fetchall()

# --- MODELO DE DADOS ---
class EventoData:
    def __init__(self, ts, tipo_orig, mag, loc, prof, hora, lat, lon, cor, categoria):
        self.ts, self.tipo_orig, self.mag, self.loc = ts, tipo_orig, mag, loc
        self.prof, self.hora = prof, hora
        # Garantindo armazenamento rigoroso como float para cálculos do mapa
        self.lat = float(lat)
        self.lon = float(lon)
        self.cor, self.categoria = cor, categoria

# --- CLASSES DE SERVIÇO (LÓGICA DE COORDENADAS POR EVENTO) ---

class SismoService:
    @staticmethod
    def fetch():
        items = []
        try:
            r = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson", timeout=5).json()
            for f in r['features']:
                p, g = f['properties'], f['geometry']['coordinates']
                if p['tsunami'] == 0:
                    # g[0]=Lon, g[1]=Lat -> Invertemos para EventoData(lat, lon)
                    items.append(EventoData(p['time'], "Sismo", p['mag'], p['place'], g[2], 
                                    datetime.fromtimestamp(p['time']/1000).strftime("%H:%M"), 
                                    g[1], g[0], "#61afef", "sismo"))
        except: pass
        return items

class TsunamiService:
    @staticmethod
    def fetch():
        items = []
        try:
            r = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson", timeout=5).json()
            for f in r['features']:
                p, g = f['properties'], f['geometry']['coordinates']
                if p['tsunami'] == 1:
                    # g[1] é Latitude, g[0] é Longitude
                    items.append(EventoData(p['time'], "Tsunami", p['mag'], p['place'], g[2], 
                                    datetime.fromtimestamp(p['time']/1000).strftime("%H:%M"), 
                                    g[1], g[0], "#e06c75", "tsunami"))
        except: pass
        return items

class VulcaoService:
    @staticmethod
    def fetch():
        items = []
        try:
            r = requests.get("https://volcano.si.edu/news/WeeklyVolcanoRSS.xml", timeout=5)
            root = ET.fromstring(r.content)
            now = datetime.now()
            # Exemplo de Coordenadas para Vulcão (Etna) - Para produção, seria necessário um parser de Lat/Lon do XML
            for item in root.findall('.//item')[:3]:
                items.append(EventoData(now.timestamp()*1000, "Erupção", "Ativo", item.find('title').text, 0, now.strftime("%H:%M"), 37.75, 14.99, "#98c379", "vulcao"))
        except: pass
        return items

class SolarService:
    @staticmethod
    def fetch():
        now = datetime.now()
        # Evento global: Centralizamos no equador (0,0) para mostrar o raio planetário
        return [EventoData(now.timestamp()*1000, "Tempestade Solar", "R1", "Ionosfera Global", 0, now.strftime("%H:%M"), 0.0, 0.0, "#e5c07b", "solar")]

class ClimaService:
    @staticmethod
    def fetch():
        now = datetime.now()
        # Mock para Furacão (Coordenadas do Atlântico Norte)
        return [EventoData(now.timestamp()*1000, "Ciclone", "Monitor", "Atlântico Norte", 0, now.strftime("%H:%M"), 25.0, -45.0, "#c678dd", "clima")]

# --- UI COMPONENTS ---

class JanelaMapa(QMainWindow):
    def __init__(self, evento):
        super().__init__()
        self.setWindowTitle(f"Impacto Geográfico: {evento.loc}")
        self.setWindowIcon(QIcon(":/img/favicon.png"))
        self.resize(900, 600)
        self.browser = QWebEngineView()
        
        raio = 800000 if evento.categoria == "tsunami" else 500000 if evento.categoria == "clima" else 8000000 if evento.categoria == "solar" else 0
        zoom = 2 if evento.categoria == "solar" else 7
        
        # IMPORTANTE: Leaflet exige obrigatoriamente [LATITUDE, LONGITUDE]
        html = f"""
        <html>
            <head>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
                <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
                <style>#map {{ height: 100%; width: 100%; }} body {{ margin: 0; }}</style>
            </head>
            <body>
                <div id="map"></div>
                <script>
                    var map = L.map('map').setView([{evento.lat}, {evento.lon}], {zoom});
                    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
                    L.marker([{evento.lat}, {evento.lon}]).addTo(map).bindPopup("<b>{evento.loc}</b>").openPopup();
                    {f"L.circle([{evento.lat}, {evento.lon}], {{color: '{evento.cor}', radius: {raio}}}).addTo(map);" if raio > 0 else ""}
                </script>
            </body>
        </html>
        """
        self.browser.setHtml(html)
        self.setCentralWidget(self.browser)

class EventoRow(QFrame):
    def __init__(self, evento):
        super().__init__()
        self.evento = evento
        self.setObjectName("Card"); self.setFixedHeight(120); self.setCursor(QCursor(Qt.PointingHandCursor))
        self.installEventFilter(self)
        layout = QHBoxLayout(self)
        dot = QLabel(" ● "); dot.setStyleSheet(f"color: {evento.cor}; font-size: 18pt;")
        layout.addWidget(dot)
        col1 = QVBoxLayout()
        lbl_tit = QLabel(f"{evento.tipo_orig.upper()} - {evento.mag}"); lbl_tit.setStyleSheet(f"color: {evento.cor}; font-weight: bold;")
        lbl_loc = QLabel(f"📍 {evento.loc}"); lbl_loc.setStyleSheet("color: #abb2bf; font-size: 9pt;")
        col1.addWidget(lbl_tit); col1.addWidget(lbl_loc); layout.addLayout(col1, 2)
        col2 = QVBoxLayout()
        impactos = {"solar": ("Aviação/GPS", "Crítico"), "tsunami": ("Marítimo", "Muito Alto"), "clima": ("Atmosférico", "Alto"), "sismo": ("Terrestre", "Médio"), "vulcao": ("Terrestre", "Alto")}
        tipo_imp, nivel = impactos.get(evento.categoria, ("Geral", "Médio"))
        lbl_imp = QLabel(f"Impacto: {tipo_imp}\nNível: {nivel}"); lbl_imp.setStyleSheet("font-size: 8pt; color: #d19a66;")
        col2.addWidget(lbl_imp); layout.addLayout(col2, 1)
        col3 = QVBoxLayout()
        lbl_h = QLabel(evento.hora); lbl_h.setStyleSheet("font-weight: bold;")
        col3.addWidget(lbl_h); col3.setAlignment(Qt.AlignCenter); layout.addLayout(col3, 1)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter: 
            self.setStyleSheet(f"QFrame#Card {{ background-color: #353b45; border: 2px solid {self.evento.cor}; border-radius: 8px; }}")
        elif event.type() == QEvent.Leave: 
            self.setStyleSheet(f"QFrame#Card {{ background-color: #282c34; border: 1px solid #3e4451; border-radius: 8px; }}")
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        self.m = JanelaMapa(self.evento); self.m.show()

class TileMenu(QPushButton):
    def __init__(self, titulo, tipo, cor, freq):
        super().__init__()
        self.setFixedSize(210, 100); self.tipo, self.cor, self.freq = tipo, cor, freq
        self.installEventFilter(self)
        l = QVBoxLayout(self)
        self.t = QLabel(titulo); self.t.setStyleSheet("font-weight: bold; color: white; background: transparent;")
        self.i = QLabel(f"Freq: {freq}min\nÚltimo: --:--"); self.i.setStyleSheet("font-size: 7pt; color: #abb2bf; background: transparent;")
        l.addWidget(self.t, 0, Qt.AlignCenter); l.addWidget(self.i, 0, Qt.AlignCenter)
        self.set_st(False)

    def set_st(self, h):
        bg = self.cor if h else "#282c34"
        text_color = "black" if h else "white"
        info_color = "#282c34" if h else "#abb2bf"
        self.t.setStyleSheet(f"color: {text_color}; font-weight: bold; background: transparent;")
        self.i.setStyleSheet(f"color: {info_color}; font-size: 7pt; background: transparent;")
        self.setStyleSheet(f"QPushButton {{ background-color: {bg}; border-bottom: 4px solid {self.cor}; border-radius: 10px; }}")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter: self.set_st(True)
        elif event.type() == QEvent.Leave: self.set_st(False)
        return super().eventFilter(obj, event)

class JanelaHistorico(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Histórico de Coleta"); self.resize(800, 600)
        self.setStyleSheet("background-color: #1e2227; color: #abb2bf;")
        layout = QVBoxLayout(self)
        self.cal = QCalendarWidget(); layout.addWidget(self.cal)
        self.area = QScrollArea(); self.area.setWidgetResizable(True); self.w = QWidget(); self.l = QVBoxLayout(self.w)
        self.area.setWidget(self.w); layout.addWidget(self.area)
        btn = QPushButton("BUSCAR HISTÓRICO"); btn.clicked.connect(self.buscar); layout.addWidget(btn)

    def buscar(self):
        d = self.cal.selectedDate().toString("yyyy-MM-dd")
        while self.l.count():
            item = self.l.takeAt(0).widget()
            if item: item.deleteLater()
        for c in ["sismo", "tsunami", "vulcao", "clima", "solar"]:
            res = self.db.buscar_historico(c, d)
            if res:
                h = QLabel(f"--- {c.upper()} ---"); h.setStyleSheet("color: #61afef; font-weight: bold; margin-top: 10px;")
                self.l.addWidget(h)
                for r in res: self.l.addWidget(QLabel(f"[{r[6]}] {r[2]} | Mag: {r[3]} | {r[4]}"))

# --- MAIN WINDOW ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DBManager()
        self.setWindowTitle(VERSAO); self.resize(1150, 850); self.setWindowIcon(QIcon(":/img/favicon.png"))
        self.setStyleSheet("QMainWindow, QWidget { background-color: #1e2227; color: #abb2bf; } QScrollArea { border: none; }")
        self.categoria_ativa, self.eventos_cache = "Geral", []
        container = QWidget(); self.main_layout = QVBoxLayout(container)
        header = QHBoxLayout(); lbl = QLabel("GEO EVENT VIEWER"); lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: #61afef;")
        self.btn_h = QPushButton("📜 HISTÓRICO"); self.btn_h.setFixedSize(120, 30); self.btn_h.installEventFilter(self)
        self.btn_h.clicked.connect(lambda: JanelaHistorico(self.db).exec_())
        self.set_btn_h_style(False)
        header.addWidget(lbl); header.addStretch(); header.addWidget(self.btn_h)
        self.main_layout.addLayout(header)
        self.tiles = {"sismo": TileMenu("SISMOS", "sismo", "#61afef", 1), "tsunami": TileMenu("TSUNAMIS", "tsunami", "#e06c75", 1), "vulcao": TileMenu("VULCÕES", "vulcao", "#98c379", 10), "clima": TileMenu("CLIMA", "clima", "#c678dd", 10), "solar": TileMenu("SOLAR", "solar", "#e5c07b", 10)}
        t_lay = QHBoxLayout()
        for t in self.tiles.values(): t_lay.addWidget(t); t.clicked.connect(lambda ch, arg=t: self.filtrar(arg))
        self.main_layout.addLayout(t_lay)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.list_w = QWidget(); self.list_l = QVBoxLayout(self.list_w); self.list_l.setAlignment(Qt.AlignTop); self.scroll.setWidget(self.list_w); self.main_layout.addWidget(self.scroll)
        self.setCentralWidget(container); self.timer = QTimer(); self.timer.timeout.connect(self.fetch_data); self.timer.start(60000); self.fetch_data()

    def set_btn_h_style(self, h):
        bg = "#61afef" if h else "transparent"
        color = "#1e2227" if h else "#61afef"
        self.btn_h.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: {color}; border: none; border-radius: 5px; font-weight: bold; }}")

    def eventFilter(self, obj, event):
        if obj == self.btn_h:
            if event.type() == QEvent.Enter: self.set_btn_h_style(True)
            elif event.type() == QEvent.Leave: self.set_btn_h_style(False)
        return super().eventFilter(obj, event)

    def filtrar(self, t): self.categoria_ativa = t.tipo; self.update_list()

    def fetch_data(self):
        temp = []
        services = [SismoService, TsunamiService, VulcaoService, SolarService, ClimaService]
        for s in services:
            res = s.fetch()
            for r in res: 
                temp.append(r)
                self.db.salvar_evento(r)
        temp.sort(key=lambda x: x.ts, reverse=True)
        self.eventos_cache = temp
        for c, t in self.tiles.items():
            v = [e for e in temp if e.categoria == c]
            if v: t.i.setText(f"Freq: {t.freq}min\nÚltimo: {v[0].hora}")
        self.update_list()

    def update_list(self):
        while self.list_l.count():
            w = self.list_l.takeAt(0).widget()
            if w: w.deleteLater()
        for ev in self.eventos_cache:
            if self.categoria_ativa == "Geral" or ev.categoria == self.categoria_ativa: self.list_l.addWidget(EventoRow(ev))

if __name__ == "__main__":
    app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec_())
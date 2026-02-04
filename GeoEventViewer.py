import sys
import requests
import sqlite3
import random
import xml.etree.ElementTree as ET
from datetime import datetime
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMainWindow, QScrollArea, QFrame, 
                             QPushButton, QCalendarWidget, QDialog)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView
import resources_rc

# Tente importar winsound (apenas Windows), senão ignora
try:
    import winsound
except ImportError:
    winsound = None

# --- CONFIGURAÇÕES GERAIS ---
VERSAO = "GEO EVENT VIEWER"
USER_AGENT = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoViewer/5.1"}
# Tempo para considerar um evento como "AGORA" (em milissegundos) -> 40 minutos
TEMPO_RECENTE_MS = 40 * 60 * 1000 

# --- GERENCIADOR DE BANCO DE DADOS ---
class DBManager:
    def __init__(self):
        self.conn = sqlite3.connect("historico_v5.db")
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, 
                tipo_orig TEXT, 
                loc TEXT, 
                lat REAL, lon REAL, 
                categoria TEXT,
                escala_tecnica TEXT,
                tipo_impacto TEXT,
                nivel_impacto TEXT,
                risco_vitimas TEXT,
                hora TEXT, data TEXT,
                UNIQUE(ts, loc)
            )
        """)
        self.conn.commit()

    def salvar_evento(self, ev):
        data_str = datetime.now().strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO eventos 
                (ts, tipo_orig, loc, lat, lon, categoria, escala_tecnica, tipo_impacto, nivel_impacto, risco_vitimas, hora, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ev.ts, ev.titulo, ev.loc, ev.lat, ev.lon, ev.categoria, ev.escala, ev.impacto_tipo, ev.impacto_nivel, ev.risco_vitimas, ev.hora, data_str))
            self.conn.commit()
        except Exception as e:
            print(f"Erro BD: {e}")

    def buscar_historico(self, cat, data):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM eventos WHERE categoria = ? AND data = ? ORDER BY ts DESC", (cat, data))
        return cursor.fetchall()

# --- MODELO DE DADOS ---
class EventoData:
    def __init__(self, ts, categoria, titulo, loc, lat, lon, cor, 
                 escala_tecnica, impacto_tipo, impacto_nivel, risco_vitimas):
        self.ts = ts
        self.categoria = categoria
        self.titulo = titulo
        self.loc = loc
        self.lat = float(lat)
        self.lon = float(lon)
        self.cor = cor
        self.hora = datetime.fromtimestamp(ts/1000).strftime("%H:%M")
        
        self.escala = escala_tecnica
        self.impacto_tipo = impacto_tipo
        self.impacto_nivel = impacto_nivel
        self.risco_vitimas = risco_vitimas

# --- SERVIÇOS DE COLETA ---

class SismoService:
    @staticmethod
    def analisar_risco(mag):
        mag = float(mag)
        if mag >= 7.0: return "Richter " + str(mag), "Muito Alto", "Alto Risco"
        if mag >= 6.0: return "Richter " + str(mag), "Alto", "Médio Risco"
        if mag >= 4.5: return "Richter " + str(mag), "Médio", "Baixo Risco"
        return "Richter " + str(mag), "Baixo", "Sem Risco"

    @staticmethod
    def fetch():
        items = []
        try:
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            r = requests.get(url, headers=USER_AGENT, timeout=5).json()
            for f in r['features']:
                p, g = f['properties'], f['geometry']['coordinates']
                if p['tsunami'] == 0:
                    escala, nivel, risco = SismoService.analisar_risco(p['mag'])
                    
                    # Extração da Sigla/País (última parte após a vírgula)
                    loc_full = p['place']
                    pais = loc_full.split(',')[-1].strip() if ',' in loc_full else "Intl"
                    # Padrão: PAÍS - TERREMOTO - Graus
                    novo_titulo = f"{pais.upper()} - TERREMOTO - {p['mag']} Richter"
                    
                    items.append(EventoData(
                        ts=p['time'], categoria="sismo", titulo=novo_titulo, loc=p['place'],
                        lat=g[1], lon=g[0], cor="#61afef", escala_tecnica=escala,
                        impacto_tipo="Terrestre / Estrutural", impacto_nivel=nivel, risco_vitimas=risco
                    ))
        except: pass
        return items

class TsunamiService:
    @staticmethod
    def analisar_risco(mag):
        m = float(mag)
        if m >= 7.5: return "Papadopoulos IV-V", "Muito Alto", "Alto Risco"
        return "Papadopoulos II-III", "Alto", "Médio Risco"

    @staticmethod
    def fetch():
        items = []
        try:
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            r = requests.get(url, headers=USER_AGENT, timeout=5).json()
            for f in r['features']:
                if f['properties']['tsunami'] == 1:
                    p, g = f['properties'], f['geometry']['coordinates']
                    escala, nivel, risco = TsunamiService.analisar_risco(p['mag'])
                    items.append(EventoData(
                        ts=p['time'], categoria="tsunami", titulo="Alerta de Tsunami", loc=p['place'],
                        lat=g[1], lon=g[0], cor="#98c379", # VERDE para Tsunami
                        escala_tecnica=escala, impacto_tipo="Costeiro / Marítimo", 
                        impacto_nivel=nivel, risco_vitimas=risco
                    ))
        except: pass
        return items

class VulcaoService:
    @staticmethod
    def fetch():
        items = []
        try:
            url = "https://volcano.si.edu/news/WeeklyVolcanoRSS.xml"
            r = requests.get(url, headers=USER_AGENT, timeout=8)
            namespaces = {'georss': 'http://www.georss.org/georss'}
            root = ET.fromstring(r.content)
            now_ts = datetime.now().timestamp() * 1000
            
            for item in root.findall('.//item')[:4]:
                title_raw = item.find('title').text
                desc = item.find('description').text
                
                import re
                match = re.search(r'(.*)\((.*)\)', title_raw)
                nome_vulcao, pais_vulcao = (match.group(1).strip(), match.group(2).strip()) if match else (title_raw, "Global")
                novo_titulo = f"{pais_vulcao.upper()} - VULCÃO - {nome_vulcao}"
                
                geo = item.find('georss:point', namespaces)
                lat, lon = (float(geo.text.split()[0]), float(geo.text.split()[1])) if geo is not None else (0.0, 0.0)
                
                nivel, risco = ("Alto", "Médio Risco") if any(x in desc.lower() for x in ["evacuation", "lava", "ash", "explosion"]) else ("Médio", "Baixo Risco")
                
                items.append(EventoData(
                    ts=now_ts, categoria="vulcao", titulo=novo_titulo, loc=title_raw,
                    lat=lat, lon=lon, cor="#e06c75", # VERMELHO para Vulcão
                    escala_tecnica="Erupção Ativa", impacto_tipo="Atmosférico / Aéreo", 
                    impacto_nivel=nivel, risco_vitimas=risco
                ))
                now_ts -= 1000
        except: pass
        return items

class SolarService:
    @staticmethod
    def fetch():
        now = datetime.now()
        # Simulação
        flares = [("B1", "Muito Baixo"), ("C3", "Baixo"), ("M1", "Médio"), ("X1", "Muito Alto")]
        f_sel = flares[1] 
        risco = "Sem Risco" if f_sel[0][0] in ['A','B','C'] else "Médio Risco"
        return [EventoData(
            ts=now.timestamp()*1000, categoria="solar", titulo="Atividade Solar", loc="Ionosfera Global",
            lat=0.0, lon=0.0, cor="#e5c07b", escala_tecnica=f"Flare {f_sel[0]}",
            impacto_tipo="Telecom / GPS", impacto_nivel=f_sel[1], risco_vitimas=risco
        )]

class ClimaService:
    @staticmethod
    def fetch():
        # Simulador de Ciclones/Furacões (Geralmente dados de NHC/NOAA)
        now = datetime.now()
        nomes = ["Alberto", "Beryl", "Chris", "Debby", "Ernesto", "Francine", "Gordon", "Helene"]
        nome_sel = random.choice(nomes)
        vento = random.choice([120, 160, 200, 260])
        
        if vento > 252: escala, nivel, risco, cat = "Cat 5", "Muito Alto", "Alto Risco", "5"
        elif vento > 178: escala, nivel, risco, cat = "Cat 3", "Alto", "Médio Risco", "3"
        else: escala, nivel, risco, cat = "Cat 1", "Médio", "Baixo Risco", "1"

        return [EventoData(
            ts=now.timestamp()*1000, categoria="clima", 
            titulo=f"FURACÃO {nome_sel} (Cat {cat})", loc="Atlântico Norte / Caribe",
            lat=random.uniform(15, 35), lon=random.uniform(-85, -45), cor="#c678dd", 
            escala_tecnica=f"Saffir-Simpson {escala} ({vento}km/h)",
            impacto_tipo="Inundação / Ventos Fortes", impacto_nivel=nivel, risco_vitimas=risco
        )]

# --- UI COMPONENTS ---

class EventoRow(QFrame):
    # Sinal criado para passar o evento para a MainWindow abrir o mapa
    clique_mapa = pyqtSignal(object)

    def __init__(self, evento, is_happening_now=False):
        super().__init__()
        self.evento = evento
        self.is_blink_active = False
        self.setObjectName("Card")
        self.setFixedHeight(100)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.installEventFilter(self)
        
        main_layout = QHBoxLayout(self)
        
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {evento.cor}; font-size: 24pt;")
        main_layout.addWidget(dot)

        c1 = QVBoxLayout()
        lbl_tit = QLabel(f"{evento.titulo}")
        lbl_tit.setStyleSheet(f"color: {evento.cor}; font-weight: bold; font-size: 12pt;")
        lbl_loc = QLabel(f"📍 {evento.loc}")
        lbl_loc.setStyleSheet("color: #abb2bf; font-size: 9pt;")
        lbl_loc.setWordWrap(True)
        c1.addWidget(lbl_tit); c1.addWidget(lbl_loc); main_layout.addLayout(c1, 3)

        c2 = QVBoxLayout()
        lbl_escala = QLabel(f"📐 {evento.escala}")
        lbl_escala.setStyleSheet("color: #d19a66; font-weight: bold;")
        lbl_imp_tipo = QLabel(f"Impacto: {evento.impacto_tipo}")
        lbl_imp_tipo.setStyleSheet("color: #98c379; font-size: 8pt;")
        c2.addWidget(lbl_escala); c2.addWidget(lbl_imp_tipo); main_layout.addLayout(c2, 3)

        c3 = QVBoxLayout()
        lbl_nivel = QLabel(f"Nível: {evento.impacto_nivel.upper()}")
        lbl_nivel.setStyleSheet("color: white; font-weight: bold; font-size: 8pt;")
        cor_risco = "#e06c75" if "Alto" in evento.risco_vitimas else "#98c379"
        lbl_risco = QLabel(f"👥 {evento.risco_vitimas}")
        lbl_risco.setStyleSheet(f"color: {cor_risco}; font-size: 8pt; font-weight: bold;")
        lbl_hora = QLabel(evento.hora)
        lbl_hora.setStyleSheet("color: #5c6370; font-size: 14pt; font-weight: bold;")
        
        c3.addWidget(lbl_nivel); c3.addWidget(lbl_risco); c3.addWidget(lbl_hora, 0, Qt.AlignRight)
        main_layout.addLayout(c3, 2)
        
        self.set_style(False)

        # Lógica de Piscar: Só inicia se estiver acontecendo "agora" (is_happening_now)
        if is_happening_now:
            self.blink_timer = QTimer(self)
            self.blink_timer.timeout.connect(self.toggle_blink)
            # Frequência dessincronizada
            intervals = {"sismo": 600, "tsunami": 400, "vulcao": 800, "clima": 1000, "solar": 1200}
            self.blink_timer.start(intervals.get(evento.categoria, 700))

    def set_style(self, hover):
        bg = "#2c313a" if hover else "#21252b"
        border_color = self.evento.cor if hover else "#181a1f"
        self.setStyleSheet(f"QFrame#Card {{ background-color: {bg}; border: 1px solid {border_color}; border-radius: 6px; }}")

    def toggle_blink(self):
        if not self.underMouse():
            self.is_blink_active = not self.is_blink_active
            if self.is_blink_active:
                self.setStyleSheet(f"QFrame#Card {{ background-color: #282c34; border: 2px solid {self.evento.cor}; }}")
            else:
                self.set_style(False)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter: self.set_style(True)
        elif event.type() == QEvent.Leave: self.set_style(False)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        # Emite sinal para a MainWindow abrir o mapa
        self.clique_mapa.emit(self.evento)

class JanelaMapa(QMainWindow):
    def __init__(self, evento):
        super().__init__()
        self.setWindowTitle(f"Monitoramento: {evento.loc}")
        self.setWindowIcon(QIcon(":/img/favicon.png"))
        self.resize(1000, 700)
        self.browser = QWebEngineView()
        
        zoom = 6
        raio = 0
        if evento.categoria == "sismo": zoom = 9
        elif evento.categoria == "vulcao": zoom = 11; raio = 15000
        elif evento.categoria == "tsunami": zoom = 5; raio = 200000
        elif evento.categoria == "clima": zoom = 6; raio = 150000
        elif evento.categoria == "solar": zoom = 2;

        html = f"""
        <html>
        <head>
            <link rel='stylesheet' href='https://unpkg.com/leaflet@1.7.1/dist/leaflet.css'/>
            <script src='https://unpkg.com/leaflet@1.7.1/dist/leaflet.js'></script>
            <style>body {{ margin: 0; background-color: #1e2227; }} #map {{ width: 100%; height: 100%; }}</style>
        </head>
        <body>
            <div id='map'></div>
            <script>
                var map = L.map('map').setView([{evento.lat}, {evento.lon}], {zoom});
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: 'GeoEvent' }}).addTo(map);
                var iconColor = "{evento.cor}";
                L.marker([{evento.lat}, {evento.lon}]).addTo(map)
                    .bindPopup("<b style='color:{evento.cor}'>{evento.titulo}</b><br>{evento.loc}<br>Escala: {evento.escala}")
                    .openPopup();
                if ({raio} > 0) {{
                    L.circle([{evento.lat}, {evento.lon}], {{ color: iconColor, fillColor: iconColor, fillOpacity: 0.2, radius: {raio} }}).addTo(map);
                }}
            </script>
        </body>
        </html>
        """
        self.browser.setHtml(html)
        self.setCentralWidget(self.browser)

class TileMenu(QPushButton):
    def __init__(self, titulo, tipo, cor):
        super().__init__()
        self.setFixedSize(200, 110)
        self.tipo, self.cor = tipo, cor
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.installEventFilter(self)
        l = QVBoxLayout(self)
        self.lbl_t = QLabel(titulo)
        self.lbl_t.setStyleSheet("font-weight: bold; font-size: 10pt; color: white; background: transparent;")
        self.lbl_info = QLabel("Aguardando dados...")
        self.lbl_info.setStyleSheet("font-size: 7pt; color: #abb2bf; background: transparent;")
        l.addWidget(self.lbl_t, 0, Qt.AlignCenter); l.addWidget(self.lbl_info, 0, Qt.AlignCenter)
        self.set_default_style()

    def set_default_style(self):
        self.setStyleSheet(f"QPushButton {{ background-color: #282c34; border-bottom: 4px solid {self.cor}; border-radius: 8px; }}")

    def set_hover_style(self):
        self.setStyleSheet(f"QPushButton {{ background-color: {self.cor}; border-bottom: 4px solid {self.cor}; border-radius: 8px; }}")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.set_hover_style()
            self.lbl_t.setStyleSheet("color: black; font-weight: bold; background: transparent;")
            self.lbl_info.setStyleSheet("color: #282c34; background: transparent;")
        elif event.type() == QEvent.Leave:
            self.set_default_style()
            self.lbl_t.setStyleSheet("color: white; font-weight: bold; background: transparent;")
            self.lbl_info.setStyleSheet("color: #abb2bf; background: transparent;")
        return super().eventFilter(obj, event)

# --- JANELA PRINCIPAL ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DBManager()
        self.bip_ativo = False
        self.maiores_ts_vistos = {}
        self.categoria_ativa = "Geral"
        self.eventos_cache = []
        
        # LISTA para manter referências das janelas de mapa abertas e evitar Garbage Collection
        self.janelas_mapa = []

        self.setWindowTitle(VERSAO)
        self.setWindowIcon(QIcon(":/img/favicon.png"))
        self.resize(1200, 850)
        self.setStyleSheet("QMainWindow, QWidget { background-color: #1e2227; font-family: 'Segoe UI'; } QScrollArea { border: none; }")

        container = QWidget(); self.main_layout = QVBoxLayout(container)
        
        header = QHBoxLayout()
        lbl_logo = QLabel("")
        lbl_logo.setStyleSheet("font-size: 18pt; font-weight: bold; color: #61afef;")
        self.btn_back = QPushButton("⬅ Voltar à Visão Geral")
        self.btn_back.setStyleSheet("background: #c678dd; color: white; font-weight: bold; padding: 5px; border-radius: 4px;")
        self.btn_back.clicked.connect(self.voltar_geral); self.btn_back.hide()
        self.btn_bip = QPushButton("🔊 SOM: OFF")
        self.btn_bip.setCheckable(True); self.btn_bip.clicked.connect(self.toggle_bip); self.update_btn_bip()
        btn_hist = QPushButton("📜 Histórico"); btn_hist.clicked.connect(lambda: JanelaHistorico(self.db).exec_())
        btn_hist.setStyleSheet("background: #3e4451; color: white; padding: 5px 15px; border-radius: 4px;")

        header.addWidget(lbl_logo); header.addStretch(); header.addWidget(self.btn_back); header.addWidget(self.btn_bip); header.addWidget(btn_hist)
        self.main_layout.addLayout(header)

        self.tiles = {
            "sismo": TileMenu("TERREMOTOS", "sismo", "#61afef"),
            "tsunami": TileMenu("TSUNAMIS", "tsunami", "#98c379"), # Atualizado para VERDE
            "vulcao": TileMenu("VULCÕES", "vulcao", "#e06c75"),   # Atualizado para VERMELHO
            "clima": TileMenu("CLIMA / FURACÃO", "clima", "#c678dd"),
            "solar": TileMenu("ATIV. SOLAR", "solar", "#e5c07b")
        }
        tile_layout = QHBoxLayout()
        for k, t in self.tiles.items(): tile_layout.addWidget(t); t.clicked.connect(lambda ch, tipo=k: self.filtrar(tipo))
        self.main_layout.addLayout(tile_layout)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.list_w = QWidget(); self.list_l = QVBoxLayout(self.list_w); self.list_l.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.list_w); self.main_layout.addWidget(self.scroll)
        self.setCentralWidget(container)

        self.timer = QTimer(); self.timer.timeout.connect(self.coletar_dados); self.timer.start(60000)
        self.coletar_dados()

    def abrir_mapa(self, evento):
        # Cria a janela e armazena na lista da MainWindow para persistir
        mapa = JanelaMapa(evento)
        self.janelas_mapa.append(mapa)
        mapa.show()
        # Opcional: Limpar janelas fechadas da lista para não acumular memória infinitamente
        # (Lógica simples: remove referências antigas se a lista ficar muito grande)
        if len(self.janelas_mapa) > 10:
            self.janelas_mapa.pop(0)

    def toggle_bip(self): self.bip_ativo = self.btn_bip.isChecked(); self.update_btn_bip()
    def update_btn_bip(self):
        txt, cor = ("🔊 SOM: ON", "#98c379") if self.bip_ativo else ("🔇 SOM: OFF", "#e06c75")
        self.btn_bip.setText(txt); self.btn_bip.setStyleSheet(f"background: transparent; border: 1px solid {cor}; color: {cor}; padding: 5px; border-radius: 4px; font-weight: bold;")
    
    def voltar_geral(self): self.categoria_ativa = "Geral"; self.btn_back.hide(); self.renderizar_lista()
    def filtrar(self, categoria): self.categoria_ativa = categoria; self.btn_back.show(); self.renderizar_lista()

    def coletar_dados(self):
        novos_eventos = []
        servicos = [SismoService, TsunamiService, VulcaoService, SolarService, ClimaService]
        som_tocar = False
        for s in servicos:
            dados = s.fetch()
            for d in dados:
                novos_eventos.append(d); self.db.salvar_evento(d)
                if d.ts > self.maiores_ts_vistos.get(d.categoria, 0):
                    self.maiores_ts_vistos[d.categoria] = d.ts; som_tocar = True
        
        if som_tocar and self.bip_ativo and winsound: winsound.Beep(1200, 300)
        novos_eventos.sort(key=lambda x: x.ts, reverse=True)
        self.eventos_cache = novos_eventos
        
        for cat, tile in self.tiles.items():
            evs = [e for e in novos_eventos if e.categoria == cat]
            if evs: tile.lbl_info.setText(f"Último: {evs[0].hora}\n{evs[0].loc[:20]}...")
            else: tile.lbl_info.setText("Sem alertas recentes")
        self.renderizar_lista()

    def renderizar_lista(self):
        while self.list_l.count():
            item = self.list_l.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        agora_ms = datetime.now().timestamp() * 1000

        for ev in self.eventos_cache:
            if self.categoria_ativa == "Geral" or ev.categoria == self.categoria_ativa:
                
                # CORREÇÃO LÓGICA PISCAR:
                # Pisca se o evento aconteceu dentro do intervalo definido (ex: 40 minutos atrás até agora)
                diferenca = agora_ms - ev.ts
                is_happening_now = diferenca < TEMPO_RECENTE_MS

                row = EventoRow(ev, is_happening_now)
                
                # CONEXÃO DO SINAL:
                # Quando o Row emitir 'clique_mapa', chama self.abrir_mapa desta classe
                row.clique_mapa.connect(self.abrir_mapa)
                
                self.list_l.addWidget(row)

class JanelaHistorico(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Histórico Completo"); self.resize(900, 600)
        self.setStyleSheet("background: #21252b; color: #abb2bf;")
        l = QVBoxLayout(self)
        top = QHBoxLayout(); self.cal = QCalendarWidget(); self.cal.setStyleSheet("background: #282c34; color: black;")
        btn = QPushButton("Buscar Data"); btn.setFixedHeight(50); btn.setStyleSheet("background: #61afef; color: white; font-weight: bold;")
        btn.clicked.connect(self.buscar); top.addWidget(self.cal); top.addWidget(btn); l.addLayout(top)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.w_lista = QWidget(); self.l_lista = QVBoxLayout(self.w_lista)
        self.scroll.setWidget(self.w_lista); l.addWidget(self.scroll)

    def buscar(self):
        # Captura a data selecionada
        d = self.cal.selectedDate().toString("yyyy-MM-dd")
        
        # FORMA CORRETA E SEGURA DE LIMPAR O LAYOUT NO PYQT5
        while self.l_lista.count():
            item = self.l_lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Busca e renderiza os novos itens
        for c in ["sismo", "tsunami", "vulcao", "clima", "solar"]:
            try:
                rows = self.db.buscar_historico(c, d)
                if rows:
                    header = QLabel(f"--- {c.upper()} ---")
                    header.setStyleSheet("font-weight: bold; color: #61afef; margin-top: 10px;")
                    self.l_lista.addWidget(header)
                    
                    for r in rows:
                        # r[11] é data, r[3] é local, r[7] é impacto, r[10] é hora
                        texto = f"[{r[10]}] {r[3]} | {r[7]}"
                        item_label = QLabel(texto)
                        item_label.setStyleSheet("border-bottom: 1px solid #3e4451; padding: 2px;")
                        self.l_lista.addWidget(item_label)
            except Exception as e:
                print(f"Erro ao buscar categoria {c}: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec_())
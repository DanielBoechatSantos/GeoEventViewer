import sys
import sqlite3
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from sklearn.cluster import KMeans
from datetime import datetime

# Exportação e UI
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QFileDialog, QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

# --- CONFIGURAÇÃO DE CAMINHO ---
DB_PATH = r"D:\Automacoes\Automacoes\historico_v5.db"
MAPA_LOCAL = r"D:\Automacoes\Automacoes\world_map.geojson"

class IAEngine:
    def __init__(self, df):
        # Filtra apenas dados com coordenadas válidas para análise espacial
        self.df_geo = df[(df['lat'] != 0) & (df['lon'] != 0)].copy()

    def calcular_hotspots(self, n_clusters=3):
        if len(self.df_geo) < n_clusters: 
            return []
            
        coords = self.df_geo[['lat', 'lon']].values
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        
        # O fit_predict associa cada evento a um cluster específico
        self.df_geo['cluster_label'] = kmeans.fit_predict(coords)
        
        # Calcula a densidade (probabilidade real) de cada região
        contagem = self.df_geo['cluster_label'].value_counts(normalize=True) * 100
        centros = kmeans.cluster_centers_
        
        hotspots_com_info = []
        for i, centro in enumerate(centros):
            hotspots_com_info.append({
                'lat': centro[0],
                'lon': centro[1],
                'prob': contagem.get(i, 0)
            })
            
        return hotspots_com_info

class AnaliseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GEO-INTELLIGENCE ANALYZER PRO v2.8")
        self.resize(1300, 850)
        self.setStyleSheet("background-color: #1e2227; color: #abb2bf; font-family: 'Segoe UI';")
        
        self.filtro_ativo = "Geral"
        self.blink_status = True
        self.hotspots_info = []
        
        self.df_total = self.carregar_dados()
        self.init_ui()
        
        # Timer para o Blink das Zonas Críticas
        self.timer_blink = QTimer()
        self.timer_blink.timeout.connect(self.toggle_blink)
        self.timer_blink.start(600)

    def carregar_dados(self):
        if not os.path.exists(DB_PATH): 
            return pd.DataFrame()
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM eventos", conn)
        conn.close()
        df.columns = df.columns.str.strip()
        return df

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # BARRA SUPERIOR
        top_bar = QHBoxLayout()
        header = QLabel("🌍 DIAGNÓSTICO GEOESTATÍSTICO")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #61afef;")
        top_bar.addWidget(header)
        top_bar.addStretch()
        
        btn_exportar = QPushButton("📥 EXPORTAR")
        btn_exportar.setStyleSheet("background: #98c379; color: #1e2227; padding: 8px 15px; border-radius: 4px; font-weight: bold;")
        btn_exportar.clicked.connect(self.menu_exportacao)
        top_bar.addWidget(btn_exportar)
        main_layout.addLayout(top_bar)

        # FILTROS
        filter_bar = QHBoxLayout()
        self.btn_filtros = {}
        categorias = [("GERAL", "Geral", "#abb2bf"), ("VULCÕES", "vulcao", "#e06c75"), 
                      ("SISMOS", "sismo", "#61afef"), ("CLIMA", "clima", "#c678dd"), 
                      ("TSUNAMI", "tsunami", "#98c379")]
        
        for nome, chave, cor in categorias:
            btn = QPushButton(nome)
            btn.setCheckable(True)
            btn.setStyleSheet(f"QPushButton {{ background: #282c34; border: 1px solid {cor}; color: {cor}; padding: 6px; border-radius: 4px; }} "
                               f"QPushButton:checked {{ background: {cor}; color: #1e2227; font-weight: bold; }}")
            btn.clicked.connect(lambda ch, k=chave: self.set_filtro(k))
            filter_bar.addWidget(btn)
            self.btn_filtros[chave] = btn
        self.btn_filtros["Geral"].setChecked(True)
        main_layout.addLayout(filter_bar)

        # CONTEÚDO PRINCIPAL
        content = QHBoxLayout()
        
        # Mapa com Toolbar
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        self.fig, self.ax = plt.subplots(facecolor='#1e2227')
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("background-color: #abb2bf; border-radius: 4px;")
        
        map_layout.addWidget(self.toolbar)
        map_layout.addWidget(self.canvas)
        content.addWidget(map_container, 3)

        # PAINEL LATERAL
        side_panel = QVBoxLayout()
        
        self.frame_detalhes = QFrame()
        self.frame_detalhes.setStyleSheet("background: #282c34; border-radius: 10px; border: 1px solid #3e4451;")
        self.frame_detalhes.setFixedHeight(320)
        det_layout = QVBoxLayout(self.frame_detalhes)
        
        lbl_det_tit = QLabel("🔍 DETALHES DA SELEÇÃO")
        lbl_det_tit.setStyleSheet("font-weight: bold; color: #61afef;")
        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setStyleSheet("border: none; background: transparent; color: white;")
        
        det_layout.addWidget(lbl_det_tit)
        det_layout.addWidget(self.txt_info)
        side_panel.addWidget(self.frame_detalhes)

        self.table = QTableWidget()
        self.configurar_tabela()
        side_panel.addWidget(self.table)
        
        content.addLayout(side_panel, 1)
        main_layout.addLayout(content)
        
        # Conexão de Pick (Clique)
        self.canvas.mpl_connect("pick_event", self.on_pick)
        
        self.atualizar_view()

    def configurar_tabela(self):
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Localização", "Freq %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("QTableWidget { background: #21252b; border: none; color: white; }")

    def set_filtro(self, filtro):
        self.filtro_ativo = filtro
        for k, btn in self.btn_filtros.items(): btn.setChecked(k == filtro)
        self.txt_info.clear()
        self.atualizar_view()

    def atualizar_view(self):
        self.df_view = self.df_total if self.filtro_ativo == "Geral" else self.df_total[self.df_total['categoria'] == self.filtro_ativo]
        self.plotar_mapa()
        self.popular_tabela()

    def plotar_mapa(self):
        self.ax.clear()
        self.ax.set_facecolor('#1e2227')
        
        try:
            import geopandas as gpd
            if not os.path.exists(MAPA_LOCAL):
                world = gpd.read_file("https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson")
                world.to_file(MAPA_LOCAL, driver='GeoJSON')
            else:
                world = gpd.read_file(MAPA_LOCAL)
            world.plot(ax=self.ax, color='#2c313a', edgecolor='#3e4451', alpha=0.5)
        except:
            self.ax.grid(color='#2c313a', linestyle='--', alpha=0.3)

        self.ax.set_xlim(-180, 180); self.ax.set_ylim(-90, 90)

        if not self.df_view.empty:
            df_plot = self.df_view[self.df_view['lat'] != 0].copy()
            if not df_plot.empty:
                self.points = self.ax.scatter(df_plot['lon'], df_plot['lat'], 
                                              c='#61afef', alpha=0.6, s=40, 
                                              edgecolors='white', picker=5)
                self.current_plot_data = df_plot 
            
            ia = IAEngine(self.df_view)
            self.hotspots_info = ia.calcular_hotspots()
            
            if len(self.hotspots_info) > 0:
                lats = [h['lat'] for h in self.hotspots_info]
                lons = [h['lon'] for h in self.hotspots_info]
                self.cluster_marks = self.ax.scatter(lons, lats, 
                                                     c='#e06c75', s=250, marker='X', 
                                                     edgecolors='white', picker=10)
        
        self.ax.set_title(f"Padrões Detectados: {self.filtro_ativo.upper()}", color='#61afef')
        self.canvas.draw()

    def on_pick(self, event):
        # Clique em Ponto Azul (Histórico)
        if hasattr(self, 'points') and event.artist == self.points:
            idx = event.ind[0]
            row = self.current_plot_data.iloc[idx]
            msg = (f"<b style='color:#61afef;'>📊 REGISTRO HISTÓRICO</b><br><br>"
                   f"<b>TIPO:</b> {row.get('tipo_orig', 'Evento')}<br>"
                   f"<b>LOCAL:</b> {row.get('loc', 'N/A')}<br>"
                   f"<b>DATA/HORA:</b> {row.get('data')} {row.get('hora')}<br>"
                   f"<b>ESCALA:</b> {row.get('escala_tecnica')}")
            self.txt_info.setHtml(msg)

        # Clique em X Vermelho (IA)
        elif hasattr(self, 'cluster_marks') and event.artist == self.cluster_marks:
            idx_cluster = event.ind[0]
            dados = self.hotspots_info[idx_cluster]
            
            cat = self.filtro_ativo.upper()
            impacto = "Danos Estruturais" if cat == "SISMO" else "Risco Geográfico"
            if cat == "VULCAO": impacto = "Cinzas e Solo"
            if cat in ["CLIMA", "TSUNAMI"]: impacto = "Inundação e Infraestrutura"

            msg = (f"<b style='color:#e06c75;'>⚠ ZONA DE PROBABILIDADE (IA)</b><br><br>"
                   f"<b>CONFIANÇA ESTATÍSTICA:</b> {dados['prob']:.1f}%<br>"
                   f"<b>CATEGORIA:</b> {cat}<br>"
                   f"<b>IMPACTO PREVISTO:</b> {impacto}<br>"
                   f"<b>COORDENADAS:</b> {dados['lat']:.2f}, {dados['lon']:.2f}")
            self.txt_info.setHtml(msg)

    def toggle_blink(self):
        if hasattr(self, 'cluster_marks'):
            self.blink_status = not self.blink_status
            self.cluster_marks.set_visible(self.blink_status)
            self.canvas.draw_idle()

    def popular_tabela(self):
        self.table.setRowCount(0)
        if not self.df_view.empty:
            counts = self.df_view['loc'].value_counts(normalize=True).head(12) * 100
            self.table.setRowCount(len(counts))
            for i, (loc, prob) in enumerate(counts.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(loc)[:28]))
                self.table.setItem(i, 1, QTableWidgetItem(f"{prob:.1f}%"))

    def menu_exportacao(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Como", "", "Excel (*.xlsx);;PDF (*.pdf)")
        if path:
            if path.endswith('.xlsx'):
                self.df_view.to_excel(path, index=False)
                QMessageBox.information(self, "OK", "Excel exportado!")
            else:
                self.exportar_pdf(path)

    def exportar_pdf(self, path):
        c = canvas.Canvas(path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, f"RELATÓRIO DE INTELIGÊNCIA GEO: {self.filtro_ativo.upper()}")
        c.setFont("Helvetica", 10)
        c.drawString(50, 730, f"Data: {datetime.now().strftime('%d/%m/%Y')}")
        y = 680
        for i, row in self.df_view.head(25).iterrows():
            c.drawString(50, y, f"- {row['tipo_orig']} em {row['loc'][:45]}")
            y -= 20
        c.save()
        QMessageBox.information(self, "OK", "PDF exportado!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AnaliseWindow()
    win.show()
    sys.exit(app.exec_())
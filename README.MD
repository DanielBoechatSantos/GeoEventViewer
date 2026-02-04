# 🌍 GeoEventViewer Pro v5.1 & Intelligence Analyzer

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PyQt5](https://img.shields.io/badge/PyQt5-41cd52?style=for-the-badge&logo=qt&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)

O **GeoEventViewer Suite** é um ecossistema avançado de monitoramento e análise geológica. O projeto evoluiu de um dashboard descritivo para uma ferramenta de **Business Intelligence (BI)** aplicada a geociências, integrando ingestão de dados em tempo real com diagnósticos preditivos baseados em Inteligência Artificial.

## 🛠️ Novidades da Versão Pro (Arquitetura & IA)

- **Geo-Intelligence Analyzer:** Módulo analítico independente que consome o banco de dados histórico para identificação de padrões globais.
- **Motor de IA (K-Means Clustering):** Implementação de Machine Learning para calcular "Hotspots" de risco, prevendo centros de massa de futuras ocorrências baseando-se na densidade histórica e probabilidade estatística real.
- **Visualização Cartográfica:** Integração com `GeoPandas` e `Matplotlib` para renderização de mapas-múndi profissionais com suporte a **Cache Local**, garantindo performance e resiliência em operações offline.
- **Relatórios Corporativos:** Sistema de exportação nativo para **Excel (.xlsx)** e **PDF (.pdf)** formatado, permitindo a extração de diagnósticos para auditorias ou estudos técnicos externos.



## 🚀 Funcionalidades Principais

### 📡 Monitoramento (GeoEventViewer.py)
- **Filtro Brasil & Fronteiras:** Lógica geoespacial para detecção de sismos em território nacional ou áreas limítrofes, com alertas sonoros diferenciados via `winsound`.
- **Interatividade Visual:** Cards dinâmicos com efeito *blink* para eventos recentes e integração com `OpenStreetMap` via `PyQtWebEngine`.
- **Parsing de Dados:** Normalização automática de strings para o padrão profissional: `PAÍS - TIPO DE EVENTO - NOME/ESCALA`.

### 🧠 Análise Preditiva (analise.py)
- **Zonas Críticas Inteligentes:** Hotspots calculados pela IA que utilizam animação visual (blink) para destacar áreas de recorrência iminente.
- **UX por Seleção:** Painel lateral detalhado que exibe **Confiança Estatística**, **Vulnerabilidade Setorial** e **Impacto Previsto** ao interagir com as marcações do mapa.
- **Interação Avançada:** Barra de ferramentas integrada para Zoom dinâmico, Pan (movimentação) e captura de tela do mapa.

## 📂 Estrutura de Arquivos

O projeto segue uma arquitetura de persistência desacoplada para garantir integridade e escalabilidade:

* **Banco de Dados (Relacional):** `historico_v5.db` centralizado em na pasta raiz do projeto para integração entre múltiplos módulos.
* **Cache Geográfico:** `world_map.geojson` gerado automaticamente para otimizar o carregamento cartográfico.

## 📋 Instalação e Dependências

Para rodar o ecossistema completo, instale as bibliotecas necessárias via terminal:

```bash
pip install requests PyQt5 PyQtWebEngine pandas scikit-learn matplotlib geopandas reportlab openpyxl
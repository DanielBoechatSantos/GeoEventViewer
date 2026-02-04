# 🌍 GeoEventViewer v3.0

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PyQt5](https://img.shields.io/badge/PyQt5-41cd52?style=for-the-badge&logo=qt&logoColor=white)
![Geospatial](https://img.shields.io/badge/Geospatial-Analysis-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

O **GeoEventViewer** é um dashboard avançado de monitoramento planetário em tempo real. A aplicação consome dados de agências globais (USGS, Smithsonian, NOAA) e utiliza lógica geoespacial para visualizar o raio de influência de desastres naturais e eventos atmosféricos.

## 🛠️ Novidades da Versão 3.0 (Arquitetura Pro)

- **Arquitetura Orientada a Objetos (O.O):** Separação total entre a lógica de dados (`EventoData`) e a interface gráfica, seguindo princípios de Clean Code e MVC.
- **Visualização de Raio de Influência:** O mapa agora renderiza círculos de impacto técnico dinâmicos:
    - **Tsunamis:** Raio de 800km de alerta marítimo.
    - **Clima (Furacões/Tufões):** Raio de 500km de influência atmosférica.
    - **Solar:** Impacto global (8.000km) com zoom adaptativo.
- **Correção de Geolocalização:** Sistema de validação de coordenadas que impede o erro de "Null Island" (0,0), garantindo precisão milimétrica nos eventos sísmicos.
- **Data Pipeline:** Consumo otimizado de múltiplas fontes via REST API e RSS XML.

## 🚀 Funcionalidades Principais

- **Monitoramento Multicategoria:** Sismos, Tsunamis, Vulcões, Clima e Atividade Solar.
- **Interface Dark Soft:** Design otimizado para baixa fadiga visual e alta densidade de informação.
- **Horário Local:** Todos os eventos são convertidos automaticamente para o fuso horário do usuário.
- **Análise de Impacto Setorial:** Classificação automática de risco (Terrestre, Marítimo, Aviação, etc).

## 📋 Pré-requisitos e Instalação

```bash
# Dependências necessárias
pip install requests PyQt5 PyQtWebEngine
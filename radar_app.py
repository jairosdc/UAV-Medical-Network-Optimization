"""
radar_app.py — FlyRadar: Visor Interactivo de Drones Médicos
=============================================================

Aplicación Streamlit + PyDeck conectada al motor DES.

Este archivo NO decide lógica de simulación.
Solo:
- ejecuta run_simulation(config),
- lee la telemetría generada por el motor,
- interpola posiciones,
- pinta el mapa.
"""

import json
import os
import math
import time

import streamlit as st
import pandas as pd
import pydeck as pdk
import numpy as np

# ---------------------------------------------------------------------------
# Importaciones del proyecto
# ---------------------------------------------------------------------------

from config import HOSPITALS, BASES
from red import ServicioRed
from simulacion import run_simulation, ESCENARIOS

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

RUTA_TELEMETRIA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "telemetria_vuelos.json",
)

MADRID_LAT = 40.42
MADRID_LON = -3.70

ESCENARIO_RADAR = "personalizado"
CONFIG_ESCENARIO_RADAR = ESCENARIOS[ESCENARIO_RADAR]

# Colores de misiones (Functional high-contrast palette)
COLOR_INVENTARIO = [0, 200, 83, 240]    # Green for standard inventory
COLOR_ORGANO = [255, 40, 40, 250]       # Bright red for urgent organ missions
COLOR_VUELTA = [60, 60, 60, 220]        # Dark gray for return flights
COLOR_BATERIA_BAJA = [255, 214, 0, 250] # Vibrant yellow for low battery
COLOR_RECIEN_LLEGADO = [255, 255, 255, 180]

# Colores de nodos — V2 design: white/cyan hospitals, red bases
COLOR_HOSPITAL_NODO = [200, 230, 255, 240]   # White-blue (crosshair markers)

UMBRAL_BATERIA_BAJA = 25.0
MARGEN_PERSISTENCIA_MIN = 3

# Configuración visual por base.
# V2 design: all bases use red tones to match the Command Center theme.
CONFIG_BASES = {
    "BASE NOROESTE": {"color_rgb": [230, 59, 46], "radio": 6000},
    "BASE NORTE CAPITAL": {"color_rgb": [200, 40, 40], "radio": 4504},
    "BASE ESTE CORREDOR": {"color_rgb": [255, 80, 60], "radio": 3500},
    "BASE SUR FUENLABRADA": {"color_rgb": [180, 30, 30], "radio": 4000},
}

COLORES_BASE_FALLBACK = [
    [230, 59, 46],
    [200, 40, 40],
    [255, 80, 60],
    [180, 30, 30],
    [240, 50, 50],
    [210, 45, 40],
    [190, 35, 35],
]


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def limpiar_telemetria_previa():
    """
    Elimina la telemetría anterior antes de ejecutar una simulación nueva.

    Esto evita el fallo típico:
    - la simulación nueva falla o no genera vuelos,
    - pero el radar sigue pintando un JSON viejo.
    """
    if os.path.exists(RUTA_TELEMETRIA):
        os.remove(RUTA_TELEMETRIA)


def obtener_config_base(nombre_base, indice):
    """
    Devuelve configuración visual de una base.

    La lógica de qué base conecta con qué hospital sigue dependiendo de
    ServicioRed. Esto solo da color y radio visual.
    """
    if nombre_base in CONFIG_BASES:
        return CONFIG_BASES[nombre_base]

    color = COLORES_BASE_FALLBACK[indice % len(COLORES_BASE_FALLBACK)]

    return {
        "color_rgb": color,
        "radio": 3500,
    }


@st.cache_data(show_spinner=False)
def preparar_datos_estaticos():
    """
    Genera DataFrames estáticos para las capas de topología del mapa:
    - hospitales,
    - bases,
    - aristas base -> hospital según ServicioRed.
    """
    servicio_red = ServicioRed()

    filas_h = []
    filas_aristas = []
    filas_b = []

    indice_base = {
        nombre_base: i
        for i, nombre_base in enumerate(BASES.keys())
    }

    for nombre, nodo in HOSPITALS.items():
        filas_h.append({
            "nombre": nombre,
            "lat": nodo.lat,
            "lon": nodo.lon,
            "color_rgb": COLOR_HOSPITAL_NODO,
        })

        try:
            nombre_base, distancia_km = servicio_red.base_mas_cercana_a(nombre)
            base_nodo = BASES[nombre_base]
            base_cfg = obtener_config_base(
                nombre_base,
                indice_base.get(nombre_base, 0),
            )

            filas_aristas.append({
                "origen_lat": base_nodo.lat,
                "origen_lon": base_nodo.lon,
                "destino_lat": nodo.lat,
                "destino_lon": nodo.lon,
                "distancia_km": round(distancia_km, 2),
                "nombre_base": nombre_base,
                "nombre_hospital": nombre,
                "color_arista": base_cfg["color_rgb"] + [80],
            })

        except Exception:
            # Si una base/hospital todavía no está bien conectado,
            # no tumbamos el radar entero.
            pass

    for i, (nombre, nodo) in enumerate(BASES.items()):
        cfg = obtener_config_base(nombre, i)

        filas_b.append({
            "nombre": nombre,
            "lat": nodo.lat,
            "lon": nodo.lon,
            "color_rgb": cfg["color_rgb"],
            "color_rgba_cobertura": cfg["color_rgb"] + [15],
            "radio": cfg["radio"],
        })

    return (
        pd.DataFrame(filas_h),
        pd.DataFrame(filas_b),
        pd.DataFrame(filas_aristas),
    )


def cargar_telemetria_json():
    """
    Lee el JSON de telemetría si existe.

    Compatible con:
    - {"vuelos": [...]}
    - [...]
    """
    if not os.path.exists(RUTA_TELEMETRIA):
        return []

    try:
        with open(RUTA_TELEMETRIA, "r", encoding="utf-8") as archivo:
            data = json.load(archivo)

    except json.JSONDecodeError:
        st.warning("El archivo de telemetría existe, pero no contiene JSON válido.")
        return []

    except OSError as error:
        st.warning(f"No se pudo leer la telemetría: {error}")
        return []

    if isinstance(data, dict):
        vuelos = data.get("vuelos", [])
        return vuelos if isinstance(vuelos, list) else []

    if isinstance(data, list):
        return data

    return []


def validar_vuelos(vuelos):
    """
    Filtra vuelos inválidos para evitar errores de PyDeck.

    El radar no debe romperse por un registro incompleto.
    """
    campos_obligatorios = {
        "dron_id",
        "origen",
        "destino",
        "lat_origen",
        "lon_origen",
        "lat_destino",
        "lon_destino",
        "t_salida",
        "t_llegada",
        "tipo_mision",
        "bateria",
    }

    vuelos_validos = []

    for vuelo in vuelos:
        if not isinstance(vuelo, dict):
            continue

        if not campos_obligatorios.issubset(vuelo.keys()):
            continue

        try:
            t_salida = float(vuelo["t_salida"])
            t_llegada = float(vuelo["t_llegada"])

            if t_llegada < t_salida:
                continue

            vuelo_limpio = dict(vuelo)
            vuelo_limpio["t_salida"] = t_salida
            vuelo_limpio["t_llegada"] = t_llegada
            vuelo_limpio["lat_origen"] = float(vuelo["lat_origen"])
            vuelo_limpio["lon_origen"] = float(vuelo["lon_origen"])
            vuelo_limpio["lat_destino"] = float(vuelo["lat_destino"])
            vuelo_limpio["lon_destino"] = float(vuelo["lon_destino"])
            vuelo_limpio["bateria"] = float(vuelo["bateria"])

            vuelos_validos.append(vuelo_limpio)

        except (TypeError, ValueError):
            continue

    return vuelos_validos


def obtener_vuelos_actuales(resultado):
    """
    Fuente de verdad visual.

    Orden:
    1. Si run_simulation devuelve resultado["telemetria"], se usa.
    2. Si ya hay vuelos en session_state, se usan.
    3. Si no, se carga telemetria_vuelos.json.

    Con el repo actual, normalmente se usa el JSON.
    """
    if isinstance(resultado, dict):
        telemetria_resultado = resultado.get("telemetria")
        if isinstance(telemetria_resultado, list):
            return validar_vuelos(telemetria_resultado)

    vuelos_session = st.session_state.get("vuelos_telemetria")
    if isinstance(vuelos_session, list):
        return validar_vuelos(vuelos_session)

    return validar_vuelos(cargar_telemetria_json())


def interpolar_posicion(vuelo, t):
    """
    Interpola linealmente lat/lon del dron en el instante t.

    Importante:
    Aquí no se decide ninguna ruta. Solo se interpola el tramo que ya viene
    en la telemetría.
    """
    t0 = vuelo["t_salida"]
    t1 = vuelo["t_llegada"]

    if t1 <= t0:
        return vuelo["lat_destino"], vuelo["lon_destino"], 1.0

    progreso = (t - t0) / (t1 - t0)
    progreso = max(0.0, min(1.0, progreso))

    lat = vuelo["lat_origen"] + (vuelo["lat_destino"] - vuelo["lat_origen"]) * progreso
    lon = vuelo["lon_origen"] + (vuelo["lon_destino"] - vuelo["lon_origen"]) * progreso

    return lat, lon, progreso


def color_dron(vuelo):
    """
    Elige color según la telemetría recibida.
    """
    if vuelo["bateria"] < UMBRAL_BATERIA_BAJA:
        return COLOR_BATERIA_BAJA

    tipo = vuelo["tipo_mision"]

    if tipo == "organo":
        return COLOR_ORGANO

    if tipo == "inventario":
        return COLOR_INVENTARIO

    return COLOR_VUELTA


def etiqueta_mision(tipo):
    """
    Nombre visual de la misión.
    """
    etiquetas = {
        "inventario": "Inventario",
        "organo": "Órgano",
        "vuelta_base": "Vuelta a base",
    }

    return etiquetas.get(tipo, tipo)


def drones_en_vuelo(vuelos, t):
    """
    Filtra vuelos activos en el instante t y devuelve posiciones para PyDeck.

    La persistencia tras aterrizaje es solo visual.
    """
    filas = []

    for vuelo in vuelos:
        t_salida = vuelo["t_salida"]
        t_llegada = vuelo["t_llegada"]

        if t_salida <= t <= t_llegada:
            lat, lon, progreso = interpolar_posicion(vuelo, t)

            filas.append({
                "dron_id": vuelo["dron_id"],
                "lat": lat,
                "lon": lon,
                "tipo_mision": etiqueta_mision(vuelo["tipo_mision"]),
                "bateria": round(vuelo["bateria"], 1),
                "progreso": round(progreso * 100, 1),
                "origen": vuelo["origen"],
                "destino": vuelo["destino"],
                "color": color_dron(vuelo),
            })

        elif t_llegada < t <= t_llegada + MARGEN_PERSISTENCIA_MIN:
            filas.append({
                "dron_id": vuelo["dron_id"],
                "lat": vuelo["lat_destino"],
                "lon": vuelo["lon_destino"],
                "tipo_mision": "✓ " + etiqueta_mision(vuelo["tipo_mision"]),
                "bateria": round(vuelo["bateria"], 1),
                "progreso": 100.0,
                "origen": vuelo["origen"],
                "destino": vuelo["destino"],
                "color": COLOR_RECIEN_LLEGADO,
            })

    return pd.DataFrame(filas)


def rutas_activas(vuelos, t):
    """
    Devuelve arcos de vuelos activos en el instante t.
    """
    filas = []

    for vuelo in vuelos:
        if vuelo["t_salida"] <= t <= vuelo["t_llegada"]:
            filas.append({
                "lat_origen": vuelo["lat_origen"],
                "lon_origen": vuelo["lon_origen"],
                "lat_destino": vuelo["lat_destino"],
                "lon_destino": vuelo["lon_destino"],
                "color": color_dron(vuelo),
                "origen": vuelo["origen"],
                "destino": vuelo["destino"],
                "tipo_mision": etiqueta_mision(vuelo["tipo_mision"]),
            })

    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Centro de Comando de Drones Médicos",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# ESTADO
# ---------------------------------------------------------------------------

if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "minuto_actual" not in st.session_state:
    st.session_state.minuto_actual = 0

if "velocidad_reproduccion" not in st.session_state:
    st.session_state.velocidad_reproduccion = 1

if "vuelos_telemetria" not in st.session_state:
    st.session_state.vuelos_telemetria = None

if "resultado" not in st.session_state:
    st.session_state.resultado = None

if "_slider_minuto" not in st.session_state:
    st.session_state._slider_minuto = 0


# ---------------------------------------------------------------------------
# CSS PERSONALIZADO
# ---------------------------------------------------------------------------

st.markdown("""
<link rel="stylesheet" type="text/css" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@300;400;500;600;700;800&display=swap');

    /* Global Overrides */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f2f2f2 !important;
        color: #000000;
    }

    .stApp {
        background-color: #f2f2f2;
    }

    /* Headlines */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: -0.05em;
    }

    /* Neo-Brutalist Components */
    .brutal-container {
        background-color: #ffffff;
        border: 3px solid #e63b2e;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 6px 6px 0px 0px #000000;
        position: relative;
    }

    .main-title {
        background-color: #e63b2e;
        border: 4px solid #000000;
        padding: 2rem;
        margin-bottom: 2rem;
        text-align: left;
        box-shadow: 10px 10px 0px 0px #1a1a1a;
        transform: rotate(-0.5deg);
    }

    .main-title h1 {
        color: #ffffff !important;
        font-size: 3.5rem !important;
        font-weight: 800 !important;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 1rem;
        line-height: 1;
    }

    .main-title p {
        color: #000000;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.2rem;
        margin: 0.5rem 0 0 0;
        font-weight: 700;
        text-transform: uppercase;
    }

    .metric-card {
        background-color: #ffffff;
        border: 3px solid #e63b2e;
        padding: 1.5rem;
        text-align: left;
        box-shadow: 6px 6px 0px 0px #000000;
        transition: transform 0.1s ease, box-shadow 0.1s ease;
    }

    .metric-card:hover {
        transform: translate(-2px, -2px);
        box-shadow: 8px 8px 0px 0px #000000;
    }

    .metric-card h3 {
        color: #e63b2e;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1;
    }

    .metric-card p {
        color: #000000;
        font-size: 0.9rem;
        margin: 0.3rem 0 0 0;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .product-card {
        background-color: #ffffff;
        border: 2px solid #e63b2e;
        padding: 1rem;
        text-align: left;
        margin-bottom: 0.8rem;
        box-shadow: 4px 4px 0px 0px #000000;
    }

    .product-card h4 {
        color: #e63b2e;
        font-size: 1.1rem;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .product-card p {
        color: #333333;
        font-size: 0.8rem;
        margin: 0.1rem 0 0 0;
        font-weight: 600;
    }

    .legend-box {
        background-color: #ffffff;
        border: 2px solid #000000;
        padding: 1rem;
        margin-top: 1rem;
        box-shadow: 4px 4px 0px 0px #e63b2e;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        margin-right: 1.5rem;
        font-size: 0.9rem;
        font-weight: 700;
        color: #000000;
        text-transform: uppercase;
    }

    .legend-dot {
        width: 14px;
        height: 14px;
        border: 2px solid #000;
        display: inline-block;
        margin-right: 10px;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 4px solid #e63b2e;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #e63b2e !important;
    }
    
    .sidebar-title {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem;
        font-weight: 800;
        color: #e63b2e;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
        margin-top: 1.5rem;
        border-bottom: 2px solid #e63b2e;
        padding-bottom: 0.2rem;
    }
    
    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.8rem;
        color: #ffffff;
        font-weight: 900;
        margin-bottom: 2rem;
        background-color: #e63b2e;
        padding: 0.5rem 1rem;
        border: 3px solid #000000;
        box-shadow: 4px 4px 0px 0px #000000;
    }

    /* Override Streamlit Widgets */
    .stSlider > div > div > div > div {
        background-color: #e63b2e !important;
    }
    
    .stButton > button {
        background-color: #e63b2e !important;
        color: white !important;
        border: 3px solid #000 !important;
        border-radius: 0 !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        box-shadow: 4px 4px 0px 0px #000 !important;
        transition: all 0.1s !important;
    }

    .stButton > button:hover {
        transform: translate(-2px, -2px) !important;
        box-shadow: 6px 6px 0px 0px #000 !important;
    }

    .stButton > button:active {
        transform: translate(2px, 2px) !important;
        box-shadow: 0px 0px 0px 0px #000 !important;
    }

    /* Contrast hardening: keep the same brutalist UI, but prevent
       Streamlit widget text from disappearing on white/light panels. */
    .stMarkdown,
    .stMarkdown p,
    .stCaption,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stExpander"] *,
    [data-testid="stNotification"] *,
    [data-testid="stDataFrame"] *,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #000000 !important;
    }

    section[data-testid="stSidebar"] .sidebar-header,
    section[data-testid="stSidebar"] .sidebar-header *,
    .main-title h1,
    .stButton > button,
    .stButton > button * {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] .sidebar-title,
    section[data-testid="stSidebar"] .sidebar-title *,
    .brutalist-label,
    .brutalist-label * {
        color: #e63b2e !important;
    }

    div[data-baseweb="select"],
    div[data-baseweb="select"] *,
    div[data-baseweb="input"],
    div[data-baseweb="input"] *,
    div[data-baseweb="popover"] * {
        color: #000000 !important;
    }

    input,
    textarea {
        color: #000000 !important;
        background-color: #ffffff !important;
    }

    /* Metrics Container */
    [data-testid="column"] {
        padding: 0.5rem !important;
    }

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-title">
    <h1><i class="ph ph-radar"></i> DRON COMMAND CENTER</h1>
    <p>COMUNIDAD DE MADRID • TACTICAL CONTROL & TELEMETRY HUB</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="sidebar-header"><i class="ph ph-sliders"></i> Configuración</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-title"><i class="ph ph-cpu"></i> Simulación</div>', unsafe_allow_html=True)
    minutos_sim = st.slider(
        "Duración (minutos)",
        60,
        50000,
        int(CONFIG_ESCENARIO_RADAR.get("minutos_simulacion", 1440)),
        step=60,
        help="1440 = 1 día, 10080 = 1 semana",
    )

    semilla_escenario = CONFIG_ESCENARIO_RADAR.get("semilla")
    semilla_default = semilla_escenario if semilla_escenario is not None else 0
    semilla = st.number_input(
        "Semilla aleatoria (0 = random)",
        0,
        999999,
        int(semilla_default),
    )

    st.markdown('<div class="sidebar-title"><i class="ph ph-trend-up"></i> Demanda</div>', unsafe_allow_html=True)
    factor_inv = st.slider(
        "Factor demanda inventario",
        0.1,
        3.0,
        float(CONFIG_ESCENARIO_RADAR.get("factor_demanda_inventario", 1.0)),
        0.1,
    )
    factor_org = st.slider(
        "Factor demanda órganos",
        0.1,
        3.0,
        float(CONFIG_ESCENARIO_RADAR.get("factor_demanda_organos", 1.0)),
        0.1,
    )

    st.markdown('<div class="sidebar-title"><i class="ph ph-cloud-sun"></i> Meteorología</div>', unsafe_allow_html=True)
    activar_meteo = st.checkbox(
        "Activar meteorología",
        value=bool(CONFIG_ESCENARIO_RADAR.get("activar_meteorologia", True)),
    )
    intervalo_clima = st.slider(
        "Intervalo cambio clima (min)",
        60,
        1440,
        int(CONFIG_ESCENARIO_RADAR.get("intervalo_cambio_clima_min", 300)),
        60,
    )

    opciones_clima = ["normal", "lluvioso", "adverso"]
    clima_default = CONFIG_ESCENARIO_RADAR.get("escenario_clima", "normal")
    indice_clima = opciones_clima.index(clima_default) if clima_default in opciones_clima else 0

    escenario_clima = st.selectbox(
        "Escenario",
        opciones_clima,
        index=indice_clima,
    )

    st.markdown('<div class="sidebar-title"><i class="ph ph-toggle-left"></i> Opciones</div>', unsafe_allow_html=True)
    stock_umbral = st.checkbox(
        "Stock inicial cerca del umbral",
        value=bool(CONFIG_ESCENARIO_RADAR.get("stock_inicial_cerca_umbral", True)),
    )

    st.markdown('<div class="sidebar-title"><i class="ph ph-play-circle"></i> Reproducción</div>', unsafe_allow_html=True)
    opciones_paso = [1, 2, 5, 10]

    paso_actual = st.session_state.velocidad_reproduccion
    if paso_actual not in opciones_paso:
        paso_actual = 1

    paso_temporal = st.select_slider(
        "Paso temporal (min/frame)",
        options=opciones_paso,
        value=paso_actual,
    )

    st.session_state.velocidad_reproduccion = paso_temporal

    retardo = st.slider(
        "Retardo entre frames (ms)",
        30,
        500,
        80,
        10,
        help="Menor valor = animación más rápida",
    )

    st.divider()

    ejecutar = st.button(
        "Ejecutar Simulación",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# EJECUCIÓN DE SIMULACIÓN
# ---------------------------------------------------------------------------

if ejecutar:
    # El radar siempre parte del escenario personalizado.
    # Ahí está fijada la distribución óptima de drones por base/hospital.
    # No se sobrescriben drones_por_base_config ni drones_por_hospital_config.
    config = CONFIG_ESCENARIO_RADAR.copy()
    config.update({
        "minutos_simulacion": minutos_sim,
        "semilla": semilla if semilla > 0 else None,
        "factor_demanda_inventario": factor_inv,
        "factor_demanda_organos": factor_org,
        "activar_meteorologia": activar_meteo,
        "intervalo_cambio_clima_min": intervalo_clima,
        "escenario_clima": escenario_clima,
        "stock_inicial_cerca_umbral": stock_umbral,
        "generar_graficas": False,
        "verbose": False,
        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    })

    limpiar_telemetria_previa()

    with st.spinner("Ejecutando simulación DES..."):
        resultado = run_simulation(config)

    vuelos_generados = obtener_vuelos_actuales(resultado)

    st.session_state.resultado = resultado
    st.session_state.vuelos_telemetria = vuelos_generados
    st.session_state.minutos_sim = minutos_sim
    st.session_state.minuto_actual = 0
    st.session_state._slider_minuto = 0
    st.session_state.is_playing = False

    st.success(
        f"Simulación completada — "
        f"{resultado.get('pedidos_generados', 0)} pedidos generados, "
        f"{resultado.get('pedidos_completados', 0)} completados, "
        f"{len(vuelos_generados)} tramos de vuelo en radar"
    )

# ---------------------------------------------------------------------------
# DATOS ACTUALES
# ---------------------------------------------------------------------------

resultado = st.session_state.get("resultado")
vuelos = obtener_vuelos_actuales(resultado)

df_hospitales, df_bases, df_aristas = preparar_datos_estaticos()

max_minuto = st.session_state.get("minutos_sim", 1440)

if vuelos:
    max_t_vuelos = max(vuelo["t_llegada"] for vuelo in vuelos)
    max_minuto = max(max_minuto, int(math.ceil(max_t_vuelos)))

st.session_state.minuto_actual = int(
    max(0, min(st.session_state.minuto_actual, max_minuto))
)

if st.session_state.is_playing:
    st.session_state._slider_minuto = st.session_state.minuto_actual
else:
    st.session_state._slider_minuto = int(
        max(0, min(st.session_state._slider_minuto, max_minuto))
    )

# ---------------------------------------------------------------------------
# MÉTRICAS RESUMEN
# ---------------------------------------------------------------------------

if resultado:
    # --- Fila 1: métricas principales ---
    cols = st.columns(6)

    metricas = [
        (resultado.get("pedidos_generados", 0), "Pedidos Generados", "ph-package"),
        (resultado.get("pedidos_completados", 0), "Completados", "ph-check-circle"),
        (resultado.get("pedidos_rechazados", 0), "Rechazados", "ph-x-circle"),
        (resultado.get("pedidos_en_cola", 0), "En Cola", "ph-clock"),
        (f"{resultado.get('tasa_servicio', 0) * 100:.1f}%", "Tasa de Servicio", "ph-chart-bar"),
        (f"{resultado.get('tasa_exito_organos', 0) * 100:.1f}%", "Éxito Órganos", "ph-heartbeat"),
    ]

    for i, (valor, label, icon) in enumerate(metricas):
        with cols[i]:
            st.markdown(
                f'<div class="metric-card"><i class="ph {icon}" style="font-size: 28px; color: #e63b2e; margin-bottom: 8px;"></i><h3>{valor}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    # --- Fila 2: desglose por producto ---
    conteo_completados = resultado.get("conteo_producto_completados", {})

    PRODUCTOS_INVENTARIO = [
        "sangre", "farmaco_uci", "antibiotico", "suero",
        "plasma", "analgesico", "material_sanitario", "medicamento_general",
    ]
    PRODUCTOS_ORGANOS = ["corazon", "pulmon", "rinon", "pancreas"]

    ICONO_PRODUCTO = {
        "sangre": "ph-drop", 
        "farmaco_uci": "ph-shield-plus", 
        "antibiotico": "ph-pill", 
        "suero": "ph-flask", 
        "plasma": "ph-vignette", 
        "analgesico": "ph-first-aid", 
        "material_sanitario": "ph-briefcase-metal",
        "medicamento_general": "ph-pills",
        "corazon": "ph-heartbeat", 
        "pulmon": "ph-lungs", 
        "rinon": "ph-microscope", 
        "pancreas": "ph-dna",
    }

    ICONOS_FA_ORGANOS = {
        "corazon": '<i class="fa-solid fa-heart-pulse"></i>', 
        "pulmon": '<i class="fa-solid fa-lungs"></i>', 
        "rinon": '<i class="fa-solid fa-filter"></i>', # El riñón actúa como filtro del cuerpo
        "pancreas": '<i class="fa-solid fa-capsules"></i>', # El páncreas genera insulina
    }

    with st.expander("Desglose por producto (completados)", expanded=False):
        st.markdown('<div class="brutalist-label" style="font-size:0.8rem; padding:0.2rem 0.5rem; margin-bottom:0.5rem;">Inventario</div>', unsafe_allow_html=True)
        cols_inv = st.columns(len(PRODUCTOS_INVENTARIO))
        for i, prod in enumerate(PRODUCTOS_INVENTARIO):
            n = conteo_completados.get(prod, 0)
            icon = ICONO_PRODUCTO.get(prod, "ph-package")
            nombre = prod.replace("_", " ")
            with cols_inv[i]:
                st.markdown(
                    f'<div class="product-card"><h4><i class="ph {icon}"></i> {n}</h4><p>{nombre}</p></div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="brutalist-label" style="font-size:0.8rem; padding:0.2rem 0.5rem; margin-top:1rem; margin-bottom:0.5rem;">Órganos</div>', unsafe_allow_html=True)
        cols_org = st.columns(len(PRODUCTOS_ORGANOS))
        for i, prod in enumerate(PRODUCTOS_ORGANOS):
            n = conteo_completados.get(prod, 0)
            icon_html = ICONOS_FA_ORGANOS.get(prod, '<i class="fa-solid fa-box"></i>')
            nombre = prod.replace("_", " ")
            with cols_org[i]:
                st.markdown(
                    f'<div class="product-card"><h4>{icon_html} {n}</h4><p>{nombre}</p></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONTROLES DE REPRODUCCIÓN
# ---------------------------------------------------------------------------

col_play, col_pause, col_status = st.columns([1, 1, 4])

with col_play:
    if st.button("Iniciar", use_container_width=True, disabled=not vuelos):
        st.session_state.is_playing = True
        st.session_state.minuto_actual = st.session_state._slider_minuto
        st.rerun()

with col_pause:
    if st.button("Pausar", use_container_width=True):
        st.session_state.is_playing = False
        st.session_state.minuto_actual = st.session_state._slider_minuto
        st.rerun()

with col_status:
    placeholder_status = st.empty()

vel_txt = f"{st.session_state.velocidad_reproduccion} min/frame"


def _actualizar_status(t):
    """Actualiza la barra de estado con el instante actual."""
    estado_txt = '<i class="ph ph-play-circle" style="color:#e63b2e;"></i> <span style="color:#e63b2e; font-weight:800;">EN REPRODUCCIÓN</span>' if st.session_state.is_playing else '<i class="ph ph-pause-circle" style="color:#888;"></i> Pausado'
    placeholder_status.markdown(
        f'<div style="padding:0.6rem 1rem; background:#ffffff; border:2px solid #e63b2e; '
        f'box-shadow: 4px 4px 0px 0px #000; color:#000000; font-family:\'Space Grotesk\', sans-serif; '
        f'font-size:0.9rem; display:flex; align-items:center; gap:0.8rem; text-transform:uppercase; font-weight:700;">'
        f'{estado_txt} &nbsp;·&nbsp; <i class="ph ph-gauge"></i> {vel_txt} &nbsp;·&nbsp; '
        f'<i class="ph ph-clock"></i> t = <span style="color:#e63b2e; font-size:1.1rem;">{t}</span> / {max_minuto}</div>',
        unsafe_allow_html=True,
    )


_actualizar_status(st.session_state.minuto_actual)


def _on_slider_change():
    """
    Si el usuario mueve el slider manualmente, se pausa la reproducción.
    """
    st.session_state.is_playing = False
    st.session_state.minuto_actual = st.session_state._slider_minuto


minuto_actual = st.slider(
    "Minuto de simulación",
    min_value=0,
    max_value=max_minuto,
    step=1,
    key="_slider_minuto",
    help="Arrastra para ver los drones en movimiento",
    on_change=_on_slider_change,
)

if not st.session_state.is_playing:
    st.session_state.minuto_actual = minuto_actual

# ---------------------------------------------------------------------------
# LEYENDA
# ---------------------------------------------------------------------------

st.markdown("""
<div class="legend-box">
    <span class="legend-item"><span class="legend-dot" style="background:#c8e6ff; border-color:#c8e6ff;"></span> Hospitales</span>
    <span class="legend-item"><span class="legend-dot" style="background:#e63b2e; border-color:#000;"></span> Bases</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(230,59,46,0.35);"></span> Topología</span>
    <span class="legend-item" style="color:#e63b2e; font-weight:900;">|</span>
    <span class="legend-item"><span class="legend-dot" style="background:#00c853;"></span> Inventario</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ff2828;"></span> Órgano</span>
    <span class="legend-item"><span class="legend-dot" style="background:#3c3c3c;"></span> Vuelta</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ffd600;"></span> Bat. baja</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(255,255,255,0.7);"></span> Aterrizó</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONSTRUCCIÓN DEL MAPA
# ---------------------------------------------------------------------------

def construir_mapa(t):
    """
    Construye el mapa PyDeck.

    El mapa usa:
    - topología del proyecto,
    - vuelos de la telemetría,
    - interpolación visual.
    """
    capas = []

    # --- Coverage rings: dark red glow around bases ---
    capa_cobertura = pdk.Layer(
        "ScatterplotLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_fill_color=[230, 59, 46, 12],
        get_radius="radio",
        pickable=False,
        opacity=0.12,
        stroked=True,
        get_line_color=[230, 59, 46, 60],
        line_width_min_pixels=1,
    )
    capas.append(capa_cobertura)

    # --- Topology edges: thin red lines connecting bases to hospitals ---
    if not df_aristas.empty:
        capa_aristas = pdk.Layer(
            "LineLayer",
            data=df_aristas,
            get_source_position=["origen_lon", "origen_lat"],
            get_target_position=["destino_lon", "destino_lat"],
            get_color=[230, 59, 46, 90],
            get_width=1.5,
            pickable=True,
        )
        capas.append(capa_aristas)

    # --- Hospitals: Simple point markers ---
    capa_hospital_halo = pdk.Layer(
        "ScatterplotLayer",
        data=df_hospitales,
        get_position=["lon", "lat"],
        get_fill_color=[200, 230, 255, 30],
        get_radius=300,
        pickable=False,
        opacity=0.3,
        stroked=True,
        get_line_color=[200, 230, 255, 80],
        line_width_min_pixels=1,
    )
    capas.append(capa_hospital_halo)

    capa_hospitales = pdk.Layer(
        "ScatterplotLayer",
        data=df_hospitales,
        get_position=["lon", "lat"],
        get_fill_color="color_rgb",
        get_radius=140,
        pickable=True,
        opacity=0.95,
        radiusMinPixels=4,
        stroked=True,
        get_line_color=[255, 255, 255, 200],
        line_width_min_pixels=2,
    )
    capas.append(capa_hospitales)

    # --- Bases: Simple point markers ---
    capa_base_halo = pdk.Layer(
        "ScatterplotLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_fill_color=[230, 59, 46, 25],
        get_radius=500,
        pickable=False,
        opacity=0.25,
        stroked=True,
        get_line_color=[230, 59, 46, 100],
        line_width_min_pixels=1,
    )
    capas.append(capa_base_halo)

    capa_bases = pdk.Layer(
        "ScatterplotLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_fill_color="color_rgb",
        get_radius=250,
        pickable=True,
        opacity=0.98,
        radiusMinPixels=6,
        stroked=True,
        get_line_color=[0, 0, 0, 200],
        line_width_min_pixels=3,
    )
    capas.append(capa_bases)

    # Base labels
    capa_label_bases = pdk.Layer(
        "TextLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_text="nombre",
        get_size=13,
        get_color=[30, 30, 30, 240],
        get_angle=0,
        get_text_anchor="'middle'",
        get_alignment_baseline="'top'",
        get_pixel_offset=[0, -22],
        font_family="'Space Grotesk', 'Inter', sans-serif",
        background=True,
        get_background_color=[255, 255, 255, 230],
        background_padding=[4, 2],
    )
    capas.append(capa_label_bases)

    df_drones = pd.DataFrame()
    df_rutas = pd.DataFrame()

    if vuelos:
        df_drones = drones_en_vuelo(vuelos, t)
        df_rutas = rutas_activas(vuelos, t)

    # --- Flight arcs ---
    if not df_rutas.empty:
        capas.append(pdk.Layer(
            "ArcLayer",
            data=df_rutas,
            get_source_position=["lon_origen", "lat_origen"],
            get_target_position=["lon_destino", "lat_destino"],
            get_source_color="color",
            get_target_color="color",
            get_width=4,
            opacity=0.7,
        ))

    # --- Drones: Simple point markers ---
    if not df_drones.empty:
        capa_drone_halo = pdk.Layer(
            "ScatterplotLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_fill_color=[230, 59, 46, 40],
            get_radius=600,
            pickable=False,
            opacity=0.3,
        )
        capas.append(capa_drone_halo)

        capa_drones = pdk.Layer(
            "ScatterplotLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=350,
            pickable=True,
            opacity=0.98,
            radiusMinPixels=7,
            stroked=True,
            get_line_color=[255, 255, 255, 200],
            line_width_min_pixels=2,
        )
        capas.append(capa_drones)

        capa_texto = pdk.Layer(
            "TextLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_text="dron_id",
            get_size=12,
            get_color=[30, 30, 30, 250],
            get_angle=0,
            get_text_anchor="'middle'",
            get_alignment_baseline="'top'",
            get_pixel_offset=[0, -22],
            font_family="'Space Grotesk', sans-serif",
            background=True,
            get_background_color=[255, 255, 255, 230],
            background_padding=[4, 2],
        )
        capas.append(capa_texto)

    vista = pdk.ViewState(
        latitude=MADRID_LAT,
        longitude=MADRID_LON,
        zoom=9.8,
        pitch=30,
        bearing=0,
    )

    mapa = pdk.Deck(
        layers=capas,
        initial_view_state=vista,
        map_style=pdk.map_styles.LIGHT,
        tooltip={
            "text": (
                "{nombre}\n"
                "{nombre_hospital}\n"
                "{dron_id}\n"
                "Misión: {tipo_mision}\n"
                "Batería: {bateria}%\n"
                "Progreso: {progreso}%\n"
                "{origen} → {destino}\n"
                "{distancia_km} km"
            ),
            "style": {
                "backgroundColor": "#ffffff",
                "color": "#000000",
                "border": "3px solid #e63b2e",
                "boxShadow": "4px 4px 0px #000000",
                "fontFamily": "Inter, sans-serif",
                "fontWeight": "700",
            },
        },
    )

    return mapa, df_drones, len(df_drones)


# ---------------------------------------------------------------------------
# RENDERIZADO
# ---------------------------------------------------------------------------

placeholder_mapa = st.empty()
placeholder_info = st.empty()
placeholder_tabla = st.empty()


def renderizar_frame(t):
    """
    Renderiza mapa + tabla + status para un instante t.
    """
    _actualizar_status(t)

    mapa, df_d, n = construir_mapa(t)

    with placeholder_mapa:
        st.pydeck_chart(mapa, use_container_width=True, height=650)

    with placeholder_info:
        if n > 0:
            st.markdown(f'<p style="color:#e63b2e; font-size:0.95rem; font-family:\'Space Grotesk\', sans-serif; font-weight:700; text-transform:uppercase;"><i class="ph ph-airplane-tilt"></i> {n} DRON(ES) VISIBLES en t = {t}</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:#888; font-size:0.95rem; font-family:\'Space Grotesk\', sans-serif; font-weight:700; text-transform:uppercase;"><i class="ph ph-clock"></i> t = {t} — SIN DRONES VISIBLES</p>', unsafe_allow_html=True)

    if not df_d.empty:
        with placeholder_tabla:
            st.dataframe(
                df_d[
                    [
                        "dron_id",
                        "tipo_mision",
                        "origen",
                        "destino",
                        "bateria",
                        "progreso",
                    ]
                ].rename(
                    columns={
                        "dron_id": "Dron",
                        "tipo_mision": "Misión",
                        "origen": "Origen",
                        "destino": "Destino",
                        "bateria": "Batería (%)",
                        "progreso": "Progreso (%)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
    else:
        placeholder_tabla.empty()


renderizar_frame(st.session_state.minuto_actual)

if not vuelos:
    st.info("Ejecuta una simulación desde la barra lateral para ver los drones en el radar.")

# ---------------------------------------------------------------------------
# AUTO-REPRODUCCIÓN
# ---------------------------------------------------------------------------

if st.session_state.is_playing and vuelos:
    paso = st.session_state.velocidad_reproduccion
    t = st.session_state.minuto_actual

    while t < max_minuto:
        renderizar_frame(t)
        time.sleep(retardo / 1000.0)

        t = min(t + paso, max_minuto)
        st.session_state.minuto_actual = t

    # Renderizar el último frame y auto-pausar
    renderizar_frame(max_minuto)
    st.session_state.minuto_actual = max_minuto
    st.session_state.is_playing = False
    st.rerun()


# ---------------------------------------------------------------------------
# GRÁFICAS DE RESULTADOS (réplica de visualizaciones.py)
# ---------------------------------------------------------------------------

if resultado:
    st.markdown("---")
    st.markdown("""
    <div style="margin:2rem 0 1.5rem 0; padding:1.5rem; background:#ffffff; border:4px solid #e63b2e; box-shadow: 8px 8px 0px 0px #000; text-align:center;">
        <h2 style="font-family:'Space Grotesk', sans-serif; color:#000000; font-size:2.2rem; margin:0; text-transform:uppercase; letter-spacing:2px; font-weight:900;">
            <i class="ph ph-chart-pie-slice" style="color:#e63b2e;"></i> ANÁLISIS DE SIMULACIÓN
        </h2>
        <p style="color:#333; font-family:'Inter', sans-serif; font-size:1rem; margin:0.5rem 0 0 0; font-weight:600; text-transform:uppercase; letter-spacing:1px;">
            Métricas de Rendimiento y Telemetría Industrial
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Extraer datos internos
    gestor_flota = resultado.get("_gestor_flota")
    historial_cola = resultado.get("_historial_longitud_cola", [])
    cola_pedidos_obj = resultado.get("_cola_pedidos")

    pedidos_completados = getattr(gestor_flota, "pedidos_completados", []) if gestor_flota else []
    pedidos_rechazados = getattr(gestor_flota, "pedidos_rechazados", []) if gestor_flota else []
    pedidos_pendientes = (
        getattr(cola_pedidos_obj, "pedidos_pendientes", [])
        if cola_pedidos_obj else []
    )
    estadisticas = getattr(gestor_flota, "estadisticas", None) if gestor_flota else None

    # =======================================================================
    # GRÁFICA 1: Embudo Global de Pedidos
    # =======================================================================

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown('<h4 class="brutalist-label"><i class="ph ph-funnel"></i> Embudo Global de Pedidos</h4>', unsafe_allow_html=True)

        total_gen = resultado.get("pedidos_generados", 0)
        total_comp = resultado.get("pedidos_completados", 0)
        total_pend = resultado.get("pedidos_en_cola", 0)
        total_rech = resultado.get("pedidos_rechazados", 0)

        df_embudo = pd.DataFrame({
            "Categoría": ["Generados", "Completados", "Pendientes", "Rechazados"],
            "Cantidad": [total_gen, total_comp, total_pend, total_rech],
        })

        st.bar_chart(
            df_embudo.set_index("Categoría"),
            color="#e63b2e",
            use_container_width=True,
        )

    # =======================================================================
    # GRÁFICA 2: Inventario vs Órganos
    # =======================================================================

    with col_g2:
        st.markdown('<h4 class="brutalist-label"><i class="ph ph-scales"></i> Inventario vs Órganos</h4>', unsafe_allow_html=True)

        inv_comp = resultado.get("inventario_completado", 0)
        inv_pend = resultado.get("inventario_pendiente", 0)
        org_comp = resultado.get("organos_completados", 0)
        org_pend = resultado.get("organos_pendientes", 0)
        org_rech = resultado.get("organos_rechazados", 0)

        # Rechazados de inventario = total rechazados - rechazados de órganos
        inv_rech = total_rech - org_rech

        df_tipo = pd.DataFrame({
            "Estado": ["Completados", "Pendientes", "Rechazados"],
            "Inventario": [inv_comp, inv_pend, max(inv_rech, 0)],
            "Órganos": [org_comp, org_pend, org_rech],
        }).set_index("Estado")

        st.bar_chart(df_tipo, color=["#2ecc71", "#e63b2e"], use_container_width=True)

    # =======================================================================
    # GRÁFICA 3: Cumplimiento de Órganos
    # =======================================================================

    col_g3, col_g4 = st.columns(2)

    with col_g3:
        st.markdown('<h4 class="brutalist-label"><i class="ph ph-heartbeat"></i> Cumplimiento de Órganos</h4>', unsafe_allow_html=True)

        org_on_time = resultado.get("organos_on_time", 0)
        org_late = resultado.get("organos_late", 0)

        df_org = pd.DataFrame({
            "Estado": ["A tiempo", "Tarde", "Pendientes", "Rechazados"],
            "Cantidad": [org_on_time, org_late, org_pend, org_rech],
        })

        st.bar_chart(
            df_org.set_index("Estado"),
            color="#e63b2e",
            use_container_width=True,
        )

    # =======================================================================
    # GRÁFICA 4: Demanda por hospital (Top 15)
    # =======================================================================

    with col_g4:
        st.markdown('<h4 class="brutalist-label"><i class="ph ph-buildings"></i> Top Hospitales Receptores</h4>', unsafe_allow_html=True)

        if pedidos_completados:
            conteo_hosp = {}
            for p in pedidos_completados:
                dest = p.destination_hospital
                conteo_hosp[dest] = conteo_hosp.get(dest, 0) + 1

            # Ordenar top 15
            top15 = sorted(conteo_hosp.items(), key=lambda x: x[1], reverse=True)[:15]

            df_hosp = pd.DataFrame(top15, columns=["Hospital", "Entregas"])

            st.bar_chart(
                df_hosp.set_index("Hospital"),
                color="#e63b2e",
                use_container_width=True,
                horizontal=True,
            )
        else:
            st.info("Sin datos de entregas completadas.")

    # =======================================================================
    # GRÁFICA 5: Evolución de la Cola
    # =======================================================================

    if historial_cola:
        st.markdown('<h4 class="brutalist-label"><i class="ph ph-trend-up"></i> Evolución de la Longitud de Cola</h4>', unsafe_allow_html=True)

        df_cola = pd.DataFrame({
            "Minuto": range(len(historial_cola)),
            "Pedidos en Cola": historial_cola,
        })

        st.area_chart(
            df_cola.set_index("Minuto"),
            color="#e63b2e",
            use_container_width=True,
        )

        # Métricas de cola
        cola_c1, cola_c2 = st.columns(2)
        with cola_c1:
            st.metric(
                "Longitud media de cola",
                f"{resultado.get('longitud_media_cola', 0):.1f}",
            )
        with cola_c2:
            st.metric(
                "Longitud máxima de cola",
                resultado.get("longitud_maxima_cola", 0),
            )

    # =======================================================================
    # METEOROLOGÍA + FLOTA (resumen)
    # =======================================================================

    col_m1, col_m2 = st.columns(2)

    conteo_clima = resultado.get("conteo_clima", {})
    resumen_flota = resultado.get("resumen_flota", {})

    with col_m1:
        if conteo_clima:
            st.markdown('<h4 class="brutalist-label"><i class="ph ph-cloud-rain"></i> Meteorología</h4>', unsafe_allow_html=True)
            min_sim = resultado.get("minutos_simulacion", 1)
            filas_clima = []
            for nombre_estado, mins in conteo_clima.items():
                pct = (mins / min_sim) * 100 if min_sim > 0 else 0
                filas_clima.append({
                    "Estado": nombre_estado.replace("_", " ").title(),
                    "Minutos": mins,
                    "Porcentaje": f"{pct:.1f}%",
                })
            st.dataframe(
                pd.DataFrame(filas_clima),
                use_container_width=True,
                hide_index=True,
            )

    with col_m2:
        if resumen_flota:
            st.markdown('<h4 class="brutalist-label"><i class="ph ph-airplane"></i> Estado final de la flota</h4>', unsafe_allow_html=True)

            filas_flota = [
                ("Total drones", resultado.get("total_drones", 0)),
                ("Drones base", resumen_flota.get("base_total", 0)),
                ("Drones hospital", resumen_flota.get("hospital_total", 0)),
                ("Disponibles", resumen_flota.get("available", 0)),
                ("En misión", resumen_flota.get("mission", 0)),
                ("Recargando", resumen_flota.get("charging", 0)),
                ("Utilización vuelo", f"{resultado.get('utilizacion_vuelo_pct', 0):.2f}%"),
                ("Utilización operativa", f"{resultado.get('utilizacion_operativa_pct', 0):.2f}%"),
            ]

            st.dataframe(
                pd.DataFrame(filas_flota, columns=["Métrica", "Valor"]),
                use_container_width=True,
                hide_index=True,
            )
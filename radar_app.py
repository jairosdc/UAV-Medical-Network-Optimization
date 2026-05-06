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

# ---------------------------------------------------------------------------
# Importaciones del proyecto
# ---------------------------------------------------------------------------

from hospitales_almacenes_data import HOSPITALS, BASES
from services.grafo_distancias_service import ServicioRed
from simulators.experimentacion import run_simulation

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

RUTA_TELEMETRIA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "telemetria_vuelos.json",
)

MADRID_LAT = 40.42
MADRID_LON = -3.70

# Colores de misiones
COLOR_INVENTARIO = [46, 204, 113, 230]
COLOR_ORGANO = [231, 76, 60, 240]
COLOR_VUELTA = [149, 165, 166, 180]
COLOR_BATERIA_BAJA = [255, 255, 0, 240]
COLOR_RECIEN_LLEGADO = [255, 255, 255, 160]

# Colores de nodos
COLOR_HOSPITAL_NODO = [0, 250, 154, 220]

UMBRAL_BATERIA_BAJA = 25.0
MARGEN_PERSISTENCIA_MIN = 3

# Configuración visual por base.
# Si en el proyecto aparecen nuevas bases, se les asigna un color por defecto.
CONFIG_BASES = {
    "BASE NOROESTE": {"color_rgb": [0, 255, 136], "radio": 6000},
    "BASE NORTE CAPITAL": {"color_rgb": [0, 207, 255], "radio": 4504},
    "BASE ESTE CORREDOR": {"color_rgb": [180, 120, 255], "radio": 3500},
    "BASE SUR FUENLABRADA": {"color_rgb": [255, 159, 0], "radio": 4000},
}

COLORES_BASE_FALLBACK = [
    [0, 255, 136],
    [0, 207, 255],
    [180, 120, 255],
    [255, 159, 0],
    [255, 99, 132],
    [120, 220, 120],
    [240, 240, 120],
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
    page_title="FlyRadar — UAV Medical Network",
    page_icon="🛩️",
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
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-title {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.2rem;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.06);
    }

    .main-title h1 {
        background: linear-gradient(90deg, #00b4d8, #90e0ef);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        margin: 0;
    }

    .main-title p {
        color: #8892b0;
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
    }

    .metric-card h3 {
        color: #00b4d8;
        font-size: 1.6rem;
        margin: 0;
    }

    .metric-card p {
        color: #8892b0;
        font-size: 0.8rem;
        margin: 0.2rem 0 0 0;
    }

    .legend-box {
        background: rgba(15, 12, 41, 0.85);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-top: 0.8rem;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        margin-right: 1.2rem;
        font-size: 0.82rem;
        color: #ccd6f6;
    }

    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29, #1a1a2e);
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #00b4d8;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-title">
    <h1>🛩️ FlyRadar — UAV Medical Network</h1>
    <p>Visor interactivo de drones médicos sobre la Comunidad de Madrid</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Simulación")
    minutos_sim = st.slider(
        "Duración (minutos)",
        60,
        50000,
        1440,
        step=60,
        help="1440 = 1 día, 10080 = 1 semana",
    )

    drones_base = st.slider("Drones por base", 1, 10, 2)
    drones_hosp = st.slider("Drones por hospital", 1, 5, 1)
    semilla = st.number_input("Semilla aleatoria (0 = random)", 0, 999999, 42)

    st.subheader("Demanda")
    factor_inv = st.slider("Factor demanda inventario", 0.1, 3.0, 1.0, 0.1)
    factor_org = st.slider("Factor demanda órganos", 0.1, 3.0, 1.0, 0.1)

    st.subheader("Meteorología")
    activar_meteo = st.checkbox("Activar meteorología", value=True)
    intervalo_clima = st.slider("Intervalo cambio clima (min)", 60, 1440, 300, 60)

    escenario_clima = st.selectbox(
        "Escenario",
        ["normal", "severo", "despejado"],
        index=0,
    )

    st.subheader("Opciones")
    stock_umbral = st.checkbox("Stock inicial cerca del umbral", value=True)

    st.subheader("Reproducción")
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
        "🚀 Ejecutar Simulación",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# EJECUCIÓN DE SIMULACIÓN
# ---------------------------------------------------------------------------

if ejecutar:
    config = {
        "minutos_simulacion": minutos_sim,
        "drones_por_base": drones_base,
        "drones_por_hospital": drones_hosp,
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
    }

    limpiar_telemetria_previa()

    with st.spinner("⏳ Ejecutando simulación DES..."):
        resultado = run_simulation(config)

    vuelos_generados = obtener_vuelos_actuales(resultado)

    st.session_state.resultado = resultado
    st.session_state.vuelos_telemetria = vuelos_generados
    st.session_state.minutos_sim = minutos_sim
    st.session_state.minuto_actual = 0
    st.session_state._slider_minuto = 0
    st.session_state.is_playing = False

    st.success(
        f"✅ Simulación completada — "
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
    cols = st.columns(6)

    metricas = [
        (resultado.get("pedidos_generados", 0), "Pedidos Generados"),
        (resultado.get("pedidos_completados", 0), "Completados"),
        (resultado.get("pedidos_rechazados", 0), "Rechazados"),
        (resultado.get("pedidos_en_cola", 0), "En Cola"),
        (f"{resultado.get('tasa_servicio', 0) * 100:.1f}%", "Tasa de Servicio"),
        (len(vuelos), "Tramos Radar"),
    ]

    for i, (valor, label) in enumerate(metricas):
        with cols[i]:
            st.markdown(
                f'<div class="metric-card"><h3>{valor}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONTROLES DE REPRODUCCIÓN
# ---------------------------------------------------------------------------

col_play, col_pause, col_status = st.columns([1, 1, 4])

with col_play:
    if st.button("▶ Iniciar", use_container_width=True, disabled=not vuelos):
        st.session_state.is_playing = True
        st.session_state.minuto_actual = st.session_state._slider_minuto
        st.rerun()

with col_pause:
    if st.button("⏸ Pausar", use_container_width=True):
        st.session_state.is_playing = False
        st.session_state.minuto_actual = st.session_state._slider_minuto
        st.rerun()

with col_status:
    estado_txt = "🔴 EN REPRODUCCIÓN" if st.session_state.is_playing else "⏸️ Pausado"
    vel_txt = f"{st.session_state.velocidad_reproduccion} min/frame"

    st.markdown(
        f'<div style="padding:0.45rem 0.8rem; background:rgba(15,12,41,0.6); '
        f'border-radius:8px; color:#ccd6f6; font-size:0.85rem;">'
        f'{estado_txt} &nbsp;·&nbsp; Velocidad: {vel_txt} &nbsp;·&nbsp; '
        f't = <b>{st.session_state.minuto_actual}</b> / {max_minuto}</div>',
        unsafe_allow_html=True,
    )


def _on_slider_change():
    """
    Si el usuario mueve el slider manualmente, se pausa la reproducción.
    """
    st.session_state.is_playing = False
    st.session_state.minuto_actual = st.session_state._slider_minuto


minuto_actual = st.slider(
    "⏱️ Minuto de simulación",
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
    <span class="legend-item"><span class="legend-dot" style="background:#00fa9a;"></span> Hospitales</span>
    <span class="legend-item"><span class="legend-dot" style="background:#00ff88;"></span> Bases</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(150,150,150,0.5);"></span> Topología</span>
    <span class="legend-item" style="margin-left:0.5rem;">|</span>
    <span class="legend-item"><span class="legend-dot" style="background:#2ecc71;"></span> Inventario</span>
    <span class="legend-item"><span class="legend-dot" style="background:#e74c3c;"></span> Órgano</span>
    <span class="legend-item"><span class="legend-dot" style="background:#95a5a6;"></span> Vuelta</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ffff00;"></span> Bat. baja</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(255,255,255,0.6);"></span> Aterrizó</span>
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

    capa_cobertura = pdk.Layer(
        "ScatterplotLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_fill_color="color_rgba_cobertura",
        get_radius="radio",
        pickable=False,
        opacity=0.08,
        stroked=True,
        get_line_color="color_rgb",
        line_width_min_pixels=1,
    )
    capas.append(capa_cobertura)

    if not df_aristas.empty:
        capa_aristas = pdk.Layer(
            "LineLayer",
            data=df_aristas,
            get_source_position=["origen_lon", "origen_lat"],
            get_target_position=["destino_lon", "destino_lat"],
            get_color="color_arista",
            get_width=2,
            pickable=True,
        )
        capas.append(capa_aristas)

    capa_hospitales = pdk.Layer(
        "ScatterplotLayer",
        data=df_hospitales,
        get_position=["lon", "lat"],
        get_fill_color="color_rgb",
        get_radius=120,
        pickable=True,
        opacity=0.9,
        stroked=True,
        get_line_color=[255, 255, 255, 60],
        line_width_min_pixels=1,
    )
    capas.append(capa_hospitales)

    capa_bases = pdk.Layer(
        "ScatterplotLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_fill_color="color_rgb",
        get_radius=220,
        pickable=True,
        opacity=0.95,
        stroked=True,
        get_line_color=[255, 255, 255, 150],
        line_width_min_pixels=2,
    )
    capas.append(capa_bases)

    capa_label_bases = pdk.Layer(
        "TextLayer",
        data=df_bases,
        get_position=["lon", "lat"],
        get_text="nombre",
        get_size=12,
        get_color=[255, 255, 255, 200],
        get_angle=0,
        get_text_anchor="'middle'",
        get_alignment_baseline="'top'",
        get_pixel_offset=[0, -20],
        font_family="'Inter', sans-serif",
    )
    capas.append(capa_label_bases)

    df_drones = pd.DataFrame()
    df_rutas = pd.DataFrame()

    if vuelos:
        df_drones = drones_en_vuelo(vuelos, t)
        df_rutas = rutas_activas(vuelos, t)

    if not df_rutas.empty:
        capa_arcos = pdk.Layer(
            "ArcLayer",
            data=df_rutas,
            get_source_position=["lon_origen", "lat_origen"],
            get_target_position=["lon_destino", "lat_destino"],
            get_source_color="color",
            get_target_color="color",
            get_width=3,
            opacity=0.5,
        )
        capas.append(capa_arcos)

    if not df_drones.empty:
        capa_drones = pdk.Layer(
            "ScatterplotLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=300,
            pickable=True,
            opacity=0.95,
            radiusMinPixels=6,
            stroked=True,
            get_line_color=[255, 255, 255, 120],
            line_width_min_pixels=1,
        )
        capas.append(capa_drones)

        capa_texto = pdk.Layer(
            "TextLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_text="dron_id",
            get_size=11,
            get_color=[255, 255, 255, 230],
            get_angle=0,
            get_text_anchor="'middle'",
            get_alignment_baseline="'top'",
            get_pixel_offset=[0, -20],
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
        map_style=pdk.map_styles.DARK,
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
            )
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
    Renderiza mapa + tabla para un instante t.
    """
    mapa, df_d, n = construir_mapa(t)

    with placeholder_mapa:
        st.pydeck_chart(mapa, use_container_width=True, height=650)

    with placeholder_info:
        if n > 0:
            st.caption(f"🛫 **{n} dron(es) visibles** en t = {t}")
        else:
            st.caption(f"⏱️ t = {t} — Sin drones visibles")

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
    st.info("📡 Ejecuta una simulación desde la barra lateral para ver los drones en el radar.")

# ---------------------------------------------------------------------------
# AUTO-REPRODUCCIÓN
# ---------------------------------------------------------------------------

if st.session_state.is_playing and vuelos:
    if st.session_state.minuto_actual >= max_minuto:
        st.session_state.is_playing = False
        st.rerun()

    time.sleep(retardo / 1000.0)

    siguiente_t = min(
        st.session_state.minuto_actual + st.session_state.velocidad_reproduccion,
        max_minuto,
    )

    st.session_state.minuto_actual = siguiente_t
    st.rerun()
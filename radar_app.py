"""
radar_app.py — FlyRadar: Visor Interactivo de Drones Médicos
=============================================================

Aplicación Streamlit + PyDeck conectada directamente al motor DES.

Principio:
- Los escenarios salen exclusivamente de simulators/escenarios.py.
- El motor DES ejecuta la simulación.
- El radar solo consume la telemetría generada por el motor.
- Este archivo NO debe duplicar lógica de simulación.
"""

import copy
import json
import math
import os
import time

import pandas as pd
import pydeck as pdk
import streamlit as st

# ---------------------------------------------------------------------------
# Importaciones del proyecto
# ---------------------------------------------------------------------------

from hospitales_almacenes_data import HOSPITALS, BASES
from services.grafo_distancias_service import ServicioRed
from simulators.experimentacion import run_simulation
from simulators.escenarios import ESCENARIOS

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

RUTA_TELEMETRIA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "telemetria_vuelos.json",
)

MADRID_LAT = 40.42
MADRID_LON = -3.70

# Colores misiones
COLOR_INVENTARIO = [46, 204, 113, 230]
COLOR_ORGANO = [231, 76, 60, 240]
COLOR_VUELTA = [149, 165, 166, 180]
COLOR_BATERIA_BAJA = [255, 255, 0, 240]
COLOR_RECIEN_LLEGADO = [255, 255, 255, 160]

# Colores nodos
COLOR_HOSPITAL_NODO = [0, 250, 154, 220]

UMBRAL_BATERIA_BAJA = 25.0
MARGEN_PERSISTENCIA_MIN = 3

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

NOMBRES_ESCENARIOS = {
    "normal": "Normal",
    "alta_demanda": "Alta demanda",
    "lluvia_alta_demanda": "Lluvia + alta demanda",
    "baja_demanda_clima_adverso": "Baja demanda + clima adverso",
    "estres_extremo": "Estrés extremo",
}


# ---------------------------------------------------------------------------
# UTILIDADES GENERALES
# ---------------------------------------------------------------------------

def nombre_escenario_visible(clave):
    return NOMBRES_ESCENARIOS.get(clave, clave.replace("_", " ").title())


def limpiar_telemetria_previa():
    """
    Evita pintar una simulación antigua si la nueva no genera telemetría.
    """
    if os.path.exists(RUTA_TELEMETRIA):
        os.remove(RUTA_TELEMETRIA)


def preparar_config_para_streamlit(config_escenario):
    """
    Copia un escenario real y solo desactiva salidas que no tienen sentido
    dentro de Streamlit.

    No se cambia la lógica de simulación:
    - demanda,
    - duración,
    - drones,
    - clima,
    - semilla,
    - stock,
    salen del escenario.
    """
    config = copy.deepcopy(config_escenario)

    config["generar_graficas"] = False
    config["verbose"] = False
    config["imprimir_eventos_drones"] = False
    config["imprimir_eventos_hospital"] = False
    config["imprimir_eventos_clima"] = False

    return config


def formato_duracion(minutos):
    dias = minutos / 1440

    if minutos % 1440 == 0:
        return f"{minutos:,} min · {dias:.0f} días".replace(",", ".")

    return f"{minutos:,} min · {dias:.1f} días".replace(",", ".")


def porcentaje(valor):
    try:
        return f"{float(valor) * 100:.1f}%"
    except Exception:
        return "0.0%"


def firma_topologia():
    """
    Firma ligera para invalidar caché si cambian hospitales o bases.
    """
    hospitales = tuple(
        sorted(
            (nombre, nodo.lat, nodo.lon, nodo.tipo)
            for nombre, nodo in HOSPITALS.items()
        )
    )

    bases = tuple(
        sorted(
            (nombre, nodo.lat, nodo.lon, nodo.tipo)
            for nombre, nodo in BASES.items()
        )
    )

    return hospitales, bases


def obtener_config_base(nombre_base, indice):
    if nombre_base in CONFIG_BASES:
        return CONFIG_BASES[nombre_base]

    color = COLORES_BASE_FALLBACK[indice % len(COLORES_BASE_FALLBACK)]

    return {
        "color_rgb": color,
        "radio": 3500,
    }


# ---------------------------------------------------------------------------
# DATOS ESTÁTICOS DEL MAPA
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def preparar_datos_estaticos(_firma):
    """
    Genera DataFrames estáticos para:
    - hospitales,
    - bases,
    - aristas base -> hospital según ServicioRed.
    """
    servicio_red = ServicioRed()

    filas_h = []
    filas_b = []
    filas_aristas = []

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
            # Si una conexión concreta falla, no se tumba todo el radar.
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


# ---------------------------------------------------------------------------
# TELEMETRÍA
# ---------------------------------------------------------------------------

def cargar_telemetria_json():
    """
    Lee telemetria_vuelos.json.

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
    Filtra vuelos incompletos o mal tipados.
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
            vuelo_limpio = dict(vuelo)

            vuelo_limpio["t_salida"] = float(vuelo["t_salida"])
            vuelo_limpio["t_llegada"] = float(vuelo["t_llegada"])

            if vuelo_limpio["t_llegada"] < vuelo_limpio["t_salida"]:
                continue

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
    Fuente visual.

    Orden:
    1. resultado["telemetria"], si algún día el motor lo devuelve.
    2. session_state.
    3. telemetria_vuelos.json, que es lo que usa ahora el motor.
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
    Interpola un tramo ya generado por el motor.
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
    if vuelo["bateria"] < UMBRAL_BATERIA_BAJA:
        return COLOR_BATERIA_BAJA

    tipo = vuelo["tipo_mision"]

    if tipo == "organo":
        return COLOR_ORGANO

    if tipo == "inventario":
        return COLOR_INVENTARIO

    return COLOR_VUELTA


def etiqueta_mision(tipo):
    etiquetas = {
        "inventario": "Inventario",
        "organo": "Órgano",
        "vuelta_base": "Vuelta a base",
    }

    return etiquetas.get(tipo, tipo)


def drones_en_vuelo(vuelos, t):
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
# CONFIGURACIÓN STREAMLIT
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

if "escenario_actual" not in st.session_state:
    st.session_state.escenario_actual = list(ESCENARIOS.keys())[0]

if "_slider_minuto" not in st.session_state:
    st.session_state._slider_minuto = 0


# ---------------------------------------------------------------------------
# CSS
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
        border: 1px solid rgba(255,255,255,0.08);
    }

    .main-title h1 {
        background: linear-gradient(90deg, #00b4d8, #90e0ef);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.3rem;
        margin: 0;
    }

    .main-title p {
        color: #a8b2d1;
        font-size: 0.95rem;
        margin: 0.35rem 0 0 0;
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 13px;
        padding: 1rem 1.2rem;
        text-align: center;
        min-height: 92px;
    }

    .metric-card h3 {
        color: #00b4d8;
        font-size: 1.45rem;
        margin: 0;
    }

    .metric-card p {
        color: #8892b0;
        font-size: 0.78rem;
        margin: 0.25rem 0 0 0;
    }

    .scenario-card {
        background: rgba(15, 12, 41, 0.85);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }

    .scenario-card h3 {
        color: #90e0ef;
        margin-top: 0;
        margin-bottom: 0.4rem;
    }

    .scenario-card p {
        color: #ccd6f6;
        margin: 0.15rem 0;
        font-size: 0.87rem;
    }

    .legend-box {
        background: rgba(15, 12, 41, 0.85);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
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
    <p>Visor interactivo de simulaciones por escenarios definidos en <b>simulators/escenarios.py</b></p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR — ESCENARIOS
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Escenario")

    claves_escenarios = list(ESCENARIOS.keys())

    escenario_seleccionado = st.selectbox(
        "Selecciona un escenario",
        options=claves_escenarios,
        index=claves_escenarios.index(st.session_state.escenario_actual)
        if st.session_state.escenario_actual in claves_escenarios
        else 0,
        format_func=nombre_escenario_visible,
    )

    st.session_state.escenario_actual = escenario_seleccionado

    config_escenario = ESCENARIOS[escenario_seleccionado]

    st.markdown(
        f"""
        <div class="scenario-card">
            <h3>{nombre_escenario_visible(escenario_seleccionado)}</h3>
            <p><b>Duración:</b> {formato_duracion(config_escenario.get("minutos_simulacion", 0))}</p>
            <p><b>Drones/base:</b> {config_escenario.get("drones_por_base", "-")}</p>
            <p><b>Drones/hospital:</b> {config_escenario.get("drones_por_hospital", "-")}</p>
            <p><b>Demanda inventario:</b> x{config_escenario.get("factor_demanda_inventario", "-")}</p>
            <p><b>Demanda órganos:</b> x{config_escenario.get("factor_demanda_organos", "-")}</p>
            <p><b>Clima:</b> {config_escenario.get("escenario_clima", "-")}</p>
            <p><b>Meteorología:</b> {"activa" if config_escenario.get("activar_meteorologia", False) else "desactivada"}</p>
            <p><b>Semilla:</b> {config_escenario.get("semilla", None)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver configuración exacta"):
        st.json(config_escenario)

    st.subheader("Reproducción")

    opciones_paso = [1, 2, 5, 10, 30, 60]
    paso_actual = st.session_state.velocidad_reproduccion

    if paso_actual not in opciones_paso:
        paso_actual = 1

    paso_temporal = st.select_slider(
        "Paso temporal",
        options=opciones_paso,
        value=paso_actual,
        format_func=lambda x: f"{x} min/frame",
    )

    st.session_state.velocidad_reproduccion = paso_temporal

    retardo = st.slider(
        "Retardo entre frames",
        30,
        500,
        80,
        10,
        help="Menor valor = animación más rápida",
    )

    st.divider()

    ejecutar = st.button(
        "🚀 Ejecutar escenario",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# EJECUCIÓN
# ---------------------------------------------------------------------------

if ejecutar:
    config = preparar_config_para_streamlit(ESCENARIOS[escenario_seleccionado])

    limpiar_telemetria_previa()

    with st.spinner(f"⏳ Ejecutando escenario: {nombre_escenario_visible(escenario_seleccionado)}..."):
        resultado = run_simulation(config)

    vuelos_generados = obtener_vuelos_actuales(resultado)

    st.session_state.resultado = resultado
    st.session_state.vuelos_telemetria = vuelos_generados
    st.session_state.minutos_sim = config.get("minutos_simulacion", 1440)
    st.session_state.minuto_actual = 0
    st.session_state._slider_minuto = 0
    st.session_state.is_playing = False
    st.session_state.escenario_ejecutado = escenario_seleccionado

    st.success(
        f"✅ Escenario ejecutado — "
        f"{resultado.get('pedidos_generados', 0)} pedidos generados, "
        f"{resultado.get('pedidos_completados', 0)} completados, "
        f"{len(vuelos_generados)} tramos de vuelo"
    )

# ---------------------------------------------------------------------------
# DATOS ACTUALES
# ---------------------------------------------------------------------------

resultado = st.session_state.get("resultado")
vuelos = obtener_vuelos_actuales(resultado)

df_hospitales, df_bases, df_aristas = preparar_datos_estaticos(firma_topologia())

max_minuto = st.session_state.get("minutos_sim", 1440)

if vuelos:
    max_t_vuelos = max(vuelo["t_llegada"] for vuelo in vuelos)
    max_minuto = max(max_minuto, int(math.ceil(max_t_vuelos)))

st.session_state.minuto_actual = int(
    max(0, min(st.session_state.minuto_actual, max_minuto))
)

st.session_state._slider_minuto = int(
    max(0, min(st.session_state._slider_minuto, max_minuto))
)

# ---------------------------------------------------------------------------
# PANEL DE RESULTADOS
# ---------------------------------------------------------------------------

if resultado:
    escenario_ejecutado = st.session_state.get("escenario_ejecutado", escenario_seleccionado)

    st.markdown(
        f"""
        <div class="scenario-card">
            <h3>Escenario ejecutado: {nombre_escenario_visible(escenario_ejecutado)}</h3>
            <p>El radar está mostrando la telemetría generada por el motor DES para este escenario.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(6)

    metricas = [
        (resultado.get("pedidos_generados", 0), "Pedidos generados"),
        (resultado.get("pedidos_completados", 0), "Completados"),
        (resultado.get("pedidos_en_cola", 0), "En cola"),
        (porcentaje(resultado.get("tasa_servicio", 0)), "Tasa servicio"),
        (porcentaje(resultado.get("tasa_exito_organos", 0)), "Éxito órganos"),
        (len(vuelos), "Tramos radar"),
    ]

    for i, (valor, label) in enumerate(metricas):
        with cols[i]:
            st.markdown(
                f'<div class="metric-card"><h3>{valor}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    cols2 = st.columns(6)

    metricas2 = [
        (resultado.get("total_drones", 0), "Total drones"),
        (resultado.get("organos_totales", 0), "Órganos totales"),
        (resultado.get("organos_late", 0), "Órganos tarde"),
        (f'{resultado.get("utilizacion_vuelo_pct", 0):.1f}%', "Utilización vuelo"),
        (f'{resultado.get("utilizacion_operativa_pct", 0):.1f}%', "Utilización operativa"),
        (resultado.get("longitud_maxima_cola", 0), "Cola máxima"),
    ]

    for i, (valor, label) in enumerate(metricas2):
        with cols2[i]:
            st.markdown(
                f'<div class="metric-card"><h3>{valor}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    with st.expander("Detalles del resultado"):
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("Flota")
            st.json(resultado.get("resumen_flota", {}))

        with col_b:
            st.subheader("Meteorología")
            st.json(resultado.get("conteo_clima", {}))

        with col_c:
            st.subheader("Cola y uso")
            st.json({
                "longitud_media_cola": resultado.get("longitud_media_cola", 0),
                "longitud_maxima_cola": resultado.get("longitud_maxima_cola", 0),
                "tiempo_total_vuelo": resultado.get("tiempo_total_vuelo", 0),
                "tiempo_total_recarga": resultado.get("tiempo_total_recarga", 0),
            })

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
        f'<div style="padding:0.55rem 0.9rem; background:rgba(15,12,41,0.75); '
        f'border-radius:10px; color:#ccd6f6; font-size:0.88rem;">'
        f'{estado_txt} &nbsp;·&nbsp; Velocidad: {vel_txt} &nbsp;·&nbsp; '
        f't = <b>{st.session_state.minuto_actual}</b> / {max_minuto}</div>',
        unsafe_allow_html=True,
    )


def _on_slider_change():
    st.session_state.is_playing = False
    st.session_state.minuto_actual = st.session_state._slider_minuto


minuto_actual = st.slider(
    "⏱️ Minuto de simulación",
    min_value=0,
    max_value=max_minuto,
    step=1,
    key="_slider_minuto",
    help="Arrastra para navegar por la telemetría",
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
# MAPA
# ---------------------------------------------------------------------------

def construir_mapa(t):
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
    st.info("📡 Ejecuta un escenario desde la barra lateral para ver vuelos en el radar.")

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
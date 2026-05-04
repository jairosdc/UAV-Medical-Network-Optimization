"""
radar_app.py — FlyRadar: Visor Interactivo de Drones Médicos
=============================================================

Aplicación Streamlit + PyDeck conectada directamente al motor DES.
El usuario configura la simulación desde la barra lateral, la ejecuta
y luego navega por el timeline para ver los drones en movimiento.

Lanzar con:
    streamlit run radar_app.py
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

# Centro del mapa (Madrid)
MADRID_LAT = 40.42
MADRID_LON = -3.70

# Colores (RGBA)
COLOR_INVENTARIO = [46, 204, 113, 230]    # Verde
COLOR_ORGANO = [231, 76, 60, 240]         # Rojo
COLOR_VUELTA = [149, 165, 166, 180]       # Gris
COLOR_BATERIA_BAJA = [255, 255, 0, 240]   # Amarillo
COLOR_RECIEN_LLEGADO = [255, 255, 255, 160]  # Blanco semitransparente
COLOR_HOSPITAL_NODO = [0, 250, 154, 220]  # Verde primavera (SpringGreen)
COLOR_ARISTA = [150, 150, 150, 80]        # Gris semitransparente

UMBRAL_BATERIA_BAJA = 25.0
MARGEN_PERSISTENCIA_MIN = 3

# Configuración visual por base (color RGB + radio de cobertura en metros)
CONFIG_BASES = {
    "BASE NOROESTE":       {"color_rgb": [0, 255, 136],  "radio": 6000},
    "BASE NORTE CAPITAL":  {"color_rgb": [0, 207, 255],  "radio": 4504},
    "BASE ESTE CORREDOR":  {"color_rgb": [180, 120, 255], "radio": 3500},
    "BASE SUR FUENLABRADA":{"color_rgb": [255, 159, 0],  "radio": 4000},
}


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

@st.cache_data
def preparar_datos_estaticos():
    """
    Genera tres DataFrames estáticos para las capas de topología del mapa:
    - df_hospitales: nodos de hospitales con color verde primavera
    - df_bases: núcleos de bases con color y radio de cobertura
    - df_aristas: líneas base → hospital según topología (base más cercana)
    """
    servicio_red = ServicioRed()

    filas_h = []
    filas_aristas = []

    for nombre, nodo in HOSPITALS.items():
        filas_h.append({
            "nombre": nombre,
            "lat": nodo.lat,
            "lon": nodo.lon,
            "color_rgb": COLOR_HOSPITAL_NODO,
        })

        # Topología: conectar a la base más cercana
        nombre_base, distancia_km = servicio_red.base_mas_cercana_a(nombre)
        base_nodo = BASES[nombre_base]
        base_cfg = CONFIG_BASES.get(nombre_base, {"color_rgb": [255, 255, 255], "radio": 2000})

        filas_aristas.append({
            "origen_lat": base_nodo.lat,
            "origen_lon": base_nodo.lon,
            "destino_lat": nodo.lat,
            "destino_lon": nodo.lon,
            "distancia_km": round(distancia_km, 2),
            "nombre_base": nombre_base,
            "nombre_hospital": nombre,
            "color_arista": base_cfg["color_rgb"] + [80],  # RGBA tenue
        })

    filas_b = []
    for nombre, nodo in BASES.items():
        cfg = CONFIG_BASES.get(nombre, {"color_rgb": [255, 255, 255], "radio": 2000})
        filas_b.append({
            "nombre": nombre,
            "lat": nodo.lat,
            "lon": nodo.lon,
            "color_rgb": cfg["color_rgb"],
            "color_rgba_cobertura": cfg["color_rgb"] + [15],  # Muy tenue
            "radio": cfg["radio"],
        })

    return pd.DataFrame(filas_h), pd.DataFrame(filas_b), pd.DataFrame(filas_aristas)


def cargar_telemetria():
    """Lee el JSON de telemetría si existe."""
    if not os.path.exists(RUTA_TELEMETRIA):
        return []
    with open(RUTA_TELEMETRIA, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("vuelos", [])


def interpolar_posicion(vuelo, t):
    """
    Interpola linealmente lat/lon del dron en el instante t.
    Devuelve (lat, lon, progreso_0_a_1).
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
    """Elige color según tipo de misión y batería."""
    if vuelo["bateria"] < UMBRAL_BATERIA_BAJA:
        return COLOR_BATERIA_BAJA

    tipo = vuelo["tipo_mision"]
    if tipo == "organo":
        return COLOR_ORGANO
    elif tipo == "inventario":
        return COLOR_INVENTARIO
    else:
        return COLOR_VUELTA


def drones_en_vuelo(vuelos, t):
    """
    Filtra vuelos activos en el instante t y devuelve un DataFrame
    con posiciones interpoladas listas para PyDeck.

    Incluye una ventana de persistencia: los drones que acaban de
    aterrizar (t_llegada < t <= t_llegada + MARGEN) se muestran en
    su destino con color 'recién llegado'.
    """
    filas = []

    for v in vuelos:
        # Caso 1: vuelo activo (en curso)
        if v["t_salida"] <= t <= v["t_llegada"]:
            lat, lon, prog = interpolar_posicion(v, t)
            c = color_dron(v)

            filas.append({
                "dron_id": v["dron_id"],
                "lat": lat,
                "lon": lon,
                "tipo_mision": v["tipo_mision"],
                "bateria": v["bateria"],
                "progreso": round(prog * 100, 1),
                "origen": v["origen"],
                "destino": v["destino"],
                "color": c,
            })

        # Caso 2: recién aterrizado (persistencia visual)
        elif v["t_llegada"] < t <= v["t_llegada"] + MARGEN_PERSISTENCIA_MIN:
            filas.append({
                "dron_id": v["dron_id"],
                "lat": v["lat_destino"],
                "lon": v["lon_destino"],
                "tipo_mision": "✓ " + v["tipo_mision"],
                "bateria": v["bateria"],
                "progreso": 100.0,
                "origen": v["origen"],
                "destino": v["destino"],
                "color": COLOR_RECIEN_LLEGADO,
            })

    return pd.DataFrame(filas)


def rutas_activas(vuelos, t):
    """
    Devuelve un DataFrame con los arcos de vuelos activos en el instante t.
    """
    filas = []

    for v in vuelos:
        if v["t_salida"] <= t <= v["t_llegada"]:
            c = color_dron(v)
            filas.append({
                "lat_origen": v["lat_origen"],
                "lon_origen": v["lon_origen"],
                "lat_destino": v["lat_destino"],
                "lon_destino": v["lon_destino"],
                "color": c,
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
# INICIALIZACIÓN DEL ESTADO DE REPRODUCCIÓN
# ---------------------------------------------------------------------------

if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "minuto_actual" not in st.session_state:
    st.session_state.minuto_actual = 0

if "velocidad_reproduccion" not in st.session_state:
    st.session_state.velocidad_reproduccion = 1

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
# SIDEBAR — CONFIGURACIÓN DE SIMULACIÓN
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Simulación")
    minutos_sim = st.slider(
        "Duración (minutos)", 60, 50000, 1440, step=60,
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
        "Escenario", ["normal", "severo", "despejado"], index=0,
    )

    st.subheader("Opciones")
    stock_umbral = st.checkbox("Stock inicial cerca del umbral", value=True)

    st.subheader("Reproducción")
    _opciones_paso = [1, 2]
    _paso_actual = st.session_state.velocidad_reproduccion
    if _paso_actual not in _opciones_paso:
        _paso_actual = 1
    paso_temporal = st.select_slider(
        "Paso temporal (min/frame)",
        options=_opciones_paso,
        value=_paso_actual,
        help="1 = máxima precisión, 2 = doble velocidad",
    )
    st.session_state.velocidad_reproduccion = paso_temporal

    retardo = st.slider(
        "Retardo entre frames (ms)", 30, 500, 80, 10,
        help="Menor valor = animación más rápida",
    )

    st.divider()

    ejecutar = st.button("🚀 Ejecutar Simulación", type="primary", use_container_width=True)

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

    with st.spinner("⏳ Ejecutando simulación DES..."):
        resultado = run_simulation(config)

    st.session_state["resultado"] = resultado
    st.session_state["minutos_sim"] = minutos_sim
    st.session_state.minuto_actual = 0
    st.session_state.is_playing = False
    st.success(
        f"✅ Simulación completada — "
        f"{resultado['pedidos_generados']} pedidos generados, "
        f"{resultado['pedidos_completados']} completados"
    )

# ---------------------------------------------------------------------------
# MÉTRICAS RESUMEN
# ---------------------------------------------------------------------------

resultado = st.session_state.get("resultado")

if resultado:
    cols = st.columns(6)

    metricas = [
        (resultado.get("pedidos_generados", 0), "Pedidos Generados"),
        (resultado.get("pedidos_completados", 0), "Completados"),
        (resultado.get("pedidos_rechazados", 0), "Rechazados"),
        (resultado.get("pedidos_en_cola", 0), "En Cola"),
        (f"{resultado.get('tasa_servicio', 0) * 100:.1f}%", "Tasa de Servicio"),
        (f"{resultado.get('tasa_exito_organos', 0) * 100:.1f}%", "Éxito Órganos"),
    ]

    for i, (valor, label) in enumerate(metricas):
        with cols[i]:
            st.markdown(
                f'<div class="metric-card"><h3>{valor}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# MAPA RADAR
# ---------------------------------------------------------------------------

df_hospitales, df_bases, df_aristas = preparar_datos_estaticos()
vuelos = cargar_telemetria()

# Timeline slider
max_minuto = st.session_state.get("minutos_sim", 1440)

if vuelos:
    max_t_vuelos = max(v["t_llegada"] for v in vuelos)
    max_minuto = max(max_minuto, int(math.ceil(max_t_vuelos)))

# Clampear el valor actual al rango válido
st.session_state.minuto_actual = min(st.session_state.minuto_actual, max_minuto)

# --- Controles de reproducción ---
col_play, col_pause, col_status = st.columns([1, 1, 4])

with col_play:
    if st.button("▶ Iniciar", use_container_width=True):
        st.session_state.is_playing = True
        st.rerun()

with col_pause:
    if st.button("⏸ Pausar", use_container_width=True):
        st.session_state.is_playing = False
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
    """Callback: si el usuario mueve el slider a mano, pausar la reproducción."""
    st.session_state.is_playing = False
    st.session_state.minuto_actual = st.session_state._slider_minuto


minuto_actual = st.slider(
    "⏱️ Minuto de simulación",
    min_value=0,
    max_value=max_minuto,
    value=st.session_state.minuto_actual,
    step=1,
    help="Arrastra para ver los drones en movimiento (pausa auto-play)",
    key="_slider_minuto",
    on_change=_on_slider_change,
)

# Leyenda
st.markdown("""
<div class="legend-box">
    <span class="legend-item"><span class="legend-dot" style="background:#00fa9a;"></span> Hospitales</span>
    <span class="legend-item"><span class="legend-dot" style="background:#00ff88;"></span> Base Noroeste</span>
    <span class="legend-item"><span class="legend-dot" style="background:#00cfff;"></span> Base Norte Capital</span>
    <span class="legend-item"><span class="legend-dot" style="background:#b478ff;"></span> Base Este Corredor</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ff9f00;"></span> Base Sur Fuenlabrada</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(150,150,150,0.5);"></span> Topología</span>
    <span class="legend-item" style="margin-left:0.5rem;">|</span>
    <span class="legend-item"><span class="legend-dot" style="background:#2ecc71;"></span> Inv.</span>
    <span class="legend-item"><span class="legend-dot" style="background:#e74c3c;"></span> Órg.</span>
    <span class="legend-item"><span class="legend-dot" style="background:#95a5a6;"></span> Vuelta</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ffff00;"></span> Bat. Baja</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(255,255,255,0.6);"></span> Aterrizó</span>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FUNCIÓN DE CONSTRUCCIÓN DEL MAPA (reutilizable en el bucle)
# ---------------------------------------------------------------------------

def construir_mapa(t):
    """
    Construye un pdk.Deck con capas apiladas que imitan la estética
    de Grafo/generar_mapa.py (dark-matter + topología coloreada).

    Orden de capas (de abajo a arriba):
    1. Cobertura de bases (círculos translucidos grandes)
    2. Aristas topológicas (líneas base → hospital)
    3. Nodos de hospitales (puntos verdes pequeños)
    4. Núcleos de bases (puntos medianos con su color)
    5. Etiquetas de bases
    6. Arcos de vuelos activos
    7. Drones en movimiento
    8. Etiquetas de drones

    Devuelve (mapa, df_drones, n_activos).
    """

    capas = []

    # --- 1. Cobertura de bases (zonas de influencia) ---
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

    # --- 2. Aristas topológicas (base → hospital) ---
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

    # --- 3. Nodos de hospitales ---
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

    # --- 4. Núcleos de bases ---
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

    # --- 5. Etiquetas de bases ---
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

    # --- 6–8. Drones dinámicos ---
    df_drones = pd.DataFrame()

    if vuelos:
        df_drones = drones_en_vuelo(vuelos, t)
        df_rutas = rutas_activas(vuelos, t)

        if not df_drones.empty:
            # 6. Arcos de vuelo activo
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

            # 7. Drones como puntos
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

            # 8. Etiquetas de drones
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
            "text": "{nombre}\n{nombre_hospital}\n{dron_id}\nMisión: {tipo_mision}\nBatería: {bateria}%\nProgreso: {progreso}%\n{origen} → {destino}\n{distancia_km} km"
        },
    )

    return mapa, df_drones, len(df_drones)


# ---------------------------------------------------------------------------
# PLACEHOLDERS para renderizado en sitio (sin st.rerun)
# ---------------------------------------------------------------------------

placeholder_mapa = st.empty()
placeholder_info = st.empty()
placeholder_tabla = st.empty()


def renderizar_frame(t):
    """Renderiza mapa + tabla para un instante t dentro de los placeholders."""
    mapa, df_d, n = construir_mapa(t)

    with placeholder_mapa:
        st.pydeck_chart(mapa, use_container_width=True, height=650)

    with placeholder_info:
        if n > 0:
            st.caption(f"🛫 **{n} dron(es) visibles** en t = {t}")
        else:
            st.caption(f"⏱️ t = {t} — Sin drones visibles")

    with placeholder_tabla:
        if not df_d.empty:
            st.dataframe(
                df_d[["dron_id", "tipo_mision", "origen", "destino", "bateria", "progreso"]].rename(
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


# ---------------------------------------------------------------------------
# RENDERIZADO INICIAL (modo manual / pausado)
# ---------------------------------------------------------------------------

if not st.session_state.is_playing:
    renderizar_frame(minuto_actual)

    if not vuelos:
        st.info("📡 Ejecuta una simulación desde la barra lateral para ver los drones en el radar.")

# ---------------------------------------------------------------------------
# MOTOR DE AUTO-REPRODUCCIÓN (bucle in-place, sin st.rerun)
# ---------------------------------------------------------------------------

if st.session_state.is_playing:
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

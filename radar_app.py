"""
FlyRadar - Visualizador de Drones Hospitalarios sobre Madrid
=============================================================
Aplicacion Streamlit + PyDeck que interpola la posicion de los
drones en cualquier minuto de la simulacion usando el log de
telemetria generado por main.py (Opcion 2: basada en eventos).

Ejecutar con:
    streamlit run radar_app.py
"""

import json
import math
import time
import streamlit as st
import pydeck as pdk
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# CONFIGURACION DE PAGINA
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FlyRadar · Drones Hospitalarios Madrid",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS PREMIUM DARK MODE
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap');

    /* Global dark theme */
    .stApp {
        background: linear-gradient(135deg, #0a0e17 0%, #111827 50%, #0f172a 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #1e293b 100%) !important;
        border-right: 1px solid rgba(56, 189, 248, 0.15);
    }

    /* Header banner */
    .radar-header {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
    }
    .radar-header h1 {
        background: linear-gradient(135deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.2rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .radar-header p {
        color: #94a3b8;
        font-size: 0.95rem;
        margin: 6px 0 0 0;
    }

    /* Metric cards */
    .metric-row {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
    }
    .metric-card {
        flex: 1;
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.12);
        border-radius: 12px;
        padding: 16px 20px;
        backdrop-filter: blur(8px);
        text-align: center;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card .label {
        color: #64748b;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 4px;
    }

    /* Legend */
    .legend-container {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(56, 189, 248, 0.12);
        border-radius: 10px;
        padding: 14px 18px;
        margin-top: 16px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 6px 0;
        color: #cbd5e1;
        font-size: 0.85rem;
    }
    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px currentColor;
    }

    /* Slider customization */
    .stSlider > div > div > div > div {
        background: linear-gradient(90deg, #38bdf8, #818cf8) !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# UTILIDADES DE INTERPOLACION
# ─────────────────────────────────────────────────────────────

def interpolar_posicion(origen_lat, origen_lon, destino_lat, destino_lon, progreso):
    """
    Interpolación lineal entre dos coordenadas.

    progreso: float entre 0.0 (en origen) y 1.0 (en destino).
    """
    progreso = max(0.0, min(1.0, progreso))
    lat = origen_lat + (destino_lat - origen_lat) * progreso
    lon = origen_lon + (destino_lon - origen_lon) * progreso
    return lat, lon


def interpolar_bateria(bateria_inicial, progreso, tipo_trayecto):
    """
    Estima la batería interpolada basada en el progreso del vuelo.
    Heurística: un tramo de ida consume ~15% y uno de vuelta ~10%.
    """
    consumo_estimado = 15.0 if tipo_trayecto == "ida" else 10.0
    return bateria_inicial - (consumo_estimado * progreso)


def calcular_angulo(origen_lat, origen_lon, destino_lat, destino_lon):
    """Calcula el ángulo de rumbo (bearing) en grados."""
    d_lon = math.radians(destino_lon - origen_lon)
    lat1 = math.radians(origen_lat)
    lat2 = math.radians(destino_lat)
    x = math.sin(d_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# Climas adversos que activan el color amarillo
CLIMAS_ADVERSOS = {"lluvia_fuerte", "viento_fuerte", "viento_normal", "lluvia_normal"}
UMBRAL_BATERIA_BAJA = 35.0


def determinar_color_dron(bateria_actual, clima):
    """
    Color del dron según estado:
      - Rojo si batería < 35%
      - Amarillo si clima adverso
      - Cian (color radar) si todo normal
    """
    if bateria_actual < UMBRAL_BATERIA_BAJA:
        return [255, 60, 60, 230]      # Rojo
    if clima in CLIMAS_ADVERSOS:
        return [255, 200, 40, 230]     # Amarillo
    return [56, 189, 248, 240]         # Cian


def color_estela(tipo_trayecto):
    """Color de la estela de ruta."""
    if tipo_trayecto == "ida":
        return [56, 189, 248, 100]     # Cian translúcido
    return [139, 92, 246, 100]         # Púrpura translúcido


def minuto_a_hora(minuto):
    """Convierte un minuto (0-1440) a formato HH:MM."""
    h = int(minuto // 60) % 24
    m = int(minuto % 60)
    return f"{h:02d}:{m:02d}"


# ─────────────────────────────────────────────────────────────
# DATOS: Nodos estáticos (hospitales y bases)
# ─────────────────────────────────────────────────────────────

NODOS_ESTATICOS = [
    # Hospitales
    {"nombre": "La Paz",             "lat": 40.4733, "lon": -3.6899, "tipo": "hospital"},
    {"nombre": "Gregorio Marañón",   "lat": 40.4095, "lon": -3.6829, "tipo": "hospital"},
    {"nombre": "San Carlos",         "lat": 40.4427, "lon": -3.7186, "tipo": "hospital"},
    {"nombre": "12 de Octubre",      "lat": 40.3839, "lon": -3.6911, "tipo": "hospital"},
    {"nombre": "Ramón y Cajal",      "lat": 40.4724, "lon": -3.6482, "tipo": "hospital"},
    {"nombre": "La Princesa",        "lat": 40.4265, "lon": -3.6908, "tipo": "hospital"},
    {"nombre": "Jiménez Díaz",       "lat": 40.4353, "lon": -3.7236, "tipo": "hospital"},
    {"nombre": "Cruz Roja",          "lat": 40.4539, "lon": -3.7054, "tipo": "hospital"},
    # Bases
    {"nombre": "BASE NORTE",         "lat": 40.4636, "lon": -3.7012, "tipo": "base"},
    {"nombre": "BASE CENTRO",        "lat": 40.4382, "lon": -3.7155, "tipo": "base"},
    {"nombre": "BASE SUR",           "lat": 40.3968, "lon": -3.6985, "tipo": "base"},
]


# ─────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────

@st.cache_data
def cargar_telemetria():
    """Carga el archivo de telemetría generado por la simulación."""
    ruta = Path("telemetria_vuelos.json")
    if not ruta.exists():
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# LOGICA PRINCIPAL DE LA APP
# ─────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown("""
    <div class="radar-header">
        <h1>🛩️ FlyRadar</h1>
        <p>Visualización en tiempo real de la red de drones hospitalarios · Madrid</p>
    </div>
    """, unsafe_allow_html=True)

    # Cargar datos
    datos = cargar_telemetria()

    if datos is None:
        st.error(
            "⚠️ No se encontró `telemetria_vuelos.json`. "
            "Ejecuta primero `python main.py` para generar los datos de la simulación."
        )
        st.info("💡 Después de ejecutar la simulación, recarga esta página.")
        return

    total_tramos = len(datos)

    # Detectar duración máxima
    max_minuto = max(t["t_llegada"] for t in datos) if datos else 1440
    max_minuto = int(math.ceil(max_minuto))

    # ─── SIDEBAR ──────────────────────────────────────────────

    # Inicializar estado de reproducción
    if "playing" not in st.session_state:
        st.session_state.playing = False
    if "minuto" not in st.session_state:
        st.session_state.minuto = 0

    # Calcular minutos con actividad (para el botón "Saltar")
    minutos_con_vuelo = sorted(set(
        m for t in datos
        for m in range(int(t["t_salida"]), int(t["t_llegada"]) + 1)
    ))

    with st.sidebar:
        st.markdown("### ⏱️ Control de Tiempo")

        # Si el usuario mueve el slider manualmente, sincronizamos
        minuto_slider = st.slider(
            "Minuto de simulación",
            min_value=0,
            max_value=max_minuto,
            value=st.session_state.minuto,
            step=1,
            format="%d",
            help="Desplaza para ver la posición de los drones en cada minuto",
            key="slider_minuto",
        )
        # Sincronizar: si el slider cambia, actualizamos el estado
        if minuto_slider != st.session_state.minuto:
            st.session_state.minuto = minuto_slider

        minuto_actual = st.session_state.minuto
        st.markdown(f"**🕐 Hora simulada:** `{minuto_a_hora(minuto_actual)}`")

        st.markdown("---")

        # Auto-play controles
        st.markdown("### 🎬 Reproducción")

        col_play, col_stop, col_skip = st.columns(3)
        with col_play:
            if st.button(
                "⏸️ Pausa" if st.session_state.playing else "▶️ Play",
                use_container_width=True,
                type="primary" if not st.session_state.playing else "secondary",
            ):
                st.session_state.playing = not st.session_state.playing
                st.rerun()

        with col_stop:
            if st.button("⏹️ Reset", use_container_width=True):
                st.session_state.playing = False
                st.session_state.minuto = 0
                st.rerun()

        with col_skip:
            if st.button("⏭️ Saltar", use_container_width=True, help="Ir al siguiente vuelo"):
                # Buscar el próximo minuto con actividad
                siguiente = None
                for m in minutos_con_vuelo:
                    if m > minuto_actual:
                        siguiente = m
                        break
                if siguiente is not None:
                    st.session_state.minuto = siguiente
                    st.rerun()

        velocidad = st.select_slider(
            "Velocidad",
            options=[1, 2, 5, 10, 30, 60],
            value=5,
            format_func=lambda x: f"x{x}"
        )

        if st.session_state.playing:
            st.success("🔴 Reproduciendo...")
        else:
            st.info("⏸️ En pausa")

        st.markdown("---")
        st.markdown("### 📊 Estadísticas")
        st.metric("Total tramos", f"{total_tramos}")

        # Contar tramos activos en este minuto
        vuelos_activos = [
            t for t in datos
            if t["t_salida"] <= minuto_actual <= t["t_llegada"]
        ]
        drones_en_vuelo = len(set(v["id_dron"] for v in vuelos_activos))
        tramos_ida = sum(1 for v in vuelos_activos if v["tipo_trayecto"] == "ida")
        tramos_vuelta = sum(1 for v in vuelos_activos if v["tipo_trayecto"] == "vuelta")

        st.metric("Drones en vuelo", f"{drones_en_vuelo}")
        st.metric("Entregas activas", f"{tramos_ida}")
        st.metric("Retornos activos", f"{tramos_vuelta}")

        # Leyenda
        st.markdown("""
        <div class="legend-container">
            <div style="color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; 
                        letter-spacing: 1px; margin-bottom: 8px; font-weight: 600;">Leyenda</div>
            <div class="legend-item">
                <span class="legend-dot" style="background: #38bdf8; color: #38bdf8;"></span>
                Dron en vuelo normal
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background: #ffc828; color: #ffc828;"></span>
                Clima adverso
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background: #ff3c3c; color: #ff3c3c;"></span>
                Batería baja (&lt;35%)
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background: #34d399; color: #34d399;"></span>
                Hospital
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background: #c084fc; color: #c084fc;"></span>
                Base de drones
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ─── METRICAS TOP ────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{minuto_a_hora(minuto_actual)}</div>
            <div class="label">Hora Simulada</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{drones_en_vuelo}</div>
            <div class="label">Drones en Vuelo</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{tramos_ida}</div>
            <div class="label">Entregas Activas</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{tramos_vuelta}</div>
            <div class="label">Retornos Activos</div>
        </div>""", unsafe_allow_html=True)

    # ─── CALCULAR POSICIONES DE DRONES ────────────────────────
    posiciones_drones = []
    estelas = []

    for tramo in datos:
        t_sal = tramo["t_salida"]
        t_lle = tramo["t_llegada"]

        # Solo tramos activos en este minuto
        if not (t_sal <= minuto_actual <= t_lle):
            continue

        duracion = t_lle - t_sal
        if duracion <= 0:
            continue

        progreso = (minuto_actual - t_sal) / duracion

        o = tramo["origen"]
        d = tramo["destino"]

        lat, lon = interpolar_posicion(o["lat"], o["lon"], d["lat"], d["lon"], progreso)
        bat_actual = interpolar_bateria(tramo["bateria_inicial"], progreso, tramo["tipo_trayecto"])
        color = determinar_color_dron(bat_actual, tramo["clima"])
        angulo = calcular_angulo(o["lat"], o["lon"], d["lat"], d["lon"])

        posiciones_drones.append({
            "lat": lat,
            "lon": lon,
            "id_dron": tramo["id_dron"],
            "color": color,
            "angulo": angulo,
            "bateria": round(bat_actual, 1),
            "tipo": tramo["tipo_trayecto"],
            "clima": tramo["clima"],
            "destino": d["nombre"],
        })

        # Estela: línea desde la posición actual hasta el destino
        col_estela = color_estela(tramo["tipo_trayecto"])
        estelas.append({
            "origen_lat": lat,
            "origen_lon": lon,
            "destino_lat": d["lat"],
            "destino_lon": d["lon"],
            "color": col_estela,
        })

    # ─── CONSTRUIR CAPAS PYDECK ──────────────────────────────

    # Capa 1: Nodos estáticos (Hospitales + Bases)
    df_nodos = pd.DataFrame(NODOS_ESTATICOS)
    df_nodos["color"] = df_nodos["tipo"].apply(
        lambda t: [52, 211, 153, 200] if t == "hospital" else [192, 132, 252, 200]
    )
    df_nodos["size"] = df_nodos["tipo"].apply(lambda t: 280 if t == "hospital" else 350)

    capa_nodos = pdk.Layer(
        "ScatterplotLayer",
        data=df_nodos,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius="size",
        pickable=True,
        opacity=0.85,
        stroked=True,
        get_line_color=[255, 255, 255, 60],
        line_width_min_pixels=1,
    )

    # Capa 2: Etiquetas de nodos
    capa_textos = pdk.Layer(
        "TextLayer",
        data=df_nodos,
        get_position=["lon", "lat"],
        get_text="nombre",
        get_size=13,
        get_color=[203, 213, 225, 200],
        get_angle=0,
        get_text_anchor="'middle'",
        get_alignment_baseline="'top'",
        get_pixel_offset=[0, 18],
    )

    capas = [capa_nodos, capa_textos]

    # Capa 3: Estelas (rutas activas)
    if estelas:
        df_estelas = pd.DataFrame(estelas)
        capa_estelas = pdk.Layer(
            "LineLayer",
            data=df_estelas,
            get_source_position=["origen_lon", "origen_lat"],
            get_target_position=["destino_lon", "destino_lat"],
            get_color="color",
            get_width=2,
            pickable=False,
        )
        capas.append(capa_estelas)

    # Capa 4: Drones en vuelo (puntos brillantes)
    if posiciones_drones:
        df_drones = pd.DataFrame(posiciones_drones)
        capa_drones = pdk.Layer(
            "ScatterplotLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=180,
            pickable=True,
            opacity=1.0,
            stroked=True,
            get_line_color=[255, 255, 255, 180],
            line_width_min_pixels=2,
            radius_min_pixels=6,
            radius_max_pixels=14,
        )
        capas.append(capa_drones)

        # Capa 5: Etiquetas de drones
        capa_labels_drones = pdk.Layer(
            "TextLayer",
            data=df_drones,
            get_position=["lon", "lat"],
            get_text="id_dron",
            get_size=12,
            get_color=[255, 255, 255, 220],
            get_angle=0,
            get_text_anchor="'middle'",
            get_alignment_baseline="'bottom'",
            get_pixel_offset=[0, -14],
            font_family="'Inter', sans-serif",
        )
        capas.append(capa_labels_drones)

    # ─── VISTA DEL MAPA ─────────────────────────────────────
    vista = pdk.ViewState(
        latitude=40.4350,
        longitude=-3.7000,
        zoom=12.5,
        pitch=45,
        bearing=0,
    )

    mapa = pdk.Deck(
        layers=capas,
        initial_view_state=vista,
        map_style="mapbox://styles/mapbox/dark-v11",
        tooltip={
            "html": """
                <div style="
                    background: rgba(15, 23, 42, 0.95);
                    padding: 12px 16px;
                    border-radius: 10px;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    font-family: 'Inter', sans-serif;
                    min-width: 180px;
                ">
                    <div style="
                        font-size: 14px;
                        font-weight: 700;
                        color: #38bdf8;
                        margin-bottom: 6px;
                    ">{id_dron} {nombre}</div>
                    <div style="color: #94a3b8; font-size: 12px;">
                        🔋 Batería: <b style="color: #e2e8f0;">{bateria}%</b><br/>
                        📍 Destino: <b style="color: #e2e8f0;">{destino}</b><br/>
                        ✈️ Tipo: <b style="color: #e2e8f0;">{tipo}</b><br/>
                        🌤️ Clima: <b style="color: #e2e8f0;">{clima}</b>
                    </div>
                </div>
            """,
            "style": {
                "backgroundColor": "transparent",
                "border": "none",
            }
        }
    )

    st.pydeck_chart(mapa, width='stretch')

    # ─── TABLA DE VUELOS ACTIVOS ─────────────────────────────
    if posiciones_drones:
        st.markdown("### 📋 Vuelos Activos")
        df_tabla = pd.DataFrame(posiciones_drones)[
            ["id_dron", "tipo", "destino", "bateria", "clima"]
        ].rename(columns={
            "id_dron": "Dron",
            "tipo": "Trayecto",
            "destino": "Destino",
            "bateria": "Batería %",
            "clima": "Clima",
        })
        st.dataframe(
            df_tabla,
            width='stretch',
            hide_index=True,
        )
    else:
        st.info(f"🛬 No hay drones en vuelo en el minuto {minuto_actual} ({minuto_a_hora(minuto_actual)})")

    # ─── AUTO-PLAY: avanzar automáticamente ──────────────────
    if st.session_state.playing:
        if st.session_state.minuto < max_minuto:
            # Pausa según velocidad: x1 = 1s, x5 = 0.2s, x60 = 0.016s
            time.sleep(1.0 / velocidad)
            st.session_state.minuto += 1
            st.rerun()
        else:
            # Llegamos al final, paramos
            st.session_state.playing = False
            st.rerun()


if __name__ == "__main__":
    main()

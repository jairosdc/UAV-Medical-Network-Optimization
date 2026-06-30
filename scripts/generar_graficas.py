# generar_graficas.py
# ============================================================
# Gráficas finales limpias para presentación
# Red sanitaria de drones
# ============================================================

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import argparse
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# CONFIGURACIÓN
# ============================================================

DPI = 300
UMBRAL_P95_INVENTARIO = 300  # Minutos umbral para inventario

COLORES_ESCENARIO = {
    "Base": "#2CA02C",
    "Moderado": "#1F77B4",
    "Alto": "#FF9F1C",
    "Muy alto": "#D62728",
}

COLOR_A_TIEMPO = "#2CA02C"
COLOR_FALLO = "#D62728"
COLOR_PENDIENTE = "#FF9F1C"
COLOR_BASE = "#1F77B4"
COLOR_HOSPITAL = "#7B2CBF"
COLOR_GRIS = "#6C757D"
COLOR_NAVY = "#0B1F33"
COLOR_GRID = "#DDE3EA"

ORGANOS = {
    "corazon", "corazón",
    "pulmon", "pulmón",
    "rinon", "riñón",
    "pancreas", "páncreas",
    "higado", "hígado",
}


# ============================================================
# ESTILO
# ============================================================

def configurar_estilo():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": COLOR_NAVY,
        "axes.labelcolor": COLOR_NAVY,
        "axes.titlecolor": COLOR_NAVY,
        "xtick.color": COLOR_NAVY,
        "ytick.color": COLOR_NAVY,
        "text.color": COLOR_NAVY,
        "font.size": 11,
        "axes.titlesize": 17,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
        "axes.grid": True,
        "grid.color": COLOR_GRID,
        "grid.linestyle": "-",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


# ============================================================
# UTILIDADES
# ============================================================

def normalizar(x) -> str:
    if x is None:
        return ""
    x = str(x).strip()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(c for c in x if not unicodedata.combining(c))
    x = x.lower()
    x = re.sub(r"[^a-z0-9]+", "_", x)
    return x.strip("_")


def obtener_columna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    if df is None or df.empty:
        return None

    mapa = {normalizar(c): c for c in df.columns}

    for candidato in candidatos:
        c = normalizar(candidato)
        if c in mapa:
            return mapa[c]

    for candidato in candidatos:
        c = normalizar(candidato)
        for col_norm, col_real in mapa.items():
            if c in col_norm or col_norm in c:
                return col_real

    return None


def escenario_pretty(x) -> str:
    s = normalizar(x)

    if "muy" in s and "alto" in s:
        return "Muy alto"
    if "base" in s or "normal" in s:
        return "Base"
    if "moderado" in s or "medio" in s:
        return "Moderado"
    if "alto" in s:
        return "Alto"

    return str(x)


def ordenar_escenarios(df: pd.DataFrame) -> pd.DataFrame:
    if "escenario" not in df.columns:
        return df

    orden = {"Base": 0, "Moderado": 1, "Alto": 2, "Muy alto": 3}
    df = df.copy()
    df["_orden"] = df["escenario"].map(orden).fillna(99)
    df = df.sort_values("_orden").drop(columns="_orden")
    return df


def color_escenario(e):
    return COLORES_ESCENARIO.get(e, "#1F77B4")


def leer_csv(path: Path) -> pd.DataFrame:
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path)


def cargar_tabla_montecarlo(input_path: Path) -> pd.DataFrame:
    """
    Carga el archivo unificado de salida de Monte Carlo (tabla_montecarlo.csv).
    Soporta rutas directas al archivo o directorios donde buscarlo.
    """
    if input_path.is_file():
        path = input_path
    else:
        candidatos = list(input_path.glob("**/tabla_montecarlo.csv"))
        if not candidatos:
            candidatos = list(input_path.glob("**/tabla_montecarlo*.csv"))
        if not candidatos:
            raise FileNotFoundError(f"No se encontró tabla_montecarlo.csv en {input_path}")
        path = candidatos[0]

    print(f"Leyendo archivo unificado: {path}")
    return leer_csv(path)


def guardar(fig, output_dir: Path, nombre: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / nombre
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {path}")


# ============================================================
# RESÚMENES
# ============================================================

def resumen_escenarios(df_sim: pd.DataFrame) -> pd.DataFrame:
    df = df_sim.copy()

    c_esc = obtener_columna(df, ["escenario_etiqueta", "escenario"])
    c_gen = obtener_columna(df, ["pedidos_generados", "total_pedidos"])
    c_comp = obtener_columna(df, ["pedidos_completados"])
    c_p95 = obtener_columna(df, ["inventario_tiempo_p95_min", "p95_inventario"])
    c_p99 = obtener_columna(df, ["inventario_tiempo_p99_min", "p99_inventario"])
    c_cola_media = obtener_columna(df, ["cola_media", "longitud_media_cola"])
    c_cola_max = obtener_columna(df, ["cola_maxima", "longitud_maxima_cola"])
    c_org_total = obtener_columna(df, ["organos_totales"])
    c_org_ok = obtener_columna(df, ["organos_a_tiempo", "organos_on_time"])
    c_org_late = obtener_columna(df, ["organos_fuera_isquemia", "organos_late"])
    c_org_pend = obtener_columna(df, ["organos_pendientes"])
    c_min = obtener_columna(df, ["minutos_simulacion"])
    c_sim = obtener_columna(df, ["simulacion", "run"])

    if c_esc is None:
        raise ValueError("No encuentro columna de escenario en la tabla.")

    df["escenario"] = df[c_esc].apply(escenario_pretty)

    def num(c):
        if c is None:
            return pd.Series(0.0, index=df.index)
        return pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["_gen"] = num(c_gen)
    df["_comp"] = num(c_comp)
    df["_p95"] = num(c_p95)
    df["_p99"] = num(c_p99)
    df["_cola_media"] = num(c_cola_media)
    df["_cola_max"] = num(c_cola_max)
    df["_org_total"] = num(c_org_total)
    df["_org_ok"] = num(c_org_ok)
    df["_org_late"] = num(c_org_late)
    df["_org_pend"] = num(c_org_pend)
    df["_minutos"] = num(c_min)

    rows = []

    for esc, g in df.groupby("escenario"):
        gen = g["_gen"].sum()
        comp = g["_comp"].sum()
        org_total = g["_org_total"].sum()
        org_ok = g["_org_ok"].sum()
        org_late = g["_org_late"].sum()
        org_pend = g["_org_pend"].sum()

        n_sims = g[c_sim].nunique() if c_sim else len(g)

        rows.append({
            "escenario": esc,
            "simulaciones": n_sims,
            "minutos_simulacion": g["_minutos"].max(),
            "pedidos_generados": gen,
            "pedidos_completados": comp,
            "tasa_servicio_pct": comp / gen * 100 if gen > 0 else np.nan,
            "p95_inventario_medio": g["_p95"].mean(),
            "p95_inventario_peor": g["_p95"].max(),
            "p99_inventario_medio": g["_p99"].mean(),
            "cola_media": g["_cola_media"].mean(),
            "cola_maxima": g["_cola_max"].max(),
            "organos_totales": org_total,
            "organos_a_tiempo": org_ok,
            "organos_fuera_isquemia": org_late,
            "organos_pendientes": org_pend,
            "exito_clinico_pct": org_ok / org_total * 100 if org_total > 0 else np.nan,
        })

    return ordenar_escenarios(pd.DataFrame(rows))


def resumen_organos_desde_rutas(df_rutas: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa los datos de rutas con incidencias a nivel clínico.
    """
    if df_rutas.empty:
        return pd.DataFrame()

    df = df_rutas.copy()
    c_ruta = obtener_columna(df, ["ruta"])
    c_incidencias = obtener_columna(df, ["incidencias_ruta", "incidencias"])
    c_totales = obtener_columna(df, ["organos_totales_ruta", "organos_totales"])
    c_tiempo = obtener_columna(df, ["tiempo_medio_ruta_min", "tiempo_medio"])

    if not c_ruta:
        return pd.DataFrame()

    def num(c):
        if c is None:
            return pd.Series(0.0, index=df.index)
        return pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["incidencias"] = num(c_incidencias)
    df["totales"] = num(c_totales)
    df["tiempo_medio_min"] = num(c_tiempo)

    rutas = (
        df.groupby(c_ruta)
        .agg(
            organos_totales=("totales", "sum"),
            organos_fuera_isquemia=("incidencias", "sum"),
            tiempo_medio_min=("tiempo_medio_min", "mean"),
        )
        .reset_index()
    )

    # Renombramos la columna agrupada a "ruta"
    rutas.rename(columns={c_ruta: "ruta"}, inplace=True)
    rutas["incidencias"] = rutas["organos_fuera_isquemia"]
    rutas = rutas.sort_values(["incidencias", "organos_totales"], ascending=False)
    return rutas


def resumen_utilizacion_drones(df_drones: pd.DataFrame, df_sim: pd.DataFrame) -> pd.DataFrame:
    if df_drones.empty:
        return pd.DataFrame()

    df = df_drones.copy()

    c_esc = obtener_columna(df, ["escenario_etiqueta", "escenario"])
    c_sim = obtener_columna(df, ["simulacion", "run"])
    c_dron = obtener_columna(df, ["drone_id", "id_dron", "dron"])
    c_role = obtener_columna(df, ["role", "rol"])
    c_vuelo = obtener_columna(df, ["flight_minutes", "flight_time"])
    c_recarga = obtener_columna(df, ["charging_minutes", "charging_time"])

    if not all([c_esc, c_dron, c_role]):
        print("[AVISO] No se puede calcular utilización de drones: faltan columnas clave.")
        return pd.DataFrame()

    df["escenario"] = df[c_esc].apply(escenario_pretty)
    df["simulacion"] = df[c_sim].astype(str) if c_sim else "sim_1"
    df["drone_id"] = df[c_dron].astype(str)

    role_norm = df[c_role].astype(str).map(normalizar)
    df["tipo_dron"] = np.where(role_norm.str.contains("hospital"), "Hospitalarios", "Base")

    df["vuelo_min"] = pd.to_numeric(df[c_vuelo], errors="coerce").fillna(0.0) if c_vuelo else 0.0
    df["recarga_min"] = pd.to_numeric(df[c_recarga], errors="coerce").fillna(0.0) if c_recarga else 0.0

    # Duración por simulación
    duracion_default = 20160
    if not df_sim.empty:
        c_min = obtener_columna(df_sim, ["minutos_simulacion"])
        if c_min:
            duracion_default = pd.to_numeric(df_sim[c_min], errors="coerce").max()
            if pd.isna(duracion_default):
                duracion_default = 20160

    por_dron = (
        df.groupby(["escenario", "simulacion", "drone_id", "tipo_dron"], as_index=False)
        .agg(
            vuelo_min=("vuelo_min", "max"),
            recarga_min=("recarga_min", "max"),
        )
    )

    por_dron["tiempo_disponible_min"] = duracion_default
    por_dron["operativo_min"] = por_dron["vuelo_min"] + por_dron["recarga_min"]

    resumen = (
        por_dron.groupby(["escenario", "tipo_dron"], as_index=False)
        .agg(
            drones_simulacion=("drone_id", "count"),
            vuelo_min=("vuelo_min", "sum"),
            recarga_min=("recarga_min", "sum"),
            operativo_min=("operativo_min", "sum"),
            tiempo_disponible_min=("tiempo_disponible_min", "sum"),
        )
    )

    resumen["utilizacion_vuelo_pct"] = (
        resumen["vuelo_min"] / resumen["tiempo_disponible_min"] * 100
    )
    resumen["utilizacion_operativa_pct"] = (
        resumen["operativo_min"] / resumen["tiempo_disponible_min"] * 100
    )

    return ordenar_escenarios(resumen)


def preparar_cola(df_cola: pd.DataFrame) -> pd.DataFrame:
    if df_cola.empty:
        return pd.DataFrame()

    df = df_cola.copy()

    c_esc = obtener_columna(df, ["escenario_etiqueta", "escenario"])
    c_sim = obtener_columna(df, ["simulacion", "run"])
    c_min = obtener_columna(df, ["minuto"])
    c_cola = obtener_columna(df, ["longitud_cola"])

    if not all([c_esc, c_min, c_cola]):
        return pd.DataFrame()

    df["escenario"] = df[c_esc].apply(escenario_pretty)
    df["minuto"] = pd.to_numeric(df[c_min], errors="coerce")
    df["cola"] = pd.to_numeric(df[c_cola], errors="coerce")
    df["simulacion"] = df[c_sim].astype(str) if c_sim else "sim_1"

    df["dia"] = df["minuto"] / 1440
    df["bloque_dia"] = (df["dia"] * 2).round() / 2  # cada medio día

    tmp = (
        df.groupby(["escenario", "simulacion", "bloque_dia"], as_index=False)
        .agg(cola=("cola", "mean"))
    )

    out = (
        tmp.groupby(["escenario", "bloque_dia"], as_index=False)
        .agg(
            cola_media=("cola", "mean"),
            cola_p10=("cola", lambda x: x.quantile(0.10)),
            cola_p90=("cola", lambda x: x.quantile(0.90)),
        )
    )

    return ordenar_escenarios(out)


# ============================================================
# GRÁFICAS
# ============================================================

def grafica_servicio(summary: pd.DataFrame, out: Path):
    df = ordenar_escenarios(summary)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    colores = [color_escenario(e) for e in df["escenario"]]

    bars = ax.bar(df["escenario"], df["tasa_servicio_pct"], color=colores, width=0.6)

    ax.set_title("Nivel de servicio global", fontweight="bold", pad=15)
    ax.set_ylabel("Pedidos completados (%)")
    
    ylim_min = min(98.0, df["tasa_servicio_pct"].min() - 0.5)
    ax.set_ylim(max(0, ylim_min), 100.15)

    ax.axhline(99.0, color=COLOR_GRIS, linestyle="--", linewidth=1.2)

    for bar, val in zip(bars, df["tasa_servicio_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.05,
            f"{val:.2f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    guardar(fig, out, "01_nivel_servicio_global.png")


def grafica_p95_inventario(summary: pd.DataFrame, out: Path):
    df = ordenar_escenarios(summary)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    colores = [color_escenario(e) for e in df["escenario"]]

    bars = ax.bar(df["escenario"], df["p95_inventario_medio"], color=colores, width=0.6)

    ax.scatter(
        df["escenario"],
        df["p95_inventario_peor"],
        color=COLOR_NAVY,
        s=70,
        label="Peor P95 observado",
        zorder=4,
    )

    ax.axhline(
        UMBRAL_P95_INVENTARIO,
        color=COLOR_FALLO,
        linestyle="--",
        linewidth=2,
        label=f"Umbral {UMBRAL_P95_INVENTARIO} min",
    )

    ax.set_title("P95 de entrega de inventario", fontweight="bold", pad=15)
    ax.set_ylabel("Minutos")
    
    peor_val = df["p95_inventario_peor"].max()
    ax.set_ylim(0, max(UMBRAL_P95_INVENTARIO + 50, peor_val * 1.15 if peor_val else 100))
    ax.legend()

    for bar, val in zip(bars, df["p95_inventario_medio"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 10,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    guardar(fig, out, "02_p95_inventario.png")


def grafica_organos(organos: pd.DataFrame, out: Path):
    df = ordenar_escenarios(organos)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    x = np.arange(len(df))

    ax.bar(
        x,
        df["organos_a_tiempo"],
        color=COLOR_A_TIEMPO,
        width=0.62,
        label="A tiempo",
    )

    ax.bar(
        x,
        df["organos_fuera_isquemia"],
        bottom=df["organos_a_tiempo"],
        color=COLOR_FALLO,
        width=0.62,
        label="Fuera de isquemia",
    )

    if "organos_pendientes" in df.columns:
        ax.bar(
            x,
            df["organos_pendientes"],
            bottom=df["organos_a_tiempo"] + df["organos_fuera_isquemia"],
            color=COLOR_PENDIENTE,
            width=0.62,
            label="Pendientes",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(df["escenario"])
    ax.set_title("Órganos transportados por escenario", fontweight="bold", pad=15)
    ax.set_ylabel("Número de órganos")
    ax.legend()

    for i, row in df.iterrows():
        total = row["organos_totales"]
        ax.text(
            i,
            total + max(0.5, total * 0.015),
            f"{int(total)}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    guardar(fig, out, "03_organos_por_escenario.png")


def grafica_exito_clinico(organos: pd.DataFrame, out: Path):
    df = ordenar_escenarios(organos)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    colores = [color_escenario(e) for e in df["escenario"]]

    bars = ax.bar(df["escenario"], df["exito_clinico_pct"], color=colores, width=0.6)

    ax.set_title("Éxito clínico en transporte de órganos", fontweight="bold", pad=15)
    ax.set_ylabel("Órganos a tiempo (%)")
    
    ylim_min = min(98.0, df["exito_clinico_pct"].min() - 0.5)
    ax.set_ylim(max(0, ylim_min), 100.15)

    ax.axhline(99.0, color=COLOR_GRIS, linestyle="--", linewidth=1.2)

    for bar, val in zip(bars, df["exito_clinico_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.05,
            f"{val:.2f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    guardar(fig, out, "04_exito_clinico_organos.png")


def grafica_colas(summary: pd.DataFrame, out: Path):
    df = ordenar_escenarios(summary)

    fig, ax = plt.subplots(figsize=(11, 6.5))

    ax.plot(
        df["escenario"],
        df["cola_media"],
        marker="o",
        linewidth=3,
        color=COLOR_BASE,
        label="Cola media",
    )

    ax.plot(
        df["escenario"],
        df["cola_maxima"],
        marker="s",
        linewidth=2.5,
        color=COLOR_PENDIENTE,
        label="Cola máxima",
    )

    ax.set_title("Cola de pedidos por escenario", fontweight="bold", pad=15)
    ax.set_ylabel("Pedidos en cola")
    ax.legend()

    # Añadir margen superior dinámico
    peor_cola = df["cola_maxima"].max()
    ax.set_ylim(0, peor_cola * 1.25 if peor_cola else 10)

    for x, y in zip(df["escenario"], df["cola_media"]):
        ax.text(x, y + (peor_cola * 0.02 if peor_cola else 0.2), f"{y:.1f}", ha="center", va="bottom", fontweight="bold")

    guardar(fig, out, "05_colas_por_escenario.png")


def grafica_evolucion_cola(cola: pd.DataFrame, out: Path):
    if cola.empty:
        return

    fig, ax = plt.subplots(figsize=(12, 6.5))

    for esc, g in cola.groupby("escenario"):
        g = g.sort_values("bloque_dia")
        color = color_escenario(esc)

        ax.plot(
            g["bloque_dia"],
            g["cola_media"],
            linewidth=2.5,
            color=color,
            label=esc,
        )

        ax.fill_between(
            g["bloque_dia"],
            g["cola_p10"],
            g["cola_p90"],
            color=color,
            alpha=0.13,
        )

    ax.set_title("Evolución de la cola durante la simulación", fontweight="bold", pad=15)
    ax.set_xlabel("Día")
    ax.set_ylabel("Pedidos en cola")
    ax.legend()

    guardar(fig, out, "06_evolucion_cola.png")


def grafica_utilizacion(util: pd.DataFrame, out: Path):
    if util.empty:
        return

    df = ordenar_escenarios(util)

    pivot = df.pivot_table(
        index="escenario",
        columns="tipo_dron",
        values="utilizacion_operativa_pct",
        aggfunc="mean",
    )

    orden = [e for e in ["Base", "Moderado", "Alto", "Muy alto"] if e in pivot.index]
    pivot = pivot.loc[orden]

    fig, ax = plt.subplots(figsize=(11, 6.5))

    x = np.arange(len(pivot.index))
    width = 0.36

    bars1, bars2 = [], []

    if "Base" in pivot.columns:
        bars1 = ax.bar(
            x - width / 2,
            pivot["Base"],
            width,
            color=COLOR_BASE,
            label="Drones de base",
        )

    if "Hospitalarios" in pivot.columns:
        bars2 = ax.bar(
            x + width / 2,
            pivot["Hospitalarios"],
            width,
            color=COLOR_HOSPITAL,
            label="Drones hospitalarios",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_title("Utilización operativa de la flota", fontweight="bold", pad=15)
    ax.set_ylabel("Tiempo en vuelo o recarga (%)")
    ax.legend()

    for bars in [bars1, bars2]:
        for bar in bars:
            val = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val + 0.5,
                f"{val:.1f}%",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=9,
            )

    ymax = max(10.0, np.nanmax(pivot.values) * 1.25 if pivot.size else 10.0)
    ax.set_ylim(0, ymax)

    guardar(fig, out, "07_utilizacion_flota.png")


def grafica_tiempos_organos(df_rutas: pd.DataFrame, out: Path):
    """
    Muestra la distribución de tiempos de transporte de órganos usando
    el promedio de tiempo por ruta y simulación de la tabla de rutas.
    """
    if df_rutas.empty:
        return

    df = df_rutas.copy()

    c_esc = obtener_columna(df, ["escenario_etiqueta", "escenario"])
    c_t = obtener_columna(df, ["tiempo_medio_ruta_min", "tiempo_medio"])

    if not all([c_esc, c_t]):
        return

    df["escenario"] = df[c_esc].apply(escenario_pretty)
    df["tiempo_total_min"] = pd.to_numeric(df[c_t], errors="coerce")
    df = df[df["tiempo_total_min"].notna() & (df["tiempo_total_min"] >= 0)]

    if df.empty:
        return

    escenarios = [e for e in ["Base", "Moderado", "Alto", "Muy alto"] if e in df["escenario"].unique()]
    datos = [df.loc[df["escenario"] == e, "tiempo_total_min"] for e in escenarios]

    fig, ax = plt.subplots(figsize=(11, 6.5))

    bp = ax.boxplot(
        datos,
        patch_artist=True,
        showfliers=False,
        widths=0.55,
    )
    ax.set_xticks(range(1, len(escenarios) + 1))
    ax.set_xticklabels(escenarios)

    for patch, esc in zip(bp["boxes"], escenarios):
        patch.set_facecolor(color_escenario(esc))
        patch.set_alpha(0.75)

    for median in bp["medians"]:
        median.set_color("white")
        median.set_linewidth(2.5)

    ax.set_title("Tiempo medio de transporte de órganos por ruta", fontweight="bold", pad=15)
    ax.set_ylabel("Minutos de vuelo")

    guardar(fig, out, "08_tiempos_organos.png")


def grafica_rutas(rutas: pd.DataFrame, out: Path):
    if rutas.empty or "incidencias" not in rutas.columns:
        return

    df = rutas[rutas["incidencias"] > 0].copy()

    if df.empty:
        fig, ax = plt.subplots(figsize=(11, 5.8))
        ax.axis("off")
        ax.text(
            0.5,
            0.55,
            "Sin rutas críticas con retrasos",
            ha="center",
            va="center",
            fontsize=24,
            fontweight="bold",
            color=COLOR_A_TIEMPO,
        )
        guardar(fig, out, "09_rutas_criticas.png")
        return

    df = df.sort_values("incidencias", ascending=True).tail(8)

    fig, ax = plt.subplots(figsize=(12, 6.8))

    ax.barh(df["ruta"], df["incidencias"], color=COLOR_FALLO)

    ax.set_title("Rutas con incidencias clínicas (Órganos)", fontweight="bold", pad=15)
    ax.set_xlabel("Órganos fuera de isquemia (acumulado)")

    max_incidencias = df["incidencias"].max()
    ax.set_xlim(0, max_incidencias * 1.15 if max_incidencias else 10)

    for y, val in enumerate(df["incidencias"]):
        ax.text(val + (max_incidencias * 0.01 if max_incidencias else 0.1), y, f"{int(val)}", va="center", fontweight="bold")

    guardar(fig, out, "09_rutas_criticas.png")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Genera gráficas de presentación a partir del CSV de Monte Carlo.")
    parser.add_argument("--input", type=str, default="datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv")
    parser.add_argument("--output", type=str, default="graficas_presentacion")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    png_dir = output_dir / "png"
    tablas_dir = output_dir / "tablas"

    png_dir.mkdir(parents=True, exist_ok=True)
    tablas_dir.mkdir(parents=True, exist_ok=True)

    configurar_estilo()

    try:
        tabla = cargar_tabla_montecarlo(input_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Separar los DataFrames por tipo de registro según tabla_montecarlo.csv
    df_sim = tabla[tabla["tipo_registro"] == "simulacion"].copy()
    df_cola = tabla[tabla["tipo_registro"] == "cola"].copy()
    df_drones = tabla[tabla["tipo_registro"] == "dron"].copy()
    df_rutas = tabla[tabla["tipo_registro"] == "ruta"].copy()

    print("\nRegistros cargados de la tabla unificada:")
    print(f"  Simulaciones: {len(df_sim)} filas")
    print(f"  Cola temporal: {len(df_cola)} filas")
    print(f"  Drones:        {len(df_drones)} filas")
    print(f"  Rutas:         {len(df_rutas)} filas")

    # Resúmenes agrupados
    summary = resumen_escenarios(df_sim)
    
    # Extraemos la información de órganos directamente del resumen de simulaciones (df_sim)
    organos = summary[[
        "escenario",
        "organos_totales",
        "organos_a_tiempo",
        "organos_fuera_isquemia",
        "organos_pendientes",
        "exito_clinico_pct"
    ]].copy() if not summary.empty else pd.DataFrame()

    rutas = resumen_organos_desde_rutas(df_rutas)
    util = resumen_utilizacion_drones(df_drones, df_sim)
    cola = preparar_cola(df_cola)

    # Guardar tablas resumen en la carpeta de salida
    summary.to_csv(tablas_dir / "resumen_escenarios.csv", index=False, encoding="utf-8-sig")
    if not organos.empty:
        organos.to_csv(tablas_dir / "organos_por_escenario.csv", index=False, encoding="utf-8-sig")
    if not rutas.empty:
        rutas.to_csv(tablas_dir / "rutas_organos.csv", index=False, encoding="utf-8-sig")
    if not util.empty:
        util.to_csv(tablas_dir / "utilizacion_drones.csv", index=False, encoding="utf-8-sig")
    if not cola.empty:
        cola.to_csv(tablas_dir / "cola_temporal.csv", index=False, encoding="utf-8-sig")

    print("\nResumen rápido por escenario:")
    print(summary[[
        "escenario",
        "tasa_servicio_pct",
        "p95_inventario_medio",
        "p95_inventario_peor",
        "cola_media",
        "cola_maxima",
    ]].to_string(index=False))

    if not organos.empty:
        print("\nTransporte de Órganos:")
        print(organos[[
            "escenario",
            "organos_totales",
            "organos_a_tiempo",
            "organos_fuera_isquemia",
            "exito_clinico_pct",
        ]].to_string(index=False))

    if not util.empty:
        print("\nUtilización de Flota:")
        print(util[[
            "escenario",
            "tipo_dron",
            "utilizacion_vuelo_pct",
            "utilizacion_operativa_pct",
        ]].to_string(index=False))

    # Generación de gráficas
    grafica_servicio(summary, png_dir)
    grafica_p95_inventario(summary, png_dir)

    if not organos.empty:
        grafica_organos(organos, png_dir)
        grafica_exito_clinico(organos, png_dir)

    grafica_colas(summary, png_dir)
    grafica_evolucion_cola(cola, png_dir)
    grafica_utilizacion(util, png_dir)
    grafica_tiempos_organos(df_rutas, png_dir)
    grafica_rutas(rutas, png_dir)

    print("\n¡Todo listo!")
    print(f"Gráficas guardadas en: {png_dir}")
    print(f"Tablas guardadas en:   {tablas_dir}")



if __name__ == "__main__":
    main()

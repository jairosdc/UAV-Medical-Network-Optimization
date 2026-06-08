# generar_graficas_presentacion.py
# ============================================================
# Gráficas finales limpias para presentación
# Red sanitaria de drones
# ============================================================

from __future__ import annotations

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
UMBRAL_P95_INVENTARIO = 720

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


def buscar_csv(input_dir: Path, clave: str) -> Path | None:
    patrones = [
        f"**/montecarlo_{clave}_completo.csv",
        f"**/montecarlo_{clave}_completo*.csv",
        f"**/montecarlo_{clave}.csv",
        f"**/montecarlo_{clave}*.csv",
    ]

    candidatos = []
    for p in patrones:
        candidatos.extend(input_dir.glob(p))

    candidatos = [p for p in candidatos if p.is_file() and "checkpoint" not in p.name.lower()]

    if not candidatos:
        patrones_checkpoint = [
            f"**/checkpoint_{clave}_completo.csv",
            f"**/checkpoint_{clave}_completo*.csv",
            f"**/checkpoint_{clave}.csv",
            f"**/checkpoint_{clave}*.csv",
        ]
        for p in patrones_checkpoint:
            candidatos.extend(input_dir.glob(p))
        candidatos = [p for p in candidatos if p.is_file()]

    if not candidatos:
        return None

    return sorted(candidatos, key=lambda x: x.stat().st_mtime, reverse=True)[0]


def cargar_datasets(input_dir: Path) -> dict[str, pd.DataFrame]:
    claves = {
        "simulaciones": "simulaciones",
        "pedidos": "pedidos",
        "cola": "cola_tiempo",
        "drones": "drones",
        "clima": "clima",
        "productos": "productos",
    }

    dfs = {}

    print("\nCSV detectados:\n")

    for nombre, clave in claves.items():
        path = buscar_csv(input_dir, clave)

        if path is None:
            print(f"[AVISO] No encontrado: {nombre}")
            dfs[nombre] = pd.DataFrame()
            continue

        df = leer_csv(path)
        dfs[nombre] = df
        print(f"[OK] {nombre:12s} -> {path.name} ({len(df)} filas)")

    return dfs


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

    c_esc = obtener_columna(df, ["escenario", "fase", "nivel_estres"])
    c_gen = obtener_columna(df, ["pedidos_generados", "total_pedidos"])
    c_comp = obtener_columna(df, ["pedidos_completados"])
    c_p95 = obtener_columna(df, ["p95_inventario_min", "p95_inventario"])
    c_p99 = obtener_columna(df, ["p99_inventario_min", "p99_inventario"])
    c_cola_media = obtener_columna(df, ["longitud_media_cola", "cola_media"])
    c_cola_max = obtener_columna(df, ["longitud_maxima_cola", "cola_maxima"])
    c_org_total = obtener_columna(df, ["organos_totales"])
    c_org_ok = obtener_columna(df, ["organos_on_time", "organos_a_tiempo"])
    c_org_late = obtener_columna(df, ["organos_late", "organos_fuera_isquemia"])
    c_org_pend = obtener_columna(df, ["organos_pendientes"])
    c_min = obtener_columna(df, ["minutos_simulacion"])
    c_sim = obtener_columna(df, ["simulacion", "simulacion_id", "iteracion", "run"])

    if c_esc is None:
        raise ValueError("No encuentro columna de escenario en montecarlo_simulaciones.")

    df["escenario"] = df[c_esc].apply(escenario_pretty)

    def num(c):
        if c is None:
            return pd.Series(np.nan, index=df.index)
        return pd.to_numeric(df[c], errors="coerce")

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

        if c_sim:
            n_sims = g[c_sim].nunique()
        else:
            n_sims = len(g)

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


def resumen_organos_desde_pedidos(df_pedidos: pd.DataFrame, df_sim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df_pedidos.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df_pedidos.copy()

    c_esc = obtener_columna(df, ["escenario", "fase", "nivel_estres"])
    c_tipo = obtener_columna(df, ["tipo_pedido", "tipo"])
    c_prod = obtener_columna(df, ["producto"])
    c_status = obtener_columna(df, ["status", "estado"])
    c_origen = obtener_columna(df, ["origin_hospital", "origen", "hospital_origen"])
    c_destino = obtener_columna(df, ["destination_hospital", "destino", "hospital_destino"])
    c_t0 = obtener_columna(df, ["timestamp_min"])
    c_ta = obtener_columna(df, ["assigned_time_min"])
    c_tc = obtener_columna(df, ["completed_time_min"])
    c_deadline = obtener_columna(df, ["deadline_min"])
    c_late = obtener_columna(df, ["is_late", "late", "tarde"])

    if c_esc is None:
        return pd.DataFrame(), pd.DataFrame()

    df["escenario"] = df[c_esc].apply(escenario_pretty)

    es_organo = pd.Series(False, index=df.index)

    if c_tipo:
        es_organo |= df[c_tipo].astype(str).map(normalizar).eq("organo")

    if c_prod:
        es_organo |= df[c_prod].astype(str).map(normalizar).isin({normalizar(x) for x in ORGANOS})

    org = df[es_organo].copy()

    if org.empty:
        return pd.DataFrame(), pd.DataFrame()

    def num_col(c):
        if c is None:
            return pd.Series(np.nan, index=org.index)
        return pd.to_numeric(org[c], errors="coerce")

    org["timestamp_min"] = num_col(c_t0)
    org["assigned_time_min"] = num_col(c_ta)
    org["completed_time_min"] = num_col(c_tc)
    org["deadline_min"] = num_col(c_deadline)

    if c_status:
        status = org[c_status].astype(str).map(normalizar)
        org["completado"] = status.str.contains("completed|completado|finalizado")
    else:
        org["completado"] = org["completed_time_min"].notna()

    if c_late:
        org["late_explicito"] = org[c_late].astype(str).map(normalizar).isin(
            {"true", "1", "si", "sí", "yes", "late", "tarde"}
        )
    else:
        org["late_explicito"] = False

    org["fuera_isquemia"] = (
        org["late_explicito"]
        | (
            org["completado"]
            & org["completed_time_min"].notna()
            & org["deadline_min"].notna()
            & (org["completed_time_min"] > org["deadline_min"])
        )
    )

    org["a_tiempo"] = org["completado"] & ~org["fuera_isquemia"]

    org["tiempo_total_min"] = org["completed_time_min"] - org["timestamp_min"]
    org["espera_asignacion_min"] = org["assigned_time_min"] - org["timestamp_min"]

    rows = []

    for esc, g in org.groupby("escenario"):
        total = len(g)
        ok = int(g["a_tiempo"].sum())
        fuera = int(g["fuera_isquemia"].sum())
        pendientes = int((~g["completado"]).sum())

        rows.append({
            "escenario": esc,
            "organos_totales": total,
            "organos_a_tiempo": ok,
            "organos_fuera_isquemia": fuera,
            "organos_pendientes": pendientes,
            "exito_clinico_pct": ok / total * 100 if total > 0 else np.nan,
            "tiempo_medio_min": g["tiempo_total_min"].mean(),
            "tiempo_p95_min": g["tiempo_total_min"].quantile(0.95),
        })

    organos_esc = ordenar_escenarios(pd.DataFrame(rows))

    if c_origen and c_destino:
        org["ruta"] = org[c_origen].astype(str) + " → " + org[c_destino].astype(str)

        rutas = (
            org.groupby("ruta")
            .agg(
                organos_totales=("ruta", "size"),
                organos_fuera_isquemia=("fuera_isquemia", "sum"),
                organos_a_tiempo=("a_tiempo", "sum"),
                tiempo_medio_min=("tiempo_total_min", "mean"),
                espera_media_min=("espera_asignacion_min", "mean"),
            )
            .reset_index()
        )

        rutas["incidencias"] = rutas["organos_fuera_isquemia"]
        rutas = rutas.sort_values(["incidencias", "organos_totales"], ascending=False)
    else:
        rutas = pd.DataFrame()

    return organos_esc, rutas


def resumen_utilizacion_drones(df_drones: pd.DataFrame, df_sim: pd.DataFrame) -> pd.DataFrame:
    """
    Corrección importante:
    La utilización se calcula por dron-simulación, no sumando todas las filas sin control.

    Fórmula:
        utilización = sum(vuelo + recarga) / sum(tiempo disponible por dron) * 100

    Si drones_completo tiene varias filas por dron, se toma el máximo de minutos acumulados
    por escenario + simulación + dron.
    """

    if df_drones.empty:
        return pd.DataFrame()

    df = df_drones.copy()

    c_esc = obtener_columna(df, ["escenario", "fase", "nivel_estres"])
    c_sim = obtener_columna(df, ["simulacion", "simulacion_id", "iteracion", "run"])
    c_dron = obtener_columna(df, ["drone_id", "id_dron", "dron"])
    c_role = obtener_columna(df, ["role", "rol", "tipo_dron"])
    c_vuelo = obtener_columna(df, ["flight_minutes", "tiempo_vuelo", "minutos_vuelo"])
    c_recarga = obtener_columna(df, ["charging_minutes", "tiempo_recarga", "minutos_recarga"])

    if not all([c_esc, c_dron, c_role]):
        print("[AVISO] No se puede calcular utilización de drones: faltan columnas clave.")
        return pd.DataFrame()

    df["escenario"] = df[c_esc].apply(escenario_pretty)

    if c_sim:
        df["simulacion"] = df[c_sim].astype(str)
    else:
        df["simulacion"] = "sim_1"

    df["drone_id"] = df[c_dron].astype(str)

    role_norm = df[c_role].astype(str).map(normalizar)
    df["tipo_dron"] = np.where(role_norm.str.contains("hospital"), "Hospitalarios", "Base")

    if c_vuelo:
        df["vuelo_min"] = pd.to_numeric(df[c_vuelo], errors="coerce").fillna(0)
    else:
        df["vuelo_min"] = 0

    if c_recarga:
        df["recarga_min"] = pd.to_numeric(df[c_recarga], errors="coerce").fillna(0)
    else:
        df["recarga_min"] = 0

    # Duración por simulación.
    duracion_default = 20160

    if not df_sim.empty:
        c_min = obtener_columna(df_sim, ["minutos_simulacion", "duracion_min"])
        if c_min:
            duracion_default = pd.to_numeric(df_sim[c_min], errors="coerce").max()
            if pd.isna(duracion_default):
                duracion_default = 20160

    # Si hay múltiples filas por dron, tomamos el máximo acumulado.
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

    c_esc = obtener_columna(df, ["escenario", "fase", "nivel_estres"])
    c_sim = obtener_columna(df, ["simulacion", "simulacion_id", "iteracion", "run"])
    c_min = obtener_columna(df, ["minuto", "timestamp_min", "tiempo_min"])
    c_cola = obtener_columna(df, ["longitud_cola", "cola", "pedidos_en_cola", "queue_length"])

    if not all([c_esc, c_min, c_cola]):
        return pd.DataFrame()

    df["escenario"] = df[c_esc].apply(escenario_pretty)
    df["minuto"] = pd.to_numeric(df[c_min], errors="coerce")
    df["cola"] = pd.to_numeric(df[c_cola], errors="coerce")

    if c_sim:
        df["simulacion"] = df[c_sim].astype(str)
    else:
        df["simulacion"] = "sim_1"

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
    ax.set_ylim(max(98, df["tasa_servicio_pct"].min() - 0.3), 100.15)

    ax.axhline(99, color=COLOR_GRIS, linestyle="--", linewidth=1.2)

    for bar, val in zip(bars, df["tasa_servicio_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.03,
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
        label="Umbral 720 min",
    )

    ax.set_title("P95 de entrega de inventario", fontweight="bold", pad=15)
    ax.set_ylabel("Minutos")
    ax.set_ylim(0, max(760, df["p95_inventario_peor"].max() * 1.15))
    ax.legend()

    for bar, val in zip(bars, df["p95_inventario_medio"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 15,
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
            total + max(1, total * 0.015),
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
    ax.set_ylim(max(98, df["exito_clinico_pct"].min() - 0.4), 100.15)

    ax.axhline(99, color=COLOR_GRIS, linestyle="--", linewidth=1.2)

    for bar, val in zip(bars, df["exito_clinico_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.03,
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

    for x, y in zip(df["escenario"], df["cola_media"]):
        ax.text(x, y + 2, f"{y:.1f}", ha="center", va="bottom", fontweight="bold")

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

    if "Base" in pivot.columns:
        bars1 = ax.bar(
            x - width / 2,
            pivot["Base"],
            width,
            color=COLOR_BASE,
            label="Drones de base",
        )
    else:
        bars1 = []

    if "Hospitalarios" in pivot.columns:
        bars2 = ax.bar(
            x + width / 2,
            pivot["Hospitalarios"],
            width,
            color=COLOR_HOSPITAL,
            label="Drones hospitalarios",
        )
    else:
        bars2 = []

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

    ymax = max(10, np.nanmax(pivot.values) * 1.25)
    ax.set_ylim(0, ymax)

    guardar(fig, out, "07_utilizacion_flota.png")


def grafica_tiempos_organos(df_pedidos: pd.DataFrame, out: Path):
    if df_pedidos.empty:
        return

    df = df_pedidos.copy()

    c_esc = obtener_columna(df, ["escenario", "fase", "nivel_estres"])
    c_tipo = obtener_columna(df, ["tipo_pedido", "tipo"])
    c_prod = obtener_columna(df, ["producto"])
    c_t0 = obtener_columna(df, ["timestamp_min"])
    c_tc = obtener_columna(df, ["completed_time_min"])

    if not all([c_esc, c_t0, c_tc]):
        return

    es_organo = pd.Series(False, index=df.index)

    if c_tipo:
        es_organo |= df[c_tipo].astype(str).map(normalizar).eq("organo")
    if c_prod:
        es_organo |= df[c_prod].astype(str).map(normalizar).isin({normalizar(x) for x in ORGANOS})

    df = df[es_organo].copy()

    if df.empty:
        return

    df["escenario"] = df[c_esc].apply(escenario_pretty)
    df["tiempo_total_min"] = pd.to_numeric(df[c_tc], errors="coerce") - pd.to_numeric(df[c_t0], errors="coerce")
    df = df[df["tiempo_total_min"].notna()]
    df = df[df["tiempo_total_min"] >= 0]

    if df.empty:
        return

    escenarios = [e for e in ["Base", "Moderado", "Alto", "Muy alto"] if e in df["escenario"].unique()]
    datos = [df.loc[df["escenario"] == e, "tiempo_total_min"] for e in escenarios]

    fig, ax = plt.subplots(figsize=(11, 6.5))

    bp = ax.boxplot(
        datos,
        labels=escenarios,
        patch_artist=True,
        showfliers=False,
        widths=0.55,
    )

    for patch, esc in zip(bp["boxes"], escenarios):
        patch.set_facecolor(color_escenario(esc))
        patch.set_alpha(0.75)

    for median in bp["medians"]:
        median.set_color("white")
        median.set_linewidth(2.5)

    ax.set_title("Tiempo total de transporte de órganos", fontweight="bold", pad=15)
    ax.set_ylabel("Minutos desde aparición hasta entrega")

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
            "Sin rutas críticas residuales",
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

    ax.set_title("Rutas con incidencias clínicas", fontweight="bold", pad=15)
    ax.set_xlabel("Órganos fuera de isquemia")

    for y, val in enumerate(df["incidencias"]):
        ax.text(val + 0.05, y, f"{int(val)}", va="center", fontweight="bold")

    guardar(fig, out, "09_rutas_criticas.png")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=".")
    parser.add_argument("--output", type=str, default="graficas_presentacion")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    png_dir = output_dir / "png"
    tablas_dir = output_dir / "tablas"

    png_dir.mkdir(parents=True, exist_ok=True)
    tablas_dir.mkdir(parents=True, exist_ok=True)

    configurar_estilo()

    dfs = cargar_datasets(input_dir)

    df_sim = dfs["simulaciones"]
    df_pedidos = dfs["pedidos"]
    df_cola = dfs["cola"]
    df_drones = dfs["drones"]

    summary = resumen_escenarios(df_sim)
    organos, rutas = resumen_organos_desde_pedidos(df_pedidos, df_sim)
    util = resumen_utilizacion_drones(df_drones, df_sim)
    cola = preparar_cola(df_cola)

    summary.to_csv(tablas_dir / "resumen_escenarios.csv", index=False, encoding="utf-8-sig")
    organos.to_csv(tablas_dir / "organos_por_escenario.csv", index=False, encoding="utf-8-sig")
    rutas.to_csv(tablas_dir / "rutas_organos.csv", index=False, encoding="utf-8-sig")
    util.to_csv(tablas_dir / "utilizacion_drones.csv", index=False, encoding="utf-8-sig")
    cola.to_csv(tablas_dir / "cola_temporal.csv", index=False, encoding="utf-8-sig")

    print("\nResumen rápido:")
    print(summary[[
        "escenario",
        "tasa_servicio_pct",
        "p95_inventario_medio",
        "p95_inventario_peor",
        "cola_media",
        "cola_maxima",
    ]].to_string(index=False))

    if not organos.empty:
        print("\nÓrganos:")
        print(organos[[
            "escenario",
            "organos_totales",
            "organos_a_tiempo",
            "organos_fuera_isquemia",
            "organos_pendientes",
            "exito_clinico_pct",
        ]].to_string(index=False))

    if not util.empty:
        print("\nUtilización corregida:")
        print(util[[
            "escenario",
            "tipo_dron",
            "utilizacion_vuelo_pct",
            "utilizacion_operativa_pct",
        ]].to_string(index=False))

    grafica_servicio(summary, png_dir)
    grafica_p95_inventario(summary, png_dir)

    if not organos.empty:
        grafica_organos(organos, png_dir)
        grafica_exito_clinico(organos, png_dir)

    grafica_colas(summary, png_dir)
    grafica_evolucion_cola(cola, png_dir)
    grafica_utilizacion(util, png_dir)
    grafica_tiempos_organos(df_pedidos, png_dir)
    grafica_rutas(rutas, png_dir)

    print("\nHecho.")
    print(f"Gráficas: {png_dir}")
    print(f"Tablas:   {tablas_dir}")


if __name__ == "__main__":
    main()
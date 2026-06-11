"""
generar_graficas_sencillo_importantes.py
========================================

Lee la tabla unica generada por montecarlo_escenarios_sencillo.py
y crea solo las graficas mas importantes para la presentacion.

Uso:
    python generar_graficas_sencillo_importantes.py --input datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv --output graficas_presentacion
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# ---------------------------------------------------------------------------
# Configuracion basica
# ---------------------------------------------------------------------------

DPI = 300
OBJETIVO_SERVICIO_PCT = 99
UMBRAL_P95_INVENTARIO_MIN = 720
ORDEN_ESCENARIOS = ["Base", "Moderado", "Alto", "Muy alto"]

COLORES_ESCENARIO = {
    "Base": "#2CA02C",
    "Moderado": "#1F77B4",
    "Alto": "#FF9F1C",
    "Muy alto": "#D62728",
}

COLOR_A_TIEMPO = "#2CA02C"
COLOR_FUERA = "#D62728"
COLOR_PENDIENTE = "#FF9F1C"
COLOR_LINEA = "#0B1F33"
COLOR_GRIS = "#6C757D"


# ---------------------------------------------------------------------------
# Utilidades pequeñas
# ---------------------------------------------------------------------------

def configurar_estilo():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.color": "#DDE3EA",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
    })


def leer_tabla(ruta):
    tabla = pd.read_csv(ruta)
    if "tipo_registro" not in tabla.columns:
        raise ValueError("El CSV debe tener la columna 'tipo_registro'.")
    return tabla


def numero(serie):
    return pd.to_numeric(serie, errors="coerce")


def ordenar(df):
    if df.empty or "escenario_etiqueta" not in df.columns:
        return df

    orden = {escenario: i for i, escenario in enumerate(ORDEN_ESCENARIOS)}
    df = df.copy()
    df["_orden"] = df["escenario_etiqueta"].map(orden).fillna(99)
    df = df.sort_values("_orden").drop(columns="_orden")
    return df


def colores(df):
    return [
        COLORES_ESCENARIO.get(e, "#1F77B4")
        for e in df["escenario_etiqueta"]
    ]


def guardar(fig, carpeta, nombre):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    fig.savefig(ruta, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Grafica guardada: {ruta}")


def sin_datos(carpeta, nombre, titulo, mensaje):
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis("off")
    ax.text(
        0.5, 0.60,
        titulo,
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
    )
    ax.text(
        0.5, 0.45,
        mensaje,
        ha="center",
        va="center",
        fontsize=12,
        color=COLOR_GRIS,
    )
    guardar(fig, carpeta, nombre)


def anotar_barras(ax, barras, formato="{:.1f}", margen=0):
    for barra in barras:
        valor = barra.get_height()
        if pd.notna(valor):
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                valor + margen,
                formato.format(valor),
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )


def limite_porcentaje(valores):
    valores = numero(valores).dropna()
    if valores.empty:
        return 0, 100

    minimo = valores.min()

    if minimo >= 97:
        return max(96.5, minimo - 0.5), 100.5

    return max(0, minimo - 3), 100.5


# ---------------------------------------------------------------------------
# Resumen principal
# ---------------------------------------------------------------------------

def resumen_simulaciones(tabla):
    sim = tabla[tabla["tipo_registro"] == "simulacion"].copy()

    if sim.empty:
        return pd.DataFrame()

    columnas_necesarias = [
        "pedidos_generados",
        "pedidos_completados",
        "inventario_tiempo_p95_min",
        "organos_totales",
        "organos_a_tiempo",
        "organos_fuera_isquemia",
        "organos_pendientes",
        "cola_media",
        "cola_maxima",
        "utilizacion_vuelo_pct",
        "utilizacion_operativa_pct",
    ]

    # Si falta alguna columna, se crea vacia para no romper el script.
    for col in columnas_necesarias:
        if col not in sim.columns:
            sim[col] = pd.NA
        sim[col] = numero(sim[col])

    resumen = sim.groupby("escenario_etiqueta", as_index=False).agg(
        pedidos_generados=("pedidos_generados", "sum"),
        pedidos_completados=("pedidos_completados", "sum"),
        inventario_p95_medio_min=("inventario_tiempo_p95_min", "mean"),
        inventario_p95_peor_min=("inventario_tiempo_p95_min", "max"),
        organos_totales=("organos_totales", "sum"),
        organos_a_tiempo=("organos_a_tiempo", "sum"),
        organos_fuera_isquemia=("organos_fuera_isquemia", "sum"),
        organos_pendientes=("organos_pendientes", "sum"),
        cola_media=("cola_media", "mean"),
        cola_maxima=("cola_maxima", "max"),
        utilizacion_vuelo_pct=("utilizacion_vuelo_pct", "mean"),
        utilizacion_operativa_pct=("utilizacion_operativa_pct", "mean"),
    )

    resumen["tasa_servicio_pct"] = (
        resumen["pedidos_completados"]
        / resumen["pedidos_generados"].replace(0, pd.NA)
        * 100
    )

    resumen["exito_organos_pct"] = (
        resumen["organos_a_tiempo"]
        / resumen["organos_totales"].replace(0, pd.NA)
        * 100
    )

    return ordenar(resumen)


# ---------------------------------------------------------------------------
# Graficas importantes
# ---------------------------------------------------------------------------

def grafica_servicio(resumen, carpeta):
    if resumen.empty or resumen["tasa_servicio_pct"].dropna().empty:
        sin_datos(
            carpeta,
            "01_servicio_global.png",
            "Servicio global",
            "No hay datos suficientes de pedidos.",
        )
        return

    fig, ax = plt.subplots(figsize=(11, 6))

    barras = ax.bar(
        resumen["escenario_etiqueta"],
        resumen["tasa_servicio_pct"],
        color=colores(resumen),
        width=0.62,
    )

    ax.axhline(
        OBJETIVO_SERVICIO_PCT,
        color=COLOR_GRIS,
        linestyle="--",
        linewidth=1.5,
        label=f"Objetivo {OBJETIVO_SERVICIO_PCT}%",
    )

    ax.set_title("Pedidos entregados por escenario", fontweight="bold")
    ax.set_ylabel("Pedidos completados / pedidos generados (%)")
    ax.set_ylim(*limite_porcentaje(resumen["tasa_servicio_pct"]))
    ax.legend(loc="lower left")

    anotar_barras(ax, barras, "{:.2f}%", margen=0.03)
    guardar(fig, carpeta, "01_servicio_global.png")


def grafica_inventario(resumen, carpeta):
    if resumen.empty or resumen["inventario_p95_medio_min"].dropna().empty:
        sin_datos(
            carpeta,
            "02_inventario_p95.png",
            "Inventario medico",
            "No hay tiempos P95 de inventario.",
        )
        return

    fig, ax = plt.subplots(figsize=(11, 6))

    barras = ax.bar(
        resumen["escenario_etiqueta"],
        resumen["inventario_p95_medio_min"],
        color=colores(resumen),
        width=0.62,
        label="P95 medio",
    )

    ax.scatter(
        resumen["escenario_etiqueta"],
        resumen["inventario_p95_peor_min"],
        color=COLOR_LINEA,
        s=55,
        label="Peor P95",
        zorder=3,
    )

    ax.axhline(
        UMBRAL_P95_INVENTARIO_MIN,
        color=COLOR_FUERA,
        linestyle="--",
        linewidth=1.5,
        label="Umbral 720 min",
    )

    maximo = max(
        resumen["inventario_p95_peor_min"].max(),
        UMBRAL_P95_INVENTARIO_MIN,
    )

    ax.set_ylim(
        0,
        maximo * 1.15 if pd.notna(maximo) and maximo > 0 else 100,
    )

    ax.set_title("Tiempo P95 de reposicion de inventario", fontweight="bold")
    ax.set_ylabel("Minutos")
    ax.legend()

    margen = maximo * 0.015 if pd.notna(maximo) else 2
    anotar_barras(ax, barras, "{:.0f}", margen=margen)

    guardar(fig, carpeta, "02_inventario_p95.png")


def grafica_organos(resumen, carpeta):
    if resumen.empty or resumen["organos_totales"].sum() == 0:
        sin_datos(
            carpeta,
            "03_organos_clinicos.png",
            "Organos",
            "No hay organos en la simulacion.",
        )
        return

    fig, ax = plt.subplots(figsize=(11, 6))

    x = range(len(resumen))

    a_tiempo = resumen["organos_a_tiempo"]
    fuera = resumen["organos_fuera_isquemia"]
    pendientes = resumen["organos_pendientes"]

    ax.bar(
        x,
        a_tiempo,
        color=COLOR_A_TIEMPO,
        label="A tiempo",
    )

    ax.bar(
        x,
        fuera,
        bottom=a_tiempo,
        color=COLOR_FUERA,
        label="Fuera de isquemia",
    )

    ax.bar(
        x,
        pendientes,
        bottom=a_tiempo + fuera,
        color=COLOR_PENDIENTE,
        label="Pendientes",
    )

    totales = a_tiempo + fuera + pendientes

    for i, total in enumerate(totales):
        porcentaje = resumen.iloc[i]["exito_organos_pct"]
        texto = f"{porcentaje:.1f}% a tiempo" if pd.notna(porcentaje) else "sin %"

        ax.text(
            i,
            total,
            texto,
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(resumen["escenario_etiqueta"])
    ax.set_title("Resultado clinico de los transportes de organos", fontweight="bold")
    ax.set_ylabel("Numero de organos")
    ax.legend()

    guardar(fig, carpeta, "03_organos_clinicos.png")


def grafica_evolucion_cola(tabla, carpeta):
    cola = tabla[tabla["tipo_registro"] == "cola"].copy()

    if cola.empty:
        sin_datos(
            carpeta,
            "04_evolucion_cola.png",
            "Evolucion de la cola",
            "No hay registros temporales de cola.",
        )
        return

    cola["dia"] = numero(cola["dia"])
    cola["longitud_cola"] = numero(cola["longitud_cola"])

    cola = cola.dropna(subset=["dia", "longitud_cola"])

    if cola.empty:
        sin_datos(
            carpeta,
            "04_evolucion_cola.png",
            "Evolucion de la cola",
            "La cola no tiene valores validos.",
        )
        return

    media = cola.groupby(
        ["escenario_etiqueta", "dia"],
        as_index=False,
    )["longitud_cola"].mean()

    media = ordenar(media)

    fig, ax = plt.subplots(figsize=(11, 6))

    for escenario, datos in media.groupby("escenario_etiqueta"):
        ax.plot(
            datos["dia"],
            datos["longitud_cola"],
            linewidth=2.3,
            label=escenario,
            color=COLORES_ESCENARIO.get(escenario),
        )

    ax.set_title("Evolucion media de la cola de pedidos", fontweight="bold")
    ax.set_xlabel("Dia de simulacion")
    ax.set_ylabel("Pedidos en cola")
    ax.legend()

    guardar(fig, carpeta, "04_evolucion_cola.png")


def grafica_utilizacion(tabla, resumen, carpeta):
    drones = tabla[tabla["tipo_registro"] == "dron"].copy()

    columnas_dron = {
        "utilizacion_vuelo_dron_pct",
        "utilizacion_operativa_dron_pct",
    }

    if not drones.empty and columnas_dron.issubset(drones.columns):
        drones["utilizacion_vuelo_dron_pct"] = numero(
            drones["utilizacion_vuelo_dron_pct"]
        )
        drones["utilizacion_operativa_dron_pct"] = numero(
            drones["utilizacion_operativa_dron_pct"]
        )

        datos = drones.groupby("escenario_etiqueta", as_index=False).agg(
            utilizacion_vuelo_pct=("utilizacion_vuelo_dron_pct", "mean"),
            utilizacion_operativa_pct=("utilizacion_operativa_dron_pct", "mean"),
        )

        datos = ordenar(datos)

    else:
        datos = resumen[
            [
                "escenario_etiqueta",
                "utilizacion_vuelo_pct",
                "utilizacion_operativa_pct",
            ]
        ].copy()

    if datos.empty or datos[
        ["utilizacion_vuelo_pct", "utilizacion_operativa_pct"]
    ].dropna(how="all").empty:
        sin_datos(
            carpeta,
            "05_utilizacion_flota.png",
            "Utilizacion de flota",
            "No hay datos de utilizacion de drones.",
        )
        return

    fig, ax = plt.subplots(figsize=(11, 6))

    x = range(len(datos))
    ancho = 0.35

    ax.bar(
        [i - ancho / 2 for i in x],
        datos["utilizacion_vuelo_pct"],
        width=ancho,
        color="#4C78A8",
        label="Vuelo",
    )

    ax.bar(
        [i + ancho / 2 for i in x],
        datos["utilizacion_operativa_pct"],
        width=ancho,
        color="#F58518",
        label="Vuelo + recarga",
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(datos["escenario_etiqueta"])
    ax.set_title("Utilizacion media de la flota", fontweight="bold")
    ax.set_ylabel("Utilizacion (%)")
    ax.legend()

    guardar(fig, carpeta, "05_utilizacion_flota.png")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genera solo las graficas principales del Monte Carlo."
    )

    parser.add_argument(
        "--input",
        default="datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv",
        help="CSV unico generado por Monte Carlo.",
    )

    parser.add_argument(
        "--output",
        default="graficas_presentacion",
        help="Carpeta de salida.",
    )

    args = parser.parse_args()

    configurar_estilo()

    tabla = leer_tabla(args.input)
    resumen = resumen_simulaciones(tabla)
    carpeta = Path(args.output) / "png"

    grafica_servicio(resumen, carpeta)
    grafica_inventario(resumen, carpeta)
    grafica_organos(resumen, carpeta)
    grafica_evolucion_cola(tabla, carpeta)
    grafica_utilizacion(tabla, resumen, carpeta)

    print("\nGraficas principales generadas en:", carpeta)


if __name__ == "__main__":
    main()
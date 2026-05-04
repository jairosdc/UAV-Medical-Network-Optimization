import matplotlib.pyplot as plt
import numpy as np


# ===========================================================================
# UTILIDADES
# ===========================================================================

def _es_organo(pedido):
    """Devuelve True si el pedido es de tipo órgano."""
    return getattr(pedido, "tipo_pedido", "inventario") == "organo"


def _es_inventario(pedido):
    """Devuelve True si el pedido es de tipo inventario."""
    return getattr(pedido, "tipo_pedido", "inventario") == "inventario"


def _contar_elementos(iterable):
    """Cuenta ocurrencias de cada elemento en un iterable (sin Counter)."""
    conteo = {}
    for item in iterable:
        conteo[item] = conteo.get(item, 0) + 1
    return conteo


def _porcentaje(parte, total):
    """Calcula un porcentaje de forma segura (devuelve 0 si total == 0)."""
    return (parte / total) * 100 if total > 0 else 0


def _top_items(diccionario, n=15):
    """
    Devuelve los top-N elementos de un diccionario ordenados por valor
    descendente. Retorna lista de tuplas (clave, valor).
    """
    ordenados = sorted(diccionario.items(), key=lambda x: x[1], reverse=True)
    return ordenados[:n]


# ===========================================================================
# FUNCION PRINCIPAL DE GRAFICAS
# ===========================================================================

def mostrar_graficas_resultados(
    gestor_flota,
    total_generados,
    minutos_simulacion,
    historial_longitud_cola=None,
    cola_pedidos=None,
):
    """
    Genera gráficas de resultados en ventanas independientes.

    Cada figura usa su propio plt.figure() y se renderiza con un único
    plt.show() al final para abrir todas las ventanas simultáneamente.
    """

    estadisticas = gestor_flota.estadisticas
    pedidos_completados = getattr(gestor_flota, "pedidos_completados", [])
    pedidos_rechazados = getattr(gestor_flota, "pedidos_rechazados", [])

    # Pedidos pendientes (de la cola, si se proporciona)
    if cola_pedidos is not None:
        pedidos_pendientes = getattr(cola_pedidos, "pedidos_pendientes", [])
    else:
        pedidos_pendientes = []

    # -------------------------------------------------------------------
    # CALCULOS DE METRICAS GENERALES
    # -------------------------------------------------------------------

    total_completados = len(pedidos_completados)
    total_pendientes = len(pedidos_pendientes)
    total_rechazados = len(pedidos_rechazados)

    # --- Inventario ---
    inv_completados = [p for p in pedidos_completados if _es_inventario(p)]
    inv_pendientes = [p for p in pedidos_pendientes if _es_inventario(p)]
    inv_rechazados = [p for p in pedidos_rechazados if _es_inventario(p)]

    # --- Órganos ---
    org_completados = [p for p in pedidos_completados if _es_organo(p)]
    org_pendientes = [p for p in pedidos_pendientes if _es_organo(p)]
    org_rechazados = [p for p in pedidos_rechazados if _es_organo(p)]

    org_a_tiempo = estadisticas.organ_on_time
    org_tarde = estadisticas.organ_late

    # ===================================================================
    # FIGURA 1: Embudo Global de Pedidos (Barras simples)
    # ===================================================================

    fig1 = plt.figure(figsize=(9, 6))
    fig1.canvas.manager.set_window_title("1 - Embudo Global de Pedidos")

    categorias = ["Generados", "Completados", "Pendientes", "Rechazados"]
    valores = [total_generados, total_completados, total_pendientes, total_rechazados]
    colores = ["#3498db", "#2ecc71", "#f39c12", "#e74c3c"]

    bars = plt.bar(categorias, valores, color=colores, edgecolor="white", linewidth=0.8)
    plt.ylim(0, max(valores) * 1.20 if max(valores) > 0 else 1)
    plt.title("Embudo Global de Pedidos", fontsize=14, fontweight="bold")
    plt.ylabel("Cantidad", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        yval = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + (max(valores) * 0.02 if max(valores) > 0 else 0.1),
            f"{int(yval)}",
            ha="center", va="bottom", fontsize=11, fontweight="bold",
        )

    plt.tight_layout()

    # ===================================================================
    # FIGURA 2: Inventario vs Órganos (Barras agrupadas)
    # ===================================================================

    fig2 = plt.figure(figsize=(10, 6))
    fig2.canvas.manager.set_window_title("2 - Inventario vs Órganos")

    categorias_tipo = ["Completados", "Pendientes", "Rechazados"]
    vals_inv = [len(inv_completados), len(inv_pendientes), len(inv_rechazados)]
    vals_org = [len(org_completados), len(org_pendientes), len(org_rechazados)]

    x = np.arange(len(categorias_tipo))
    ancho = 0.35

    bars_inv = plt.bar(x - ancho / 2, vals_inv, ancho, label="Inventario",
                       color="#1abc9c", edgecolor="white", linewidth=0.8)
    bars_org = plt.bar(x + ancho / 2, vals_org, ancho, label="Órganos",
                       color="#e74c3c", edgecolor="white", linewidth=0.8)

    todos_vals = vals_inv + vals_org
    techo = max(todos_vals) * 1.20 if max(todos_vals) > 0 else 1
    plt.ylim(0, techo)

    plt.xticks(x, categorias_tipo, fontsize=11)
    plt.ylabel("Cantidad", fontsize=11)
    plt.title("Inventario vs Órganos", fontsize=14, fontweight="bold")
    plt.legend(fontsize=10)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in list(bars_inv) + list(bars_org):
        yval = bar.get_height()
        if yval > 0:
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                yval + (max(todos_vals) * 0.015 if max(todos_vals) > 0 else 0.1),
                f"{int(yval)}",
                ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

    plt.tight_layout()

    # ===================================================================
    # FIGURA 3: Cumplimiento de Órganos
    # ===================================================================

    fig3 = plt.figure(figsize=(9, 6))
    fig3.canvas.manager.set_window_title("3 - Cumplimiento de Órganos")

    cat_organos = ["A tiempo", "Tarde", "Pendientes", "Rechazados"]
    val_organos = [org_a_tiempo, org_tarde, len(org_pendientes), len(org_rechazados)]
    col_organos = ["#27ae60", "#e67e22", "#f1c40f", "#c0392b"]

    bars_org3 = plt.bar(cat_organos, val_organos, color=col_organos,
                        edgecolor="white", linewidth=0.8)

    techo_org = max(val_organos) * 1.20 if max(val_organos) > 0 else 1
    plt.ylim(0, techo_org)
    plt.title("Cumplimiento de Órganos", fontsize=14, fontweight="bold")
    plt.ylabel("Cantidad", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars_org3:
        yval = bar.get_height()
        if yval > 0:
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                yval + (max(val_organos) * 0.02 if max(val_organos) > 0 else 0.1),
                f"{int(yval)}",
                ha="center", va="bottom", fontsize=11, fontweight="bold",
            )

    plt.tight_layout()

    # ===================================================================
    # FIGURA 4: Top Hospitales Receptores (Barras horizontales)
    # ===================================================================

    fig4 = plt.figure(figsize=(10, 12))
    fig4.canvas.manager.set_window_title("4 - Top Hospitales Receptores")

    if pedidos_completados:
        conteo_hosp = _contar_elementos(
            p.destination_hospital for p in pedidos_completados
        )
        top = _top_items(conteo_hosp, n=len(conteo_hosp))  # Todos, ordenados

        # Invertir para que el mayor quede arriba
        top_invertido = list(reversed(top))
        etiquetas_h = [t[0] for t in top_invertido]
        valores_h = [t[1] for t in top_invertido]

        y_pos = np.arange(len(etiquetas_h))
        bars_h = plt.barh(y_pos, valores_h, color="#2980b9",
                          edgecolor="white", linewidth=0.5)
        plt.yticks(y_pos, etiquetas_h, fontsize=8)
        plt.xlabel("Entregas Completadas", fontsize=11)
        plt.title("Top Hospitales Receptores", fontsize=14, fontweight="bold")
        plt.grid(axis="x", linestyle="--", alpha=0.5)

        for bar in bars_h:
            xval = bar.get_width()
            plt.text(
                xval + (max(valores_h) * 0.01 if max(valores_h) > 0 else 0.1),
                bar.get_y() + bar.get_height() / 2,
                f"{int(xval)}",
                va="center", fontsize=8,
            )
    else:
        plt.text(0.5, 0.5, "Sin datos de entregas", ha="center", va="center",
                 fontsize=14, transform=plt.gca().transAxes)
        plt.title("Top Hospitales Receptores", fontsize=14, fontweight="bold")

    plt.tight_layout()

    # ===================================================================
    # FIGURA 5: Evolución de la Cola (Gráfico de líneas)
    # ===================================================================

    if historial_longitud_cola is not None:
        fig5 = plt.figure(figsize=(12, 5))
        fig5.canvas.manager.set_window_title("5 - Evolución de la Cola")

        minutos = range(len(historial_longitud_cola))
        plt.plot(minutos, historial_longitud_cola, color="#8e44ad",
                 linewidth=0.8, alpha=0.9)
        plt.fill_between(minutos, historial_longitud_cola,
                         color="#8e44ad", alpha=0.15)

        plt.title("Evolución de la Longitud de Cola", fontsize=14, fontweight="bold")
        plt.xlabel("Minuto de Simulación", fontsize=11)
        plt.ylabel("Pedidos en Cola", fontsize=11)
        plt.grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()

    # ===================================================================
    # RENDERIZAR TODAS LAS VENTANAS
    # ===================================================================

    plt.show()

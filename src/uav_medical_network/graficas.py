import matplotlib.pyplot as plt

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

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, height + (max(valores) * 0.01 if max(valores) > 0 else 0.01),
                 f"{int(height)}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.title("Estado Global de la Demanda de Pedidos", fontsize=14, fontweight="bold", pad=15)
    plt.ylabel("Número de Pedidos", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()

    # ===================================================================
    # FIGURA 2: Distribución por Tipo y Nivel de Cumplimiento
    # ===================================================================

    fig2 = plt.figure(figsize=(11, 6.5))
    fig2.canvas.manager.set_window_title("2 - Cumplimiento y Composición de Pedidos")

    # Subplot A: Composición de Pedidos
    plt.subplot(1, 2, 1)
    etiquetas_comp = ["Inventario", "Órganos"]
    valores_comp = [
        len(inv_completados) + len(inv_pendientes) + len(inv_rechazados),
        len(org_completados) + len(org_pendientes) + len(org_rechazados)
    ]
    plt.pie(valores_comp, labels=etiquetas_comp, autopct="%1.1f%%", startangle=90,
            colors=["#2ecc71", "#e74c3c"], textprops={"fontsize": 11},
            wedgeprops={"edgecolor": "white", "linewidth": 1})
    plt.title("Composición de la Demanda", fontsize=12, fontweight="bold", pad=10)

    # Subplot B: Cumplimiento de Órganos (Puntualidad en Isquemia)
    plt.subplot(1, 2, 2)
    etiquetas_org = ["A tiempo", "Tarde / Isquemia"]
    valores_org = [org_a_tiempo, org_tarde]
    
    if sum(valores_org) > 0:
        plt.pie(valores_org, labels=etiquetas_org, autopct="%1.1f%%", startangle=90,
                colors=["#27ae60", "#c0392b"], textprops={"fontsize": 11},
                wedgeprops={"edgecolor": "white", "linewidth": 1})
    else:
        plt.text(0.5, 0.5, "Sin órganos entregados", ha="center", va="center", fontsize=12, style="italic")
        plt.gca().axis("off")
        
    plt.title("Puntualidad en Ventana de Isquemia", fontsize=12, fontweight="bold", pad=10)

    plt.suptitle("Composición y Calidad del Servicio Clínico", fontsize=15, fontweight="bold", y=0.98)
    plt.tight_layout()

    # ===================================================================
    # FIGURA 3: Rendimiento de la Flota (Tiempos de Vuelo y Carga)
    # ===================================================================

    drones = list(gestor_flota.drones.values())
    if drones:
        fig3 = plt.figure(figsize=(12, 6.5))
        fig3.canvas.manager.set_window_title("3 - Utilización y Eficiencia de la Flota")

        drones_ordenados = sorted(drones, key=lambda d: d.drone_id)
        ids = [d.drone_id for d in drones_ordenados]
        minutos_vuelo = [d.flight_minutes for d in drones_ordenados]
        minutos_carga = [d.charging_minutes for d in drones_ordenados]

        x = range(len(ids))
        width = 0.4

        # Gráfico de barras agrupadas: Vuelo vs Carga
        plt.bar([i - width/2 for i in x], minutos_vuelo, width, label="Minutos en Vuelo", color="#2980b9")
        plt.bar([i + width/2 for i in x], minutos_carga, width, label="Minutos en Carga", color="#f1c40f")

        plt.xticks(x, ids, rotation=45, ha="right", fontsize=9)
        plt.title("Tiempo de Vuelo y Recarga por Dron", fontsize=14, fontweight="bold", pad=15)
        plt.xlabel("ID del Dron", fontsize=11)
        plt.ylabel("Minutos Acumulados", fontsize=11)
        plt.legend(frameon=True, facecolor="white", edgecolor="none")
        plt.grid(axis="y", linestyle="--", alpha=0.5)

        plt.tight_layout()

    # ===================================================================
    # FIGURA 4: Hospitales Receptores (Top 15 por entregas con éxito)
    # ===================================================================

    fig4 = plt.figure(figsize=(10, 6.5))
    fig4.canvas.manager.set_window_title("4 - Top Hospitales Receptores")

    hospitales_destino = [p.destination_hospital for p in pedidos_completados if p.destination_hospital]
    if hospitales_destino:
        conteo_destinos = _contar_elementos(hospitales_destino)
        top_destinos = _top_items(conteo_destinos, n=15)

        nombres_h = [item[0].replace("Hospital Universitario ", "H. U. ").replace("Hospital Asociado Universitario ", "H. A. U. ") for item in top_destinos]
        frecuencias_h = [item[1] for item in top_destinos]

        y_pos = range(len(nombres_h))
        plt.barh(y_pos, frecuencias_h, color="#1abc9c", edgecolor="white", height=0.6)
        plt.yticks(y_pos, nombres_h, fontsize=9)
        plt.gca().invert_yaxis()  # El más alto arriba

        plt.title("Top 15 Hospitales por Entregas Completadas", fontsize=14, fontweight="bold", pad=15)
        plt.xlabel("Entregas de Insumos / Órganos con Éxito", fontsize=11)
        plt.grid(axis="x", linestyle="--", alpha=0.5)

        for i, xval in enumerate(frecuencias_h):
            plt.text(
                xval + (max(frecuencias_h) * 0.005 if max(frecuencias_h) > 0 else 0.05),
                i,
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

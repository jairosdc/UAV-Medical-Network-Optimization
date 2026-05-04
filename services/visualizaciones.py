import matplotlib.pyplot as plt
import numpy as np

def _contar_elementos(iterable):
    """Cuenta elementos de un iterable sin usar Counter."""
    conteo = {}
    for item in iterable:
        conteo[item] = conteo.get(item, 0) + 1
    return conteo

def mostrar_graficas_resultados(gestor_flota, total_generados, minutos_simulacion):
    """
    Genera un dashboard interactivo de 5 gráficas al finalizar la simulación.
    """
    estadisticas = gestor_flota.estadisticas
        # =========================================================================
    # 1. Gráfica de Cantidad de Llamadas (Gráfico de Barras)
    # =========================================================================
    plt.figure(figsize=(8, 6))
    plt.gcf().canvas.manager.set_window_title("Estado de los Pedidos")
    
    etiquetas_llamadas = ['Generadas', 'Asignadas', 'Completadas', 'Rechazadas']
    valores_llamadas = [
        total_generados, 
        estadisticas.assigned_calls, 
        estadisticas.completed_calls, 
        estadisticas.rejected_calls
    ]
    colores_llamadas = ['#3498db', '#9b59b6', '#2ecc71', '#e74c3c']
    
    bars = plt.bar(etiquetas_llamadas, valores_llamadas, color=colores_llamadas)
    plt.ylim(0, max(valores_llamadas) * 1.15) # Margen extra para que los números no toquen el borde superior
    plt.title('Estado de los Pedidos', fontsize=12, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + (max(valores_llamadas) * 0.02), 
                 int(yval), ha='center', va='bottom', fontsize=10, fontweight='bold')
    plt.tight_layout()

    # =========================================================================
    # 2. Gráfica de Utilización de la Flota (Gráfico de Pastel)
    # =========================================================================
    plt.figure(figsize=(8, 6))
    plt.gcf().canvas.manager.set_window_title("Utilización Global de la Flota")
    
    total_vuelo = sum(d.flight_minutes for d in gestor_flota.drones.values())
    total_recarga = sum(d.charging_minutes for d in gestor_flota.drones.values())
    total_tiempo_flota = len(gestor_flota.drones) * minutos_simulacion
    total_disponible = total_tiempo_flota - total_vuelo - total_recarga
    
    if total_tiempo_flota > 0:
        porc_vuelo = (total_vuelo / total_tiempo_flota) * 100
        porc_recarga = (total_recarga / total_tiempo_flota) * 100
        porc_disponible = (total_disponible / total_tiempo_flota) * 100
    else:
        porc_vuelo = porc_recarga = porc_disponible = 0

    etiquetas_flota = ['En Vuelo', 'Recargando', 'Disponible (Base)']
    valores_flota = [porc_vuelo, porc_recarga, porc_disponible]
    colores_flota = ['#f1c40f', '#e67e22', '#95a5a6']
    
    explode = (0.1 if porc_vuelo > 0.5 else 0, 0.1 if porc_recarga > 0.5 else 0, 0)
    def my_autopct(pct):
        return ('%1.1f%%' % pct) if pct > 0.1 else ''

    wedges, texts, autotexts = plt.pie(
        valores_flota, autopct=my_autopct, colors=colores_flota, 
        startangle=140, explode=explode, shadow=True, textprops={'fontsize': 10, 'fontweight': 'bold'}
    )
    plt.legend(wedges, etiquetas_flota, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9)
    plt.title('Utilización Global (%)', fontsize=12, fontweight='bold')
    plt.tight_layout()

    # =========================================================================
    # 3. Distribución de Pedidos por Producto (Gráfico de Pastel)
    # =========================================================================
    plt.figure(figsize=(8, 6))
    plt.gcf().canvas.manager.set_window_title("Distribución por Producto")
    
    if gestor_flota.pedidos_completados:
        conteo_prod = _contar_elementos(p.producto for p in gestor_flota.pedidos_completados)
        etiquetas_prod = list(conteo_prod.keys())
        valores_prod = list(conteo_prod.values())
        
        # Usar colores automáticos pastel de matplotlib
        colores = plt.cm.Set3(np.linspace(0, 1, len(valores_prod)))
        plt.pie(valores_prod, labels=etiquetas_prod, autopct='%1.1f%%', 
                startangle=90, colors=colores, textprops={'fontsize': 8}, radius=0.8)
        plt.title('Pedidos Completados por Producto', fontsize=12, fontweight='bold')
    else:
        plt.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        plt.title('Pedidos Completados por Producto', fontsize=12, fontweight='bold')
    plt.tight_layout()

    # =========================================================================
    # 4. Demanda por Hospital (Gráfico de Barras Horizontales)
    # =========================================================================
    if gestor_flota.pedidos_completados:
        conteo_hosp = _contar_elementos(p.destination_hospital for p in gestor_flota.pedidos_completados)
        # Ordenar de mayor a menor demanda
        hosp_ordenados = sorted(conteo_hosp.items(), key=lambda x: x[1])
        etiquetas_hosp = [x[0] for x in hosp_ordenados]
        valores_hosp = [x[1] for x in hosp_ordenados]
        
        # Ajuste dinámico de altura basado en el número de hospitales
        alto_dinamico = max(6, len(hosp_ordenados) * 0.4)
        plt.figure(figsize=(10, alto_dinamico))
        plt.gcf().canvas.manager.set_window_title("Demanda por Hospital")
        
        y_pos = np.arange(len(etiquetas_hosp))
        bars_h = plt.barh(y_pos, valores_hosp, color='#1abc9c')
        plt.yticks(y_pos, etiquetas_hosp, fontsize=9)
        plt.xlabel('Cantidad de Entregas', fontsize=10)
        plt.title('Demanda por Hospital (Entregas OK)', fontsize=12, fontweight='bold')
        
        for i, bar in enumerate(bars_h):
            plt.text(bar.get_width() + (max(valores_hosp)*0.01), bar.get_y() + bar.get_height()/2, 
                     str(int(bar.get_width())), va='center', fontsize=9)
    else:
        plt.figure(figsize=(8, 6))
        plt.gcf().canvas.manager.set_window_title("Demanda por Hospital")
        plt.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        plt.title('Demanda por Hospital', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.show()

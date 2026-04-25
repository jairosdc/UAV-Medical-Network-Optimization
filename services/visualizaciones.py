import matplotlib.pyplot as plt
import numpy as np
from collections import Counter

def mostrar_graficas_resultados(gestor_flota, total_generados, minutos_simulacion):
    """
    Genera un dashboard interactivo de 5 gráficas al finalizar la simulación.
    """
    estadisticas = gestor_flota.estadisticas
    
    # Crear una figura grande (Dashboard)
    fig = plt.figure(figsize=(18, 10))
    fig.canvas.manager.set_window_title("Dashboard: Optimización de Red UAV")
    
    # =========================================================================
    # 1. Gráfica de Cantidad de Llamadas (Gráfico de Barras)
    # =========================================================================
    ax1 = plt.subplot(2, 3, 1)
    etiquetas_llamadas = ['Generadas', 'Asignadas', 'Completadas', 'Rechazadas']
    valores_llamadas = [
        total_generados, 
        estadisticas.assigned_calls, 
        estadisticas.completed_calls, 
        estadisticas.rejected_calls
    ]
    colores_llamadas = ['#3498db', '#9b59b6', '#2ecc71', '#e74c3c']
    
    bars = ax1.bar(etiquetas_llamadas, valores_llamadas, color=colores_llamadas)
    ax1.set_ylim(0, max(valores_llamadas) * 1.15) # Margen extra para que los números no toquen el borde superior
    ax1.set_title('Estado de los Pedidos', fontsize=12, fontweight='bold')
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + (max(valores_llamadas) * 0.02), 
                 int(yval), ha='center', va='bottom', fontsize=10, fontweight='bold')

    # =========================================================================
    # 2. Gráfica de Utilización de la Flota (Gráfico de Pastel)
    # =========================================================================
    ax2 = plt.subplot(2, 3, 2)
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

    wedges, texts, autotexts = ax2.pie(
        valores_flota, autopct=my_autopct, colors=colores_flota, 
        startangle=140, explode=explode, shadow=True, textprops={'fontsize': 10, 'fontweight': 'bold'}
    )
    ax2.legend(wedges, etiquetas_flota, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9)
    ax2.set_title('Utilización Global (%)', fontsize=12, fontweight='bold')

    # =========================================================================
    # 3. Distribución de Pedidos por Producto (Gráfico de Pastel)
    # =========================================================================
    ax3 = plt.subplot(2, 3, 3)
    if gestor_flota.pedidos_completados:
        conteo_prod = Counter(p.producto for p in gestor_flota.pedidos_completados)
        etiquetas_prod = list(conteo_prod.keys())
        valores_prod = list(conteo_prod.values())
        
        # Usar colores automáticos pastel de matplotlib
        colores = plt.cm.Set3(np.linspace(0, 1, len(valores_prod)))
        ax3.pie(valores_prod, labels=etiquetas_prod, autopct='%1.1f%%', 
                startangle=90, colors=colores, textprops={'fontsize': 8}, radius=0.8)
        ax3.set_title('Pedidos Completados por Producto', fontsize=12, fontweight='bold')
    else:
        ax3.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        ax3.set_title('Pedidos Completados por Producto', fontsize=12, fontweight='bold')

    # =========================================================================
    # 4. Demanda por Hospital (Gráfico de Barras Horizontales)
    # =========================================================================
    ax4 = plt.subplot(2, 3, 4)
    if gestor_flota.pedidos_completados:
        conteo_hosp = Counter(p.destination_hospital for p in gestor_flota.pedidos_completados)
        # Ordenar de mayor a menor demanda
        hosp_ordenados = sorted(conteo_hosp.items(), key=lambda x: x[1])
        etiquetas_hosp = [x[0] for x in hosp_ordenados]
        valores_hosp = [x[1] for x in hosp_ordenados]
        
        y_pos = np.arange(len(etiquetas_hosp))
        bars_h = ax4.barh(y_pos, valores_hosp, color='#1abc9c')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(etiquetas_hosp, fontsize=9)
        ax4.set_xlabel('Cantidad de Entregas', fontsize=10)
        ax4.set_title('Demanda por Hospital (Entregas OK)', fontsize=12, fontweight='bold')
        
        for i, bar in enumerate(bars_h):
            ax4.text(bar.get_width() + (max(valores_hosp)*0.01), bar.get_y() + bar.get_height()/2, 
                     str(int(bar.get_width())), va='center', fontsize=9)
    else:
        ax4.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        ax4.set_title('Demanda por Hospital', fontsize=12, fontweight='bold')

    # =========================================================================
    # 5. Utilización Detallada por Dron (Barras Apiladas)
    # =========================================================================
    ax5 = plt.subplot(2, 3, (5, 6)) # Ocupa el espacio de 2 columnas para que quepan todos los drones
    drones_ordenados = sorted(gestor_flota.drones.items())
    nombres_drones = [d_id for d_id, _ in drones_ordenados]
    
    # Calcular porcentajes individuales
    pct_vuelos = []
    pct_cargas = []
    pct_disp = []
    
    for _, d in drones_ordenados:
        v = (d.flight_minutes / minutos_simulacion) * 100 if minutos_simulacion else 0
        c = (d.charging_minutes / minutos_simulacion) * 100 if minutos_simulacion else 0
        disp = 100.0 - v - c
        pct_vuelos.append(v)
        pct_cargas.append(c)
        pct_disp.append(disp)

    x = np.arange(len(nombres_drones))
    width = 0.6
    
    # Dibujar barras apiladas
    ax5.bar(x, pct_disp, width, label='Disponible', color='#95a5a6')
    ax5.bar(x, pct_cargas, width, bottom=pct_disp, label='Cargando', color='#e67e22')
    ax5.bar(x, pct_vuelos, width, bottom=np.array(pct_disp)+np.array(pct_cargas), label='Vuelo', color='#f1c40f')
    
    # Configurar ejes
    ax5.set_xticks(x)
    # Rotar las etiquetas si hay muchos drones
    ax5.set_xticklabels(nombres_drones, rotation=45 if len(nombres_drones) > 10 else 0, ha='right', fontsize=8)
    ax5.set_ylabel('% del Tiempo Total', fontsize=10)
    ax5.set_title('Perfil de Utilización por Dron Individual', fontsize=12, fontweight='bold')
    ax5.legend(loc='upper right')

    # Ajustes finales de diseño
    fig.suptitle('Grafica visualizacion simulacion', fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96], h_pad=4.0, w_pad=3.0) # Añade separación horizontal y vertical
    plt.show()

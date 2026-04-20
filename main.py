"""
main.py - Simulador Principal de Red de Drones Hospitalarios
============================================================
Punto de entrada del simulador. Orquesta todos los modulos existentes
para ejecutar una simulacion de eventos discretos (DES).

Flujo:
  1. Inicializar red (hospitales + bases), flota de drones e inventarios.
  2. Pregenerar eventos de consumo del dia (NHPP via GeneradorPedidos).
  3. Bucle minuto a minuto:
     a. Procesar eventos DES vencidos (aterrizajes, fin de recargas).
     b. Procesar consumo de inventario -> genera pedidos si stock <= umbral s.
     c. Despachar pedidos pendientes asignando drones disponibles.
  4. Imprimir metricas de rendimiento.
"""

import heapq

# =============================================================================
# BLOQUE DE CONFIGURACION (modifica estos valores para ajustar la simulacion)
# =============================================================================

MINUTOS_SIMULACION     = 720    # Duracion total: 720 min = 12 horas
DRONES_POR_BASE        = 2      # Cuantos drones se despliegan en cada base/almacen
SEMILLA_ALEATORIA      = 42     # Semilla para reproducibilidad del generador NHPP
IMPRIMIR_EVENTOS_DRONES  = True
   # True = muestra despegues, aterrizajes y carga
IMPRIMIR_EVENTOS_HOSPITAL = False   # True = muestra consumos de medicina y alertas de umbral
STOCK_INICIAL_CERCA_UMBRAL = True  # True = arranca inventarios cerca del umbral s (genera reposiciones rapido)

# =============================================================================
# IMPORTACIONES (solo modulos existentes del repositorio)
# =============================================================================

# Datos de la red: hospitales y bases definidos en el grafo
from hospitales_almacenes_data import HOSPITALS, BASES

# Modelo de inventario con politica (s, Q)
from models.inventario import Inventario

# Servicio de red: calcula distancias reales con Haversine
from services.grafo_distancias_service import ServicioRed

# Controlador de flota: gestiona drones con patron DES
from controllers.gestor_flota_controller import GestorFlotaController

# Generador de eventos de consumo: Proceso Poisson No Homogeneo
from simulators.generador_pedidos import GeneradorPedidos

# Cola de prioridad para pedidos pendientes
from cola_prioridad import GestorPrioridad


def main():
    """Funcion principal del simulador."""

    # =========================================================================
    # FASE 1: INICIALIZACION DE TODOS LOS COMPONENTES
    # =========================================================================

    # -- 1.1 Red logistica (grafo de hospitales y bases) ----------------------
    # ServicioRed carga los nodos de hospitales_almacenes_data.py
    # y ofrece calculo de distancias via Haversine.
    red = ServicioRed()

    # -- 1.2 Flota de drones -------------------------------------------------
    # GestorFlotaController recibe el grafo y gestiona el ciclo de vida
    # de los drones (disponible -> mision -> recarga -> disponible).
    gestor_flota = GestorFlotaController(red)
    gestor_flota.inicializar_flota(drones_por_base=DRONES_POR_BASE)

    # -- 1.3 Inventarios (uno por hospital, uno por base/almacen) -------------
    # Los hospitales tienen stock normal con politica (s, Q).
    # Los almacenes tienen stock x50 y sin umbral de reposicion (no piden).
    inventarios = {}

    lista_hospitales = []
    for nombre, nodo in HOSPITALS.items():
        inv_hosp = Inventario(es_almacen_central=False)
        # Si esta activado, forzamos el stock a un 20% por encima del umbral s
        # para que las primeras unidades consumidas disparen la reposicion.
        if STOCK_INICIAL_CERCA_UMBRAL:
            for nombre_prod, prod in inv_hosp.productos.items():
                prod.stock_fisico = int(prod.umbral_s * 1.2) + 1
        inventarios[nombre] = inv_hosp
        lista_hospitales.append(nodo)

    lista_bases = []
    for nombre, nodo in BASES.items():
        inventarios[nombre] = Inventario(es_almacen_central=True)
        lista_bases.append(nodo)

    # -- 1.4 Generador de eventos de consumo (NHPP) --------------------------
    # Pregenera TODOS los eventos de consumo del dia en una sola pasada.
    # Cada evento = (minuto, hospital, producto) distribuido segun tasas horarias.
    generador = GeneradorPedidos(
        lista_hospitales,
        lista_bases,
        semilla=SEMILLA_ALEATORIA,
    )

    # -- 1.5 Cola de prioridad para pedidos de reposicion ---------------------
    # Ordena los pedidos por: prioridad clinica > timestamp > call_id
    cola_pedidos = GestorPrioridad()

    # -- 1.6 Cola de eventos DES (heap) --------------------------------------
    # Cada evento: (tiempo_float, secuencia_int, tipo_str, datos)
    # La secuencia rompe empates en el heap cuando dos eventos coinciden en tiempo.
    cola_eventos_des = []
    secuencia_evento = 0

    # =========================================================================
    # FASE 2: BUCLE PRINCIPAL DE SIMULACION (minuto a minuto)
    # =========================================================================

    print("=" * 60)
    print("  SIMULADOR DE RED DE DRONES HOSPITALARIOS")
    print("=" * 60)
    print(f"  Duracion:       {MINUTOS_SIMULACION} minutos ({MINUTOS_SIMULACION/60:.0f} horas)")
    print(f"  Drones/base:    {DRONES_POR_BASE}")
    print(f"  Hospitales:     {len(HOSPITALS)}")
    print(f"  Bases:          {len(BASES)}")
    print(f"  Semilla:        {SEMILLA_ALEATORIA}")
    print(f"  Eventos dia:    {generador.total_eventos_dia()}")
    print("-" * 60)
    
    # -- Reporte de Inventario Inicial ----------------------------------------
    print("\n--- INVENTARIO INICIAL (hospitales) ---")
    for nombre_hospital in HOSPITALS:
        inv = inventarios[nombre_hospital]
        print(f"\n  {nombre_hospital}:")
        for nombre_prod, prod in inv.productos.items():
            print(f"    {nombre_prod:25s}  "
                  f"stock={prod.stock_fisico:5d}  "
                  f"umbral_s={prod.umbral_s:4d}")
    print("-" * 60)
    print("\nIniciando simulacion...\n")

    for minuto in range(MINUTOS_SIMULACION):

        # -- PASO A: Procesar eventos DES vencidos ----------------------------
        # Los eventos del heap que ya "ocurrieron" (su tiempo <= minuto actual)
        # se procesan en orden cronologico.
        while cola_eventos_des and cola_eventos_des[0][0] <= minuto:
            _, _, tipo_evento, id_dron = heapq.heappop(cola_eventos_des)

            if tipo_evento == "aterrizaje":
                # El dron llega a destino -> cierra el pedido y entra a recargar.
                tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje(
                    id_dron, minuto
                )
                # Programamos el evento futuro de fin de recarga.
                secuencia_evento += 1
                heapq.heappush(cola_eventos_des, (
                    tiempo_fin_recarga, secuencia_evento, "fin_recarga", id_dron
                ))
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:04d}] ATERRIZAJE {id_dron} "
                          f"-> recarga hasta t={tiempo_fin_recarga:.0f}")

            elif tipo_evento == "fin_recarga":
                # El dron termina de cargar -> vuelve a estar disponible.
                gestor_flota.procesar_evento_fin_recarga(id_dron)
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:04d}] FIN RECARGA {id_dron} -> disponible")

        # -- PASO B: Consumo de inventario y generacion de pedidos ------------
        # GeneradorPedidos procesa los eventos de consumo pregenerados para
        # este minuto. Si algun producto cae al umbral s, se crea un
        # DeliveryCall y se encola automaticamente en cola_pedidos.
        generador.procesar_minuto(minuto, inventarios, cola_pedidos, verbose=IMPRIMIR_EVENTOS_HOSPITAL)

        # -- PASO C: Despachar pedidos pendientes -----------------------------
        # Intentamos asignar drones a los pedidos en orden de prioridad.
        # Si no hay drones disponibles, paramos (los pedidos quedan en cola).
        while cola_pedidos.size() > 0:
            # Verificamos si hay al menos un dron disponible antes de sacar el pedido
            resumen = gestor_flota.obtener_resumen_estado()
            if resumen["available"] == 0:
                break  # No hay drones, los pedidos esperan al siguiente minuto

            # Extraemos el pedido de mayor prioridad
            pedido = cola_pedidos.obtener_siguiente_pedido()

            # El gestor de flota intenta asignar el mejor dron disponible.
            # Retorna el ETA (tiempo de llegada) o None si no es viable.
            eta = gestor_flota.procesar_nuevo_pedido(pedido, minuto)

            if eta is not None:
                # Mision asignada: programamos el evento de aterrizaje
                id_dron_asignado = pedido.assigned_drone_id
                secuencia_evento += 1
                heapq.heappush(cola_eventos_des, (
                    eta, secuencia_evento, "aterrizaje", id_dron_asignado
                ))
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:04d}] DESPACHO pedido #{pedido.call_id} "
                          f"-> {id_dron_asignado} ETA={eta:.0f}")
            else:
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:04d}] RECHAZO pedido #{pedido.call_id}")

    # =========================================================================
    # FASE 3: PROCESAR EVENTOS DES RESTANTES (post-simulacion)
    # =========================================================================
    # Algunos drones aun estan volando o recargando al terminar el bucle.
    # Los procesamos para que las estadisticas reflejen entregas completadas.
    while cola_eventos_des:
        _, _, tipo_evento, id_dron = heapq.heappop(cola_eventos_des)
        if tipo_evento == "aterrizaje":
            gestor_flota.procesar_evento_aterrizaje(id_dron, MINUTOS_SIMULACION)
        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)

    # =========================================================================
    # FASE 4: METRICAS DE RENDIMIENTO
    # =========================================================================
    estadisticas = gestor_flota.estadisticas
    resumen_flota = gestor_flota.obtener_resumen_estado()

    print("\n" + "=" * 60)
    print("  RESULTADOS DE LA SIMULACION")
    print("=" * 60)

    # -- Metricas de pedidos --------------------------------------------------
    print("\n--- PEDIDOS ---")
    print(f"  Total pedidos generados:    {estadisticas.total_calls}")
    print(f"  Pedidos asignados (OK):     {estadisticas.assigned_calls}")
    print(f"  Pedidos rechazados:         {estadisticas.rejected_calls}")
    print(f"  Pedidos completados:        {estadisticas.completed_calls}")
    print(f"  Pedidos aun en cola:        {cola_pedidos.size()}")

    # -- Tasa de servicio -----------------------------------------------------
    if estadisticas.total_calls > 0:
        tasa_servicio = (estadisticas.completed_calls / estadisticas.total_calls) * 100
        print(f"  Tasa de servicio:           {tasa_servicio:.1f}%")

    # -- Estado final de la flota ---------------------------------------------
    print("\n--- FLOTA DE DRONES ---")
    print(f"  Disponibles:  {resumen_flota['available']}")
    print(f"  En mision:    {resumen_flota['mission']}")
    print(f"  Recargando:   {resumen_flota['charging']}")

    # Detalle por dron
    print("\n  Detalle por dron:")
    for id_dron, dron in sorted(gestor_flota.drones.items()):
        print(f"    {id_dron}: base={dron.base_name:12s} "
              f"bateria={dron.battery_percent:6.1f}%  estado={dron.status}")

    # -- Inventario final de cada hospital ------------------------------------
    print("\n--- INVENTARIO FINAL (hospitales) ---")
    for nombre_hospital in HOSPITALS:
        inv = inventarios[nombre_hospital]
        print(f"\n  {nombre_hospital}:")
        for nombre_prod, prod in inv.productos.items():
            indicador = " [!]" if prod.stock_fisico <= prod.umbral_s else ""
            print(f"    {nombre_prod:25s}  "
                  f"stock={prod.stock_fisico:5d}  "
                  f"en_camino={prod.stock_en_camino:5d}  "
                  f"umbral_s={prod.umbral_s:4d}{indicador}")

    print("\n" + "=" * 60)
    print("  FIN DE LA SIMULACION")
    print("=" * 60)


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    main()

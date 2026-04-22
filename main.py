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

# Ajustes de simulación
MINUTOS_SIMULACION       = 7200
DRONES_POR_BASE          = 15
SEMILLA_ALEATORIA        = None      # None = aleatorio real; pon un int (ej. 42) para reproducibilidad
IMPRIMIR_EVENTOS_DRONES  = True
IMPRIMIR_EVENTOS_HOSPITAL = True
STOCK_INICIAL_CERCA_UMBRAL = False

from hospitales_almacenes_data import HOSPITALS, BASES
from models.inventario import Inventario
from services.grafo_distancias_service import ServicioRed
from controllers.gestor_flota_controller import GestorFlotaController
from simulators.generador_pedidos import GeneradorPedidos
from simulators.simulador_clima import SimuladorClima
from cola_prioridad import GestorPrioridad


def main():
    """Funcion principal del simulador."""

    # Definición del grafo
    red = ServicioRed()

    # GestorFlotaController recibe el grafo y gestiona el ciclo de vida
    gestor_flota = GestorFlotaController(red)
    gestor_flota.inicializar_flota(drones_por_base=DRONES_POR_BASE)

    inventarios = {}

    lista_hospitales = []
    for nombre, nodo in HOSPITALS.items():
        inv_hosp = Inventario(es_almacen_central=False)
        # Si esta activado, forzamos el stock a un 20% por encima del umbral s, para forzar rapida reposicion
        if STOCK_INICIAL_CERCA_UMBRAL:
            for nombre_prod, prod in inv_hosp.productos.items():
                prod.stock_fisico = int(prod.umbral_s * 1.2) + 1
        inventarios[nombre] = inv_hosp
        lista_hospitales.append(nodo)

    lista_bases = []
    for nombre, nodo in BASES.items():
        inventarios[nombre] = Inventario(es_almacen_central=True)
        lista_bases.append(nodo)

    generador = GeneradorPedidos(
        lista_hospitales,
        lista_bases,
        semilla=SEMILLA_ALEATORIA,
        duracion_min=MINUTOS_SIMULACION,
    )

    # Cola de prioridad para gestionar los empates de llamada
    cola_pedidos = GestorPrioridad()

    # Simulador de clima estocástico: cambia el clima cada 60 minutos simulados
    clima_sim = SimuladorClima(intervalo_cambio_min=60, semilla=SEMILLA_ALEATORIA)

    # Contadores para estadísticas de clima al final
    conteo_clima = {}          # nombre_estado -> minutos en ese estado
    estado_clima_anterior = None  # Para detectar cambios y mostrarlos

    # 'Calendario de eventos discretos'
    cola_eventos_des = []
    secuencia_evento = 0

    # FASE 2: BUCLE PRINCIPAL DE SIMULACION (minuto a minuto)

    print("=" * 60)
    print("  SIMULADOR DE RED DE DRONES HOSPITALARIOS")
    print("=" * 60)
    dias = MINUTOS_SIMULACION / 1440
    print(f"  Duracion:       {MINUTOS_SIMULACION} min  ({dias:.1f} dias)")
    print(f"  Drones/base:    {DRONES_POR_BASE}")
    print(f"  Hospitales:     {len(HOSPITALS)}")
    print(f"  Bases:          {len(BASES)}")
    semilla_str = str(SEMILLA_ALEATORIA) if SEMILLA_ALEATORIA is not None else "aleatorio (None)"
    print(f"  Semilla:        {semilla_str}")
    print(f"  Eventos totales pregenerados: {generador.total_eventos_dia()}  "
          f"(~{generador.total_eventos_dia()/max(dias,1):.0f}/dia)")
    print(f"  Clima:          Simulado (cambio cada {clima_sim.intervalo_cambio_min} min)")
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

        # -- PASO CLIMA: Actualizar el estado meteorológico -----------------
        estado_clima = clima_sim.actualizar(minuto)
        factor_vel = estado_clima.factor_velocidad

        # Contabilizar minutos en cada estado (para estadísticas finales)
        conteo_clima[estado_clima.nombre] = conteo_clima.get(estado_clima.nombre, 0) + 1

        # Mostrar en consola cuando el clima cambia
        if estado_clima is not estado_clima_anterior:
            print(f"  [t={minuto:05d}] CLIMA       {estado_clima.descripcion}  "
                  f"(velocidad x{factor_vel:.2f})")
            estado_clima_anterior = estado_clima

        # -- PASO A: Procesar eventos DES vencidos ----------------------------
        # Los eventos del heap que ya "ocurrieron" (su tiempo <= minuto actual)
        # se procesan en orden cronologico.
        while cola_eventos_des and cola_eventos_des[0][0] <= minuto:
            evento = heapq.heappop(cola_eventos_des)
            if len(evento) == 4:
                _, _, tipo_evento, id_dron = evento
                decision = None
            else:
                _, _, tipo_evento, id_dron, decision = evento

            if tipo_evento == "llegada_hospital":
                eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                    id_dron, minuto, decision
                )
                if pedido_ok and pedido_ok.producto:
                    inventarios[pedido_ok.destination_hospital].recibir_dron(pedido_ok.producto, pedido_ok.unidades)
                # Programamos regreso a base
                secuencia_evento += 1
                heapq.heappush(cola_eventos_des, (
                    eta_base, secuencia_evento, "aterrizaje_base", id_dron, None
                ))
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:05d}] DESCARGA    {id_dron} en {pedido_ok.destination_hospital} "
                          f"-> regreso ETA={eta_base:.0f}")

            elif tipo_evento == "aterrizaje_base":
                bat_antes = gestor_flota.drones[id_dron].battery_percent
                tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje_base(id_dron, minuto)
                if tiempo_fin_recarga is not None:
                    secuencia_evento += 1
                    heapq.heappush(cola_eventos_des, (
                        tiempo_fin_recarga, secuencia_evento, "fin_recarga", id_dron, None
                    ))
                    if IMPRIMIR_EVENTOS_DRONES:
                        print(f"  [t={minuto:05d}] ATERRIZAJE  {id_dron} en base bat={bat_antes:.1f}% -> RECARGA ETA={tiempo_fin_recarga:.0f}")
                else:
                    if IMPRIMIR_EVENTOS_DRONES:
                        print(f"  [t={minuto:05d}] ATERRIZAJE  {id_dron} en base bat={bat_antes:.1f}% -> DISPONIBLE")

            elif tipo_evento == "fin_recarga":
                gestor_flota.procesar_evento_fin_recarga(id_dron)
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:05d}] FIN RECARGA {id_dron} bat=100.0% -> DISPONIBLE")

        # PASO B: Consumo de inventario y generacion de pedidos 
        # GeneradorPedidos procesa los eventos de consumo pregenerados para
        # este minuto. Si algun producto cae al umbral s, se crea un
        # DeliveryCall y se encola automaticamente en cola_pedidos.
        generador.procesar_minuto(minuto, inventarios, cola_pedidos, verbose=IMPRIMIR_EVENTOS_HOSPITAL)

        # -- PASO C: Despachar pedidos pendientes 
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
            resultado = gestor_flota.procesar_nuevo_pedido(pedido, minuto, factor_vel)

            if resultado is not None:
                eta_ida, decision = resultado
                id_dron_asignado = pedido.assigned_drone_id
                bat_pre = 100.0  
                bat_post = gestor_flota.drones[id_dron_asignado].battery_percent

                if pedido.producto:
                    inventarios[pedido.origin_hospital].enviar_dron(pedido.producto, pedido.unidades)

                secuencia_evento += 1
                heapq.heappush(cola_eventos_des, (
                    eta_ida, secuencia_evento, "llegada_hospital", id_dron_asignado, decision
                ))
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:05d}] DESPACHO    {id_dron_asignado} "
                          f"bat->{bat_post:.1f}% "
                          f"| {pedido.producto} x{pedido.unidades} "
                          f"-> {pedido.destination_hospital}  ETA={eta_ida:.0f}")
            else:
                if IMPRIMIR_EVENTOS_DRONES:
                    print(f"  [t={minuto:05d}] RECHAZO     pedido #{pedido.call_id} "
                          f"({pedido.producto} x{pedido.unidades})")


    # FASE 3: PROCESAR EVENTOS DES RESTANTES (post-simulacion)
    # Algunos drones aun estan volando o recargando al terminar el bucle.
    # Los procesamos para que las estadisticas reflejen entregas completadas.
    while cola_eventos_des:
        evento = heapq.heappop(cola_eventos_des)
        if len(evento) == 4:
            _, _, tipo_evento, id_dron = evento
            decision = None
        else:
            _, _, tipo_evento, id_dron, decision = evento

        if tipo_evento == "llegada_hospital":
            eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(id_dron, MINUTOS_SIMULACION, decision)
            if pedido_ok and pedido_ok.producto:
                inventarios[pedido_ok.destination_hospital].recibir_dron(pedido_ok.producto, pedido_ok.unidades)
            gestor_flota.procesar_evento_aterrizaje_base(id_dron, MINUTOS_SIMULACION)
        elif tipo_evento == "aterrizaje_base":
            gestor_flota.procesar_evento_aterrizaje_base(id_dron, MINUTOS_SIMULACION)
        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)

    # FASE 4: METRICAS DE RENDIMIENTO
    estadisticas = gestor_flota.estadisticas
    resumen_flota = gestor_flota.obtener_resumen_estado()

    print("\n" + "=" * 60)
    print("  RESULTADOS DE LA SIMULACION")
    print("=" * 60)

    # Metricas de pedidos
    total_gen = generador._contador_pedidos   # pedidos realmente generados por NHPP
    print("\n--- PEDIDOS ---")
    print(f"  Pedidos generados (NHPP):   {total_gen}")
    print(f"  Pedidos procesados:         {estadisticas.total_calls}")
    print(f"  Pedidos asignados (OK):     {estadisticas.assigned_calls}")
    print(f"  Pedidos rechazados:         {estadisticas.rejected_calls}")
    print(f"  Pedidos completados:        {estadisticas.completed_calls}")
    print(f"  Pedidos aun en cola:        {cola_pedidos.size()}")
    dias_sim = MINUTOS_SIMULACION / 1440
    if estadisticas.total_calls > 0:
        tasa_servicio = (estadisticas.completed_calls / estadisticas.total_calls) * 100
        print(f"  Tasa de servicio:           {tasa_servicio:.1f}%")
    if dias_sim > 0:
        print(f"  Entregas/dia (completadas): {estadisticas.completed_calls/dias_sim:.1f}")

    # Estado final de la flota 
    print("\n--- FLOTA DE DRONES ---")
    print(f"  Disponibles:  {resumen_flota['available']}")
    print(f"  En mision:    {resumen_flota['mission']}")
    print(f"  Recargando:   {resumen_flota['charging']}")

    # Detalle por dron
    print("\n  Detalle y utilizacion por dron:")
    for id_dron, d in sorted(gestor_flota.drones.items()):
        u_vuelo  = (d.flight_minutes / MINUTOS_SIMULACION) * 100 if MINUTOS_SIMULACION else 0
        u_recarg = (d.charging_minutes / MINUTOS_SIMULACION) * 100 if MINUTOS_SIMULACION else 0
        u_disp   = 100.0 - u_vuelo - u_recarg
        print(f"    {id_dron}: bat={d.battery_percent:5.1f}%  estado={d.status:10s} "
              f"| entregas={d.deliveries_made:2d} "
              f"| vuelo={u_vuelo:4.1f}%  carga={u_recarg:4.1f}%  disp={u_disp:4.1f}%")

    # Inventario final de cada hospital
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

    # Estadísticas meteorológicas
    print("\n--- METEOROLOGÍA (simulada) ---")
    from simulators.simulador_clima import ESTADOS_CLIMA
    for estado in ESTADOS_CLIMA:
        minutos_en_estado = conteo_clima.get(estado.nombre, 0)
        porcentaje = (minutos_en_estado / MINUTOS_SIMULACION) * 100 if MINUTOS_SIMULACION else 0
        print(f"  {estado.descripcion:25s}  "
              f"{minutos_en_estado:5d} min  ({porcentaje:5.1f}%)  "
              f"vel. x{estado.factor_velocidad:.2f}")
    print(f"\n  Cambios de clima registrados: {len(clima_sim.historial)}")

    print("\n" + "=" * 60)
    print("  FIN DE LA SIMULACION")
    print("=" * 60)

# PUNTO DE ENTRADA
if __name__ == "__main__":
    main()

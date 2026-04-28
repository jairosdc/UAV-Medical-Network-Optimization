"""
main.py - Simulador Principal de Red de Drones Hospitalarios
============================================================
Punto de entrada del simulador. Orquesta todos los modulos existentes
para ejecutar una simulacion de eventos discretos (DES).

Flujo:
  1. Inicializar red (hospitales + bases), flota de drones e inventarios.
  2. Pregenerar eventos de consumo del dia y eventos especiales de organos.
  3. Bucle minuto a minuto:
     a. Procesar eventos DES vencidos (aterrizajes, fin de recargas).
     b. Procesar consumo de inventario -> genera pedidos si stock <= umbral s.
     c. Procesar eventos especiales de organos -> genera pedidos hospital-hospital.
     d. Despachar pedidos pendientes asignando drones disponibles.
  4. Imprimir metricas de rendimiento.
"""

import heapq

# Ajustes de simulacion
MINUTOS_SIMULACION        = 525600
DRONES_POR_BASE           = 2
SEMILLA_ALEATORIA         = None
IMPRIMIR_EVENTOS_DRONES   = True
IMPRIMIR_EVENTOS_HOSPITAL = True
IMPRIMIR_EVENTOS_CLIMA    = True
INTERVALO_CAMBIO_CLIMA_MIN = 300
STOCK_INICIAL_CERCA_UMBRAL = True
ACTIVAR_METEOROLOGIA      = True

from hospitales_almacenes_data import HOSPITALS, BASES
from models.inventario import Inventario
from services.grafo_distancias_service import ServicioRed
from controllers.gestor_flota_controller import GestorFlotaController
from simulators.generador_pedidos import GeneradorPedidos
from simulators.simulador_clima import SimuladorClima
from cola_prioridad import GestorPrioridad


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES PARA DIFERENCIAR TIPOS DE PEDIDO
# ---------------------------------------------------------------------------

def es_pedido_inventario(pedido):
    """
    Devuelve True si el pedido corresponde a reposicion de inventario.

    Importante:
    - Los pedidos de inventario SI actualizan stock.
    - Los pedidos de organos NO actualizan stock.
    """
    return getattr(pedido, "tipo_pedido", "inventario") == "inventario"


def es_pedido_organo(pedido):
    """
    Devuelve True si el pedido corresponde a un envio especial de organo.
    """
    return getattr(pedido, "tipo_pedido", "inventario") == "organo"


def descripcion_pedido(pedido):
    """
    Devuelve una descripcion legible para consola.
    """
    if es_pedido_organo(pedido):
        return (
            f"ORGANO {pedido.producto.upper()} "
            f"{pedido.origin_hospital} -> {pedido.destination_hospital}"
        )

    return (
        f"{pedido.producto} x{pedido.unidades} "
        f"{pedido.origin_hospital} -> {pedido.destination_hospital}"
    )


def main():
    """Funcion principal del simulador."""

    # -----------------------------------------------------------------------
    # FASE 1: INICIALIZACION DEL SISTEMA
    # -----------------------------------------------------------------------

    # Definicion del grafo
    red = ServicioRed()

    # Gestor de flota
    gestor_flota = GestorFlotaController(red)
    gestor_flota.inicializar_flota(drones_por_base=DRONES_POR_BASE)

    # Diccionario general de inventarios:
    # - hospitales: inventario real con politica (s, Q)
    # - bases: inventario central ampliado
    inventarios = {}

    # Inicializar hospitales
    lista_hospitales = []

    for nombre, nodo in HOSPITALS.items():
        inv_hosp = Inventario(es_almacen_central=False)

        # Si esta activado, forzamos el stock inicial cerca del umbral
        # para provocar reposiciones rapidamente.
        if STOCK_INICIAL_CERCA_UMBRAL:
            for nombre_prod, prod in inv_hosp.productos.items():
                prod.stock_fisico = int(prod.umbral_s * 1.2) + 1

        inventarios[nombre] = inv_hosp
        lista_hospitales.append(nodo)

    # Inicializar bases / almacenes centrales
    lista_bases = []

    for nombre, nodo in BASES.items():
        inventarios[nombre] = Inventario(es_almacen_central=True)
        lista_bases.append(nodo)

    # Generador de pedidos:
    # - consumo de productos de inventario
    # - eventos especiales de organos
    generador = GeneradorPedidos(
        lista_hospitales,
        lista_bases,
        semilla=SEMILLA_ALEATORIA,
        duracion_min=MINUTOS_SIMULACION,
    )

    # Cola de prioridad
    cola_pedidos = GestorPrioridad()

    # Simulador meteorologico
    clima_sim = SimuladorClima(
        intervalo_cambio_min=INTERVALO_CAMBIO_CLIMA_MIN,
        semilla=SEMILLA_ALEATORIA
    )

    # Contadores de clima
    conteo_clima = {}
    estado_clima_anterior = None

    # Calendario de eventos discretos:
    # elementos del heap:
    # (tiempo_evento, secuencia_evento, tipo_evento, id_dron, decision)
    cola_eventos_des = []
    secuencia_evento = 0

    # -----------------------------------------------------------------------
    # REPORTE INICIAL
    # -----------------------------------------------------------------------

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

    print(
        f"  Eventos totales pregenerados: {generador.total_eventos_dia()}  "
        f"(~{generador.total_eventos_dia() / max(dias, 1):.0f}/dia)"
    )

    clima_str = (
        f"Simulado (cambio cada {clima_sim.intervalo_cambio_min} min)"
        if ACTIVAR_METEOROLOGIA
        else "Desactivado (dia normal)"
    )
    print(f"  Clima:          {clima_str}")
    print("-" * 60)

    # Reporte de inventario inicial
    print("\n--- INVENTARIO INICIAL (hospitales) ---")

    for nombre_hospital in HOSPITALS:
        inv = inventarios[nombre_hospital]
        print(f"\n  {nombre_hospital}:")

        for nombre_prod, prod in inv.productos.items():
            print(
                f"    {nombre_prod:25s}  "
                f"stock={prod.stock_fisico:5d}  "
                f"umbral_s={prod.umbral_s:4d}"
            )

    print("-" * 60)
    print("\nIniciando simulacion...\n")

    # -----------------------------------------------------------------------
    # FASE 2: BUCLE PRINCIPAL DE SIMULACION
    # -----------------------------------------------------------------------

    for minuto in range(MINUTOS_SIMULACION):

        # -------------------------------------------------------------------
        # PASO CLIMA: actualizar meteorologia
        # -------------------------------------------------------------------

        if ACTIVAR_METEOROLOGIA:
            estado_clima = clima_sim.actualizar(minuto)
            factor_vel = estado_clima.factor_velocidad

            conteo_clima[estado_clima.nombre] = (
                conteo_clima.get(estado_clima.nombre, 0) + 1
            )

            if IMPRIMIR_EVENTOS_CLIMA and estado_clima is not estado_clima_anterior:
                print(
                    f"  [t={minuto:05d}] CLIMA       {estado_clima.descripcion}  "
                    f"(velocidad x{factor_vel:.2f})"
                )

            estado_clima_anterior = estado_clima

        else:
            factor_vel = 1.0

        # -------------------------------------------------------------------
        # PASO A: procesar eventos DES vencidos
        # -------------------------------------------------------------------

        while cola_eventos_des and cola_eventos_des[0][0] <= minuto:
            evento = heapq.heappop(cola_eventos_des)

            if len(evento) == 4:
                _, _, tipo_evento, id_dron = evento
                decision = None
            else:
                _, _, tipo_evento, id_dron, decision = evento

            # ---------------------------------------------------------------
            # Llegada del dron al hospital destino
            # ---------------------------------------------------------------

            if tipo_evento == "llegada_hospital":
                eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                    id_dron,
                    minuto,
                    decision
                )

                # MUY IMPORTANTE:
                # Solo los pedidos de inventario actualizan stock.
                # Los organos NO se reciben como inventario.
                if (
                    pedido_ok is not None
                    and es_pedido_inventario(pedido_ok)
                    and pedido_ok.producto
                ):
                    inventarios[pedido_ok.destination_hospital].recibir_dron(
                        pedido_ok.producto,
                        pedido_ok.unidades
                    )

                # Programar regreso a base
                secuencia_evento += 1
                heapq.heappush(
                    cola_eventos_des,
                    (
                        eta_base,
                        secuencia_evento,
                        "aterrizaje_base",
                        id_dron,
                        None
                    )
                )

                if IMPRIMIR_EVENTOS_DRONES and pedido_ok is not None:
                    if es_pedido_organo(pedido_ok):
                        print(
                            f"  [t={minuto:05d}] ENTREGA ORG {id_dron} "
                            f"| {pedido_ok.producto.upper()} "
                            f"{pedido_ok.origin_hospital} -> {pedido_ok.destination_hospital} "
                            f"| regreso ETA={eta_base:.0f}"
                        )
                    else:
                        print(
                            f"  [t={minuto:05d}] DESCARGA    {id_dron} "
                            f"en {pedido_ok.destination_hospital} "
                            f"| {pedido_ok.producto} x{pedido_ok.unidades} "
                            f"-> regreso ETA={eta_base:.0f}"
                        )

            # ---------------------------------------------------------------
            # Aterrizaje del dron en base
            # ---------------------------------------------------------------

            elif tipo_evento == "aterrizaje_base":
                bat_antes = gestor_flota.drones[id_dron].battery_percent

                tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje_base(
                    id_dron,
                    minuto
                )

                if tiempo_fin_recarga is not None:
                    secuencia_evento += 1
                    heapq.heappush(
                        cola_eventos_des,
                        (
                            tiempo_fin_recarga,
                            secuencia_evento,
                            "fin_recarga",
                            id_dron,
                            None
                        )
                    )

                    if IMPRIMIR_EVENTOS_DRONES:
                        print(
                            f"  [t={minuto:05d}] ATERRIZAJE  {id_dron} "
                            f"en base bat={bat_antes:.1f}% "
                            f"-> RECARGA ETA={tiempo_fin_recarga:.0f}"
                        )

                else:
                    if IMPRIMIR_EVENTOS_DRONES:
                        print(
                            f"  [t={minuto:05d}] ATERRIZAJE  {id_dron} "
                            f"en base bat={bat_antes:.1f}% -> DISPONIBLE"
                        )

            # ---------------------------------------------------------------
            # Fin de recarga
            # ---------------------------------------------------------------

            elif tipo_evento == "fin_recarga":
                gestor_flota.procesar_evento_fin_recarga(id_dron)

                if IMPRIMIR_EVENTOS_DRONES:
                    print(
                        f"  [t={minuto:05d}] FIN RECARGA {id_dron} "
                        f"bat=100.0% -> DISPONIBLE"
                    )

        # -------------------------------------------------------------------
        # PASO B: procesar eventos generados para este minuto
        # -------------------------------------------------------------------
        # Aqui pueden aparecer:
        # - consumos de inventario
        # - eventos especiales de organos
        #
        # El propio GeneradorPedidos distingue ambos casos.
        # -------------------------------------------------------------------

        generador.procesar_minuto(
            minuto,
            inventarios,
            cola_pedidos,
            verbose=IMPRIMIR_EVENTOS_HOSPITAL
        )

        # -------------------------------------------------------------------
        # PASO C: despachar pedidos pendientes
        # -------------------------------------------------------------------

        while cola_pedidos.size() > 0:

            # Si no hay drones disponibles, se deja el pedido esperando.
            resumen = gestor_flota.obtener_resumen_estado()

            if resumen["available"] == 0:
                break

            # Extraer pedido con mayor prioridad
            pedido = cola_pedidos.obtener_siguiente_pedido()

            # Intentar asignar dron
            resultado = gestor_flota.procesar_nuevo_pedido(
                pedido,
                minuto,
                factor_vel
            )

            if resultado is not None:
                eta_ida, decision = resultado
                id_dron_asignado = pedido.assigned_drone_id
                bat_post = gestor_flota.drones[id_dron_asignado].battery_percent

                # MUY IMPORTANTE:
                # Solo los pedidos de inventario descuentan stock en el origen.
                # Los organos NO salen de un inventario.
                if es_pedido_inventario(pedido) and pedido.producto:
                    inventarios[pedido.origin_hospital].enviar_dron(
                        pedido.producto,
                        pedido.unidades
                    )

                # Programar llegada al hospital destino
                secuencia_evento += 1
                heapq.heappush(
                    cola_eventos_des,
                    (
                        eta_ida,
                        secuencia_evento,
                        "llegada_hospital",
                        id_dron_asignado,
                        decision
                    )
                )

                if IMPRIMIR_EVENTOS_DRONES:
                    if es_pedido_organo(pedido):
                        print(
                            f"  [t={minuto:05d}] DESPACHO ORG {id_dron_asignado} "
                            f"bat->{bat_post:.1f}% "
                            f"| {pedido.producto.upper()} "
                            f"{pedido.origin_hospital} -> {pedido.destination_hospital} "
                            f"| deadline={pedido.deadline_min:.0f} "
                            f"| ETA={eta_ida:.0f}"
                        )
                    else:
                        print(
                            f"  [t={minuto:05d}] DESPACHO    {id_dron_asignado} "
                            f"bat->{bat_post:.1f}% "
                            f"| {pedido.producto} x{pedido.unidades} "
                            f"{pedido.origin_hospital} -> {pedido.destination_hospital} "
                            f"| ETA={eta_ida:.0f}"
                        )

            else:
                if IMPRIMIR_EVENTOS_DRONES:
                    if es_pedido_organo(pedido):
                        print(
                            f"  [t={minuto:05d}] RECHAZO ORG pedido #{pedido.call_id} "
                            f"({pedido.producto.upper()} "
                            f"{pedido.origin_hospital} -> {pedido.destination_hospital})"
                        )
                    else:
                        print(
                            f"  [t={minuto:05d}] RECHAZO     pedido #{pedido.call_id} "
                            f"({pedido.producto} x{pedido.unidades})"
                        )

    # -----------------------------------------------------------------------
    # FASE 3: PROCESAR EVENTOS DES RESTANTES POST-SIMULACION
    # -----------------------------------------------------------------------
    # Algunos drones pueden seguir volando o recargando cuando acaba el bucle.
    # Se procesan para cerrar estadisticas.
    # -----------------------------------------------------------------------

    while cola_eventos_des:
        evento = heapq.heappop(cola_eventos_des)

        if len(evento) == 4:
            _, _, tipo_evento, id_dron = evento
            decision = None
        else:
            _, _, tipo_evento, id_dron, decision = evento

        if tipo_evento == "llegada_hospital":
            eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                id_dron,
                MINUTOS_SIMULACION,
                decision
            )

            # De nuevo: solo inventario actualiza stock.
            if (
                pedido_ok is not None
                and es_pedido_inventario(pedido_ok)
                and pedido_ok.producto
            ):
                inventarios[pedido_ok.destination_hospital].recibir_dron(
                    pedido_ok.producto,
                    pedido_ok.unidades
                )

            gestor_flota.procesar_evento_aterrizaje_base(
                id_dron,
                MINUTOS_SIMULACION
            )

        elif tipo_evento == "aterrizaje_base":
            gestor_flota.procesar_evento_aterrizaje_base(
                id_dron,
                MINUTOS_SIMULACION
            )

        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)

    # -----------------------------------------------------------------------
    # FASE 4: METRICAS DE RENDIMIENTO
    # -----------------------------------------------------------------------

    estadisticas = gestor_flota.estadisticas
    resumen_flota = gestor_flota.obtener_resumen_estado()

    print("\n" + "=" * 60)
    print("  RESULTADOS DE LA SIMULACION")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Metricas generales de pedidos
    # -----------------------------------------------------------------------

    total_gen = generador._contador_pedidos

    print("\n--- PEDIDOS ---")
    print(f"  Pedidos generados:           {total_gen}")
    print(f"  Pedidos procesados:          {estadisticas.total_calls}")
    print(f"  Pedidos asignados (OK):      {estadisticas.assigned_calls}")
    print(f"  Pedidos rechazados:          {estadisticas.rejected_calls}")
    print(f"  Pedidos completados:         {estadisticas.completed_calls}")
    print(f"  Pedidos aun en cola:         {cola_pedidos.size()}")

    dias_sim = MINUTOS_SIMULACION / 1440

    if estadisticas.total_calls > 0:
        tasa_servicio = (
            estadisticas.completed_calls / estadisticas.total_calls
        ) * 100
        print(f"  Tasa de servicio:            {tasa_servicio:.1f}%")

    if dias_sim > 0:
        print(
            f"  Entregas/dia completadas:    "
            f"{estadisticas.completed_calls / dias_sim:.1f}"
        )

    # -----------------------------------------------------------------------
    # Metricas especificas de organos
    # -----------------------------------------------------------------------

    pedidos_completados = getattr(gestor_flota, "pedidos_completados", [])
    pedidos_rechazados = getattr(gestor_flota, "pedidos_rechazados", [])

    organos_completados = [
        p for p in pedidos_completados
        if es_pedido_organo(p)
    ]

    organos_rechazados = [
        p for p in pedidos_rechazados
        if es_pedido_organo(p)
    ]

    organos_totales = len(organos_completados) + len(organos_rechazados)

    print("\n--- ORGANOS ---")
    print(f"  Organos completados:         {len(organos_completados)}")
    print(f"  Organos rechazados:          {len(organos_rechazados)}")
    print(f"  Organos totales evaluados:   {organos_totales}")

    if organos_totales > 0:
        tasa_org = len(organos_completados) / organos_totales * 100
        print(f"  Tasa de exito organos:       {tasa_org:.1f}%")

    # -----------------------------------------------------------------------
    # Estado final de la flota
    # -----------------------------------------------------------------------

    print("\n--- FLOTA DE DRONES ---")
    print(f"  Disponibles:  {resumen_flota['available']}")
    print(f"  En mision:    {resumen_flota['mission']}")
    print(f"  Recargando:   {resumen_flota['charging']}")

    print("\n  Detalle y utilizacion por dron:")

    for id_dron, d in sorted(gestor_flota.drones.items()):
        u_vuelo = (
            d.flight_minutes / MINUTOS_SIMULACION
        ) * 100 if MINUTOS_SIMULACION else 0

        u_recarg = (
            d.charging_minutes / MINUTOS_SIMULACION
        ) * 100 if MINUTOS_SIMULACION else 0

        u_disp = 100.0 - u_vuelo - u_recarg

        print(
            f"    {id_dron}: bat={d.battery_percent:5.1f}%  "
            f"estado={d.status:10s} "
            f"| entregas={d.deliveries_made:2d} "
            f"| vuelo={u_vuelo:4.1f}%  "
            f"carga={u_recarg:4.1f}%  "
            f"disp={u_disp:4.1f}%"
        )

    # -----------------------------------------------------------------------
    # Inventario final
    # -----------------------------------------------------------------------
    # Aqui NO deben aparecer organos.
    # Si aparecen corazon, pulmon, rinon, pancreas, etc.,
    # entonces se han metido mal en CONFIG_INVENTARIO.
    # -----------------------------------------------------------------------

    print("\n--- INVENTARIO FINAL (hospitales) ---")

    for nombre_hospital in HOSPITALS:
        inv = inventarios[nombre_hospital]
        print(f"\n  {nombre_hospital}:")

        for nombre_prod, prod in inv.productos.items():
            indicador = " [!]" if prod.stock_fisico <= prod.umbral_s else ""

            print(
                f"    {nombre_prod:25s}  "
                f"stock={prod.stock_fisico:5d}  "
                f"en_camino={prod.stock_en_camino:5d}  "
                f"umbral_s={prod.umbral_s:4d}{indicador}"
            )

    # -----------------------------------------------------------------------
    # Estadisticas meteorologicas
    # -----------------------------------------------------------------------

    if ACTIVAR_METEOROLOGIA:
        print("\n--- METEOROLOGIA (simulada) ---")

        from simulators.simulador_clima import ESTADOS_CLIMA

        for estado in ESTADOS_CLIMA:
            minutos_en_estado = conteo_clima.get(estado.nombre, 0)

            porcentaje = (
                minutos_en_estado / MINUTOS_SIMULACION
            ) * 100 if MINUTOS_SIMULACION else 0

            print(
                f"  {estado.descripcion:25s}  "
                f"{minutos_en_estado:5d} min  "
                f"({porcentaje:5.1f}%)  "
                f"vel. x{estado.factor_velocidad:.2f}"
            )

        print(f"\n  Cambios de clima registrados: {len(clima_sim.historial)}")

    print("\n" + "=" * 60)
    print("  FIN DE LA SIMULACION")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # FASE 5: GRAFICAS Y VISUALIZACIONES
    # -----------------------------------------------------------------------

    try:
        from services.visualizaciones import mostrar_graficas_resultados

        print("\n  Generando graficas de resultados...")
        mostrar_graficas_resultados(
            gestor_flota,
            total_gen,
            MINUTOS_SIMULACION
        )

    except ImportError as e:
        print(
            "\n  [Aviso] No se pudieron generar las graficas. "
            f"¿Esta instalado matplotlib? Error: {e}"
        )

    total_vuelo = sum(d.flight_minutes for d in gestor_flota.drones.values())
    total_recarga = sum(d.charging_minutes for d in gestor_flota.drones.values())
    total_tiempo_flota = len(gestor_flota.drones) * MINUTOS_SIMULACION

    print("DEBUG UTILIZACION")
    print("Drones:", len(gestor_flota.drones))
    print("Minutos simulacion:", MINUTOS_SIMULACION)
    print("Tiempo total flota:", total_tiempo_flota)
    print("Minutos vuelo:", total_vuelo)
    print("Minutos recarga:", total_recarga)
    print("Vuelo %:", total_vuelo / total_tiempo_flota * 100)

# PUNTO DE ENTRADA
if __name__ == "__main__":
    main()
"""
experimentacion.py - Motor configurable de simulacion
====================================================

Motor reutilizable:

    resultado = run_simulation(config)

Reglas operativas:
- Reposición: base -> hospital -> vuelve a base.
- Órganos: hospital origen -> hospital destino -> el dron se queda en destino.
"""

import heapq

from hospitales_almacenes_data import HOSPITALS, BASES
from models.inventario import Inventario
from services.grafo_distancias_service import ServicioRed
from controllers.gestor_flota_controller import GestorFlotaController
from simulators.generador_pedidos import GeneradorPedidos
from simulators.simulador_clima import SimuladorClima
from cola_prioridad import GestorPrioridad


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def es_pedido_inventario(pedido):
    return getattr(pedido, "tipo_pedido", "inventario") == "inventario"


def es_pedido_organo(pedido):
    return getattr(pedido, "tipo_pedido", "inventario") == "organo"


def descripcion_pedido(pedido):
    if es_pedido_organo(pedido):
        return (
            f"ORGANO {pedido.producto.upper()} "
            f"{pedido.origin_hospital} -> {pedido.destination_hospital}"
        )

    return (
        f"{pedido.producto} x{pedido.unidades} "
        f"{pedido.origin_hospital} -> {pedido.destination_hospital}"
    )


# ---------------------------------------------------------------------------
# FUNCION PRINCIPAL
# ---------------------------------------------------------------------------

def run_simulation(config=None):
    """
    Ejecuta una simulación completa del sistema.

    Parámetro:
        config: diccionario con parámetros de simulación.

    Devuelve:
        resultado: diccionario con métricas básicas.
    """

    if config is None:
        config = {}

    # -----------------------------------------------------------------------
    # CONFIGURACIÓN
    # -----------------------------------------------------------------------

    MINUTOS_SIMULACION = config.get("minutos_simulacion", 1440)

    DRONES_POR_BASE = config.get("drones_por_base", 2)
    DRONES_POR_HOSPITAL = config.get("drones_por_hospital", 1)

    SEMILLA_ALEATORIA = config.get("semilla", None)

    FACTOR_DEMANDA_INVENTARIO = config.get("factor_demanda_inventario", 1.0)
    FACTOR_DEMANDA_ORGANOS = config.get("factor_demanda_organos", 1.0)
    ESCENARIO_CLIMA = config.get("escenario_clima", "normal")

    ACTIVAR_METEOROLOGIA = config.get("activar_meteorologia", True)
    INTERVALO_CAMBIO_CLIMA_MIN = config.get("intervalo_cambio_clima_min", 300)

    STOCK_INICIAL_CERCA_UMBRAL = config.get("stock_inicial_cerca_umbral", True)

    GENERAR_GRAFICAS = config.get("generar_graficas", False)
    VERBOSE = config.get("verbose", True)

    IMPRIMIR_EVENTOS_DRONES = config.get("imprimir_eventos_drones", False)
    IMPRIMIR_EVENTOS_HOSPITAL = config.get("imprimir_eventos_hospital", False)
    IMPRIMIR_EVENTOS_CLIMA = config.get("imprimir_eventos_clima", False)

    # -----------------------------------------------------------------------
    # FASE 1: INICIALIZACIÓN
    # -----------------------------------------------------------------------

    red = ServicioRed()

    gestor_flota = GestorFlotaController(red)
    gestor_flota.inicializar_flota(
        drones_por_base=DRONES_POR_BASE,
        drones_por_hospital=DRONES_POR_HOSPITAL,
    )

    inventarios = {}
    lista_hospitales = []

    for nombre, nodo in HOSPITALS.items():
        inventario_hospital = Inventario(es_almacen_central=False)

        if STOCK_INICIAL_CERCA_UMBRAL:
            for _, producto in inventario_hospital.productos.items():
                producto.stock_fisico = int(producto.umbral_s * 1.2) + 1

        inventarios[nombre] = inventario_hospital
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
        factor_demanda_inventario=FACTOR_DEMANDA_INVENTARIO,
        factor_demanda_organos=FACTOR_DEMANDA_ORGANOS,
    )

    cola_pedidos = GestorPrioridad()

    clima_sim = SimuladorClima(
        intervalo_cambio_min=INTERVALO_CAMBIO_CLIMA_MIN,
        semilla=SEMILLA_ALEATORIA,
        escenario_clima=ESCENARIO_CLIMA,
    )

    conteo_clima = {}
    estado_clima_anterior = None

    cola_eventos_des = []
    secuencia_evento = 0

    historial_longitud_cola = []

    # -----------------------------------------------------------------------
    # REPORTE INICIAL
    # -----------------------------------------------------------------------

    if VERBOSE:
        print("=" * 60)
        print("  SIMULADOR DE RED DE DRONES HOSPITALARIOS")
        print("=" * 60)

        dias = MINUTOS_SIMULACION / 1440

        print(f"  Duracion:          {MINUTOS_SIMULACION} min  ({dias:.1f} dias)")
        print(f"  Drones/base:       {DRONES_POR_BASE}")
        print(f"  Drones/hospital:   {DRONES_POR_HOSPITAL}")
        print(f"  Hospitales:        {len(HOSPITALS)}")
        print(f"  Bases:             {len(BASES)}")

        print(f"  Demanda inventario: x{FACTOR_DEMANDA_INVENTARIO}")
        print(f"  Demanda organos:    x{FACTOR_DEMANDA_ORGANOS}")
        print(f"  Escenario clima:    {ESCENARIO_CLIMA}")

        semilla_str = (
            str(SEMILLA_ALEATORIA)
            if SEMILLA_ALEATORIA is not None
            else "aleatorio (None)"
        )

        print(f"  Semilla:           {semilla_str}")

        print(
            f"  Eventos pregenerados: {generador.total_eventos_dia()}  "
            f"(~{generador.total_eventos_dia() / max(dias, 1):.0f}/dia)"
        )

        clima_str = (
            f"Simulado (cambio cada {clima_sim.intervalo_cambio_min} min)"
            if ACTIVAR_METEOROLOGIA
            else "Desactivado"
        )

        print(f"  Clima:             {clima_str}")
        print("-" * 60)

    # -----------------------------------------------------------------------
    # FASE 2: BUCLE PRINCIPAL
    # -----------------------------------------------------------------------

    for minuto in range(MINUTOS_SIMULACION):

        # -------------------------------------------------------------------
        # PASO CLIMA
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

            if tipo_evento == "llegada_hospital":
                eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                    id_dron,
                    minuto,
                    decision,
                )

                if (
                    pedido_ok is not None
                    and es_pedido_inventario(pedido_ok)
                    and pedido_ok.producto
                ):
                    inventarios[pedido_ok.destination_hospital].recibir_dron(
                        pedido_ok.producto,
                        pedido_ok.unidades,
                    )

                if eta_base is not None:
                    secuencia_evento += 1
                    heapq.heappush(
                        cola_eventos_des,
                        (
                            eta_base,
                            secuencia_evento,
                            "aterrizaje_base",
                            id_dron,
                            None,
                        ),
                    )

                if IMPRIMIR_EVENTOS_DRONES and pedido_ok is not None:
                    if es_pedido_organo(pedido_ok):
                        print(
                            f"  [t={minuto:05d}] ENTREGA ORG {id_dron} "
                            f"| {pedido_ok.producto.upper()} "
                            f"{pedido_ok.origin_hospital} -> {pedido_ok.destination_hospital} "
                            f"| dron queda en destino"
                        )
                    else:
                        print(
                            f"  [t={minuto:05d}] DESCARGA    {id_dron} "
                            f"en {pedido_ok.destination_hospital} "
                            f"| {pedido_ok.producto} x{pedido_ok.unidades} "
                            f"-> regreso ETA={eta_base:.0f}"
                        )

            elif tipo_evento == "aterrizaje_base":
                bat_antes = gestor_flota.drones[id_dron].battery_percent

                tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje_base(
                    id_dron,
                    minuto,
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
                            None,
                        ),
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

            elif tipo_evento == "fin_recarga":
                gestor_flota.procesar_evento_fin_recarga(id_dron)

                if IMPRIMIR_EVENTOS_DRONES:
                    print(
                        f"  [t={minuto:05d}] FIN RECARGA {id_dron} "
                        f"bat=100.0% -> DISPONIBLE"
                    )

        # -------------------------------------------------------------------
        # PASO B: generar pedidos del minuto
        # -------------------------------------------------------------------

        generador.procesar_minuto(
            minuto,
            inventarios,
            cola_pedidos,
            verbose=IMPRIMIR_EVENTOS_HOSPITAL,
        )

        # -------------------------------------------------------------------
        # PASO C: despachar cola por rondas
        # -------------------------------------------------------------------
        # Se intenta asignar cada pedido como máximo una vez por minuto.
        # Si no se puede asignar, vuelve a la cola.
        # -------------------------------------------------------------------

        pedidos_ronda = cola_pedidos.extraer_ronda_ordenada()

        for pedido in pedidos_ronda:

            resumen = gestor_flota.obtener_resumen_estado()

            if es_pedido_organo(pedido) and resumen.get("hospital_available", 0) == 0:
                cola_pedidos.añadir_pedido(pedido)
                continue

            if es_pedido_inventario(pedido) and resumen.get("base_available", 0) == 0:
                cola_pedidos.añadir_pedido(pedido)
                continue

            resultado = gestor_flota.procesar_nuevo_pedido(
                pedido,
                minuto,
                factor_vel,
            )

            if resultado is None:
                cola_pedidos.añadir_pedido(pedido)

                if IMPRIMIR_EVENTOS_DRONES:
                    if es_pedido_organo(pedido):
                        print(
                            f"  [t={minuto:05d}] ESPERA ORG pedido #{pedido.call_id} "
                            f"({pedido.producto.upper()} "
                            f"{pedido.origin_hospital} -> {pedido.destination_hospital})"
                        )
                    else:
                        print(
                            f"  [t={minuto:05d}] ESPERA INV pedido #{pedido.call_id} "
                            f"({pedido.producto} x{pedido.unidades} "
                            f"{pedido.origin_hospital} -> {pedido.destination_hospital})"
                        )

                continue

            eta_ida, decision = resultado
            id_dron_asignado = pedido.assigned_drone_id
            bat_post = gestor_flota.drones[id_dron_asignado].battery_percent

            if es_pedido_inventario(pedido) and pedido.producto:
                inventarios[pedido.origin_hospital].enviar_dron(
                    pedido.producto,
                    pedido.unidades,
                )

            secuencia_evento += 1
            heapq.heappush(
                cola_eventos_des,
                (
                    eta_ida,
                    secuencia_evento,
                    "llegada_hospital",
                    id_dron_asignado,
                    decision,
                ),
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

        historial_longitud_cola.append(cola_pedidos.size())

    # -----------------------------------------------------------------------
    # FASE 3: PROCESAR EVENTOS DES RESTANTES POST-SIMULACION
    # -----------------------------------------------------------------------
    # Se completan misiones ya asignadas, pero no se despachan pedidos nuevos.
    # -----------------------------------------------------------------------

    while cola_eventos_des:
        evento = heapq.heappop(cola_eventos_des)

        if len(evento) == 4:
            tiempo_evento, _, tipo_evento, id_dron = evento
            decision = None
        else:
            tiempo_evento, _, tipo_evento, id_dron, decision = evento

        if tipo_evento == "llegada_hospital":
            eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                id_dron,
                tiempo_evento,
                decision,
            )

            if (
                pedido_ok is not None
                and es_pedido_inventario(pedido_ok)
                and pedido_ok.producto
            ):
                inventarios[pedido_ok.destination_hospital].recibir_dron(
                    pedido_ok.producto,
                    pedido_ok.unidades,
                )

            if eta_base is not None:
                tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje_base(
                    id_dron,
                    eta_base,
                )

                if tiempo_fin_recarga is not None:
                    gestor_flota.procesar_evento_fin_recarga(id_dron)

        elif tipo_evento == "aterrizaje_base":
            tiempo_fin_recarga = gestor_flota.procesar_evento_aterrizaje_base(
                id_dron,
                tiempo_evento,
            )

            if tiempo_fin_recarga is not None:
                gestor_flota.procesar_evento_fin_recarga(id_dron)

        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)

    # -----------------------------------------------------------------------
    # FASE 4: MÉTRICAS
    # -----------------------------------------------------------------------

    estadisticas = gestor_flota.estadisticas
    resumen_flota = gestor_flota.obtener_resumen_estado()

    total_gen = generador._contador_pedidos

    pedidos_completados = getattr(gestor_flota, "pedidos_completados", [])
    pedidos_rechazados = getattr(gestor_flota, "pedidos_rechazados", [])
    pedidos_pendientes = getattr(cola_pedidos, "pedidos_pendientes", [])

    organos_completados = [
        pedido for pedido in pedidos_completados
        if es_pedido_organo(pedido)
    ]

    organos_rechazados = [
        pedido for pedido in pedidos_rechazados
        if es_pedido_organo(pedido)
    ]

    organos_pendientes = [
        pedido for pedido in pedidos_pendientes
        if es_pedido_organo(pedido)
    ]

    inventario_completado = [
        pedido for pedido in pedidos_completados
        if es_pedido_inventario(pedido)
    ]

    inventario_pendiente = [
        pedido for pedido in pedidos_pendientes
        if es_pedido_inventario(pedido)
    ]

    organos_totales = estadisticas.organ_calls

    total_vuelo = sum(dron.flight_minutes for dron in gestor_flota.drones.values())
    total_recarga = sum(dron.charging_minutes for dron in gestor_flota.drones.values())
    total_tiempo_flota = len(gestor_flota.drones) * MINUTOS_SIMULACION

    utilizacion_vuelo = (
        total_vuelo / total_tiempo_flota
        if total_tiempo_flota > 0
        else 0
    )

    utilizacion_operativa = (
        (total_vuelo + total_recarga) / total_tiempo_flota
        if total_tiempo_flota > 0
        else 0
    )

    longitud_media_cola = (
        sum(historial_longitud_cola) / len(historial_longitud_cola)
        if historial_longitud_cola
        else 0
    )

    longitud_maxima_cola = (
        max(historial_longitud_cola)
        if historial_longitud_cola
        else 0
    )

    tasa_servicio = (
        estadisticas.completed_calls / estadisticas.total_calls
        if estadisticas.total_calls > 0
        else 0
    )

    tasa_exito_organos = (
        estadisticas.organ_on_time / organos_totales
        if organos_totales > 0
        else 0
    )

    resultado = {
        "minutos_simulacion": MINUTOS_SIMULACION,
        "drones_por_base": DRONES_POR_BASE,
        "drones_por_hospital": DRONES_POR_HOSPITAL,
        "total_drones": len(gestor_flota.drones),
        "numero_hospitales": len(HOSPITALS),
        "numero_bases": len(BASES),

        "factor_demanda_inventario": FACTOR_DEMANDA_INVENTARIO,
        "factor_demanda_organos": FACTOR_DEMANDA_ORGANOS,
        "escenario_clima": ESCENARIO_CLIMA,

        "pedidos_generados": total_gen,
        "pedidos_procesados": estadisticas.total_calls,
        "pedidos_asignados": estadisticas.assigned_calls,
        "pedidos_completados": estadisticas.completed_calls,
        "pedidos_rechazados": estadisticas.rejected_calls,
        "pedidos_en_cola": cola_pedidos.size(),
        "tasa_servicio": tasa_servicio,

        "inventario_completado": len(inventario_completado),
        "inventario_pendiente": len(inventario_pendiente),

        "organos_totales": organos_totales,
        "organos_completados": len(organos_completados),
        "organos_rechazados": len(organos_rechazados),
        "organos_pendientes": len(organos_pendientes),
        "organos_on_time": estadisticas.organ_on_time,
        "organos_late": estadisticas.organ_late,
        "tasa_exito_organos": tasa_exito_organos,

        "utilizacion_vuelo_pct": utilizacion_vuelo * 100,
        "utilizacion_operativa_pct": utilizacion_operativa * 100,
        "tiempo_total_vuelo": total_vuelo,
        "tiempo_total_recarga": total_recarga,

        "longitud_media_cola": longitud_media_cola,
        "longitud_maxima_cola": longitud_maxima_cola,

        "resumen_flota": resumen_flota,
        "conteo_clima": conteo_clima,
    }

    # -----------------------------------------------------------------------
    # REPORTE FINAL
    # -----------------------------------------------------------------------

    if VERBOSE:
        print("\n" + "=" * 60)
        print("  RESULTADOS DE LA SIMULACION")
        print("=" * 60)

        print("\n--- PEDIDOS ---")
        print(f"  Pedidos generados:           {total_gen}")
        print(f"  Pedidos procesados:          {estadisticas.total_calls}")
        print(f"  Pedidos asignados:           {estadisticas.assigned_calls}")
        print(f"  Pedidos rechazados:          {estadisticas.rejected_calls}")
        print(f"  Pedidos completados:         {estadisticas.completed_calls}")
        print(f"  Pedidos aun en cola:         {cola_pedidos.size()}")
        print(f"  Tasa de servicio:            {tasa_servicio * 100:.1f}%")

        print("\n--- INVENTARIO ---")
        print(f"  Inventario completado:       {len(inventario_completado)}")
        print(f"  Inventario pendiente:        {len(inventario_pendiente)}")

        print("\n--- ORGANOS ---")
        print(f"  Organos totales:             {organos_totales}")
        print(f"  Organos completados:         {len(organos_completados)}")
        print(f"  Organos rechazados:          {len(organos_rechazados)}")
        print(f"  Organos pendientes:          {len(organos_pendientes)}")
        print(f"  Organos a tiempo:            {estadisticas.organ_on_time}")
        print(f"  Organos tarde:               {estadisticas.organ_late}")
        print(f"  Tasa exito organos:          {tasa_exito_organos * 100:.1f}%")

        print("\n--- COLA ---")
        print(f"  Longitud media de cola:      {longitud_media_cola:.2f}")
        print(f"  Longitud maxima de cola:     {longitud_maxima_cola}")

        print("\n--- FLOTA DE DRONES ---")
        print(f"  Total drones:                {len(gestor_flota.drones)}")
        print(f"  Drones base total:           {resumen_flota.get('base_total', 0)}")
        print(f"  Drones hospital total:       {resumen_flota.get('hospital_total', 0)}")
        print(f"  Disponibles total:           {resumen_flota.get('available', 0)}")
        print(f"  Disponibles base:            {resumen_flota.get('base_available', 0)}")
        print(f"  Disponibles hospital:        {resumen_flota.get('hospital_available', 0)}")
        print(f"  En mision:                   {resumen_flota.get('mission', 0)}")
        print(f"  Volviendo a base:            {resumen_flota.get('returning', 0)}")
        print(f"  Recargando:                  {resumen_flota.get('charging', 0)}")
        print(f"  Utilizacion vuelo:           {utilizacion_vuelo * 100:.2f}%")
        print(f"  Utilizacion operativa:       {utilizacion_operativa * 100:.2f}%")

        if ACTIVAR_METEOROLOGIA:
            print("\n--- METEOROLOGIA ---")
            for nombre_estado, minutos_estado in conteo_clima.items():
                porcentaje = (
                    minutos_estado / MINUTOS_SIMULACION
                ) * 100 if MINUTOS_SIMULACION else 0

                print(
                    f"  {nombre_estado:20s} "
                    f"{minutos_estado:5d} min "
                    f"({porcentaje:5.1f}%)"
                )

        print("\n" + "=" * 60)
        print("  FIN DE LA SIMULACION")
        print("=" * 60)

    # -----------------------------------------------------------------------
    # GRÁFICAS OPCIONALES
    # -----------------------------------------------------------------------

    if GENERAR_GRAFICAS:
        try:
            from services.visualizaciones import mostrar_graficas_resultados

            mostrar_graficas_resultados(
                gestor_flota,
                total_gen,
                MINUTOS_SIMULACION,
                historial_longitud_cola=historial_longitud_cola,
                cola_pedidos=cola_pedidos,
            )

        except ImportError as error:
            if VERBOSE:
                print(
                    "\n  [Aviso] No se pudieron generar las graficas. "
                    f"¿Está instalado matplotlib? Error: {error}"
                )

    return resultado
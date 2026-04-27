"""
main.py - Entrada funcional del simulador de drones hospitalarios.

Modos disponibles:
  python main.py --list-hospitals
  python main.py --mode single --origin "La Paz" --destination "12 de Octubre"
  python main.py --mode fleet --minutes 1440 --drones-per-base 2
"""

import argparse
import heapq
from dataclasses import dataclass


# Ajustes de simulacion

MINUTOS_SIMULACION       = 1440      

MINUTOS_SIMULACION       = 525600     

DRONES_POR_BASE          = 2
SEMILLA_ALEATORIA        = None       
IMPRIMIR_EVENTOS_DRONES  = True
IMPRIMIR_EVENTOS_HOSPITAL = False
IMPRIMIR_EVENTOS_CLIMA   = True       
INTERVALO_CAMBIO_CLIMA_MIN = 300
STOCK_INICIAL_CERCA_UMBRAL = False
ACTIVAR_METEOROLOGIA     = True       

from hospitales_almacenes_data import HOSPITALS, BASES
from models.inventario import Inventario
from services.grafo_distancias_service import ServicioRed
from controllers.gestor_flota_controller import GestorFlotaController
from simulators.generador_pedidos import GeneradorPedidos
from simulators.simulador_clima import SimuladorClima

from cola_prioridad import GestorPrioridad
from controllers.gestor_flota_controller import GestorFlotaController
from controllers.simulation_controller import SimulationController
from hospitales_almacenes_data import BASES, HOSPITALS
from models.clases_models import MissionRequest
from models.inventario import Inventario
from parametros_globales import (
    DEFAULT_CALL_PROBABILITY_PER_MIN,
    DEFAULT_SIMULATION_MINUTES,
)
from services.grafo_distancias_service import ServicioRed
from simulators.generador_pedidos import GeneradorPedidos
from simulators.simulador_clima import ESTADOS_CLIMA, SimuladorClima


@dataclass
class FleetRunResult:
    gestor_flota: GestorFlotaController
    generador: GeneradorPedidos
    cola_pedidos: GestorPrioridad
    inventarios: dict
    conteo_clima: dict
    clima_sim: SimuladorClima


def build_parser():
    parser = argparse.ArgumentParser(
        description="Simulador de red de drones para transporte medico."
    )
    parser.add_argument("--list-hospitals", action="store_true")
    parser.add_argument("--list-bases", action="store_true")
    parser.add_argument("--mode", choices=("single", "fleet"), default="fleet")

    parser.add_argument("--origin", help="Hospital origen para modo single.")
    parser.add_argument("--destination", help="Hospital destino para modo single.")
    parser.add_argument("--payload", type=float, default=1.0, help="Carga en kg.")
    parser.add_argument("--battery", type=float, default=100.0, help="Bateria inicial en porcentaje.")
    parser.add_argument("--date", help="Fecha YYYY-MM-DD para semilla meteorologica en modo single.")
    parser.add_argument("--ignore-weather", action="store_true", help="Ignora meteorologia en modo single.")

    parser.add_argument("--minutes", type=int, default=DEFAULT_SIMULATION_MINUTES)
    parser.add_argument("--drones-per-base", type=int, default=2)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--weather-change-min", type=int, default=300)
    parser.add_argument("--no-weather", action="store_true", help="Desactiva meteorologia en modo fleet.")
    parser.add_argument("--verbose", action="store_true", help="Muestra eventos de drones y consumo.")
    parser.add_argument("--show-inventory", action="store_true", help="Muestra inventario inicial y final.")
    parser.add_argument("--stock-near-threshold", action="store_true", help="Arranca hospitales cerca del umbral s.")
    parser.add_argument("--graphs", action="store_true", help="Muestra graficas matplotlib al terminar.")
    parser.add_argument(
        "--demand-scale",
        type=float,
        default=None,
        help="Multiplicador de demanda del generador NHPP.",
    )
    parser.add_argument(
        "--call-probability",
        type=float,
        default=DEFAULT_CALL_PROBABILITY_PER_MIN,
        help="Compatibilidad con demos antiguas; se traduce a escala de demanda.",
    )
    return parser


def list_network(red, show_hospitals=False, show_bases=False):
    if show_hospitals:
        print("Hospitales disponibles:")
        for nombre in red.listar_hospitales():
            nodo = red.obtener_hospital(nombre)
            print(f" - {nodo.nombre} ({nodo.lat:.4f}, {nodo.lon:.4f})")

    if show_bases:
        print("Bases disponibles:")
        for nombre in red.listar_bases():
            nodo = red.obtener_base(nombre)
            print(f" - {nodo.nombre} ({nodo.lat:.4f}, {nodo.lon:.4f})")


def run_single_mode(args):
    if not args.origin or not args.destination:
        raise SystemExit("Modo single requiere --origin y --destination.")

    request = MissionRequest(
        origin_hospital=args.origin,
        destination_hospital=args.destination,
        payload_kg=args.payload,
        battery_start_percent=args.battery,
        ignore_weather=args.ignore_weather,
        date=args.date,
    )
    result = SimulationController().simulate_mission(request)

    print("=" * 58)
    print(" RESULTADO MISION")
    print("=" * 58)
    print(f"Viable: {'SI' if result.feasible else 'NO'}")
    print(f"Base seleccionada: {result.selected_base or '-'}")
    print(f"Ruta: {request.origin_hospital} -> {request.destination_hospital}")
    print(f"Carga: {request.payload_kg:.2f} kg")
    print(f"Distancia base -> origen: {result.distance_base_to_origin_km:.2f} km")
    print(f"Distancia origen -> destino: {result.distance_origin_to_destination_km:.2f} km")
    print(f"Distancia destino -> base: {result.distance_destination_to_base_km:.2f} km")
    print(f"Distancia total: {result.distance_total_km:.2f} km")
    print(f"Tiempo entrega estimado: {result.estimated_delivery_time_min} min")
    print(f"Tiempo total estimado: {result.estimated_time_min} min")
    print(f"Bateria inicial: {result.battery_start_percent:.1f}%")
    print(f"Bateria final estimada: {result.battery_end_percent:.1f}%")
    print(f"Clima OK: {result.weather_ok} ({result.weather_description})")

    if result.reasons:
        print("\nMotivos / observaciones:")
        for reason in result.reasons:
            print(f" - {reason}")

    return result


def build_inventories(stock_near_threshold=False):
    inventarios = {}

    for nombre in HOSPITALS:
        inventario = Inventario(es_almacen_central=False)
        if stock_near_threshold:
            for producto in inventario.productos.values():
                producto.stock_fisico = producto.umbral_s + 1
        inventarios[nombre] = inventario

    for nombre in BASES:
        inventarios[nombre] = Inventario(es_almacen_central=True)

    return inventarios


def print_inventory(title, inventarios):
    print(f"\n--- {title} ---")
    for nombre_hospital in HOSPITALS:
        inv = inventarios[nombre_hospital]
        print(f"\n{nombre_hospital}:")
        for nombre_prod, prod in inv.productos.items():
            marker = " [!]" if prod.stock_fisico <= prod.umbral_s else ""
            print(
                f"  {nombre_prod:24s} stock={prod.stock_fisico:5d} "
                f"en_camino={prod.stock_en_camino:5d} umbral_s={prod.umbral_s:4d}{marker}"
            )


def resolve_demand_scale(args):
    if args.demand_scale is not None:
        return max(0.0, args.demand_scale)

    if DEFAULT_CALL_PROBABILITY_PER_MIN <= 0:
        return 1.0

    return max(0.0, args.call_probability / DEFAULT_CALL_PROBABILITY_PER_MIN)


def run_fleet_mode(args):
    if args.minutes < 0:
        raise SystemExit("--minutes debe ser mayor o igual que 0.")
    if args.drones_per_base < 0:
        raise SystemExit("--drones-per-base debe ser mayor o igual que 0.")

    red = ServicioRed()
    gestor_flota = GestorFlotaController(red)
    gestor_flota.inicializar_flota(drones_por_base=args.drones_per_base)

    inventarios = build_inventories(args.stock_near_threshold)
    hospitales = list(HOSPITALS.values())
    bases = list(BASES.values())
    demand_scale = resolve_demand_scale(args)

    generador = GeneradorPedidos(
        hospitales,
        bases,
        semilla=args.seed,
        duracion_min=args.minutes,
        escala_demanda=demand_scale,
    )
    cola_pedidos = GestorPrioridad()
    clima_sim = SimuladorClima(
        intervalo_cambio_min=args.weather_change_min,
        semilla=args.seed,
    )
    conteo_clima = {}
    estado_clima_anterior = None
    cola_eventos_des = []
    secuencia_evento = 0

    print("=" * 58)
    print(" SIMULADOR DE RED DE DRONES HOSPITALARIOS")
    print("=" * 58)
    print(f"Duracion: {args.minutes} min ({args.minutes / 1440:.2f} dias)")
    print(f"Drones/base: {args.drones_per_base}")
    print(f"Hospitales: {len(HOSPITALS)}")
    print(f"Bases: {len(BASES)}")
    print(f"Semilla: {args.seed if args.seed is not None else 'aleatoria'}")
    print(f"Escala demanda: x{demand_scale:.2f}")
    print(f"Eventos pregenerados: {generador.total_eventos_dia()}")
    print(f"Clima: {'desactivado' if args.no_weather else 'simulado'}")

    if args.show_inventory:
        print_inventory("INVENTARIO INICIAL (hospitales)", inventarios)

    for minuto in range(args.minutes):
        if args.no_weather:
            factor_velocidad = 1.0
        else:
            estado_clima = clima_sim.actualizar(minuto)
            factor_velocidad = estado_clima.factor_velocidad
            conteo_clima[estado_clima.nombre] = conteo_clima.get(estado_clima.nombre, 0) + 1
            if args.verbose and estado_clima is not estado_clima_anterior:
                print(
                    f"[t={minuto:05d}] CLIMA      {estado_clima.descripcion} "
                    f"(velocidad x{factor_velocidad:.2f})"
                )
            estado_clima_anterior = estado_clima

        secuencia_evento = process_due_events(
            cola_eventos_des,
            gestor_flota,
            inventarios,
            minuto,
            secuencia_evento,
            args.verbose,
        )

        generador.procesar_minuto(
            minuto,
            inventarios,
            cola_pedidos,
            verbose=args.verbose,
        )

        secuencia_evento = dispatch_pending_orders(
            cola_pedidos,
            cola_eventos_des,
            gestor_flota,
            inventarios,
            minuto,
            factor_velocidad,
            secuencia_evento,
            args.verbose,
        )

    drain_remaining_events(cola_eventos_des, gestor_flota, inventarios, args.verbose)
    print_fleet_summary(
        gestor_flota,
        generador,
        cola_pedidos,
        inventarios,
        conteo_clima,
        clima_sim,
        args,
    )

    if args.graphs:
        from services.visualizaciones import mostrar_graficas_resultados

        mostrar_graficas_resultados(
            gestor_flota=gestor_flota,
            total_generados=generador._contador_pedidos,
            minutos_simulacion=args.minutes,
        )

    return FleetRunResult(
        gestor_flota=gestor_flota,
        generador=generador,
        cola_pedidos=cola_pedidos,
        inventarios=inventarios,
        conteo_clima=conteo_clima,
        clima_sim=clima_sim,
    )


def process_due_events(
    cola_eventos_des,
    gestor_flota,
    inventarios,
    minuto,
    secuencia_evento,
    verbose,
):
    while cola_eventos_des and cola_eventos_des[0][0] <= minuto:
        event_time, _, tipo_evento, id_dron, decision = heapq.heappop(cola_eventos_des)

        if tipo_evento == "llegada_hospital":
            eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                id_dron, event_time, decision
            )
            if pedido_ok and pedido_ok.producto:
                inventarios[pedido_ok.destination_hospital].recibir_dron(
                    pedido_ok.producto,
                    pedido_ok.unidades,
                )
            secuencia_evento += 1
            heapq.heappush(
                cola_eventos_des,
                (eta_base, secuencia_evento, "aterrizaje_base", id_dron, None),
            )
            if verbose and pedido_ok:
                print(
                    f"[t={minuto:05d}] DESCARGA   {id_dron} en "
                    f"{pedido_ok.destination_hospital} -> regreso ETA={eta_base:.0f}"
                )

        elif tipo_evento == "aterrizaje_base":
            battery_before = gestor_flota.drones[id_dron].battery_percent
            recharge_end = gestor_flota.procesar_evento_aterrizaje_base(id_dron, event_time)
            if recharge_end is not None:
                secuencia_evento += 1
                heapq.heappush(
                    cola_eventos_des,
                    (recharge_end, secuencia_evento, "fin_recarga", id_dron, None),
                )
                if verbose:
                    print(
                        f"[t={minuto:05d}] ATERRIZAJE {id_dron} "
                        f"bat={battery_before:.1f}% -> RECARGA ETA={recharge_end:.0f}"
                    )
            elif verbose:
                print(
                    f"[t={minuto:05d}] ATERRIZAJE {id_dron} "
                    f"bat={battery_before:.1f}% -> DISPONIBLE"
                )

        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)
            if verbose:
                print(f"[t={minuto:05d}] FIN RECARGA {id_dron} bat=100.0% -> DISPONIBLE")

    return secuencia_evento


def dispatch_pending_orders(
    cola_pedidos,
    cola_eventos_des,
    gestor_flota,
    inventarios,
    minuto,
    factor_velocidad,
    secuencia_evento,
    verbose,
):
    while cola_pedidos.size() > 0:
        resumen = gestor_flota.obtener_resumen_estado()
        if resumen["available"] == 0:
            break

        pedido = cola_pedidos.obtener_siguiente_pedido()
        resultado = gestor_flota.procesar_nuevo_pedido(
            pedido,
            minuto,
            factor_velocidad,
        )

        if resultado is None:
            if verbose:
                print(
                    f"[t={minuto:05d}] RECHAZO    pedido #{pedido.call_id} "
                    f"({pedido.producto} x{pedido.unidades})"
                )
            continue

        eta_ida, decision = resultado
        id_dron = pedido.assigned_drone_id

        if pedido.producto and pedido.origin_hospital in inventarios:
            inventarios[pedido.origin_hospital].enviar_dron(
                pedido.producto,
                pedido.unidades,
            )

        secuencia_evento += 1
        heapq.heappush(
            cola_eventos_des,
            (eta_ida, secuencia_evento, "llegada_hospital", id_dron, decision),
        )

        if verbose:
            print(
                f"[t={minuto:05d}] DESPACHO   {id_dron} bat="
                f"{decision.battery_before_percent:.1f}%->{decision.battery_after_percent:.1f}% "
                f"| {pedido.producto} x{pedido.unidades} "
                f"{pedido.origin_hospital} -> {pedido.destination_hospital} ETA={eta_ida:.0f}"
            )

    return secuencia_evento


def drain_remaining_events(cola_eventos_des, gestor_flota, inventarios, verbose):
    while cola_eventos_des:
        event_time, _, tipo_evento, id_dron, decision = heapq.heappop(cola_eventos_des)

        if tipo_evento == "llegada_hospital":
            eta_base, pedido_ok = gestor_flota.procesar_evento_llegada_hospital(
                id_dron,
                event_time,
                decision,
            )
            if pedido_ok and pedido_ok.producto:
                inventarios[pedido_ok.destination_hospital].recibir_dron(
                    pedido_ok.producto,
                    pedido_ok.unidades,
                )
            recharge_end = gestor_flota.procesar_evento_aterrizaje_base(id_dron, eta_base)
            if recharge_end is not None:
                gestor_flota.procesar_evento_fin_recarga(id_dron)

        elif tipo_evento == "aterrizaje_base":
            recharge_end = gestor_flota.procesar_evento_aterrizaje_base(id_dron, event_time)
            if recharge_end is not None:
                gestor_flota.procesar_evento_fin_recarga(id_dron)

        elif tipo_evento == "fin_recarga":
            gestor_flota.procesar_evento_fin_recarga(id_dron)

    if verbose:
        print("Eventos restantes procesados tras el horizonte de simulacion.")


def print_fleet_summary(
    gestor_flota,
    generador,
    cola_pedidos,
    inventarios,
    conteo_clima,
    clima_sim,
    args,
):
    estadisticas = gestor_flota.estadisticas
    resumen = gestor_flota.obtener_resumen_estado()
    total_generated = generador._contador_pedidos
    dias = args.minutes / 1440 if args.minutes else 0

    print("\n" + "=" * 58)
    print(" FIN SIMULACION")
    print("=" * 58)
    print(f"Total pedidos generados: {total_generated}")
    print(f"Procesados por flota: {estadisticas.total_calls}")
    print(f"Asignados: {estadisticas.assigned_calls}")
    print(f"Rechazados: {estadisticas.rejected_calls}")
    print(f"Completados: {estadisticas.completed_calls}")
    print(f"Pendientes en cola: {cola_pedidos.size()}")
    if estadisticas.total_calls:
        print(f"Tasa de servicio: {(estadisticas.completed_calls / estadisticas.total_calls) * 100:.1f}%")
    if dias:
        print(f"Entregas/dia: {estadisticas.completed_calls / dias:.1f}")

    print("\n--- FLOTA ---")
    print(f"Disponibles: {resumen['available']}")
    print(f"En mision: {resumen['mission']}")
    print(f"Regresando: {resumen['returning']}")
    print(f"Recargando: {resumen['charging']}")

    print("\nDetalle por dron:")
    for id_dron, dron in sorted(gestor_flota.drones.items()):
        vuelo = (dron.flight_minutes / args.minutes) * 100 if args.minutes else 0
        carga = (dron.charging_minutes / args.minutes) * 100 if args.minutes else 0
        disponible = max(0.0, 100.0 - vuelo - carga)
        print(
            f"  {id_dron}: bat={dron.battery_percent:5.1f}% estado={dron.status:10s} "
            f"entregas={dron.deliveries_made:3d} vuelo={vuelo:5.1f}% "
            f"carga={carga:5.1f}% disp={disponible:5.1f}%"
        )

    if args.show_inventory:
        print_inventory("INVENTARIO FINAL (hospitales)", inventarios)

    if not args.no_weather:
        print("\n--- METEOROLOGIA ---")
        for estado in ESTADOS_CLIMA:
            minutos = conteo_clima.get(estado.nombre, 0)
            pct = (minutos / args.minutes) * 100 if args.minutes else 0
            print(
                f"{estado.nombre:16s} {minutos:5d} min ({pct:5.1f}%) "
                f"vel. x{estado.factor_velocidad:.2f}"
            )
        print(f"Cambios registrados: {len(clima_sim.historial)}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    red = ServicioRed()
    if args.list_hospitals or args.list_bases:
        list_network(
            red,
            show_hospitals=args.list_hospitals,
            show_bases=args.list_bases,
        )
        return 0

    if args.mode == "single":
        run_single_mode(args)
    else:
        run_fleet_mode(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

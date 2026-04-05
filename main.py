import argparse

from controllers.simulation_controller import SimulationController
from controllers.fleet_controller import FleetController
from   models.models import MissionRequest
from services.network_service import NetworkService
from simulators.random_calls_simulator import RandomCallsSimulator
from   config import (
    DEFAULT_SIMULATION_MINUTES,
    DEFAULT_CALL_PROBABILITY_PER_MIN,
)


def build_parser():
    parser = argparse.ArgumentParser(description="Simulador de red de drones hospitalarios")

    parser.add_argument("--mode", choices=["single", "fleet"], default="fleet")

    # modo single
    parser.add_argument("--origin", help="Hospital origen")
    parser.add_argument("--destination", help="Hospital destino")
    parser.add_argument("--payload", type=float, help="Carga en kg")
    parser.add_argument("--battery", type=float, default=100.0, help="Batería inicial en %")
    parser.add_argument("--date", type=str, default=None, help="Fecha clima YYYY-MM-DD")
    parser.add_argument("--ignore-weather", action="store_true", help="Ignorar validación climática")

    # modo fleet
    parser.add_argument("--minutes", type=int, default=DEFAULT_SIMULATION_MINUTES, help="Duración simulación en minutos")
    parser.add_argument("--call-probability", type=float, default=DEFAULT_CALL_PROBABILITY_PER_MIN, help="Probabilidad de llamada por minuto")
    parser.add_argument("--drones-per-base", type=int, default=2, help="Número de drones por base")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria")
    parser.add_argument("--verbose", action="store_true", help="Mostrar eventos minuto a minuto")

    parser.add_argument("--list-hospitals", action="store_true", help="Mostrar hospitales disponibles")
    return parser


def run_single_mode(args):
    controller = SimulationController()

    request = MissionRequest(
        origin_hospital=args.origin,
        destination_hospital=args.destination,
        payload_kg=args.payload,
        battery_start_percent=args.battery,
        weather_date=args.date,
        ignore_weather=args.ignore_weather,
    )

    result = controller.simulate_mission(request)

    print("\n========== RESULTADO MISIÓN ==========")
    print(f"Viable: {'SÍ' if result.feasible else 'NO'}")
    print(f"Base seleccionada: {result.selected_base}")
    print(f"Distancia total: {result.distance_total_km:.2f} km" if result.distance_total_km is not None else "Distancia total: N/D")
    print(
        f"Tiempo estimado: {result.estimated_flight_minutes:.2f} min"
        if result.estimated_flight_minutes is not None
        else "Tiempo estimado: N/D"
    )
    print(
        f"Batería final estimada: {result.battery_after_percent:.2f}%"
        if result.battery_after_percent is not None
        else "Batería final estimada: N/D"
    )
    print(f"Clima OK: {result.weather_ok}")

    if result.route_plan:
        print("\n--- Ruta ---")
        print(f"Base -> Origen: {result.route_plan.distance_base_to_origin_km:.2f} km")
        print(f"Origen -> Destino: {result.route_plan.distance_origin_to_destination_km:.2f} km")

    if result.reasons:
        print("\n--- Motivos / observaciones ---")
        for r in result.reasons:
            print(f" - {r}")

    print("=====================================\n")


def run_fleet_mode(args):
    network = NetworkService()
    fleet = FleetController(network)
    fleet.initialize_default_fleet(drones_per_base=args.drones_per_base)

    simulator = RandomCallsSimulator(
        hospitals=network.list_hospitals(),
        seed=args.seed,
    )

    print("\n========== INICIO SIMULACIÓN FLOTILLA ==========")
    print(f"Duración: {args.minutes} min")
    print(f"Llamadas/min prob.: {args.call_probability}")
    print(f"Drones por base: {args.drones_per_base}")
    print("================================================\n")

    for minute in range(args.minutes):
        fleet.update_time(minute)

        call = simulator.maybe_generate_call(
            current_minute=minute,
            probability=args.call_probability
        )

        if call is not None:
            decision = fleet.assign_call(call, current_minute=minute)

            if args.verbose:
                if decision is None:
                    print(
                        f"[t={minute:04d}] CALL {call.call_id} | P{call.priority} | "
                        f"{call.origin_hospital} -> {call.destination_hospital} | "
                        f"{call.payload_kg}kg | RECHAZADA"
                    )
                else:
                    print(
                        f"[t={minute:04d}] CALL {call.call_id} | P{call.priority} | "
                        f"{call.origin_hospital} -> {call.destination_hospital} | "
                        f"{call.payload_kg}kg | "
                        f"Drone {decision.drone_id} | dist={decision.distance_total_km:.2f}km | "
                        f"bat {decision.battery_before_percent:.1f}%->{decision.battery_after_percent:.1f}% | "
                        f"dur={decision.estimated_duration_min}min"
                    )

        if args.verbose and minute % 60 == 0:
            snapshot = fleet.get_status_snapshot()
            print(
                f"[t={minute:04d}] STATUS | "
                f"available={snapshot['available']} | "
                f"mission={snapshot['mission']} | "
                f"charging={snapshot['charging']}"
            )

    snapshot = fleet.get_status_snapshot()

    print("\n========== FIN SIMULACIÓN ==========")
    print(f"Total llamadas: {fleet.stats.total_calls}")
    print(f"Asignadas: {fleet.stats.assigned_calls}")
    print(f"Rechazadas: {fleet.stats.rejected_calls}")
    print(f"Completadas: {fleet.stats.completed_calls}")
    print(f"Prioridad alta: {fleet.stats.high_priority_calls}")
    print(f"Prioridad media: {fleet.stats.medium_priority_calls}")
    print(f"Prioridad baja: {fleet.stats.low_priority_calls}")
    print("\n--- Estado final drones ---")
    print(f"Disponibles: {snapshot['available']}")
    print(f"En misión: {snapshot['mission']}")
    print(f"Cargando: {snapshot['charging']}")

    print("\n--- Batería final de drones ---")
    for drone in fleet.drones:
        print(
            f"{drone.drone_id} | {drone.base_name} | "
            f"status={drone.status} | battery={drone.battery_percent:.1f}%"
        )

    print("===================================\n")


def main():
    parser = build_parser()
    args = parser.parse_args()

    network = NetworkService()

    if args.list_hospitals:
        print("Hospitales disponibles:")
        for h in network.list_hospitals():
            print(f" - {h}")
        return

    if args.mode == "single":
        if not args.origin or not args.destination or args.payload is None:
            raise ValueError("En modo single debes indicar --origin --destination --payload")
        run_single_mode(args)
    else:
        run_fleet_mode(args)


if __name__ == "__main__":
    main()

# Ejemplo uso: python main.py --mode fleet
# python main.py --mode fleet --minutes 1440 --call-probability 0.2 --drones-per-base 3 --verbose
# python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 3 --battery 100 --ignore-weather
from models.models import Drone, DeliveryCall, SimulationStats
from services.charging_service import ChargingService
from services.dispatcher_service import DispatcherService


class FleetController:
    def __init__(self, network_service):
        self.network = network_service
        self.dispatcher = DispatcherService(network_service)
        self.drones = []
        self.active_calls = []
        self.completed_calls = []
        self.rejected_calls = []
        self.stats = SimulationStats()

    def add_drone(self, drone: Drone):
        if drone.current_node is None:
            drone.current_node = drone.base_name
        self.drones.append(drone)

    def initialize_default_fleet(self, drones_per_base: int = 2):
        counter = 1
        for base_name in self.network.list_bases():
            for _ in range(drones_per_base):
                drone = Drone(
                    drone_id=f"D{counter:02d}",
                    base_name=base_name,
                    battery_percent=100.0,
                    status="available",
                    current_node=base_name
                )
                self.add_drone(drone)
                counter += 1

    def update_time(self, current_minute: int):
        for drone in self.drones:
            if drone.status == "mission" and current_minute >= drone.busy_until_min:
                drone.status = "charging"
                drone.current_call_id = None
                drone.busy_until_min = 0

            elif drone.status == "charging":
                ChargingService.update_drone_charging(drone, elapsed_minutes=1)

        # completar llamadas cuya misión ha terminado
        still_active = []
        for call in self.active_calls:
            assigned_drone = self.get_drone_by_id(call.assigned_drone_id)
            if assigned_drone and assigned_drone.status != "mission":
                call.status = "completed"
                self.completed_calls.append(call)
                self.stats.completed_calls += 1
            else:
                still_active.append(call)

        self.active_calls = still_active

    def get_drone_by_id(self, drone_id: str):
        for drone in self.drones:
            if drone.drone_id == drone_id:
                return drone
        return None

    def assign_call(self, call: DeliveryCall, current_minute: int):
        self.stats.total_calls += 1

        if call.priority == 1:
            self.stats.high_priority_calls += 1
        elif call.priority == 2:
            self.stats.medium_priority_calls += 1
        else:
            self.stats.low_priority_calls += 1

        decision = self.dispatcher.choose_best_drone(self.drones, call)

        if decision is None:
            call.status = "rejected"
            call.rejection_reason = "No hay drones disponibles con batería suficiente."
            self.rejected_calls.append(call)
            self.stats.rejected_calls += 1
            return None

        drone = self.get_drone_by_id(decision.drone_id)

        drone.status = "mission"
        drone.current_call_id = call.call_id
        drone.battery_percent = decision.battery_after_percent
        drone.busy_until_min = current_minute + decision.estimated_duration_min
        drone.current_node = call.destination_hospital

        call.status = "assigned"
        call.assigned_drone_id = drone.drone_id

        self.active_calls.append(call)
        self.stats.assigned_calls += 1

        return decision

    def get_status_snapshot(self):
        summary = {
            "available": 0,
            "mission": 0,
            "charging": 0,
        }

        for drone in self.drones:
            summary[drone.status] += 1

        return summary
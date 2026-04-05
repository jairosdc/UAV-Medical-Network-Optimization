from  config import BATTERY_RESERVE_PERCENT, CRUISE_SPEED_M_S
from  models.models import DispatchDecision
from services.battery_service import BatteryService


class DispatcherService:
    def __init__(self, network_service):
        self.network = network_service

    @staticmethod
    def estimate_duration_min(distance_km: float) -> int:
        speed_km_h = CRUISE_SPEED_M_S * 3.6
        minutes = (distance_km / speed_km_h) * 60.0
        return max(1, int(round(minutes)))

    @staticmethod
    def dispatch_score(priority: int, distance_to_origin_km: float, battery_after_percent: float) -> float:
        # score más bajo = mejor
        if priority == 1:
            return distance_to_origin_km * 10.0 - battery_after_percent * 0.05
        elif priority == 2:
            return distance_to_origin_km * 5.0 - battery_after_percent * 0.08
        else:
            return distance_to_origin_km * 3.0 - battery_after_percent * 0.10

    def choose_best_drone(self, drones, call):
        candidates = []

        origin_node = self.network.get_hospital(call.origin_hospital)
        destination_node = self.network.get_hospital(call.destination_hospital)

        for drone in drones:
            if drone.status != "available":
                continue

            base_node = self.network.get_base(drone.base_name)

            distance_to_origin = self.network.distance_between_nodes(base_node, origin_node)
            distance_origin_to_destination = self.network.distance_between_nodes(origin_node, destination_node)
            total_distance = distance_to_origin + distance_origin_to_destination

            try:
                battery_after = BatteryService.battery_after(
                    payload_kg=call.payload_kg,
                    distance_km=total_distance,
                    battery_start_percent=drone.battery_percent,
                )
            except ValueError:
                continue

            if battery_after < BATTERY_RESERVE_PERCENT:
                continue

            score = self.dispatch_score(
                priority=call.priority,
                distance_to_origin_km=distance_to_origin,
                battery_after_percent=battery_after,
            )

            duration_min = self.estimate_duration_min(total_distance)

            candidates.append(
                DispatchDecision(
                    drone_id=drone.drone_id,
                    call_id=call.call_id,
                    priority=call.priority,
                    distance_to_origin_km=distance_to_origin,
                    distance_total_km=total_distance,
                    battery_before_percent=drone.battery_percent,
                    battery_after_percent=battery_after,
                    estimated_duration_min=duration_min,
                    score=score,
                )
            )

        if not candidates:
            return None

        candidates.sort(key=lambda x: x.score)
        return candidates[0]
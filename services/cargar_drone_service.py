from parametros_globales import CHARGE_RATE_PERCENT_PER_MIN


class ChargingService:
    @staticmethod
    def update_drone_charging(drone, elapsed_minutes: int = 1):
        if drone.status != "charging":
            return

        drone.battery_percent = min(
            100.0,
            drone.battery_percent + CHARGE_RATE_PERCENT_PER_MIN * elapsed_minutes
        )

        if drone.battery_percent >= 100.0:
            drone.battery_percent = 100.0
            drone.status = "available"
            drone.busy_until_min = 0
            drone.current_call_id = None
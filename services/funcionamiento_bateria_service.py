from parametros_globales import CARGA_MAXIMA_KG, MAX_RANGE_KM_EMPTY


class BatteryService:
    @staticmethod
    def autonomy_km(payload_kg: float) -> float:
        if payload_kg < 0:
            raise ValueError("La carga no puede ser negativa.")
        if payload_kg > CARGA_MAXIMA_KG:
            raise ValueError(f"La carga excede el máximo permitido ({CARGA_MAXIMA_KG} kg).")
        return MAX_RANGE_KM_EMPTY - (22.0 * payload_kg) / CARGA_MAXIMA_KG

    @staticmethod
    def consumption_percent(payload_kg: float, distance_km: float) -> float:
        autonomy = BatteryService.autonomy_km(payload_kg)
        return (distance_km / autonomy) * 100.0

    @staticmethod
    def battery_after(payload_kg: float, distance_km: float, battery_start_percent: float) -> float:
        return battery_start_percent - BatteryService.consumption_percent(payload_kg, distance_km)

    @staticmethod
    def has_enough_battery(payload_kg: float, distance_km: float, battery_start_percent: float, reserve_percent: float) -> bool:
        battery_end = BatteryService.battery_after(payload_kg, distance_km, battery_start_percent)
        return battery_end >= reserve_percent
import json
import os

from   parametros_globales import (
    WEATHER_CACHE_FILE,
    DEFAULT_AEMET_STATION_ID,
    MIN_TEMP_C,
    MAX_TEMP_C,
    MAX_WIND_AVG_M_S,
    MAX_WIND_GUST_M_S,
    MAX_PRECIP_MM_DAY,
)


def limpiar_float(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        try:
            if valor.lower() == "ip":
                return 0.0
            return float(valor.replace(",", "."))
        except ValueError:
            return None
    return None


class WeatherService:
    def __init__(self):
        self.cache_file = WEATHER_CACHE_FILE

    def load_cached_data(self):
        if not self.cache_file.exists():
            return []
        with open(self.cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_and_cache_data(self, months_back=6, station_id=DEFAULT_AEMET_STATION_ID):
        from aemet_client import AEMETClient

        client = AEMETClient()
        data = client.fetch_historical_data(station_id, months_back=months_back)

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data

    def get_weather_for_date(self, target_date: str, allow_fetch_if_missing: bool = False) -> Optional[Dict[str, Any]]:
        data = self.load_cached_data()

        if not data and allow_fetch_if_missing and os.environ.get("AEMET_API_KEY"):
            data = self.fetch_and_cache_data()

        for day in data:
            fecha = str(day.get("fecha", ""))[:10]
            if fecha == target_date:
                return day
        return None

    def is_operational_day(self, day: Dict[str, Any]) -> (bool, list): # type: ignore
        reasons = []

        tmax = limpiar_float(day.get("tmax"))
        tmin = limpiar_float(day.get("tmin"))
        velmedia = limpiar_float(day.get("velmedia"))
        racha = limpiar_float(day.get("racha"))
        prec = limpiar_float(day.get("prec"))

        if tmax is not None and tmax > MAX_TEMP_C:
            reasons.append(f"Temperatura máxima demasiado alta: {tmax}°C")
        if tmin is not None and tmin < MIN_TEMP_C:
            reasons.append(f"Temperatura mínima demasiado baja: {tmin}°C")
        if velmedia is not None and velmedia > MAX_WIND_AVG_M_S:
            reasons.append(f"Viento medio demasiado alto: {velmedia} m/s")
        if racha is not None and racha > MAX_WIND_GUST_M_S:
            reasons.append(f"Racha demasiado alta: {racha} m/s")
        if prec is not None and prec > MAX_PRECIP_MM_DAY:
            reasons.append(f"Precipitación demasiado alta: {prec} mm/día")

        return len(reasons) == 0, reasons
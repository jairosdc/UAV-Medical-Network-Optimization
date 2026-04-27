from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Dron / misión ---
CARGA_MAXIMA_KG = 4.7 # (kg)
AUTONOMIA_MAX_EN_VACIO = 94.0 # (km)
BATERIA_MINIMA_VUELO = 20.0 # (%)
VELOCIDAD_DRON_M_S = 25.0 # (m/s)

# --- Clima operativo ---
MIN_TEMP_C = 0.0
MAX_TEMP_C = 45.0
MAX_WIND_AVG_M_S = 15.0
MAX_WIND_GUST_M_S = 20.0
MAX_PRECIP_MM_DAY = 12.7

# --- Simulación de flota ---
DEFAULT_IGNORE_WEATHER = True
DEFAULT_SIMULATION_MINUTES = 7200
DEFAULT_CALL_PROBABILITY_PER_MIN = 0.15

# Carga: de 20% a 100% en 50 min => 80/50 = 1.6 %/min
CHARGE_RATE_PERCENT_PER_MIN = 1.6

# Cuando termina misión, si no está al 100%, entra a cargar
CHARGE_TO_FULL = True
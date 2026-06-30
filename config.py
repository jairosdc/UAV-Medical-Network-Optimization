"""
config.py
=========

Parámetros físicos del dron y de la simulación, más los datos
geográficos de la red (hospitales y bases de Madrid).

Importa Node desde modelos.py para construir los diccionarios HOSPITALS y BASES.
"""

from modelos import Node

# ---------------------------------------------------------------------------
# Parámetros físicos del dron
# ---------------------------------------------------------------------------

CARGA_MAXIMA_KG          = 4.7   # kg
AUTONOMIA_MAX_EN_VACIO   = 94.0  # km (sin carga)
BATERIA_MINIMA_VUELO     = 5     # % mínimo al aterrizar
VELOCIDAD_DRON_M_S       = 25.0  # m/s crucero

# ---------------------------------------------------------------------------
# Límites climáticos operativos
# ---------------------------------------------------------------------------

MIN_TEMP_C          = 0.0
MAX_TEMP_C          = 45.0
MAX_WIND_AVG_M_S    = 15.0
MAX_WIND_GUST_M_S   = 20.0
MAX_PRECIP_MM_DAY   = 12.7

# ---------------------------------------------------------------------------
# Parámetros de simulación por defecto
# ---------------------------------------------------------------------------

DEFAULT_IGNORE_WEATHER           = True
DEFAULT_SIMULATION_MINUTES       = 7200
DEFAULT_CALL_PROBABILITY_PER_MIN = 0.15

# Velocidad de recarga: de 20 % a 100 % en 40 min → 2 %/min
CHARGE_RATE_PERCENT_PER_MIN = 2

# Al terminar misión, si no está al 100 %, entra a cargar
CHARGE_TO_FULL = True

# ---------------------------------------------------------------------------
# Red hospitalaria de la Comunidad de Madrid
# ---------------------------------------------------------------------------

HOSPITALS = {
    "Hospital Asociado Universitario Guadarrama":             Node("Hospital Asociado Universitario Guadarrama",             40.6695311, -4.0863566, "hospital"),
    "Hospital Central de la Cruz Roja San José y Santa Adela": Node("Hospital Central de la Cruz Roja San José y Santa Adela", 40.4472853, -3.7076046, "hospital"),
    "Hospital Central de la Defensa Gómez Ulla":              Node("Hospital Central de la Defensa Gómez Ulla",              40.3892726, -3.7468206, "hospital"),
    "Hospital Clínico San Carlos":                            Node("Hospital Clínico San Carlos",                            40.4403419, -3.7198249, "hospital"),
    "Hospital El Escorial":                                   Node("Hospital El Escorial",                                   40.6075703, -4.1201247, "hospital"),
    "Hospital Universitario Fundación Jiménez Díaz":          Node("Hospital Universitario Fundación Jiménez Díaz",          40.4391044, -3.7190248, "hospital"),
    "Hospital General Universitario Gregorio Marañón":        Node("Hospital General Universitario Gregorio Marañón",        40.4191053, -3.6703866, "hospital"),
    "Hospital Universitario General de Villalba":             Node("Hospital Universitario General de Villalba",             40.6548820, -4.0006330, "hospital"),
    "Hospital Infantil Universitario Niño Jesús":             Node("Hospital Infantil Universitario Niño Jesús",             40.4147653, -3.6773850, "hospital"),
    "Hospital La Fuenfría":                                   Node("Hospital La Fuenfría",                                   40.7608072, -4.0738752, "hospital"),
    "Hospital Universitario 12 de Octubre":                   Node("Hospital Universitario 12 de Octubre",                   40.3763009, -3.6969903, "hospital"),
    "Hospital Universitario de Fuenlabrada":                  Node("Hospital Universitario de Fuenlabrada",                  40.2862287, -3.8157011, "hospital"),
    "Hospital Universitario de Getafe":                       Node("Hospital Universitario de Getafe",                       40.3125523, -3.7423468, "hospital"),
    "Hospital Universitario de La Princesa":                  Node("Hospital Universitario de La Princesa",                  40.4344005, -3.6756778, "hospital"),
    "Hospital Universitario de Móstoles":                     Node("Hospital Universitario de Móstoles",                     40.3157343, -3.8777007, "hospital"),
    "Hospital Universitario de Torrejón":                     Node("Hospital Universitario de Torrejón",                     40.4648596, -3.4353915, "hospital"),
    "Hospital Universitario del Henares":                     Node("Hospital Universitario del Henares",                     40.4185953, -3.5324909, "hospital"),
    "Hospital Universitario del Sureste":                     Node("Hospital Universitario del Sureste",                     40.2968407, -3.4570632, "hospital"),
    "Hospital Universitario Dr. Rodríguez Lafora":            Node("Hospital Universitario Dr. Rodríguez Lafora",            40.5321449, -3.6919534, "hospital"),
    "Hospital Universitario Fundación Alcorcón":              Node("Hospital Universitario Fundación Alcorcón",              40.3492887, -3.8357520, "hospital"),
    "Hospital Universitario Infanta Cristina":                Node("Hospital Universitario Infanta Cristina",                40.2183805, -3.7828910, "hospital"),
    "Hospital Universitario Infanta Elena":                   Node("Hospital Universitario Infanta Elena",                   40.1983634, -3.6966741, "hospital"),
    "Hospital Universitario Infanta Leonor":                  Node("Hospital Universitario Infanta Leonor",                  40.3862884, -3.6178551, "hospital"),
    "Hospital Virgen de la Torre":                            Node("Hospital Virgen de la Torre",                            40.3810453, -3.6192869, "hospital"),
    "Hospital Universitario Infanta Sofía":                   Node("Hospital Universitario Infanta Sofía",                   40.5579621, -3.6108580, "hospital"),
    "Hospital Universitario José Germain":                    Node("Hospital Universitario José Germain",                    40.3271947, -3.7676681, "hospital"),
    "Hospital Universitario La Paz":                          Node("Hospital Universitario La Paz",                          40.4811633, -3.6873983, "hospital"),
    "Hospital Carlos III":                                    Node("Hospital Carlos III",                                    40.4746512, -3.6974467, "hospital"),
    "Hospital Cantoblanco":                                   Node("Hospital Cantoblanco",                                   40.5380087, -3.6947978, "hospital"),
    "Hospital Enfermera Isabel Zendal":                       Node("Hospital Enfermera Isabel Zendal",                       40.4839231, -3.6063051, "hospital"),
    "Hospital Universitario Príncipe de Asturias":            Node("Hospital Universitario Príncipe de Asturias",            40.5094354, -3.3475358, "hospital"),
    "Hospital Universitario Puerta de Hierro Majadahonda":    Node("Hospital Universitario Puerta de Hierro Majadahonda",    40.4500415, -3.8740056, "hospital"),
    "Hospital Universitario Ramón y Cajal":                   Node("Hospital Universitario Ramón y Cajal",                   40.4874172, -3.6945485, "hospital"),
    "Hospital Universitario Rey Juan Carlos":                 Node("Hospital Universitario Rey Juan Carlos",                 40.3389470, -3.8709040, "hospital"),
    "Hospital Universitario Santa Cristina":                  Node("Hospital Universitario Santa Cristina",                  40.4218103, -3.6710590, "hospital"),
    "Hospital Universitario Severo Ochoa":                    Node("Hospital Universitario Severo Ochoa",                    40.3210980, -3.7687637, "hospital"),
}

BASES = {
    "BASE NOROESTE":       Node("BASE NOROESTE",       40.6732, -4.0702, "base"),
    "BASE NORTE CAPITAL":  Node("BASE NORTE CAPITAL",  40.4503, -3.6884, "base"),
    "BASE ESTE CORREDOR":  Node("BASE ESTE CORREDOR",  40.4450, -3.5300, "base"),
    "BASE SUR FUENLABRADA": Node("BASE SUR FUENLABRADA", 40.2964, -3.7954, "base"),
}

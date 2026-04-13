from services.funcionamiento_bateria_service import calcular_autonomia_km, calcular_consumo_porcentaje, calcular_bateria_restante, tiene_bateria_suficiente
from parametros_globales import BATERIA_MINIMA_VUELO

carga = 3 # kg
distancia = 10 # km
bateria_inicial = 10

try:
    tiene_bateria_suficiente(carga, distancia, bateria_inicial, BATERIA_MINIMA_VUELO)
    bateria_postviaje = round(calcular_bateria_restante(carga, distancia, bateria_inicial), 2)
except Exception as e:
    print(e)
print(f'La batería tras el viaje de {distancia} km ha pasado de {bateria_inicial} a {bateria_postviaje}')
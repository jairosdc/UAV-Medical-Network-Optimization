from services.grafo_distancias_service import ServicioRed
from hospitales_almacenes_data import HOSPITALS, BASES

red = ServicioRed()
 
print("=" * 45)
print("       DEMO — ServicioRed")
print("=" * 45)
 
print("Hospitales disponibles:")
for h in red.listar_hospitales():
    nodo = red.obtener_hospital(h)
    print(f"   {nodo.nombre}  ({nodo.lat}, {nodo.lon})")
 
print("Bases disponibles:")
for b in red.listar_bases():
    nodo = red.obtener_base(b)
    print(f"   {nodo.nombre}  ({nodo.lat}, {nodo.lon})")
 
print("Distancia entre hospitales:")
h1 = red.obtener_hospital("Gregorio Marañón")
h2 = red.obtener_hospital("12 de Octubre")
distancia = red.distancia_entre_nodos_km(h1, h2)
print(f"   {h1.nombre} → {h2.nombre}: {distancia:.2f} km")
 
print("Base más cercana a Gregorio Marañón:")
base, dist = red.base_mas_cercana_a("Gregorio Marañón")
print(f"   {base}  ({dist:.2f} km)")
 
print("Plan de ruta completo:")
plan = red.planificar_reposicion("12 de Octubre")
print(f"   Salida desde:   {plan.start_base}")
print(f"   Origen:         {plan.origin_hospital}")
print(f"   Destino:        {plan.destination_hospital}")
print(f"   Base → Origen:  {plan.distance_base_to_origin_km:.2f} km")
print(f"   Origen → Dest:  {plan.distance_origin_to_destination_km:.2f} km")
print(f"   Total:          {plan.distance_total_km:.2f} km")
print()

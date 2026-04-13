import sys
sys.path.insert(0, '.')

from services.grafo_distancias_service import ServicioRed
from models.clases_models import Drone, DeliveryCall
from services.optimizador_asignacion_service import ServicioDespacho

red      = ServicioRed()
despacho = ServicioDespacho(red)

# Flota de prueba
flota = [
    Drone("DRON-01", base_name="BASE SUR", battery_percent=100.0, status="available"),
    Drone("DRON-02", base_name="BASE SUR", battery_percent=65.0,  status="available"),
    Drone("DRON-03", base_name="BASE SUR", battery_percent=30.0,  status="mission"),
]

escenarios = [
    ("CRITICA   (prioridad=1)", flota,         DeliveryCall(1, 0,  "Gregorio Maranon", "12 de Octubre", payload_kg=1.0, priority=1)),
    ("URGENTE   (prioridad=2)", flota,         DeliveryCall(2, 5,  "Gregorio Maranon", "12 de Octubre", payload_kg=2.5, priority=2)),
    ("RUTINARIA (prioridad=3)", flota,         DeliveryCall(3, 10, "Gregorio Maranon", "12 de Octubre", payload_kg=4.0, priority=3)),
]

# Nombres reales con tildes para la red
escenarios_reales = [
    ("CRITICA   (prioridad=1)", flota,         DeliveryCall(1, 0,  "Gregorio Marañón", "12 de Octubre", payload_kg=1.0, priority=1)),
    ("URGENTE   (prioridad=2)", flota,         DeliveryCall(2, 5,  "Gregorio Marañón", "12 de Octubre", payload_kg=2.5, priority=2)),
    ("RUTINARIA (prioridad=3)", flota,         DeliveryCall(3, 10, "Gregorio Marañón", "12 de Octubre", payload_kg=4.0, priority=3)),
]

print("----------------------------------------------")
print("         DEMO - ServicioDespacho")
print("----------------------------------------------")
print(f"Flota activa: {[d.drone_id for d in flota]}")
print(f"  DRON-01: {flota[0].battery_percent}% bateria, estado={flota[0].status}")
print(f"  DRON-02: {flota[1].battery_percent}% bateria, estado={flota[1].status}")
print(f"  DRON-03: {flota[2].battery_percent}% bateria, estado={flota[2].status}  <- no disponible")

for etiqueta, flota_activa, pedido in escenarios_reales:
    print()
    print(f"--- {etiqueta} ---")
    print(f"  Pedido: {pedido.origin_hospital} -> {pedido.destination_hospital}, carga={pedido.payload_kg} kg")
    decision = despacho.elegir_mejor_dron(flota_activa, pedido)
    if decision is None:
        print("  Resultado: ningun dron puede realizar esta mision")
    else:
        print(f"  Resultado: asignado {decision.drone_id}")
        print(f"    bateria antes:   {decision.battery_before_percent:.1f}%")
        print(f"    bateria despues: {decision.battery_after_percent:.1f}%")
        print(f"    distancia total: {decision.distance_total_km:.2f} km")
        print(f"    duracion est.:   {decision.estimated_duration_min} min")

print()
print("----------------------------------------------")

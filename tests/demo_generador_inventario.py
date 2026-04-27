import sys
sys.path.insert(0, '.')

from simulators.generador_pedidos import GeneradorPedidos, PRIORIDAD_PRODUCTO
from models.inventario import Inventario, CONFIG_INVENTARIO
from cola_prioridad import GestorPrioridad
from models.clases_models import Node

# ---------------------------------------------------------------------------
# Nodos
# ---------------------------------------------------------------------------
hospitales = [
    Node("Gregorio Marañón", 40.4095, -3.6829, "hospital"),
    Node("12 de Octubre",    40.3839, -3.6911, "hospital"),
]
bases = [Node("BASE SUR", 40.3968, -3.6985, "base")]

# ---------------------------------------------------------------------------
# BLOQUE 1: inventario en aislado
# ---------------------------------------------------------------------------
print("----------------------------------------------")
print("  BLOQUE 1 - Inventario: logica (s, Q)")
print("----------------------------------------------")

inv = Inventario(es_almacen_central=False)
prod = inv.productos["sangre"]

print(f"  Producto: sangre")
print(f"  Stock inicial: {prod.stock_fisico}  |  umbral s={prod.umbral_s}  |  lote Q={prod.cantidad_a_pedir_Q}")
print()

# Consumimos hasta romper el umbral
for consumo in range(1, 60):
    q = inv.registrar_consumo("sangre", 1)
    if q > 0:
        print(f"  Consumo #{consumo}: stock_fisico={prod.stock_fisico}  stock_en_camino={prod.stock_en_camino}  -> REPOSICION GENERADA ({q} uds)")
        break

print()
print("  Simulando llegada del dron con la reposicion...")
inv.recibir_dron("sangre", prod.cantidad_a_pedir_Q)
print(f"  Tras recepcion: stock_fisico={prod.stock_fisico}  stock_en_camino={prod.stock_en_camino}")

print()
print("  Verificando que el almacen central NO genera reposicion...")
inv_almacen = Inventario(es_almacen_central=True)
q = inv_almacen.registrar_consumo("sangre", 1)
print(f"  registrar_consumo en almacen devuelve: {q}  (correcto: 0)")

# ---------------------------------------------------------------------------
# BLOQUE 2: generador de eventos
# ---------------------------------------------------------------------------
print()
print("----------------------------------------------")
print("  BLOQUE 2 - GeneradorPedidos: agenda diaria")
print("----------------------------------------------")

gen = GeneradorPedidos(hospitales, bases, semilla=42)
print(f"  Eventos de consumo pregenerados para el dia: {gen.total_eventos_dia()}")

conteo = {}
for evs in gen._agenda.values():
    for ev in evs:
        producto = ev["producto"]
        conteo[producto] = conteo.get(producto, 0) + 1
print()
print("  Distribucion por producto:")
for prod_nombre, n in sorted(conteo.items(), key=lambda x: -x[1]):
    prioridad = PRIORIDAD_PRODUCTO[prod_nombre]
    print(f"    {prod_nombre:25s}  eventos={n:3d}  prioridad={prioridad}")

# ---------------------------------------------------------------------------
# BLOQUE 3: flujo completo con stocks cerca del umbral
# ---------------------------------------------------------------------------
print()
print("----------------------------------------------")
print("  BLOQUE 3 - Flujo completo: consumo -> reposicion -> cola")
print("----------------------------------------------")
print("  (stocks arrancados cerca del umbral para ver reposiciones)")
print()

gen2  = GeneradorPedidos(hospitales, bases, semilla=42)
cola  = GestorPrioridad()

# Arrancamos con stock justo por encima del umbral para que las primeras
# unidades consumidas disparen la reposicion
inventarios = {}
for h in hospitales:
    inv_h = Inventario(es_almacen_central=False)
    for nombre_prod, p in inv_h.productos.items():
        # Ponemos el stock un 20% por encima del umbral s
        p.stock_fisico = int(p.umbral_s * 1.2) + 1
    inventarios[h.nombre] = inv_h

n = 67328

for minuto in range(n):
    gen2.procesar_minuto(minuto, inventarios, cola)

print(f"  Pedidos de reposicion generados en {n} min: {cola.size()}")
print()

vistos = 0
while cola.size() > 0 and vistos < 6:
    p = cola.obtener_siguiente_pedido()
    print(f"  Pedido #{p.call_id:2d}  min={p.timestamp_min:4d}  "
          f"origen={p.origin_hospital:10s}  destino={p.destination_hospital:20s}  "
          f"prioridad={p.priority}  payload={p.payload_kg} kg")
    vistos += 1

print()
print("----------------------------------------------")

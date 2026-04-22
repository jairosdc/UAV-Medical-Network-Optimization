"""
demo_integracion_clima.py - Demo de Integracion Clima vs. Simulador Principal
=============================================================================
Este script demuestra de forma aislada como el factor de velocidad
generado por el Simulador de Clima afecta a las decisiones del
Gestor de Flota y al Optimizador de Asignacion.

Ejecutar desde la raiz del proyecto:
    python tests/demo_integracion_clima.py
"""

import sys
sys.path.insert(0, '.')

from simulators.simulador_clima import ESTADOS_CLIMA
from services.grafo_distancias_service import ServicioRed
from controllers.gestor_flota_controller import GestorFlotaController
from models.clases_models import DeliveryCall

def main():
    print("=" * 70)
    print("  DEMO - IMPACTO DEL CLIMA EN EL GESTOR DE FLOTA")
    print("=" * 70)
    print("\nInicializando la red y el gestor de flota...\n")

    # 1. Inicializar componentes principales
    red = ServicioRed()
    gestor_flota = GestorFlotaController(red)
    
    # Colocamos un par de drones en la Base Norte
    gestor_flota.inicializar_flota(drones_por_base=2)
    
    print("Flota disponible:")
    for id_dron, dron in gestor_flota.drones.items():
        if dron.base_name == "BASE NORTE":
            print(f"  - {id_dron} en {dron.base_name} (Bateria: {dron.battery_percent}%)")

    # 2. Definir un pedido estandar
    # Usaremos nombres sin tildes si la red los usa asi, 
    # pero el grafo base suele tener los nombres exactos.
    origen = "La Paz"
    destino = "12 de Octubre"
    carga_kg = 2.0
    
    print(f"\nEscenario de prueba:")
    print(f"  Ruta: {origen} -> {destino}")
    print(f"  Carga: {carga_kg} kg")
    print("-" * 70)
    
    print(f"{'Estado Climatico':<20s} | {'Dron Asignado':<13s} | {'Tiempo Ida':<11s} | {'Tiempo Total':<13s} | {'Bateria Restante'}")
    print("-" * 70)

    # 3. Probar el mismo pedido con todos los climas posibles
    for i, estado in enumerate(ESTADOS_CLIMA):
        # Reiniciamos la flota para que cada prueba sea independiente
        # (Todos los drones vuelven a estar 100% disponibles)
        for dron in gestor_flota.drones.values():
            dron.status = "available"
            dron.battery_percent = 100.0

        # Creamos un pedido nuevo cada vez
        pedido = DeliveryCall(
            call_id=i+1,
            timestamp_min=0,
            origin_hospital=origen,
            destination_hospital=destino,
            payload_kg=carga_kg,
            priority=1,
            producto="sangre",
            unidades=5
        )

        # Hacemos la peticion al gestor de flota pasandole el factor del clima
        resultado = gestor_flota.procesar_nuevo_pedido(
            pedido=pedido, 
            tiempo_actual=0, 
            factor_velocidad=estado.factor_velocidad
        )

        if resultado is not None:
            eta_ida, decision = resultado
            
            # Formatear la salida
            tiempo_ida = f"{decision.estimated_flight_ida_min} min"
            tiempo_total = f"{decision.estimated_duration_min} min"
            bat_restante = f"{decision.battery_after_percent:.1f}%"
            
            print(f"{estado.nombre:<20s} | {decision.drone_id:<13s} | {tiempo_ida:<11s} | {tiempo_total:<13s} | {bat_restante}")
        else:
            print(f"{estado.nombre:<20s} | {'RECHAZADO':<13s} | {'-':<11s} | {'-':<13s} | {'-'}")

    print("-" * 70)
    print("\nConclusion: A medida que el clima empeora (menor factor de velocidad),")
    print("el tiempo de vuelo aumenta significativamente. Si la penalizacion fuera")
    print("suficientemente extrema, la bateria restante caeria por debajo del limite")
    print("de seguridad y el pedido seria rechazado.\n")
    print("=" * 70)

if __name__ == "__main__":
    main()

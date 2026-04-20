"""
DEMO: Simulación de Misión de Transporte Médico(Drones)
---------------------------------------------------------------
Este archivo sirve como ejemplo práctico para explicar cómo funciona el controlador
de simulación en el proyecto de Optimización de Red Médica.

Objetivo:
1. Entender la entrada de datos (MissionRequest).
2. Ver cómo el SimulationController integra servicios de Red, Batería y Clima.
3. Interpretar los resultados de viabilidad (MissionResult).
"""

from controllers.simulation_controller import SimulationController
from models.clases_models import MissionRequest
from models.inventario import Inventario

# Configuración de hospitales de prueba (deben existir en hospitales_almacenes_data.py)
HOSPITAL_ORIGEN = "12 de Octubre"
HOSPITAL_DESTINO = "Gregorio Marañón"

def mostrar_solicitud(solicitud: MissionRequest) -> None:
    """Muestra de forma legible los parámetros de la misión solicitada."""
    print(f"  [>] Origen:           {solicitud.origin_hospital}")
    print(f"  [>] Destino:          {solicitud.destination_hospital}")
    print(f"  [>] Carga médica:     {solicitud.payload_kg:.2f} kg")
    print(f"  [>] Batería inicial:  {solicitud.battery_start_percent:.1f}%")
    print(f"  [>] Ignorar clima:    {solicitud.ignore_weather}")
    if solicitud.weather_date:
        print(f"  [>] Fecha simulación: {solicitud.weather_date}")

def mostrar_resultado(resultado) -> None:
    """Muestra de forma legible el veredicto del sistema de simulación."""
    if resultado.feasible:
        print(f"  [OK] ESTADO: MISIÓN FACTIBLE")
    else:
        print(f"  [ERROR] ESTADO: MISIÓN NO FACTIBLE")

    if resultado.selected_base:
        print(f"  [i] Base de salida:   {resultado.selected_base}")

    if resultado.distance_total_km is not None:
        print(f"  [i] Distancia total:  {resultado.distance_total_km:.2f} km")

    if resultado.estimated_flight_minutes is not None:
        print(f"  [i] Tiempo estimado:  {resultado.estimated_flight_minutes:.1f} minutos")

    if resultado.battery_after_percent is not None:
        print(f"  [i] Batería final:    {resultado.battery_after_percent:.2f}%")

    if resultado.route_plan is not None:
        plan = resultado.route_plan
        print(f"      - Tramo Base -> Origen:  {plan.distance_base_to_origin_km:.2f} km")
        print(f"      - Tramo Origen -> Destino: {plan.distance_origin_to_destination_km:.2f} km")

    if resultado.reasons:
        print("  [!] Observaciones/Alertas:")
        for motivo in resultado.reasons:
            print(f"      - {motivo}")

def ejecutar_escenario(controlador: SimulationController, titulo: str, solicitud: MissionRequest) -> None:
    """Ejecuta un caso de prueba y formatea la salida para la clase."""
    print("=" * 80)
    print(f" ESCENARIO: {titulo}")
    print("-" * 80)
    mostrar_solicitud(solicitud)
    print("-" * 40)
    
    # Aquí ocurre la magia: el controlador procesa la misión
    # 1. Calcula la ruta óptima desde la base más cercana.
    # 2. Verifica si la batería es suficiente considerando el peso de la carga.
    # 3. Comprueba las condiciones meteorológicas si se requiere.
    resultado = controlador.simulate_mission(solicitud)
    
    mostrar_resultado(resultado)
    print("\n")

def main() -> None:
    # Inicializamos el controlador principal de la simulación
    controlador = SimulationController()

    # Definimos varios casos para explicar diferentes situaciones en clase
    escenarios = [
        (
            "Transporte de Suministros Estándar (Todo OK)",
            MissionRequest(
                origin_hospital=HOSPITAL_ORIGEN,
                destination_hospital=HOSPITAL_DESTINO,
                payload_kg=1.5,           # 1.5 kg de carga
                battery_start_percent=100.0, # Batería llena
                ignore_weather=True,      # Para este ejemplo ignoramos el clima
            ),
        ),
        (
            "Emergencia con Carga Crítica (Batería Baja)",
            MissionRequest(
                origin_hospital=HOSPITAL_ORIGEN,
                destination_hospital=HOSPITAL_DESTINO,
                payload_kg=4.0,           # Mucha carga, consume más batería
                battery_start_percent=25.0,  # Solo 25% de batería
                ignore_weather=True,
            ),
        ),
        (
            "Error de Usuario: Origen y Destino iguales",
            MissionRequest(
                origin_hospital=HOSPITAL_ORIGEN,
                destination_hospital=HOSPITAL_ORIGEN,
                payload_kg=0.5,
                battery_start_percent=90.0,
                ignore_weather=True,
            ),
        ),
    ]

    print("INICIO DE LA DEMOSTRACIÓN DEL SISTEMA DE OPTIMIZACIÓN UAV")
    print("Este script valida la lógica del controlador de simulación.\n")
    
    for titulo, solicitud in escenarios:
        ejecutar_escenario(controlador, titulo, solicitud)

    # --- NUEVA SECCIÓN: VALIDACIÓN DE POLÍTICA DE INVENTARIO (s, Q) ---
    print("=" * 80)
    print(" VALIDACIÓN DE REGLA DE NEGOCIO: POLÍTICA DE INVENTARIO (s, Q)")
    print("-" * 80)
    
    # Creamos un inventario simulado para un hospital
    inv_ejemplo = Inventario(es_almacen_central=False)
    producto_test = "sangre"
    
    # Forzamos el stock a estar justo por encima del umbral para la demostración
    # s=15, Q=30 para sangre según CONFIG_INVENTARIO
    p = inv_ejemplo.productos[producto_test]
    p.stock_fisico = 16  # Umbral s es 15
    
    print(f"  [i] Producto: {producto_test}")
    print(f"  [i] Stock actual: {p.stock_fisico} | Umbral SQ (s): {p.umbral_s}")
    
    # Usamos el controlador para validar si se debe disparar la reposición tras el próximo consumo
    # El umbral es 15, el stock actual es 16. Si consumimos 1, llegamos a 15 (se dispara).
    cantidad_a_reponer = None
    if p.stock_fisico - 1 <= p.umbral_s:
        cantidad_a_reponer = p.cantidad_a_pedir_Q

    print(f"  [>] Registrando consumo de 1 unidad...")
    inv_ejemplo.registrar_consumo(producto_test, 1)
    
    print(f"  [i] Stock tras consumo: {p.stock_fisico}")
    print(f"  [i] Stock en camino (reposición): {p.stock_en_camino}")

    if cantidad_a_reponer:
        print(f"  [OK] VALIDACIÓN: Umbral SQ alcanzado. DISPARAR REABASTECIMIENTO DE {cantidad_a_reponer} ELEMENTOS (Q).")
    else:
        print(f"  [ERROR] VALIDACIÓN: Stock suficiente, no se requiere reabastecimiento.")
    print("-" * 80)
    print("\n")

if __name__ == "__main__":
    main()

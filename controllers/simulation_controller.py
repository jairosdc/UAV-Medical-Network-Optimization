"""
SimulationController - Controlador de Simulación de Misiones UAV
================================================================
Responsabilidad única: orquestar todos los servicios necesarios para
evaluar si una misión de transporte médico es viable o no.

Este controlador NO calcula nada por sí mismo. Delega en:
  - NetworkService    → calcula rutas y distancias entre nodos del grafo
  - WeatherService    → verifica si las condiciones meteorológicas permiten volar
  - Batería (service) → calcula el consumo de energía según carga y distancia
  - Inventario (model)→ comprueba si un producto necesita reabastecimiento (s, Q)

Flujo principal de una misión:
  1. Validar que origen ≠ destino
  2. Calcular la ruta óptima (base → origen → destino)
  3. Calcular si la batería es suficiente para el trayecto
  4. Verificar las condiciones meteorológicas del día
  5. Devolver el resultado completo (MissionResult)
"""

from typing import Optional

# ── Constantes globales del sistema ──────────────────────────────────────────
# Importamos los umbrales operativos definidos de forma centralizada.
# Si necesitas cambiar la velocidad o la reserva mínima, hazlo SOLO en parametros_globales.py
from parametros_globales import (
    BATERIA_MINIMA_VUELO,   # Porcentaje mínimo de batería que debe quedar al aterrizar
    VELOCIDAD_DRON_M_S,     # Velocidad de crucero del dron en metros/segundo
)

# ── Modelos de datos (estructuras de entrada/salida) ─────────────────────────
# MissionRequest: lo que el usuario solicita (origen, destino, carga, batería, fecha)
# MissionResult : la respuesta del sistema (viable/no viable, distancia, tiempo, motivos)
from models.clases_models import MissionRequest, MissionResult

# ── Servicios especializados ─────────────────────────────────────────────────
# Funciones de cálculo de batería (consumption model)
from services.funcionamiento_bateria_service import (
    calcular_bateria_restante,  # ¿Cuánta batería queda al final del vuelo?
    tiene_bateria_suficiente,   # ¿Supera el umbral mínimo de seguridad?
)

# Servicio de red: calcula distancias reales con la fórmula de Haversine
# y encuentra la ruta base → origen → destino
from services.grafo_distancias_service import NetworkService

# Servicio meteorológico: consulta el caché de datos AEMET para la fecha indicada
from services.meteorologia_service import WeatherService

# Modelo de inventario: contiene la lógica de la política de reabastecimiento (s, Q)
from models.inventario import Inventario


class SimulationController:
    """
    Controlador principal de simulación de misiones.

    Instancia los servicios de red y meteorología una sola vez (en el constructor)
    para no recrearlos en cada llamada y mejorar el rendimiento.
    Los nombres 'network' y 'weather' deben mantenerse: otros módulos los referencian.
    """

    def __init__(self):
        # Servicio de red: grafo de hospitales y bases con cálculo de distancias
        self.network = NetworkService()
        # Servicio meteorológico: acceso a datos AEMET en caché local
        self.weather = WeatherService()

    # ── Utilidades de conversión ──────────────────────────────────────────────

    @staticmethod
    def km_to_minutes(distance_km: float, speed_m_s: float) -> float:
        """
        Convierte una distancia en km y una velocidad en m/s a minutos de vuelo.
        Fórmula: t(min) = [d(km) / v(km/h)] × 60
        Es un método estático porque no necesita acceder a ningún atributo de la clase.
        """
        velocidad_km_h = speed_m_s * 3.6          # Conversión m/s → km/h
        return (distance_km / velocidad_km_h) * 60.0

    # ── Método principal ──────────────────────────────────────────────────────

    def simulate_mission(self, request: MissionRequest) -> MissionResult:
        """
        Evalúa la viabilidad completa de una misión de transporte médico.

        Parámetros:
            request (MissionRequest): todos los datos de la misión solicitada.

        Retorna:
            MissionResult: resultado con el veredicto (feasible=True/False) y
                           todos los detalles calculados (distancia, tiempo, batería...).
        """
        # Lista acumulativa de motivos de rechazo o advertencias.
        # Si está vacía al final, la misión es completamente viable.
        motivos = []

        # ── VALIDACIÓN 1: Origen ≠ Destino ───────────────────────────────────
        # Un dron no puede "transportar" algo al mismo lugar del que sale.
        if request.origin_hospital == request.destination_hospital:
            motivos.append("El origen y el destino no pueden ser el mismo hospital.")
            return MissionResult(feasible=False, reasons=motivos)

        # ── PASO 1: Calcular la ruta ──────────────────────────────────────────
        # NetworkService encuentra la base más cercana al hospital de origen
        # y calcula el trayecto completo: base → origen → destino.
        # 'route' es un RoutePlan con las distancias parciales y totales.
        ruta = self.network.build_route_plan(
            request.origin_hospital,
            request.destination_hospital,
        )

        # ── PASO 2: Calcular el consumo de batería ────────────────────────────
        # A mayor carga (kg), el dron consume más batería por km recorrido.
        # Si la carga excede el máximo físico, el servicio lanza ValueError.
        try:
            bateria_final = calcular_bateria_restante(
                carga_kg=request.payload_kg,
                distancia_km=ruta.distance_total_km,
                bateria_inicial_pct=request.battery_start_percent,
            )
        except ValueError as error:
            # Error físico: la carga supera la capacidad máxima del dron.
            # Abortamos inmediatamente con el mensaje del servicio.
            return MissionResult(feasible=False, reasons=[str(error)])

        # ── VALIDACIÓN 2: Comprobación de reserva mínima de batería ──────────
        # No basta con llegar: el dron debe aterrizar con al menos BATERIA_MINIMA_VUELO %.
        # Esto evita que el equipo quede varado sin energía en el hospital de destino.
        bateria_suficiente = tiene_bateria_suficiente(
            carga_kg=request.payload_kg,
            distancia_km=ruta.distance_total_km,
            bateria_inicial_pct=request.battery_start_percent,
            reserva_minima_pct=BATERIA_MINIMA_VUELO,
        )

        if not bateria_suficiente:
            motivos.append(
                f"Batería insuficiente: quedaría {bateria_final:.2f}% "
                f"y la reserva mínima es {BATERIA_MINIMA_VUELO:.2f}%."
            )

        # ── PASO 3: Estimar el tiempo de vuelo ───────────────────────────────
        # Tiempo estimado desde la base hasta el hospital de destino (en minutos).
        tiempo_estimado_min = self.km_to_minutes(ruta.distance_total_km, VELOCIDAD_DRON_M_S)

        # ── PASO 4: Verificar condiciones meteorológicas ──────────────────────
        # Hay tres posibles situaciones:
        #   a) ignore_weather=True  → el usuario pide ignorar el clima (útil para tests).
        #   b) weather_date presente → consultamos el caché AEMET para esa fecha.
        #   c) Sin fecha ni flag     → asumimos condiciones operativas por defecto.
        clima_ok = None

        if request.ignore_weather:
            # Modo "sin restricción climática": útil en demos y pruebas unitarias.
            clima_ok = True

        elif request.weather_date:
            # Buscamos los datos meteorológicos del día solicitado en el caché local.
            datos_clima = self.weather.get_weather_for_date(
                request.weather_date,
                allow_fetch_if_missing=True,  # Si no está en caché, intenta descargarlo
            )

            if datos_clima is None:
                # No hay datos para esa fecha: misión bloqueada por seguridad.
                clima_ok = False
                motivos.append(
                    f"No hay datos meteorológicos para la fecha {request.weather_date}."
                )
            else:
                # El servicio evalúa temperatura, viento y precipitación.
                # Retorna (True/False, lista_de_razones_si_falla).
                clima_ok, razones_clima = self.weather.is_operational_day(datos_clima)
                motivos.extend(razones_clima)

        else:
            # Sin fecha explícita, asumimos que el clima es operativo.
            clima_ok = True

        # ── DECISIÓN FINAL DE VIABILIDAD ─────────────────────────────────────
        # La misión es viable SOLO si pasa AMBAS verificaciones:
        #   ✓ Batería suficiente para completar el trayecto con reserva de seguridad
        #   ✓ Condiciones meteorológicas aptas para el vuelo
        es_viable = bateria_suficiente and (clima_ok is True)

        # ── RESULTADO ─────────────────────────────────────────────────────────
        # IMPORTANTE: los nombres de los parámetros (feasible, reasons, selected_base, etc.)
        # son los que define el dataclass MissionResult en models/clases_models.py.
        # NO se pueden renombrar aquí sin modificar también ese archivo.
        return MissionResult(
            feasible=es_viable,
            reasons=motivos,
            selected_base=ruta.start_base,
            distance_total_km=ruta.distance_total_km,
            estimated_flight_minutes=tiempo_estimado_min,
            battery_after_percent=bateria_final,
            weather_ok=clima_ok,
            route_plan=ruta,
        )

    # ── Validación de inventario ──────────────────────────────────────────────

    def verificar_politica_inventario(self, inventario: Inventario, nombre_producto: str) -> Optional[int]:
        """
        Comprueba si un producto ha alcanzado el umbral de reabastecimiento.

        Política (s, Q):
            - 's' es el umbral mínimo de seguridad (punto de pedido).
            - 'Q' es el lote fijo que se ordena cuando el stock baja hasta 's'.

        Lógica:
            Si stock_total_estimado <= s  →  pedir Q unidades (reabastecimiento).
            Si stock_total_estimado >  s  →  no hacer nada todavía.

        El stock_total_estimado incluye el stock físico más el stock ya pedido
        pero aún en tránsito (en el dron), para evitar pedir doble.

        Retorna:
            int  → cantidad Q a reponer si se ha alcanzado el umbral.
            None → si el stock es suficiente o el producto no existe.
        """
        # Verificamos que el producto existe en este inventario
        if nombre_producto not in inventario.productos:
            return None

        producto = inventario.productos[nombre_producto]

        # Regla (s, Q): si el stock total (físico + en camino) toca o cae bajo el umbral...
        if producto.stock_total_estimado <= producto.umbral_s:
            # ...se ordena un lote de reposición de tamaño Q
            return producto.cantidad_a_pedir_Q

        # Stock todavía por encima del umbral: no se necesita reabastecimiento
        return None
import unittest
from unittest.mock import MagicMock, patch

from models.clases_models import Drone, DeliveryCall
from services.optimizador_asignacion_service import ServicioDespacho
from parametros_globales import BATTERY_RESERVE_PERCENT

class TestServicioDespacho(unittest.TestCase):

    def setUp(self):
        """
        Prepara el entorno antes de cada test. 
        Simula la red logística para no depender de la base de datos real.
        """
        self.red_mock = MagicMock()
        self.red_mock.get_hospital.return_value = "Nodo_Hospital"
        self.red_mock.get_node.return_value = "Nodo_Dron"
        
        self.servicio = ServicioDespacho(self.red_mock)

    @patch('services.optimizador_asignacion_service.calcular_bateria_restante')
    def test_flota_completamente_ocupada(self, mock_bateria):
        """Caso 1: Ningún dron está disponible (en misión o cargando)."""
        drones = [
            Drone(drone_id="D01", base_name="Base1", status="mission"),
            Drone(drone_id="D02", base_name="Base1", status="charging")
        ]
        pedido = DeliveryCall(call_id=1, timestamp_min=0, origin_hospital="H1", destination_hospital="H2", payload_kg=2.0, priority=1)
        
        resultado = self.servicio.choose_best_drone(drones, pedido)
        
        self.assertIsNone(resultado)
        # Verificamos que ni siquiera se intentó calcular distancias
        self.red_mock.distance_between_nodes.assert_not_called()

    @patch('services.optimizador_asignacion_service.calcular_bateria_restante')
    def test_violacion_reserva_seguridad(self, mock_bateria):
        """Caso 2: El viaje consume demasiada batería y rompe el margen de seguridad."""
        drones = [Drone(drone_id="D01", base_name="Base1", status="available")]
        pedido = DeliveryCall(call_id=1, timestamp_min=0, origin_hospital="H1", destination_hospital="H2", payload_kg=2.0, priority=1)
        
        # Forzamos que la función matemática devuelva un valor por debajo de la reserva
        mock_bateria.return_value = BATTERY_RESERVE_PERCENT - 5.0 
        
        resultado = self.servicio.choose_best_drone(drones, pedido)
        self.assertIsNone(resultado)

    @patch('services.optimizador_asignacion_service.calcular_bateria_restante')
    def test_exceso_de_carga_fisica(self, mock_bateria):
        """Caso 3: El paquete excede la capacidad de carga del dron (captura de ValueError)."""
        drones = [Drone(drone_id="D01", base_name="Base1", status="available")]
        pedido = DeliveryCall(call_id=1, timestamp_min=0, origin_hospital="H1", destination_hospital="H2", payload_kg=50.0, priority=1) 
        
        # Simulamos que el módulo físico lanza un error por exceso de peso
        mock_bateria.side_effect = ValueError("Exceso de carga útil")
        
        resultado = self.servicio.choose_best_drone(drones, pedido)
        self.assertIsNone(resultado)

    @patch('services.optimizador_asignacion_service.calcular_bateria_restante')
    def test_prioridad_1_distancia_aproximacion(self, mock_bateria):
        """Caso 4: Prioridad 1 (Vital). Debe elegir al dron más cercano al hospital de origen."""
        drones = [
            Drone(drone_id="D_Lejano", base_name="Base1", status="available"),
            Drone(drone_id="D_Cercano", base_name="Base1", status="available")
        ]
        pedido = DeliveryCall(call_id=1, timestamp_min=0, origin_hospital="H1", destination_hospital="H2", payload_kg=2.0, priority=1)
        
        mock_bateria.return_value = 50.0 # Batería suficiente
        
        # Simulamos las distancias devueltas por la red:
        # D_Lejano: 20km al origen, 2km al destino
        # D_Cercano: 5km al origen, 30km al destino
        self.red_mock.distance_between_nodes.side_effect = [20.0, 2.0, 5.0, 30.0]
        
        resultado = self.servicio.choose_best_drone(drones, pedido)
        
        self.assertIsNotNone(resultado)
        # La lógica Topológica de P1 prioriza la distancia de aproximación, por tanto gana D_Cercano
        self.assertEqual(resultado.drone_id, "D_Cercano")

    @patch('services.optimizador_asignacion_service.calcular_bateria_restante')
    def test_prioridad_3_conservacion_energia(self, mock_bateria):
        """Caso 5: Prioridad 3 (Rutinario). Debe elegir al dron que termine con más batería."""
        drones = [
            Drone(drone_id="D_PocaBat", base_name="Base1", status="available"),
            Drone(drone_id="D_MuchaBat", base_name="Base1", status="available")
        ]
        pedido = DeliveryCall(call_id=1, timestamp_min=0, origin_hospital="H1", destination_hospital="H2", payload_kg=2.0, priority=3)
        
        # Simulamos los cálculos de batería final para ambos drones
        mock_bateria.side_effect = [30.0, 80.0]
        self.red_mock.distance_between_nodes.return_value = 10.0 # Distancia constante para no interferir
        
        resultado = self.servicio.choose_best_drone(drones, pedido)
        
        self.assertIsNotNone(resultado)
        # La lógica de P3 prioriza la magnitud de estado de la batería, ordenando en reverso
        self.assertEqual(resultado.drone_id, "D_MuchaBat")

if __name__ == '__main__':
    unittest.main()
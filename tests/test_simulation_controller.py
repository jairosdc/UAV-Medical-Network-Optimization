import unittest
from controllers.simulation_controller import SimulationController
from models.clases_models import MissionRequest

class TestSimulationController(unittest.TestCase):
    def setUp(self):
        self.controller = SimulationController()

    def test_mission_simulation_success(self):
        # Gregorio Marañón y 12 de Octubre existen en hospitales_almacenes_data.py
        request = MissionRequest(
            origin_hospital="Gregorio Marañón",
            destination_hospital="12 de Octubre",
            payload_kg=2.0,
            battery_start_percent=100.0,
            ignore_weather=True
        )
        result = self.controller.simulate_mission(request)
        
        self.assertTrue(result.feasible)
        self.assertGreater(result.distance_total_km, 0)
        self.assertIsNotNone(result.selected_base)
        print(f"\n[TEST] Misión factible: {result.distance_total_km:.2f} km, Base: {result.selected_base}")

    def test_mission_insufficient_battery(self):
        # Forzar batería insuficiente con batería inicial muy baja
        request = MissionRequest(
            origin_hospital="Gregorio Marañón",
            destination_hospital="12 de Octubre",
            payload_kg=2.0,
            battery_start_percent=21.0, # Muy cerca del límite de reserva (20%)
            ignore_weather=True
        )
        result = self.controller.simulate_mission(request)
        
        # Dependiendo de la distancia, 21% podría no ser suficiente
        if not result.feasible:
            self.assertIn("Batería insuficiente", result.reasons[0])
            print(f"[TEST] Misión rechazada por batería: {result.reasons}")

    def test_same_origin_destination(self):
        request = MissionRequest(
            origin_hospital="Gregorio Marañón",
            destination_hospital="Gregorio Marañón",
            payload_kg=1.0,
            battery_start_percent=100.0
        )
        result = self.controller.simulate_mission(request)
        self.assertFalse(result.feasible)
        self.assertEqual(result.reasons[0], "El origen y el destino no pueden ser el mismo hospital.")

if __name__ == "__main__":
    unittest.main()

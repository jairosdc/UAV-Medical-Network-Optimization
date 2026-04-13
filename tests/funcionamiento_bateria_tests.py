import unittest

# Importamos las funciones puras desde el archivo refactorizado
# (Asume que el archivo se llama funcionamiento_bateria_service.py)
from services.funcionamiento_bateria_service import (
    calcular_autonomia_km,
    calcular_consumo_porcentaje,
    calcular_bateria_restante,
    tiene_bateria_suficiente
)

class TestMotorBateria(unittest.TestCase):

    def test_autonomia_fronteras(self):
        """Verifica la autonomía en los límites de masa operativa."""
        # Límite inferior: Dron vacío
        self.assertAlmostEqual(calcular_autonomia_km(0.0), 94.0, places=2)
        
        # Límite superior: Carga máxima permitida (4.7 kg)
        self.assertAlmostEqual(calcular_autonomia_km(4.7), 72.0, places=2)
        
        # Interpolación: Media carga (2.35 kg)
        # 94.0 - 22.0 * (2.35 / 4.7) = 94.0 - 11.0 = 83.0
        self.assertAlmostEqual(calcular_autonomia_km(2.35), 83.0, places=2)

    def test_consumo_porcentaje(self):
        """Verifica la linealidad del consumo respecto a la distancia y la masa."""
        # 47 km vacío (sobre 94km de autonomía) = 50%
        self.assertAlmostEqual(calcular_consumo_porcentaje(0.0, 47.0), 50.0, places=2)
        
        # 36 km a carga máxima (sobre 72km de autonomía) = 50%
        self.assertAlmostEqual(calcular_consumo_porcentaje(4.7, 36.0), 50.0, places=2)

    def test_bateria_restante(self):
        """Verifica la correcta sustracción del flujo energético."""
        # Vuelo que consume 50%, empezando con 100% -> Resta 50%
        bateria_final = calcular_bateria_restante(carga_kg=0.0, distancia_km=47.0, bateria_inicial_pct=100.0)
        self.assertAlmostEqual(bateria_final, 50.0, places=2)

        # Vuelo que consume 50%, pero empezando con un 60% de batería -> Resta 10%
        bateria_final_2 = calcular_bateria_restante(carga_kg=4.7, distancia_km=36.0, bateria_inicial_pct=60.0)
        self.assertAlmostEqual(bateria_final_2, 10.0, places=2)

    def test_funcion_indicatriz_viabilidad(self):
        """Evalúa la lógica booleana del umbral de reserva s_bateria."""
        RESERVA = 20.0
        
        # Caso Viable: Inicia al 100%, consume 50% -> Queda 50% >= 20%
        self.assertTrue(tiene_bateria_suficiente(4.7, 36.0, 100.0, RESERVA))
        
        # Caso Inviable: Inicia al 60%, consume 50% -> Queda 10% < 20%
        self.assertFalse(tiene_bateria_suficiente(4.7, 36.0, 60.0, RESERVA))
        
        # Caso Límite Crítico: Inicia al 70%, consume 50% -> Queda 20% == 20%
        self.assertTrue(tiene_bateria_suficiente(4.7, 36.0, 70.0, RESERVA))

    def test_excepciones_dominio(self):
        """Asegura que el modelo rechace valores físicamente imposibles."""
        with self.assertRaises(ValueError):
            calcular_autonomia_km(-1.0)
            
        with self.assertRaises(ValueError):
            calcular_autonomia_km(5.0) # Mayor a 4.7 kg

if __name__ == '__main__':
    unittest.main(verbosity=2)
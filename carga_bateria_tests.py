import unittest
from dataclasses import dataclass
from typing import Optional

# Importamos la función pura que acabamos de crear
# (Ajusta el 'from' al nombre del archivo donde la hayas guardado)
from services.cargar_drone_service import procesar_recarga_dron

# Mokeamos (simulamos) la clase Dron para no tener que importar dependencias externas
@dataclass
class DronMock:
    battery_percent: float
    status: str
    busy_until_min: int = 0
    current_call_id: Optional[int] = None

class TestMotorRecarga(unittest.TestCase):

    def setUp(self):
        # Para hacer las matemáticas evidentes en el test, forzamos temporalmente
        # la tasa de recarga a un valor redondo (ej. 2.0% por minuto)
        import services.cargar_drone_service
        services.cargar_drone_service.CHARGE_RATE_PERCENT_PER_MIN = 2.0

    def test_invarianza_si_no_esta_cargando(self):
        """Verifica que un dron volando o disponible no absorba energía por error."""
        dron = DronMock(battery_percent=50.0, status="mission", busy_until_min=10, current_call_id=5)
        
        procesar_recarga_dron(dron, minutos_transcurridos=5)
        
        self.assertEqual(dron.battery_percent, 50.0)
        self.assertEqual(dron.status, "mission")

    def test_recarga_lineal_sin_saturacion(self):
        """Verifica la proyección lineal simple B(t + dt) = B(t) + r * dt."""
        # Batería 50%. Tasa 2.0%/min. Pasan 10 min -> Debería sumar 20%. Final: 70%.
        dron = DronMock(battery_percent=50.0, status="charging")
        
        procesar_recarga_dron(dron, minutos_transcurridos=10)
        
        self.assertEqual(dron.battery_percent, 70.0)
        self.assertEqual(dron.status, "charging") # Aún no ha terminado

    def test_saturacion_y_cambio_de_estado(self):
        """Verifica que cruzar el 100% detiene la carga y libera el dron."""
        # Batería 95%. Tasa 2.0%/min. Pasan 5 min -> Proyecta 105%.
        dron = DronMock(battery_percent=95.0, status="charging", busy_until_min=999, current_call_id=12)
        
        procesar_recarga_dron(dron, minutos_transcurridos=5)
        
        # Debe saturar en 100 y limpiar las variables
        self.assertEqual(dron.battery_percent, 100.0)
        self.assertEqual(dron.status, "available")
        self.assertEqual(dron.busy_until_min, 0)
        self.assertIsNone(dron.current_call_id)

    def test_saturacion_exacta(self):
        """Verifica el comportamiento crítico matemático cuando coincide exactamente en 100%."""
        # Batería 90%. Tasa 2.0%/min. Pasan 5 min -> Proyecta 100.0% exacto.
        dron = DronMock(battery_percent=90.0, status="charging")
        
        procesar_recarga_dron(dron, minutos_transcurridos=5)
        
        self.assertEqual(dron.battery_percent, 100.0)
        self.assertEqual(dron.status, "available")

if __name__ == '__main__':
    unittest.main(verbosity=2)
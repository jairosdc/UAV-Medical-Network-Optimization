import unittest
from unittest.mock import MagicMock
from services.visualizaciones import mostrar_graficas_resultados

class TestVisualizaciones(unittest.TestCase):
    def test_mostrar_graficas_no_falla(self):
        """
        Prueba que la función de mostrar_graficas_resultados se ejecuta sin
        lanzar excepciones con datos simulados. Se usa mock para evitar que
        plt.show() bloquee la ejecución.
        """
        import matplotlib.pyplot as plt
        
        # Guardamos la funcion original
        original_show = plt.show
        
        try:
            # Mock de plt.show para que no se abra la ventana gráfica durante el test
            plt.show = MagicMock()
            
            # Crear un gestor de flota simulado
            mock_gestor = MagicMock()
            
            # Simular estadísticas
            mock_gestor.estadisticas.assigned_calls = 100
            mock_gestor.estadisticas.completed_calls = 90
            mock_gestor.estadisticas.rejected_calls = 10
            
            # Simular drones
            dron1 = MagicMock()
            dron1.flight_minutes = 200
            dron1.charging_minutes = 50
            
            dron2 = MagicMock()
            dron2.flight_minutes = 150
            dron2.charging_minutes = 100
            
            mock_gestor.drones = {"D01": dron1, "D02": dron2}
            
            # Llamar a la función
            mostrar_graficas_resultados(gestor_flota=mock_gestor, total_generados=120, minutos_simulacion=1000)
            
            # Verificar que plt.show fue llamado
            plt.show.assert_called_once()
            
        finally:
            # Restaurar la función original
            plt.show = original_show

if __name__ == '__main__':
    unittest.main()

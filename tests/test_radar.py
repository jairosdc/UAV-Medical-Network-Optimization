"""
test_radar.py - Tests de Validacion para FlyRadar
==================================================
Verifica:
  1. Interpolacion lineal de coordenadas (la logica central del radar).
  2. Determinacion correcta de colores por bateria y clima.
  3. Interpolacion de bateria estimada.
  4. Registro y exportacion de telemetria.
"""

import sys
import os
import json
import math
import tempfile
import unittest

# Ajustar path para importar modulos del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestInterpolacionPosicion(unittest.TestCase):
    """Verifica la interpolacion lineal de lat/lon."""

    def setUp(self):
        """Coordenadas reales de prueba: BASE SUR -> 12 de Octubre."""
        self.lat_origen = 40.3968   # BASE SUR
        self.lon_origen = -3.6985
        self.lat_destino = 40.3839  # 12 de Octubre
        self.lon_destino = -3.6911

    def _interpolar(self, progreso):
        """Funcion auxiliar de interpolacion (replica de radar_app.py)."""
        progreso = max(0.0, min(1.0, progreso))
        lat = self.lat_origen + (self.lat_destino - self.lat_origen) * progreso
        lon = self.lon_origen + (self.lon_destino - self.lon_origen) * progreso
        return lat, lon

    def test_progreso_0_esta_en_origen(self):
        """En t_salida (progreso=0), el dron esta en el origen."""
        lat, lon = self._interpolar(0.0)
        self.assertAlmostEqual(lat, self.lat_origen, places=6)
        self.assertAlmostEqual(lon, self.lon_origen, places=6)

    def test_progreso_1_esta_en_destino(self):
        """En t_llegada (progreso=1), el dron esta en el destino."""
        lat, lon = self._interpolar(1.0)
        self.assertAlmostEqual(lat, self.lat_destino, places=6)
        self.assertAlmostEqual(lon, self.lon_destino, places=6)

    def test_progreso_50_esta_en_punto_medio(self):
        """Al 50%, el dron esta exactamente en el punto medio."""
        lat, lon = self._interpolar(0.5)
        lat_esperada = (self.lat_origen + self.lat_destino) / 2
        lon_esperada = (self.lon_origen + self.lon_destino) / 2
        self.assertAlmostEqual(lat, lat_esperada, places=6)
        self.assertAlmostEqual(lon, lon_esperada, places=6)

    def test_progreso_25_esta_a_un_cuarto(self):
        """Al 25%, la posicion es 1/4 del camino."""
        lat, lon = self._interpolar(0.25)
        lat_esperada = self.lat_origen + (self.lat_destino - self.lat_origen) * 0.25
        lon_esperada = self.lon_origen + (self.lon_destino - self.lon_origen) * 0.25
        self.assertAlmostEqual(lat, lat_esperada, places=6)
        self.assertAlmostEqual(lon, lon_esperada, places=6)

    def test_progreso_negativo_clampea_a_0(self):
        """Valores negativos se tratan como 0."""
        lat, lon = self._interpolar(-0.5)
        self.assertAlmostEqual(lat, self.lat_origen, places=6)
        self.assertAlmostEqual(lon, self.lon_origen, places=6)

    def test_progreso_mayor_que_1_clampea_a_1(self):
        """Valores > 1 se tratan como 1."""
        lat, lon = self._interpolar(1.5)
        self.assertAlmostEqual(lat, self.lat_destino, places=6)
        self.assertAlmostEqual(lon, self.lon_destino, places=6)

    def test_interpolacion_desde_minutos(self):
        """
        Caso real: el dron sale en min 0 y llega en min 4.
        En el minuto 2, progreso = (2-0)/(4-0) = 0.5
        """
        t_salida = 0
        t_llegada = 4
        t_actual = 2

        progreso = (t_actual - t_salida) / (t_llegada - t_salida)
        self.assertAlmostEqual(progreso, 0.5)

        lat, lon = self._interpolar(progreso)
        lat_esperada = (self.lat_origen + self.lat_destino) / 2
        self.assertAlmostEqual(lat, lat_esperada, places=6)


class TestColorDron(unittest.TestCase):
    """Verifica la logica de colores del radar."""

    CLIMAS_ADVERSOS = {"lluvia_fuerte", "viento_fuerte", "viento_normal", "lluvia_normal"}
    UMBRAL_BATERIA = 35.0

    def _determinar_color(self, bateria, clima):
        """Replica de la funcion de radar_app.py."""
        if bateria < self.UMBRAL_BATERIA:
            return [255, 60, 60, 230]       # Rojo
        if clima in self.CLIMAS_ADVERSOS:
            return [255, 200, 40, 230]      # Amarillo
        return [56, 189, 248, 240]          # Cian

    def test_bateria_baja_es_rojo(self):
        """Bateria < 35% siempre da rojo, sin importar el clima."""
        color = self._determinar_color(20.0, "dia_normal")
        self.assertEqual(color[0], 255)
        self.assertEqual(color[1], 60)

    def test_bateria_baja_prioridad_sobre_clima(self):
        """Bateria baja tiene prioridad sobre clima adverso."""
        color = self._determinar_color(10.0, "viento_fuerte")
        self.assertEqual(color[0], 255)
        self.assertEqual(color[1], 60)  # Rojo, no amarillo

    def test_clima_adverso_es_amarillo(self):
        """Con bateria normal y clima adverso, da amarillo."""
        for clima in self.CLIMAS_ADVERSOS:
            color = self._determinar_color(80.0, clima)
            self.assertEqual(color[0], 255, f"Fallo con clima: {clima}")
            self.assertEqual(color[1], 200, f"Fallo con clima: {clima}")

    def test_normal_es_cian(self):
        """Con bateria ok y buen clima, da cian."""
        color = self._determinar_color(90.0, "dia_normal")
        self.assertEqual(color[0], 56)
        self.assertEqual(color[1], 189)

    def test_bateria_exacta_35_es_normal(self):
        """Bateria exactamente en 35% NO es baja (es >= umbral)."""
        color = self._determinar_color(35.0, "dia_normal")
        self.assertEqual(color[0], 56)  # Cian, no rojo


class TestInterpolacionBateria(unittest.TestCase):
    """Verifica la estimacion de bateria durante el vuelo."""

    def _interpolar_bateria(self, bateria_inicial, progreso, tipo):
        consumo = 15.0 if tipo == "ida" else 10.0
        return bateria_inicial - (consumo * progreso)

    def test_bateria_al_inicio(self):
        """Al inicio del vuelo, la bateria no ha cambiado."""
        bat = self._interpolar_bateria(100.0, 0.0, "ida")
        self.assertAlmostEqual(bat, 100.0)

    def test_bateria_al_final_ida(self):
        """Al final de un tramo de ida, se consume ~15%."""
        bat = self._interpolar_bateria(100.0, 1.0, "ida")
        self.assertAlmostEqual(bat, 85.0)

    def test_bateria_al_final_vuelta(self):
        """Al final de un tramo de vuelta, se consume ~10%."""
        bat = self._interpolar_bateria(50.0, 1.0, "vuelta")
        self.assertAlmostEqual(bat, 40.0)

    def test_bateria_medio_camino(self):
        """A mitad de camino, la bateria esta a medio consumo."""
        bat = self._interpolar_bateria(100.0, 0.5, "ida")
        self.assertAlmostEqual(bat, 92.5)


class TestTelemetriaService(unittest.TestCase):
    """Verifica el servicio de registro de telemetria."""

    def test_registrar_tramo(self):
        """Un tramo registrado se guarda correctamente."""
        from services.telemetria_service import TelemetriaService
        ts = TelemetriaService()
        ts.registrar_tramo(
            id_dron="D01",
            nombre_origen="BASE SUR",
            nombre_destino="12 de Octubre",
            t_salida=0,
            t_llegada=4,
            tipo_trayecto="ida",
            bateria_inicial=100.0,
            clima="dia_normal",
        )
        self.assertEqual(ts.total_tramos(), 1)
        reg = ts.registros[0]
        self.assertEqual(reg["id_dron"], "D01")
        self.assertEqual(reg["origen"]["nombre"], "BASE SUR")
        self.assertEqual(reg["destino"]["nombre"], "12 de Octubre")
        self.assertEqual(reg["tipo_trayecto"], "ida")

    def test_exportar_json(self):
        """La exportacion a JSON genera un archivo valido."""
        from services.telemetria_service import TelemetriaService
        ts = TelemetriaService()
        ts.registrar_tramo(
            id_dron="D02",
            nombre_origen="BASE NORTE",
            nombre_destino="La Paz",
            t_salida=10,
            t_llegada=13,
            tipo_trayecto="ida",
            bateria_inicial=95.0,
            clima="viento_normal",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            ruta_tmp = tmp.name

        try:
            ts.exportar_json(ruta_tmp)
            with open(ruta_tmp, "r", encoding="utf-8") as f:
                datos = json.load(f)
            self.assertEqual(len(datos), 1)
            self.assertEqual(datos[0]["id_dron"], "D02")
            self.assertIn("lat", datos[0]["origen"])
            self.assertIn("lon", datos[0]["destino"])
        finally:
            os.unlink(ruta_tmp)

    def test_coordenadas_reales_en_registro(self):
        """Las coordenadas del nodo se rellenan automaticamente."""
        from services.telemetria_service import TelemetriaService
        ts = TelemetriaService()
        ts.registrar_tramo(
            id_dron="D01",
            nombre_origen="La Paz",
            nombre_destino="BASE NORTE",
            t_salida=5,
            t_llegada=8,
            tipo_trayecto="vuelta",
            bateria_inicial=60.0,
            clima="dia_normal",
        )
        reg = ts.registros[0]
        self.assertAlmostEqual(reg["origen"]["lat"], 40.4733, places=3)
        self.assertAlmostEqual(reg["destino"]["lat"], 40.4636, places=3)


if __name__ == "__main__":
    unittest.main()

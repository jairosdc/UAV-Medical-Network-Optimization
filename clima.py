"""
clima.py
========

Simulador estocástico de condiciones meteorológicas.

Cada intervalo de tiempo, el clima puede cambiar a un estado diferente
según las probabilidades del escenario activo. Los drones SIEMPRE vuelan,
pero su velocidad se penaliza según el estado climático.

Escenarios disponibles:
  - "normal"   : clima favorable la mayor parte del tiempo
  - "lluvioso" : más lluvia normal y lluvia fuerte
  - "adverso"  : más lluvia fuerte y viento fuerte

Uso:
    clima = SimuladorClima(intervalo_cambio_min=300, escenario_clima="normal")
    estado = clima.actualizar(minuto_actual)
    factor_velocidad = estado.factor_velocidad
"""

import random
from dataclasses import dataclass


@dataclass
class EstadoClima:
    nombre: str
    probabilidad: float
    factor_velocidad: float
    descripcion: str


# ---------------------------------------------------------------------------
# Perfiles climáticos
# ---------------------------------------------------------------------------
# Las probabilidades de cada escenario deben sumar 1.0.
# Los factores de velocidad son fijos independientemente del escenario.

PERFILES_CLIMA = {
    "normal": [
        EstadoClima("dia_normal",    0.67, 1.00, "[SOL] Día normal"),
        EstadoClima("lluvia_normal", 0.12, 0.85, "[LLU] Lluvia ligera"),
        EstadoClima("lluvia_fuerte", 0.04, 0.65, "[TOR] Lluvia fuerte"),
        EstadoClima("calor",         0.04, 0.90, "[CAL] Calor extremo"),
        EstadoClima("viento_normal", 0.12, 0.90, "[VIE] Viento moderado"),
        EstadoClima("viento_fuerte", 0.01, 0.60, "[VEN] Viento fuerte"),
    ],
    "lluvioso": [
        EstadoClima("dia_normal",    0.40, 1.00, "[SOL] Día normal"),
        EstadoClima("lluvia_normal", 0.30, 0.85, "[LLU] Lluvia ligera"),
        EstadoClima("lluvia_fuerte", 0.15, 0.65, "[TOR] Lluvia fuerte"),
        EstadoClima("calor",         0.03, 0.90, "[CAL] Calor extremo"),
        EstadoClima("viento_normal", 0.10, 0.90, "[VIE] Viento moderado"),
        EstadoClima("viento_fuerte", 0.02, 0.60, "[VEN] Viento fuerte"),
    ],
    "adverso": [
        EstadoClima("dia_normal",    0.25, 1.00, "[SOL] Día normal"),
        EstadoClima("lluvia_normal", 0.20, 0.85, "[LLU] Lluvia ligera"),
        EstadoClima("lluvia_fuerte", 0.25, 0.65, "[TOR] Lluvia fuerte"),
        EstadoClima("calor",         0.05, 0.90, "[CAL] Calor extremo"),
        EstadoClima("viento_normal", 0.15, 0.90, "[VIE] Viento moderado"),
        EstadoClima("viento_fuerte", 0.10, 0.60, "[VEN] Viento fuerte"),
    ],
}


class SimuladorClima:

    def __init__(self, intervalo_cambio_min=60, semilla=None, escenario_clima="normal"):
        if escenario_clima not in PERFILES_CLIMA:
            raise ValueError(
                f"escenario_clima inválido: '{escenario_clima}'. "
                f"Opciones: {list(PERFILES_CLIMA.keys())}"
            )

        self.intervalo_cambio_min = intervalo_cambio_min
        self.escenario_clima = escenario_clima
        self.rng = random.Random(semilla)
        self.estados = PERFILES_CLIMA[escenario_clima]

        suma = sum(e.probabilidad for e in self.estados)
        assert abs(suma - 1.0) < 0.01, f"Probabilidades no suman 1.0 ({suma})"

        self.estado_actual = self.estados[0]
        self.ultimo_cambio_min = -self.intervalo_cambio_min
        self.historial = []

    def actualizar(self, minuto_actual):
        """Actualiza el clima si ha pasado el intervalo. Devuelve el estado actual."""
        if (minuto_actual - self.ultimo_cambio_min) >= self.intervalo_cambio_min:
            estado_anterior = self.estado_actual
            self.estado_actual = self._sortear_estado()
            self.ultimo_cambio_min = minuto_actual
            self.historial.append({
                "minuto": minuto_actual,
                "estado_anterior": estado_anterior.nombre,
                "estado_nuevo": self.estado_actual.nombre,
                "factor_velocidad": self.estado_actual.factor_velocidad,
            })
        return self.estado_actual

    def _sortear_estado(self):
        pesos = [e.probabilidad for e in self.estados]
        return self.rng.choices(self.estados, weights=pesos, k=1)[0]

    def obtener_factor_velocidad(self):
        return self.estado_actual.factor_velocidad

    def obtener_descripcion(self):
        return self.estado_actual.descripcion

    def obtener_nombre(self):
        return self.estado_actual.nombre

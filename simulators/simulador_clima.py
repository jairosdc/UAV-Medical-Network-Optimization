"""
SimuladorClima - Motor de Meteorología Estocástica
===================================================

Genera estados climáticos aleatorios usando perfiles de probabilidad.

Cada estado tiene:
  - Una probabilidad de ocurrencia
  - Un factor de penalización sobre la velocidad del dron

Los drones SIEMPRE vuelan, pero su velocidad se reduce según el clima.

Escenarios disponibles:
  - normal: clima favorable la mayor parte del tiempo
  - lluvioso: más lluvia normal y lluvia fuerte
  - adverso: más lluvia fuerte y viento fuerte
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
# PERFILES CLIMÁTICOS
# ---------------------------------------------------------------------------
# Cada escenario cambia solo las probabilidades.
# Los factores de velocidad se mantienen fijos para cada estado climático.
# ---------------------------------------------------------------------------

PERFILES_CLIMA = {
    "normal": [
        EstadoClima(
            nombre="dia_normal",
            probabilidad=0.67,
            factor_velocidad=1.00,
            descripcion="[SOL] Dia normal",
        ),
        EstadoClima(
            nombre="lluvia_normal",
            probabilidad=0.12,
            factor_velocidad=0.85,
            descripcion="[LLU] Lluvia ligera",
        ),
        EstadoClima(
            nombre="lluvia_fuerte",
            probabilidad=0.04,
            factor_velocidad=0.65,
            descripcion="[TOR] Lluvia fuerte",
        ),
        EstadoClima(
            nombre="calor",
            probabilidad=0.04,
            factor_velocidad=0.90,
            descripcion="[CAL] Calor extremo",
        ),
        EstadoClima(
            nombre="viento_normal",
            probabilidad=0.12,
            factor_velocidad=0.90,
            descripcion="[VIE] Viento moderado",
        ),
        EstadoClima(
            nombre="viento_fuerte",
            probabilidad=0.01,
            factor_velocidad=0.60,
            descripcion="[VEN] Viento fuerte",
        ),
    ],

    "lluvioso": [
        EstadoClima(
            nombre="dia_normal",
            probabilidad=0.40,
            factor_velocidad=1.00,
            descripcion="[SOL] Dia normal",
        ),
        EstadoClima(
            nombre="lluvia_normal",
            probabilidad=0.30,
            factor_velocidad=0.85,
            descripcion="[LLU] Lluvia ligera",
        ),
        EstadoClima(
            nombre="lluvia_fuerte",
            probabilidad=0.15,
            factor_velocidad=0.65,
            descripcion="[TOR] Lluvia fuerte",
        ),
        EstadoClima(
            nombre="calor",
            probabilidad=0.03,
            factor_velocidad=0.90,
            descripcion="[CAL] Calor extremo",
        ),
        EstadoClima(
            nombre="viento_normal",
            probabilidad=0.10,
            factor_velocidad=0.90,
            descripcion="[VIE] Viento moderado",
        ),
        EstadoClima(
            nombre="viento_fuerte",
            probabilidad=0.02,
            factor_velocidad=0.60,
            descripcion="[VEN] Viento fuerte",
        ),
    ],

    "adverso": [
        EstadoClima(
            nombre="dia_normal",
            probabilidad=0.25,
            factor_velocidad=1.00,
            descripcion="[SOL] Dia normal",
        ),
        EstadoClima(
            nombre="lluvia_normal",
            probabilidad=0.20,
            factor_velocidad=0.85,
            descripcion="[LLU] Lluvia ligera",
        ),
        EstadoClima(
            nombre="lluvia_fuerte",
            probabilidad=0.25,
            factor_velocidad=0.65,
            descripcion="[TOR] Lluvia fuerte",
        ),
        EstadoClima(
            nombre="calor",
            probabilidad=0.05,
            factor_velocidad=0.90,
            descripcion="[CAL] Calor extremo",
        ),
        EstadoClima(
            nombre="viento_normal",
            probabilidad=0.15,
            factor_velocidad=0.90,
            descripcion="[VIE] Viento moderado",
        ),
        EstadoClima(
            nombre="viento_fuerte",
            probabilidad=0.10,
            factor_velocidad=0.60,
            descripcion="[VEN] Viento fuerte",
        ),
    ],
}


class SimuladorClima:

    def __init__(
        self,
        intervalo_cambio_min=60,
        semilla=None,
        escenario_clima="normal",
    ):

        if escenario_clima not in PERFILES_CLIMA:
            escenarios_validos = ", ".join(PERFILES_CLIMA.keys())
            raise ValueError(
                f"escenario_clima inválido: {escenario_clima}. "
                f"Opciones válidas: {escenarios_validos}"
            )

        self.intervalo_cambio_min = intervalo_cambio_min
        self.escenario_clima = escenario_clima
        self.rng = random.Random(semilla)

        self.estados = PERFILES_CLIMA[escenario_clima]

        suma = sum(e.probabilidad for e in self.estados)
        assert abs(suma - 1.0) < 0.01, (
            f"ERROR: Las probabilidades deben sumar 1.0, pero suman {suma}"
        )

        self.estado_actual = self.estados[0]
        self.ultimo_cambio_min = -self.intervalo_cambio_min
        self.historial = []

    def actualizar(self, minuto_actual):

        if (minuto_actual - self.ultimo_cambio_min) >= self.intervalo_cambio_min:
            estado_anterior = self.estado_actual
            self.estado_actual = self._sortear_estado()
            self.ultimo_cambio_min = minuto_actual

            self.historial.append({
                "minuto": minuto_actual,
                "escenario_clima": self.escenario_clima,
                "estado_anterior": estado_anterior.nombre,
                "estado_nuevo": self.estado_actual.nombre,
                "factor_velocidad": self.estado_actual.factor_velocidad,
            })

        return self.estado_actual

    def _sortear_estado(self):

        pesos = [estado.probabilidad for estado in self.estados]
        elegido = self.rng.choices(self.estados, weights=pesos, k=1)[0]
        return elegido

    def obtener_factor_velocidad(self):
        return self.estado_actual.factor_velocidad

    def obtener_descripcion(self):
        return self.estado_actual.descripcion

    def obtener_nombre(self):
        return self.estado_actual.nombre
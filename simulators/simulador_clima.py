"""
SimuladorClima - Motor de Meteorología Estocástica
===================================================
Genera estados climáticos aleatorios usando un vector de probabilidades.

Cada estado tiene:
  - Una probabilidad de ocurrencia (las probabilidades suman 1.0)
  - Un factor de penalización sobre la velocidad del dron

Los drones SIEMPRE vuelan, pero su velocidad se reduce según el clima.
Ejemplo: con viento fuerte, el dron vuela al 60% de su velocidad nominal.

Estados posibles (6):
  1. Día normal       → velocidad completa (factor 1.00)
  2. Lluvia normal    → ligeramente más lento (factor 0.85)
  3. Lluvia fuerte    → bastante más lento (factor 0.65)
  4. Calor extremo    → algo más lento (factor 0.90)
  5. Viento normal    → moderadamente más lento (factor 0.80)
  6. Viento fuerte    → significativamente más lento (factor 0.60)
"""

import random
from dataclasses import dataclass

# Estados climaticos con sus probabilidades y factores de velocidad
@dataclass
class EstadoClima:

    nombre: str
    probabilidad: float
    factor_velocidad: float
    descripcion: str

ESTADOS_CLIMA = [
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
        factor_velocidad=0.70,
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
        factor_velocidad=0.70,
        descripcion="[VEN] Viento fuerte",
    ),
]

class SimuladorClima:

    def __init__(self, intervalo_cambio_min=60, semilla=None):
        
        self.intervalo_cambio_min = intervalo_cambio_min
        self.rng = random.Random(semilla) # Semilla para reproducibilidad
        self.estados = ESTADOS_CLIMA

        suma = sum(e.probabilidad for e in self.estados)
        assert abs(suma - 1.0) < 0.01, (
            f"ERROR: Las probabilidades deben sumar 1.0, pero suman {suma}"
        )

        self.estado_actual = self.estados[0]
        self.ultimo_cambio_min = -self.intervalo_cambio_min
        self.historial = []

    def actualizar(self, minuto_actual):

        if (minuto_actual - self.ultimo_cambio_min) >= self.intervalo_cambio_min:
            # Toca sortear un nuevo estado climático
            estado_anterior = self.estado_actual
            self.estado_actual = self._sortear_estado()
            self.ultimo_cambio_min = minuto_actual

            # Registramos el cambio en el historial
            self.historial.append({
                "minuto": minuto_actual,
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

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

Uso típico:
    clima = SimuladorClima(intervalo_cambio_min=60, semilla=42)
    for minuto in range(7200):
        estado = clima.actualizar(minuto)
        velocidad_real = VELOCIDAD_DRON_M_S * estado.factor_velocidad
"""

import random
from dataclasses import dataclass
from typing import Optional, List


# ── Modelo de datos ──────────────────────────────────────────────────────────

@dataclass
class EstadoClima:
    """
    Representa un estado meteorológico concreto.

    Atributos:
        nombre:           Identificador interno (ej: "dia_normal")
        probabilidad:     Probabilidad de que ocurra (0.0 a 1.0)
        factor_velocidad: Multiplicador de la velocidad del dron.
                          1.0 = velocidad completa, 0.6 = 40% más lento.
        descripcion:      Texto legible para mostrar en consola.
    """
    nombre: str
    probabilidad: float
    factor_velocidad: float
    descripcion: str


# ── Vector de estados climáticos ─────────────────────────────────────────────
# Cada estado tiene una probabilidad distinta porque no todos los climas
# son igual de frecuentes. La suma de todas las probabilidades debe ser 1.0.
#
# Las penalizaciones de velocidad están basadas en efectos reales:
#   - Lluvia: reduce visibilidad y los sensores del dron funcionan peor.
#   - Calor extremo: el aire es menos denso, los motores rinden menos.
#   - Viento: el dron gasta más energía luchando contra las corrientes.

ESTADOS_CLIMA: List[EstadoClima] = [
    EstadoClima(
        nombre="dia_normal",
        probabilidad=0.40,
        factor_velocidad=1.00,
        descripcion="☀️  Día normal",
    ),
    EstadoClima(
        nombre="lluvia_normal",
        probabilidad=0.15,
        factor_velocidad=0.85,
        descripcion="🌧️  Lluvia ligera",
    ),
    EstadoClima(
        nombre="lluvia_fuerte",
        probabilidad=0.05,
        factor_velocidad=0.65,
        descripcion="⛈️  Lluvia fuerte",
    ),
    EstadoClima(
        nombre="calor",
        probabilidad=0.15,
        factor_velocidad=0.90,
        descripcion="🌡️  Calor extremo",
    ),
    EstadoClima(
        nombre="viento_normal",
        probabilidad=0.15,
        factor_velocidad=0.80,
        descripcion="💨 Viento moderado",
    ),
    EstadoClima(
        nombre="viento_fuerte",
        probabilidad=0.10,
        factor_velocidad=0.60,
        descripcion="🌪️  Viento fuerte",
    ),
]


# ── Motor de simulación ─────────────────────────────────────────────────────

class SimuladorClima:
    """
    Motor de simulación climática estocástica.

    Funcionamiento:
        - Cada 'intervalo_cambio_min' minutos simulados (por defecto 60 = 1 hora),
          se "lanza un dado" para decidir el nuevo estado del clima.
        - El dado está cargado: cada estado tiene una probabilidad distinta
          (definida en ESTADOS_CLIMA).
        - El estado se mantiene estable hasta el siguiente sorteo.

    Parámetros del constructor:
        intervalo_cambio_min: Cada cuántos minutos se re-evalúa el clima.
        semilla:              Semilla para el generador aleatorio.
                              Si es None, cada ejecución será distinta.
                              Si es un entero (ej: 42), el resultado es reproducible.
    """

    def __init__(self, intervalo_cambio_min: int = 60, semilla: Optional[int] = None):
        # Guardamos la configuración
        self.intervalo_cambio_min = intervalo_cambio_min

        # Generador aleatorio propio (no afecta al random global del proyecto)
        self.rng = random.Random(semilla)

        # Copia local del vector de estados
        self.estados = ESTADOS_CLIMA

        # Verificación de seguridad: las probabilidades deben sumar 1.0
        suma = sum(e.probabilidad for e in self.estados)
        assert abs(suma - 1.0) < 0.01, (
            f"ERROR: Las probabilidades deben sumar 1.0, pero suman {suma}"
        )

        # Estado inicial: comenzamos con día normal
        self.estado_actual: EstadoClima = self.estados[0]

        # Marcador del último minuto en que se cambió el clima
        # Lo ponemos en -infinito para forzar un sorteo en t=0
        self.ultimo_cambio_min: int = -self.intervalo_cambio_min

        # Historial de cambios (útil para análisis posterior)
        self.historial: List[dict] = []

    # ── Método principal (se llama en cada minuto del bucle) ──────────────

    def actualizar(self, minuto_actual: int) -> EstadoClima:
        """
        Evalúa si toca cambiar el clima y retorna el estado vigente.

        Lógica:
          - Si han pasado >= 'intervalo_cambio_min' desde el último cambio,
            se sortea un nuevo estado usando las probabilidades.
          - Si no, se devuelve el estado actual sin cambios.

        Retorna:
            EstadoClima: el estado meteorológico vigente en este minuto.
        """
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

    # ── Sorteo estocástico ───────────────────────────────────────────────

    def _sortear_estado(self) -> EstadoClima:
        """
        Selecciona un estado climático al azar usando el vector de probabilidades.

        Usa random.choices() con pesos (weights). Esta función de Python
        permite pasar una lista de pesos y seleccionar 1 elemento (k=1)
        respetando las probabilidades relativas de cada peso.

        Ejemplo:
          Si los pesos son [0.40, 0.15, 0.05, 0.15, 0.15, 0.10],
          el primer estado (día normal) tiene un 40% de ser elegido.
        """
        pesos = [estado.probabilidad for estado in self.estados]
        elegido = self.rng.choices(self.estados, weights=pesos, k=1)[0]
        return elegido

    # ── Métodos de consulta (getters) ────────────────────────────────────

    def obtener_factor_velocidad(self) -> float:
        """Retorna el factor de velocidad del estado climático actual (0.0 a 1.0)."""
        return self.estado_actual.factor_velocidad

    def obtener_descripcion(self) -> str:
        """Retorna la descripción legible del estado actual (con emoji)."""
        return self.estado_actual.descripcion

    def obtener_nombre(self) -> str:
        """Retorna el nombre interno del estado actual."""
        return self.estado_actual.nombre

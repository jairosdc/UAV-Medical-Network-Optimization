"""
demo_simulador_clima.py - Demo del Simulador de Meteorologia
=============================================================
Este script demuestra como funciona el motor de meteorologia simulada
para la red de drones hospitalarios.

Ejecutar desde la raiz del proyecto:
    python tests/demo_simulador_clima.py

Lo que veras:
  1. Tabla de todos los estados climaticos con sus probabilidades
  2. Simulacion de 24 horas con cambios cada hora
  3. Comparativa: distribucion teorica vs. observada
  4. Ejemplo de impacto en el tiempo de vuelo de un dron
"""

import sys
sys.path.insert(0, '.')  # Para poder importar modulos desde la raiz del proyecto

# Importamos el simulador de clima y sus constantes
from simulators.simulador_clima import SimuladorClima, ESTADOS_CLIMA

# Importamos la velocidad del dron para calcular ejemplos
from parametros_globales import VELOCIDAD_DRON_M_S


def main():
    """Funcion principal de la demo."""

    print("=" * 70)
    print("  DEMO - SIMULADOR DE METEOROLOGIA ESTOCASTICA")
    print("=" * 70)

    # =====================================================================
    # PARTE 1: Mostrar la tabla de estados climaticos
    # =====================================================================
    # El vector de probabilidades define que tan probable es cada clima.
    # Los factores de velocidad representan la penalizacion sobre el dron.

    print("\n--- PARTE 1: ESTADOS CLIMATICOS DISPONIBLES ---\n")

    velocidad_base_km_h = VELOCIDAD_DRON_M_S * 3.6  # Conversion m/s -> km/h

    print(f"  Velocidad base del dron: {VELOCIDAD_DRON_M_S} m/s = {velocidad_base_km_h:.0f} km/h\n")
    print(f"  {'Estado':<22s} {'Prob.':<8s} {'Factor':<8s} {'Vel. Efectiva':<15s} {'Penalizacion'}")
    print(f"  {'-' * 22} {'-' * 7} {'-' * 7} {'-' * 14} {'-' * 14}")

    for estado in ESTADOS_CLIMA:
        vel_efectiva = velocidad_base_km_h * estado.factor_velocidad
        penalizacion = (1.0 - estado.factor_velocidad) * 100  # En porcentaje

        # Construimos la linea descriptiva
        if penalizacion == 0:
            texto_penalizacion = "Sin penalizacion"
        else:
            texto_penalizacion = f"-{penalizacion:.0f}% velocidad"

        print(f"  {estado.nombre:<22s} {estado.probabilidad:<8.2f} "
              f"x{estado.factor_velocidad:<7.2f} {vel_efectiva:>6.0f} km/h      "
              f"{texto_penalizacion}")

    # Verificacion: las probabilidades suman 1.0
    suma = sum(e.probabilidad for e in ESTADOS_CLIMA)
    print(f"\n  Suma de probabilidades: {suma:.2f} (debe ser 1.00)")

    # =====================================================================
    # PARTE 2: Simulacion de 24 horas con cambios cada hora
    # =====================================================================
    # Creamos un simulador con semilla fija para que el resultado sea
    # reproducible (ideal para explicar en clase: siempre sale lo mismo).

    print("\n\n--- PARTE 2: SIMULACION DE 24 HORAS ---\n")

    DURACION_MIN = 1440   # 24 horas = 1440 minutos
    INTERVALO = 60        # Cambio de clima cada 60 minutos (1 hora)
    SEMILLA = 42          # Semilla fija para reproducibilidad

    clima = SimuladorClima(intervalo_cambio_min=INTERVALO, semilla=SEMILLA)

    # Variables para rastrear los cambios
    estado_anterior = None
    conteo = {}  # nombre -> minutos en ese estado

    print(f"  Duracion: {DURACION_MIN} min ({DURACION_MIN / 60:.0f} horas)")
    print(f"  Intervalo de cambio: cada {INTERVALO} min")
    print(f"  Semilla aleatoria: {SEMILLA}")
    print()
    print(f"  {'Hora':<8s} {'Minuto':<10s} {'Estado climatico':<22s} {'Factor vel.'}")
    print(f"  {'-' * 8} {'-' * 9} {'-' * 22} {'-' * 11}")

    for minuto in range(DURACION_MIN):
        estado = clima.actualizar(minuto)

        # Contabilizar minutos en cada estado
        conteo[estado.nombre] = conteo.get(estado.nombre, 0) + 1

        # Solo mostrar cuando hay un cambio de estado
        if estado is not estado_anterior:
            hora = minuto // 60
            print(f"  {hora:02d}:00    t={minuto:<7d} {estado.nombre:<22s} "
                  f"x{estado.factor_velocidad:.2f}")
            estado_anterior = estado

    # =====================================================================
    # PARTE 3: Distribucion teorica vs. observada
    # =====================================================================
    # Comparamos las probabilidades definidas en el vector con la frecuencia
    # real observada. Con mas horas, deberia converger (ley de los grandes numeros).

    print("\n\n--- PARTE 3: DISTRIBUCION TEORICA vs. OBSERVADA ---\n")

    print(f"  {'Estado':<22s} {'Prob. Teorica':<15s} {'Freq. Observada':<17s} {'Diferencia'}")
    print(f"  {'-' * 22} {'-' * 14} {'-' * 16} {'-' * 10}")

    for estado in ESTADOS_CLIMA:
        minutos_observados = conteo.get(estado.nombre, 0)
        freq_observada = minutos_observados / DURACION_MIN
        diferencia = freq_observada - estado.probabilidad

        # Indicador visual de desviacion
        if abs(diferencia) < 0.05:
            indicador = " OK"    # Cercano al teorico
        else:
            indicador = " (!)"   # Se desvia (normal en muestras pequenas)

        print(f"  {estado.nombre:<22s} "
              f"{estado.probabilidad:>6.1%}         "
              f"{freq_observada:>6.1%}           "
              f"{diferencia:>+6.1%}{indicador}")

    print(f"\n  Nota: con solo {DURACION_MIN // INTERVALO} sorteos (24 horas), "
          f"es normal que haya desviaciones.")
    print(f"  Con mas tiempo simulado (ej: 7200 min = 5 dias), convergeria mas.")

    # =====================================================================
    # PARTE 4: Impacto en el tiempo de vuelo
    # =====================================================================
    # Calculamos cuanto tarda un dron en recorrer una distancia fija
    # bajo cada estado climatico. Esto muestra el efecto real de la
    # penalizacion de velocidad.

    print("\n\n--- PARTE 4: IMPACTO EN EL TIEMPO DE VUELO ---\n")

    distancia_ejemplo_km = 15.0  # Distancia de ejemplo (15 km)
    print(f"  Distancia de ejemplo: {distancia_ejemplo_km} km\n")

    print(f"  {'Estado':<22s} {'Velocidad':<12s} {'Tiempo vuelo':<14s} {'Diferencia vs normal'}")
    print(f"  {'-' * 22} {'-' * 11} {'-' * 13} {'-' * 20}")

    # Calcular el tiempo base (dia normal) para comparar
    vel_normal_km_h = velocidad_base_km_h  # Factor 1.0
    tiempo_normal_min = (distancia_ejemplo_km / vel_normal_km_h) * 60

    for estado in ESTADOS_CLIMA:
        vel_efectiva_km_h = velocidad_base_km_h * estado.factor_velocidad
        tiempo_min = (distancia_ejemplo_km / vel_efectiva_km_h) * 60
        diferencia_min = tiempo_min - tiempo_normal_min

        if diferencia_min == 0:
            texto_diff = "Referencia"
        else:
            texto_diff = f"+{diferencia_min:.1f} min mas lento"

        print(f"  {estado.nombre:<22s} "
              f"{vel_efectiva_km_h:>5.0f} km/h   "
              f"{tiempo_min:>5.1f} min     "
              f"{texto_diff}")

    print(f"\n  Conclusion: en el peor caso (viento fuerte), un vuelo de")
    print(f"  {distancia_ejemplo_km} km tarda {(distancia_ejemplo_km / (velocidad_base_km_h * 0.60)) * 60:.1f} min "
          f"en lugar de {tiempo_normal_min:.1f} min.\n")

    print("=" * 70)
    print("  FIN DE LA DEMO")
    print("=" * 70)


# -- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    main()

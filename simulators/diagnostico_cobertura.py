"""
diagnostico_cobertura.py
========================

Analiza si las bases actuales cubren bien los hospitales.

Calcula:
- base mas cercana a cada hospital,
- distancia hospital-base,
- si una reposicion base-hospital-base es viable,
- hospitales problematicos por distancia/autonomia.

Ejecutar desde la raiz del proyecto:

    python -m simulators.diagnostico_cobertura
"""

import math

from hospitales_almacenes_data import HOSPITALS, BASES
from parametros_globales import (
    CARGA_MAXIMA_KG,
    AUTONOMIA_MAX_EN_VACIO,
    BATERIA_MINIMA_VUELO,
)


def distancia_haversine_km(nodo_a, nodo_b):
    radio_tierra_km = 6371.0

    lat1 = math.radians(nodo_a.lat)
    lat2 = math.radians(nodo_b.lat)

    dlat = math.radians(nodo_b.lat - nodo_a.lat)
    dlon = math.radians(nodo_b.lon - nodo_a.lon)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return radio_tierra_km * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


def calcular_autonomia_km(carga_kg):
    """
    Misma idea que funcionamiento_bateria_service.py.

    A mayor carga, menor autonomia.
    """
    return AUTONOMIA_MAX_EN_VACIO - (22.0 * carga_kg) / CARGA_MAXIMA_KG


def calcular_consumo_pct(carga_kg, distancia_km):
    autonomia = calcular_autonomia_km(carga_kg)
    return (distancia_km / autonomia) * 100.0


def evaluar_reposicion(base, hospital, carga_kg):
    """
    Evalua una ruta simple:

        base -> hospital con carga
        hospital -> base sin carga

    Devuelve:
        consumo_total_pct, bateria_final_pct, viable
    """

    distancia_ida = distancia_haversine_km(base, hospital)
    distancia_vuelta = distancia_haversine_km(hospital, base)

    consumo_ida = calcular_consumo_pct(carga_kg, distancia_ida)
    consumo_vuelta = calcular_consumo_pct(0.0, distancia_vuelta)

    consumo_total = consumo_ida + consumo_vuelta
    bateria_final = 100.0 - consumo_total

    viable = bateria_final >= BATERIA_MINIMA_VUELO

    return consumo_total, bateria_final, viable


def base_mas_cercana(hospital):
    mejor_nombre = None
    mejor_base = None
    mejor_distancia = float("inf")

    for nombre_base, base in BASES.items():
        distancia = distancia_haversine_km(base, hospital)

        if distancia < mejor_distancia:
            mejor_nombre = nombre_base
            mejor_base = base
            mejor_distancia = distancia

    return mejor_nombre, mejor_base, mejor_distancia


def main():
    carga_prueba = CARGA_MAXIMA_KG

    filas = []

    for nombre_hospital, hospital in HOSPITALS.items():
        nombre_base, base, distancia = base_mas_cercana(hospital)

        consumo, bateria_final, viable = evaluar_reposicion(
            base,
            hospital,
            carga_prueba
        )

        filas.append({
            "hospital": nombre_hospital,
            "base": nombre_base,
            "distancia_km": distancia,
            "consumo_pct": consumo,
            "bateria_final_pct": bateria_final,
            "viable": viable,
        })

    filas.sort(key=lambda x: x["distancia_km"], reverse=True)

    print("=" * 90)
    print("DIAGNOSTICO DE COBERTURA BASE-HOSPITAL")
    print("=" * 90)

    print(f"Hospitales: {len(HOSPITALS)}")
    print(f"Bases:      {len(BASES)}")
    print(f"Carga usada para prueba: {carga_prueba:.2f} kg")
    print(f"Reserva minima bateria:  {BATERIA_MINIMA_VUELO:.1f}%")

    print("\n--- HOSPITALES ORDENADOS POR DISTANCIA A SU BASE MAS CERCANA ---")

    for fila in filas:
        estado = "OK" if fila["viable"] else "NO VIABLE"

        print(
            f"{estado:9s} | "
            f"{fila['distancia_km']:6.2f} km | "
            f"bat final={fila['bateria_final_pct']:6.2f}% | "
            f"{fila['base']:12s} -> {fila['hospital']}"
        )

    no_viables = [f for f in filas if not f["viable"]]

    print("\n--- RESUMEN ---")
    print(f"Hospitales viables:    {len(filas) - len(no_viables)}")
    print(f"Hospitales no viables: {len(no_viables)}")

    if no_viables:
        print("\nHospitales problematicos:")
        for fila in no_viables:
            print(
                f"- {fila['hospital']} "
                f"({fila['distancia_km']:.2f} km desde {fila['base']}, "
                f"bat final={fila['bateria_final_pct']:.2f}%)"
            )

    print("\nConclusion:")
    if no_viables:
        print(
            "Las bases actuales NO cubren bien toda la red. "
            "Hay hospitales perifericos que requieren nuevas bases "
            "o una restriccion geografica del modelo."
        )
    else:
        print("Las bases actuales cubren todos los hospitales para esta carga.")


if __name__ == "__main__":
    main()
"""
diagnostico_cobertura.py
========================

Analiza si las bases actuales cubren bien los hospitales.

Calcula:
- base más cercana a cada hospital,
- distancia hospital-base,
- si una reposición base-hospital-base es viable según batería,
- hospitales problemáticos por distancia/autonomía.

Ejecutar desde la raíz del proyecto:

    python diagnostico.py
"""

from config import HOSPITALS, BASES, CARGA_MAXIMA_KG, BATERIA_MINIMA_VUELO
from red import ServicioRed, calcular_bateria_restante


def _base_mas_cercana(hospital):
    """Devuelve (nombre_base, nodo_base, distancia_km) de la base más cercana."""
    mejor_nombre = None
    mejor_base = None
    mejor_distancia = float("inf")

    for nombre_base, base in BASES.items():
        distancia = ServicioRed.distancia_haversine_km(
            base.lat, base.lon,
            hospital.lat, hospital.lon,
        )
        if distancia < mejor_distancia:
            mejor_nombre = nombre_base
            mejor_base = base
            mejor_distancia = distancia

    return mejor_nombre, mejor_base, mejor_distancia


def evaluar_reposicion(base, hospital, carga_kg):
    """
    Evalúa una ruta simple:

        base -> hospital con carga
        hospital -> base sin carga

    Devuelve:
        (consumo_total_pct, bateria_final_pct, es_viable)
    """
    distancia_ida = ServicioRed.distancia_haversine_km(
        base.lat, base.lon, hospital.lat, hospital.lon
    )
    distancia_vuelta = ServicioRed.distancia_haversine_km(
        hospital.lat, hospital.lon, base.lat, base.lon
    )

    bateria_tras_ida = calcular_bateria_restante(carga_kg, distancia_ida, 100.0)
    bateria_final = calcular_bateria_restante(0.0, distancia_vuelta, bateria_tras_ida)

    consumo_total = 100.0 - bateria_final
    es_viable = bateria_final >= BATERIA_MINIMA_VUELO

    return consumo_total, bateria_final, es_viable


def main():
    carga_prueba = CARGA_MAXIMA_KG

    filas = []

    for nombre_hospital, hospital in HOSPITALS.items():
        nombre_base, base, distancia = _base_mas_cercana(hospital)

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
    print(f"Reserva mínima batería:  {BATERIA_MINIMA_VUELO:.1f}%")

    print("\n--- HOSPITALES ORDENADOS POR DISTANCIA A SU BASE MÁS CERCANA ---")

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
        print("\nHospitales problemáticos:")
        for fila in no_viables:
            print(
                f"- {fila['hospital']} "
                f"({fila['distancia_km']:.2f} km desde {fila['base']}, "
                f"bat final={fila['bateria_final_pct']:.2f}%)"
            )

    print("\nConclusión:")
    if no_viables:
        print(
            "Las bases actuales NO cubren bien toda la red. "
            "Hay hospitales periféricos que requieren nuevas bases "
            "o una restricción geográfica del modelo."
        )
    else:
        print("Las bases actuales cubren todos los hospitales para esta carga.")


if __name__ == "__main__":
    main()
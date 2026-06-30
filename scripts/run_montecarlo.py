"""
run_montecarlo.py
=================

Ejecuta simulaciones Monte Carlo y guarda un único CSV.
Ese CSV es la tabla que después lee el script de gráficas.

Uso desde la raíz del proyecto:
    python scripts/run_montecarlo.py

También puedes cambiar parámetros:
    python scripts/run_montecarlo.py --simulaciones 20 --salida datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv
"""

from __future__ import annotations

import sys
import argparse
import json
import time
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

# Añadir carpeta 'src' al path para poder ejecutar el script directamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from uav_medical_network.simulacion import run_simulation, ESCENARIOS


# ---------------------------------------------------------------------------
# Configuracion sencilla
# ---------------------------------------------------------------------------

NUM_SIMULACIONES = 20
SEMILLA_BASE = 67
MINUTOS_SIMULACION = 14 * 24 * 60
ESCENARIO_BASE = "personalizado"
INTERVALO_MUESTREO_COLA_MIN = 60
UMBRAL_P95_INVENTARIO_MIN = 300
ARCHIVO_SALIDA = "datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv"

NIVELES_ESTRES = [
    {"nombre": "estres_1_base", "etiqueta": "Base", "factor_demanda_inventario": 1.0, "factor_demanda_organos": 1.0},
    {"nombre": "estres_2_moderado", "etiqueta": "Moderado", "factor_demanda_inventario": 1.5, "factor_demanda_organos": 1.25},
    {"nombre": "estres_3_alto", "etiqueta": "Alto", "factor_demanda_inventario": 2.0, "factor_demanda_organos": 1.5},
    {"nombre": "estres_4_muy_alto", "etiqueta": "Muy alto", "factor_demanda_inventario": 2.5, "factor_demanda_organos": 2.0},
]

DRONES_BASE_CONFIG = {
    "BASE NOROESTE": 2,
    "BASE NORTE CAPITAL": 5,
    "BASE ESTE CORREDOR": 4,
    "BASE SUR FUENLABRADA": 3,
}

DRONES_HOSPITALARIOS_CONFIG = {
    "Hospital Universitario La Paz": 1,
    "Hospital Universitario Ramón y Cajal": 1,
    "Hospital Universitario Infanta Sofía": 2,
    "Hospital General Universitario Gregorio Marañón": 1,
    "Hospital Universitario 12 de Octubre": 1,
    "Hospital Universitario de Fuenlabrada": 1,
    "Hospital Universitario Infanta Cristina": 1,
    "Hospital Universitario Infanta Elena": 3,
    "Hospital Universitario José Germain": 1,
    "Hospital Universitario Puerta de Hierro Majadahonda": 3,
    "Hospital Asociado Universitario Guadarrama": 3,
    "Hospital La Fuenfría": 2,
    "Hospital El Escorial": 1,
    "Hospital Universitario de Torrejón": 1,
    "Hospital Universitario Príncipe de Asturias": 1,
    "Hospital Universitario del Sureste": 1,
}

ORGANOS = {
    "corazon", "corazón", "pulmon", "pulmón", "rinon", "riñón",
    "pancreas", "páncreas", "higado", "hígado",
}


# ---------------------------------------------------------------------------
# Utilidades pequeñas
# ---------------------------------------------------------------------------

def valor(diccionario, clave, defecto=0):
    if diccionario is None:
        return defecto
    dato = diccionario.get(clave, defecto)
    return defecto if dato is None else dato


def attr(objeto, nombre, defecto=None):
    return getattr(objeto, nombre, defecto)


def porcentaje(parte, total):
    return parte / total * 100 if total else 0


def percentil(valores, p):
    datos = sorted(float(x) for x in valores if x is not None)
    if not datos:
        return None

    k = (len(datos) - 1) * p / 100
    i = int(k)
    j = min(i + 1, len(datos) - 1)
    if i == j:
        return datos[i]
    return datos[i] * (j - k) + datos[j] * (k - i)


def media(valores):
    datos = [float(x) for x in valores if x is not None]
    return sum(datos) / len(datos) if datos else None


def guardar_tabla(filas, ruta_salida):
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(ruta_salida, index=False, encoding="utf-8")
    print(f"CSV guardado: {ruta_salida} ({len(filas)} filas)")


# ---------------------------------------------------------------------------
# Configuracion de cada simulacion
# ---------------------------------------------------------------------------

def crear_configuracion(nivel, indice_simulacion):
    config = deepcopy(ESCENARIOS[ESCENARIO_BASE])

    config["minutos_simulacion"] = MINUTOS_SIMULACION
    config["semilla"] = SEMILLA_BASE + indice_simulacion

    config["escenario_clima"] = "normal"
    config["activar_meteorologia"] = True
    config["intervalo_cambio_clima_min"] = 300

    config["factor_demanda_inventario"] = nivel["factor_demanda_inventario"]
    config["factor_demanda_organos"] = nivel["factor_demanda_organos"]

    config["drones_por_base"] = 0
    config["drones_por_base_config"] = deepcopy(DRONES_BASE_CONFIG)
    config["drones_por_hospital"] = 0
    config["drones_por_hospital_config"] = deepcopy(DRONES_HOSPITALARIOS_CONFIG)

    config["verbose"] = False
    config["generar_graficas"] = False
    config["imprimir_eventos_drones"] = False
    config["imprimir_eventos_hospital"] = False
    config["imprimir_eventos_clima"] = False

    return config


# ---------------------------------------------------------------------------
# Lectura de objetos internos del simulador
# ---------------------------------------------------------------------------

def obtener_pedidos(resultado):
    gestor = resultado.get("_gestor_flota")
    cola = resultado.get("_cola_pedidos")

    completados = list(getattr(gestor, "pedidos_completados", [])) if gestor else []
    rechazados = list(getattr(gestor, "pedidos_rechazados", [])) if gestor else []
    pendientes = list(getattr(cola, "pedidos_pendientes", [])) if cola else []

    return completados, rechazados, pendientes


def obtener_drones(resultado):
    gestor = resultado.get("_gestor_flota")
    if gestor is None:
        return []
    return list(getattr(gestor, "drones", {}).values())


def obtener_historial_cola(resultado):
    return list(resultado.get("_historial_longitud_cola", []) or [])


def es_organo(pedido):
    tipo = attr(pedido, "tipo_pedido", "")
    producto = str(attr(pedido, "producto", "")).lower()
    return tipo == "organo" or producto in ORGANOS


def tiempo_total(pedido):
    inicio = attr(pedido, "timestamp_min")
    fin = attr(pedido, "completed_time_min")
    return None if inicio is None or fin is None else fin - inicio


def espera_asignacion(pedido):
    inicio = attr(pedido, "timestamp_min")
    asignado = attr(pedido, "assigned_time_min")
    return None if inicio is None or asignado is None else asignado - inicio


def fuera_isquemia(pedido, minutos_simulacion):
    if not es_organo(pedido):
        return False

    deadline = attr(pedido, "deadline_min")
    fin = attr(pedido, "completed_time_min")

    if deadline is None:
        return False
    if fin is not None and fin > deadline:
        return True
    if fin is None and deadline <= minutos_simulacion:
        return True

    return False


def pendiente_por_corte(pedido, minutos_simulacion):
    if not es_organo(pedido):
        return False

    deadline = attr(pedido, "deadline_min")
    fin = attr(pedido, "completed_time_min")

    return deadline is not None and fin is None and deadline > minutos_simulacion


# ---------------------------------------------------------------------------
# Filas de la tabla unica
# ---------------------------------------------------------------------------

def base_fila(tipo, nivel, simulacion, config):
    return {
        "tipo_registro": tipo,
        "escenario": nivel["nombre"],
        "escenario_etiqueta": nivel["etiqueta"],
        "simulacion": simulacion,
        "semilla": config["semilla"],
        "minutos_simulacion": config["minutos_simulacion"],
        "factor_demanda_inventario": nivel["factor_demanda_inventario"],
        "factor_demanda_organos": nivel["factor_demanda_organos"],
    }


def fila_simulacion(resultado, nivel, simulacion, config, tiempo_s, pedidos, drones):
    completados, rechazados, pendientes = pedidos
    todos_pedidos = completados + rechazados + pendientes
    minutos = config["minutos_simulacion"]

    tiempos_inv = []
    tiempos_org = []
    esperas = []

    organos_total = 0
    organos_a_tiempo = 0
    organos_fuera = 0
    organos_pendientes = 0
    organos_rechazados = 0

    for estado, lista in [("completed", completados), ("rejected", rechazados), ("pending", pendientes)]:
        for pedido in lista:
            t = tiempo_total(pedido)
            e = espera_asignacion(pedido)
            if e is not None:
                esperas.append(e)

            if es_organo(pedido):
                organos_total += 1
                if estado == "rejected":
                    organos_rechazados += 1
                elif estado == "pending":
                    organos_pendientes += 1

                tarde = fuera_isquemia(pedido, minutos)
                if tarde:
                    organos_fuera += 1
                elif estado == "completed":
                    organos_a_tiempo += 1

                if estado == "completed" and t is not None:
                    tiempos_org.append(t)
            else:
                if estado == "completed" and t is not None:
                    tiempos_inv.append(t)

    historial = obtener_historial_cola(resultado)
    total_drones = len(drones)
    vuelo_total = sum(attr(d, "flight_minutes", 0) or 0 for d in drones)
    recarga_total = sum(attr(d, "charging_minutes", 0) or 0 for d in drones)
    tiempo_drones = total_drones * minutos

    pedidos_generados = valor(resultado, "pedidos_generados", len(todos_pedidos))
    pedidos_completados = valor(resultado, "pedidos_completados", len(completados))

    fila = base_fila("simulacion", nivel, simulacion, config)
    fila.update({
        "tiempo_ejecucion_s": tiempo_s,
        "dias_simulacion": minutos / 1440,
        "drones_base_total": sum(DRONES_BASE_CONFIG.values()),
        "drones_hospitalarios_total": sum(DRONES_HOSPITALARIOS_CONFIG.values()),
        "drones_config_json": json.dumps({"base": DRONES_BASE_CONFIG, "hospitalarios": DRONES_HOSPITALARIOS_CONFIG}, ensure_ascii=False),

        "pedidos_generados": pedidos_generados,
        "pedidos_completados": pedidos_completados,
        "pedidos_rechazados": valor(resultado, "pedidos_rechazados", len(rechazados)),
        "pedidos_pendientes": valor(resultado, "pedidos_en_cola", len(pendientes)),
        "tasa_servicio_pct": porcentaje(pedidos_completados, pedidos_generados),

        "inventario_completado": valor(resultado, "inventario_completado", None),
        "inventario_pendiente": valor(resultado, "inventario_pendiente", None),
        "inventario_tiempo_medio_min": media(tiempos_inv),
        "inventario_tiempo_p95_min": percentil(tiempos_inv, 95),
        "inventario_tiempo_p99_min": percentil(tiempos_inv, 99),
        "p95_inventario_cumple_300_min": int((percentil(tiempos_inv, 95) or 10**9) <= UMBRAL_P95_INVENTARIO_MIN),

        "organos_totales": organos_total,
        "organos_a_tiempo": organos_a_tiempo,
        "organos_fuera_isquemia": organos_fuera,
        "organos_pendientes": organos_pendientes,
        "organos_rechazados": organos_rechazados,
        "exito_clinico_pct": porcentaje(organos_a_tiempo, organos_total),
        "organos_tiempo_medio_min": media(tiempos_org),
        "organos_tiempo_p95_min": percentil(tiempos_org, 95),
        "organos_tiempo_p99_min": percentil(tiempos_org, 99),

        "cola_media": media(historial) or 0,
        "cola_p95": percentil(historial, 95) or 0,
        "cola_maxima": max(historial) if historial else 0,
        "espera_asignacion_media_min": media(esperas),
        "espera_asignacion_p95_min": percentil(esperas, 95),

        "drones_totales": total_drones,
        "vuelo_total_min": vuelo_total,
        "recarga_total_min": recarga_total,
        "utilizacion_vuelo_pct": porcentaje(vuelo_total, tiempo_drones),
        "utilizacion_operativa_pct": porcentaje(vuelo_total + recarga_total, tiempo_drones),
    })
    return fila


def filas_cola(resultado, nivel, simulacion, config):
    filas = []
    historial = obtener_historial_cola(resultado)

    for minuto, longitud in enumerate(historial):
        if minuto % INTERVALO_MUESTREO_COLA_MIN != 0:
            continue
        fila = base_fila("cola", nivel, simulacion, config)
        fila.update({"minuto": minuto, "dia": minuto / 1440, "longitud_cola": longitud})
        filas.append(fila)

    return filas


def filas_drones(resultado, nivel, simulacion, config):
    filas = []
    minutos = config["minutos_simulacion"]

    for dron in obtener_drones(resultado):
        vuelo = attr(dron, "flight_minutes", 0) or 0
        recarga = attr(dron, "charging_minutes", 0) or 0
        rol = attr(dron, "role", "base") or "base"

        fila = base_fila("dron", nivel, simulacion, config)
        fila.update({
            "drone_id": attr(dron, "drone_id", None),
            "role": rol,
            "base_name": attr(dron, "base_name", None),
            "deliveries_made": attr(dron, "deliveries_made", 0) or 0,
            "flight_minutes": vuelo,
            "charging_minutes": recarga,
            "utilizacion_vuelo_dron_pct": porcentaje(vuelo, minutos),
            "utilizacion_operativa_dron_pct": porcentaje(vuelo + recarga, minutos),
        })
        filas.append(fila)

    return filas


def filas_rutas(nivel, simulacion, config, pedidos):
    completados, rechazados, pendientes = pedidos
    rutas = defaultdict(lambda: {"organos_totales": 0, "a_tiempo": 0, "fuera": 0, "pendientes": 0, "tiempos": []})
    minutos = config["minutos_simulacion"]

    for estado, lista in [("completed", completados), ("rejected", rechazados), ("pending", pendientes)]:
        for pedido in lista:
            if not es_organo(pedido):
                continue

            origen = attr(pedido, "origin_hospital", "Origen desconocido")
            destino = attr(pedido, "destination_hospital", "Destino desconocido")
            ruta = f"{origen} → {destino}"

            r = rutas[ruta]
            r["organos_totales"] += 1

            tarde = fuera_isquemia(pedido, minutos)
            if tarde:
                r["fuera"] += 1
            elif estado == "completed":
                r["a_tiempo"] += 1
            elif estado == "pending":
                r["pendientes"] += 1

            t = tiempo_total(pedido)
            if t is not None:
                r["tiempos"].append(t)

    filas = []
    for ruta, datos in rutas.items():
        fila = base_fila("ruta", nivel, simulacion, config)
        fila.update({
            "ruta": ruta,
            "organos_totales_ruta": datos["organos_totales"],
            "organos_a_tiempo_ruta": datos["a_tiempo"],
            "organos_fuera_isquemia_ruta": datos["fuera"],
            "organos_pendientes_ruta": datos["pendientes"],
            "incidencias_ruta": datos["fuera"] + datos["pendientes"],
            "tiempo_medio_ruta_min": media(datos["tiempos"]),
        })
        filas.append(fila)

    return filas


# ---------------------------------------------------------------------------
# Ejecucion
# ---------------------------------------------------------------------------

def ejecutar_una_simulacion(nivel, simulacion):
    config = crear_configuracion(nivel, simulacion)

    inicio = time.time()
    resultado = run_simulation(config)
    tiempo_s = time.time() - inicio

    pedidos = obtener_pedidos(resultado)
    drones = obtener_drones(resultado)

    filas = [fila_simulacion(resultado, nivel, simulacion, config, tiempo_s, pedidos, drones)]
    filas.extend(filas_cola(resultado, nivel, simulacion, config))
    filas.extend(filas_drones(resultado, nivel, simulacion, config))
    filas.extend(filas_rutas(nivel, simulacion, config, pedidos))

    return filas


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo sencillo para la red sanitaria de drones.")
    parser.add_argument("--simulaciones", type=int, default=NUM_SIMULACIONES, help="Simulaciones por escenario.")
    parser.add_argument("--salida", default=ARCHIVO_SALIDA, help="Ruta del CSV unico de salida.")
    args = parser.parse_args()

    filas = []
    total = args.simulaciones * len(NIVELES_ESTRES)
    contador = 0

    print("=" * 72)
    print("MONTE CARLO SENCILLO - RED SANITARIA DE DRONES")
    print("=" * 72)
    print(f"Simulaciones por escenario: {args.simulaciones}")
    print(f"Total de simulaciones:      {total}")
    print(f"Salida:                     {args.salida}")
    print("=" * 72)

    try:
        for nivel in NIVELES_ESTRES:
            print(f"\nEscenario: {nivel['etiqueta']}")

            for i in range(1, args.simulaciones + 1):
                contador += 1
                nuevas_filas = ejecutar_una_simulacion(nivel, i)
                filas.extend(nuevas_filas)

                fila_sim = nuevas_filas[0]
                print(
                    f"  {contador}/{total} | sim {i:02d} | "
                    f"servicio={fila_sim['tasa_servicio_pct']:.2f}% | "
                    f"organos={fila_sim['organos_a_tiempo']}/{fila_sim['organos_totales']} | "
                    f"fuera_iso={fila_sim['organos_fuera_isquemia']} | "
                    f"cola_max={fila_sim['cola_maxima']}"
                )

    except KeyboardInterrupt:
        ruta = str(args.salida).replace(".csv", "_interrumpido.csv")
        print("\nEjecucion interrumpida. Guardo lo acumulado.")
        guardar_tabla(filas, ruta)
        return

    guardar_tabla(filas, args.salida)
    print("\nHecho. Ese CSV es la unica tabla que debe leer el script de graficas.")


if __name__ == "__main__":
    main()


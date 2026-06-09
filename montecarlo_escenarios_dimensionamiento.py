"""
montecarlo_escenarios.py
========================

Monte Carlo ampliado para dimensionamiento de flota.

Versión rápida de validación:
- 20 simulaciones por nivel.
- 4 niveles de estrés.
- 1 semana por simulación.
- Sin nivel extremo.
- Guardado parcial tras cada nivel y guardado de emergencia si se interrumpe.

Este archivo ejecuta múltiples simulaciones y genera un dataset completo
para análisis posterior, redimensionamiento de flota y generación de gráficas.

Salidas generadas en la carpeta datasets_montecarlo_dimensionamiento_1semana/:

1. montecarlo_simulaciones_completo.csv
   Una fila por simulación. Métricas globales, inventario, órganos,
   cola, flota, clima y configuración.

2. montecarlo_resumen_escenarios_completo.csv
   Resumen agregado por nivel de estrés.

3. montecarlo_pedidos_completo.csv
   Una fila por pedido registrado: inventario, órganos, completados,
   pendientes o rechazados.

4. montecarlo_cola_tiempo.csv
   Evolución temporal de la cola durante la simulación.

5. montecarlo_drones_completo.csv
   Una fila por dron y simulación: rol, base, entregas, vuelo, recarga,
   utilización aproximada.

6. montecarlo_clima_completo.csv
   Tiempo en cada estado meteorológico por simulación.

7. montecarlo_productos_completo.csv
   Conteo por producto, estado y simulación.

Uso desde la raíz del proyecto:

    python -m simulators.montecarlo_escenarios
"""

import csv
import json
import os
import time
from copy import deepcopy
from statistics import mean, median

from simulators.experimentacion import run_simulation
from simulators.escenarios import ESCENARIOS
from random import random

# ---------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------------------------

NUM_SIMULACIONES = 20
SEMILLA_BASE = 67

MINUTOS_SIMULACION = 14 * 24 * 60

MINUTOS_14_DIAS = MINUTOS_SIMULACION

ESCENARIO_BASE = "personalizado"

# Carpeta separada para no mezclar estos resultados con el Monte Carlo largo.
CARPETA_SALIDA = "datasets_montecarlo_dimensionamiento_1semana"

# Si quieres cola minuto a minuto, pon 1.
# Si quieres dataset más ligero, deja 30 o 60.
INTERVALO_MUESTREO_COLA_MIN = 60

# Umbrales útiles para análisis de cola.
UMBRALES_COLA = [5, 10, 25, 50, 100, 150, 200]

# Umbral orientativo para inventario: 720 min = 12 horas.
UMBRAL_P95_INVENTARIO_MIN = 720


# ---------------------------------------------------------------------------
# NIVELES DE ESTRÉS
# ---------------------------------------------------------------------------
# Siempre usamos escenario personalizado y clima normal.
# Solo cambia la presión del sistema:
# - factor_demanda_inventario
# - factor_demanda_organos
# ---------------------------------------------------------------------------

NIVELES_ESTRES = [
    {
        "nombre": "estres_1_base",
        "etiqueta": "Base",
        "factor_demanda_inventario": 1.0,
        "factor_demanda_organos": 1.0,
    },
    {
        "nombre": "estres_2_moderado",
        "etiqueta": "Moderado",
        "factor_demanda_inventario": 1.5,
        "factor_demanda_organos": 1.25,
    },
    {
        "nombre": "estres_3_alto",
        "etiqueta": "Alto",
        "factor_demanda_inventario": 2.0,
        "factor_demanda_organos": 1.5,
    },
    {
        "nombre": "estres_4_muy_alto",
        "etiqueta": "Muy alto",
        "factor_demanda_inventario": 2.5,
        "factor_demanda_organos": 2.0,
    }
]


# ---------------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DRONES DE BASE
# ---------------------------------------------------------------------------
# Estos drones afectan principalmente a la reposición de inventario.
# ---------------------------------------------------------------------------

DRONES_BASE_CONFIG = {
    "BASE NOROESTE": 2,
    "BASE NORTE CAPITAL": 5,
    "BASE ESTE CORREDOR": 4,
    "BASE SUR FUENLABRADA": 3,
}


# ---------------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DRONES HOSPITALARIOS
# ---------------------------------------------------------------------------
# Estos drones afectan principalmente al transporte de órganos.
# ---------------------------------------------------------------------------

DRONES_HOSPITALARIOS_CONFIG = {
    # Norte / norte capital
    "Hospital Universitario La Paz": 1,
    "Hospital Universitario Ramón y Cajal": 1,
    "Hospital Universitario Infanta Sofía": 2,

    # Centro
    "Hospital General Universitario Gregorio Marañón": 1,

    # Sur / suroeste
    "Hospital Universitario 12 de Octubre": 1,
    "Hospital Universitario de Fuenlabrada": 1,
    "Hospital Universitario Infanta Cristina": 1,
    "Hospital Universitario Infanta Elena": 3,  # antes 2
    "Hospital Universitario José Germain": 1,

    # Oeste / noroeste / sierra
    "Hospital Universitario Puerta de Hierro Majadahonda": 3,  # antes 2
    "Hospital Asociado Universitario Guadarrama": 3,           # antes 2
    "Hospital La Fuenfría": 2,
    "Hospital El Escorial": 1,

    # Este / corredor del Henares
    "Hospital Universitario de Torrejón": 1,
    "Hospital Universitario Príncipe de Asturias": 1,
    "Hospital Universitario del Sureste": 1,
}


# ---------------------------------------------------------------------------
# UTILIDADES GENERALES
# ---------------------------------------------------------------------------

def crear_carpeta_salida():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)


def ruta_salida(nombre_archivo):
    crear_carpeta_salida()
    return os.path.join(CARPETA_SALIDA, nombre_archivo)


def valor_seguro(diccionario, clave, defecto=0):
    if diccionario is None:
        return defecto

    valor = diccionario.get(clave, defecto)
    return defecto if valor is None else valor


def attr_seguro(objeto, atributo, defecto=None):
    return getattr(objeto, atributo, defecto)


def bool_a_int(valor):
    return 1 if bool(valor) else 0


def serializar_json(valor):
    try:
        return json.dumps(valor, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(valor), ensure_ascii=False)


def calcular_percentil(valores, percentil):
    valores_limpios = [
        float(v)
        for v in valores
        if v is not None
    ]

    if not valores_limpios:
        return None

    valores_limpios.sort()

    k = (len(valores_limpios) - 1) * percentil / 100
    f = int(k)
    c = min(f + 1, len(valores_limpios) - 1)

    if f == c:
        return valores_limpios[f]

    return (
        valores_limpios[f] * (c - k)
        + valores_limpios[c] * (k - f)
    )


def media_segura_valores(valores):
    valores_limpios = [
        float(v)
        for v in valores
        if v is not None
    ]

    if not valores_limpios:
        return None

    return mean(valores_limpios)


def mediana_segura_valores(valores):
    valores_limpios = [
        float(v)
        for v in valores
        if v is not None
    ]

    if not valores_limpios:
        return None

    return median(valores_limpios)


def max_seguro_valores(valores):
    valores_limpios = [
        float(v)
        for v in valores
        if v is not None
    ]

    if not valores_limpios:
        return None

    return max(valores_limpios)


def min_seguro_valores(valores):
    valores_limpios = [
        float(v)
        for v in valores
        if v is not None
    ]

    if not valores_limpios:
        return None

    return min(valores_limpios)


def guardar_csv(nombre_archivo, filas):
    if not filas:
        print(f"[Aviso] No se guarda {nombre_archivo}: no hay filas.")
        return

    columnas = sorted(
        set().union(*(fila.keys() for fila in filas))
    )

    ruta = ruta_salida(nombre_archivo)

    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas)

    print(f"CSV generado: {ruta}  ({len(filas)} filas)")


# ---------------------------------------------------------------------------
# CLASIFICACIÓN DE PEDIDOS
# ---------------------------------------------------------------------------

def es_pedido_organo(pedido):
    tipo = attr_seguro(pedido, "tipo_pedido", None)
    producto = str(attr_seguro(pedido, "producto", "")).lower()

    organos = {
        "corazon",
        "corazón",
        "pulmon",
        "pulmón",
        "rinon",
        "riñon",
        "riñón",
        "pancreas",
        "páncreas",
        "higado",
        "hígado",
    }

    return tipo == "organo" or producto in organos


def es_pedido_inventario(pedido):
    return not es_pedido_organo(pedido)


def obtener_tiempo_entrega_pedido(pedido):
    timestamp = attr_seguro(pedido, "timestamp_min", None)
    completed = attr_seguro(pedido, "completed_time_min", None)

    if timestamp is None or completed is None:
        return None

    return completed - timestamp


def obtener_wait_time_pedido(pedido):
    timestamp = attr_seguro(pedido, "timestamp_min", None)
    assigned = attr_seguro(pedido, "assigned_time_min", None)

    if timestamp is None or assigned is None:
        return None

    return assigned - timestamp


def obtener_flight_time_aproximado_pedido(pedido):
    assigned = attr_seguro(pedido, "assigned_time_min", None)
    completed = attr_seguro(pedido, "completed_time_min", None)

    if assigned is None or completed is None:
        return None

    return completed - assigned


def obtener_estado_pedido(pedido):
    return attr_seguro(pedido, "status", "desconocido")


def pedido_fuera_isquemia(pedido, minutos_simulacion):
    if not es_pedido_organo(pedido):
        return False

    deadline = attr_seguro(pedido, "deadline_min", None)
    completed = attr_seguro(pedido, "completed_time_min", None)

    if deadline is None:
        return False

    # Entregado tarde.
    if completed is not None and completed > deadline:
        return True

    # Pendiente y vencido dentro del horizonte de simulación.
    if completed is None and deadline <= minutos_simulacion:
        return True

    return False


def pedido_pendiente_por_corte(pedido, minutos_simulacion):
    if not es_pedido_organo(pedido):
        return False

    deadline = attr_seguro(pedido, "deadline_min", None)
    completed = attr_seguro(pedido, "completed_time_min", None)

    if deadline is None:
        return False

    return completed is None and deadline > minutos_simulacion


def minutos_hasta_deadline_en_corte(pedido, minutos_simulacion):
    deadline = attr_seguro(pedido, "deadline_min", None)

    if deadline is None:
        return None

    return deadline - minutos_simulacion


# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------

def crear_configuracion(nivel_estres, indice_simulacion):
    config = deepcopy(ESCENARIOS[ESCENARIO_BASE])

    semilla = SEMILLA_BASE + indice_simulacion

    config["minutos_simulacion"] = MINUTOS_SIMULACION
    config["semilla"] = semilla

    # Clima normal, pero meteorología activa.
    # Dentro de "normal" sigue existiendo variabilidad meteorológica propia del simulador.
    config["escenario_clima"] = "normal"
    config["activar_meteorologia"] = True
    config["intervalo_cambio_clima_min"] = 300

    config["factor_demanda_inventario"] = nivel_estres["factor_demanda_inventario"]
    config["factor_demanda_organos"] = nivel_estres["factor_demanda_organos"]

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
# EXTRACCIÓN DE OBJETOS INTERNOS
# ---------------------------------------------------------------------------

def obtener_listas_pedidos(resultado):
    gestor_flota = resultado.get("_gestor_flota")
    cola_pedidos = resultado.get("_cola_pedidos")

    pedidos_completados = []
    pedidos_rechazados = []
    pedidos_pendientes = []

    if gestor_flota is not None:
        pedidos_completados = list(
            getattr(gestor_flota, "pedidos_completados", [])
        )

        pedidos_rechazados = list(
            getattr(gestor_flota, "pedidos_rechazados", [])
        )

    if cola_pedidos is not None:
        pedidos_pendientes = list(
            getattr(cola_pedidos, "pedidos_pendientes", [])
        )

    return pedidos_completados, pedidos_rechazados, pedidos_pendientes


def obtener_historial_cola(resultado):
    historial = resultado.get("_historial_longitud_cola", [])
    return list(historial) if historial is not None else []


def obtener_drones(resultado):
    gestor_flota = resultado.get("_gestor_flota")

    if gestor_flota is None:
        return []

    drones_dict = getattr(gestor_flota, "drones", {})
    return list(drones_dict.values())


# ---------------------------------------------------------------------------
# FILAS DE PEDIDOS
# ---------------------------------------------------------------------------

def crear_filas_pedidos(resultado, nivel_estres, indice_simulacion, config):
    minutos_simulacion = valor_seguro(resultado, "minutos_simulacion", 0)

    pedidos_completados, pedidos_rechazados, pedidos_pendientes = obtener_listas_pedidos(
        resultado
    )

    filas = []

    fuentes = [
        ("completed", pedidos_completados),
        ("rejected", pedidos_rechazados),
        ("pending", pedidos_pendientes),
    ]

    for estado_dataset, pedidos in fuentes:
        for pedido in pedidos:
            tipo = "organo" if es_pedido_organo(pedido) else "inventario"

            timestamp = attr_seguro(pedido, "timestamp_min", None)
            assigned = attr_seguro(pedido, "assigned_time_min", None)
            completed = attr_seguro(pedido, "completed_time_min", None)
            deadline = attr_seguro(pedido, "deadline_min", None)

            tiempo_total = obtener_tiempo_entrega_pedido(pedido)
            espera_asignacion = obtener_wait_time_pedido(pedido)
            vuelo_aprox = obtener_flight_time_aproximado_pedido(pedido)

            fuera_isquemia = pedido_fuera_isquemia(pedido, minutos_simulacion)
            pendiente_corte = pedido_pendiente_por_corte(pedido, minutos_simulacion)

            tiempo_restante_fin = None
            if timestamp is not None:
                tiempo_restante_fin = minutos_simulacion - timestamp

            margen_deadline_entrega = None
            if deadline is not None and completed is not None:
                margen_deadline_entrega = deadline - completed

            filas.append(
                {
                    "escenario": nivel_estres["nombre"],
                    "escenario_etiqueta": nivel_estres["etiqueta"],
                    "simulacion": indice_simulacion,
                    "semilla": config["semilla"],
                    "minutos_simulacion": minutos_simulacion,
                    "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
                    "factor_demanda_organos": nivel_estres["factor_demanda_organos"],

                    "pedido_estado_dataset": estado_dataset,
                    "pedido_estado_modelo": obtener_estado_pedido(pedido),

                    "call_id": attr_seguro(pedido, "call_id", None),
                    "tipo_pedido": tipo,
                    "producto": attr_seguro(pedido, "producto", None),
                    "unidades": attr_seguro(pedido, "unidades", None),
                    "priority": attr_seguro(pedido, "priority", None),

                    "origin_hospital": attr_seguro(pedido, "origin_hospital", None),
                    "destination_hospital": attr_seguro(pedido, "destination_hospital", None),
                    "assigned_drone_id": attr_seguro(pedido, "assigned_drone_id", None),

                    "timestamp_min": timestamp,
                    "assigned_time_min": assigned,
                    "completed_time_min": completed,
                    "deadline_min": deadline,

                    "tiempo_total_entrega_min": tiempo_total,
                    "tiempo_espera_asignacion_min": espera_asignacion,
                    "tiempo_vuelo_aprox_min": vuelo_aprox,

                    "tiempo_restante_fin_simulacion_min": tiempo_restante_fin,
                    "margen_deadline_entrega_min": margen_deadline_entrega,
                    "minutos_hasta_deadline_en_corte": minutos_hasta_deadline_en_corte(
                        pedido,
                        minutos_simulacion,
                    ),

                    "es_organo": bool_a_int(tipo == "organo"),
                    "es_inventario": bool_a_int(tipo == "inventario"),
                    "es_completado": bool_a_int(estado_dataset == "completed"),
                    "es_pendiente": bool_a_int(estado_dataset == "pending"),
                    "es_rechazado": bool_a_int(estado_dataset == "rejected"),

                    "is_late_modelo": bool_a_int(attr_seguro(pedido, "is_late", False)),
                    "fuera_isquemia": bool_a_int(fuera_isquemia),
                    "pendiente_por_corte": bool_a_int(pendiente_corte),
                    "cumple_deadline": bool_a_int(
                        deadline is not None
                        and completed is not None
                        and completed <= deadline
                    ),
                }
            )

    return filas


# ---------------------------------------------------------------------------
# FILAS DE COLA EN EL TIEMPO
# ---------------------------------------------------------------------------

def crear_filas_cola_tiempo(resultado, nivel_estres, indice_simulacion, config):
    historial = obtener_historial_cola(resultado)

    filas = []

    if not historial:
        return filas

    for minuto, longitud in enumerate(historial):
        if minuto % INTERVALO_MUESTREO_COLA_MIN != 0:
            continue

        filas.append(
            {
                "escenario": nivel_estres["nombre"],
                "escenario_etiqueta": nivel_estres["etiqueta"],
                "simulacion": indice_simulacion,
                "semilla": config["semilla"],
                "minuto": minuto,
                "hora": minuto / 60,
                "dia": minuto / 1440,
                "longitud_cola": longitud,
                "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
                "factor_demanda_organos": nivel_estres["factor_demanda_organos"],
            }
        )

    return filas


# ---------------------------------------------------------------------------
# FILAS DE DRONES
# ---------------------------------------------------------------------------

def crear_filas_drones(resultado, nivel_estres, indice_simulacion, config):
    minutos_simulacion = valor_seguro(resultado, "minutos_simulacion", 0)
    drones = obtener_drones(resultado)

    filas = []

    for dron in drones:
        flight_minutes = attr_seguro(dron, "flight_minutes", 0) or 0
        charging_minutes = attr_seguro(dron, "charging_minutes", 0) or 0

        utilizacion_vuelo_pct = (
            flight_minutes / minutos_simulacion * 100
            if minutos_simulacion > 0
            else 0
        )

        utilizacion_operativa_pct = (
            (flight_minutes + charging_minutes) / minutos_simulacion * 100
            if minutos_simulacion > 0
            else 0
        )

        filas.append(
            {
                "escenario": nivel_estres["nombre"],
                "escenario_etiqueta": nivel_estres["etiqueta"],
                "simulacion": indice_simulacion,
                "semilla": config["semilla"],
                "minutos_simulacion": minutos_simulacion,

                "drone_id": attr_seguro(dron, "drone_id", None),
                "role": attr_seguro(dron, "role", None),
                "base_name": attr_seguro(dron, "base_name", None),
                "current_node_final": attr_seguro(dron, "current_node", None),
                "status_final": attr_seguro(dron, "status", None),
                "battery_percent_final": attr_seguro(dron, "battery_percent", None),

                "deliveries_made": attr_seguro(dron, "deliveries_made", 0),
                "flight_minutes": flight_minutes,
                "charging_minutes": charging_minutes,

                "utilizacion_vuelo_pct": utilizacion_vuelo_pct,
                "utilizacion_operativa_pct": utilizacion_operativa_pct,

                "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
                "factor_demanda_organos": nivel_estres["factor_demanda_organos"],
            }
        )

    return filas


# ---------------------------------------------------------------------------
# FILAS DE CLIMA
# ---------------------------------------------------------------------------

def crear_filas_clima(resultado, nivel_estres, indice_simulacion, config):
    conteo_clima = valor_seguro(resultado, "conteo_clima", {})
    minutos_simulacion = valor_seguro(resultado, "minutos_simulacion", 0)

    filas = []

    for estado_clima, minutos_estado in conteo_clima.items():
        porcentaje = (
            minutos_estado / minutos_simulacion * 100
            if minutos_simulacion > 0
            else 0
        )

        filas.append(
            {
                "escenario": nivel_estres["nombre"],
                "escenario_etiqueta": nivel_estres["etiqueta"],
                "simulacion": indice_simulacion,
                "semilla": config["semilla"],
                "escenario_clima": config.get("escenario_clima", "normal"),
                "estado_clima": estado_clima,
                "minutos_estado": minutos_estado,
                "porcentaje_estado": porcentaje,
                "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
                "factor_demanda_organos": nivel_estres["factor_demanda_organos"],
            }
        )

    return filas


# ---------------------------------------------------------------------------
# FILAS DE PRODUCTOS
# ---------------------------------------------------------------------------

def crear_filas_productos(resultado, nivel_estres, indice_simulacion, config):
    filas = []

    fuentes = [
        ("completed", valor_seguro(resultado, "conteo_producto_completados", {})),
        ("pending", valor_seguro(resultado, "conteo_producto_pendientes", {})),
        ("rejected", valor_seguro(resultado, "conteo_producto_rechazados", {})),
    ]

    for estado, conteo in fuentes:
        for producto, cantidad in conteo.items():
            filas.append(
                {
                    "escenario": nivel_estres["nombre"],
                    "escenario_etiqueta": nivel_estres["etiqueta"],
                    "simulacion": indice_simulacion,
                    "semilla": config["semilla"],
                    "estado": estado,
                    "producto": producto,
                    "cantidad": cantidad,
                    "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
                    "factor_demanda_organos": nivel_estres["factor_demanda_organos"],
                }
            )

    return filas


# ---------------------------------------------------------------------------
# MÉTRICAS DERIVADAS DE PEDIDOS
# ---------------------------------------------------------------------------

def metricas_tiempos_pedidos(filas_pedidos):
    tiempos_todos = []
    tiempos_inventario = []
    tiempos_organos = []

    esperas_todos = []
    esperas_inventario = []
    esperas_organos = []

    vuelos_todos = []
    vuelos_inventario = []
    vuelos_organos = []

    for fila in filas_pedidos:
        if not fila["es_completado"]:
            continue

        tiempo_total = fila["tiempo_total_entrega_min"]
        espera = fila["tiempo_espera_asignacion_min"]
        vuelo = fila["tiempo_vuelo_aprox_min"]

        tipo = fila["tipo_pedido"]

        if tiempo_total is not None:
            tiempos_todos.append(tiempo_total)
            if tipo == "inventario":
                tiempos_inventario.append(tiempo_total)
            elif tipo == "organo":
                tiempos_organos.append(tiempo_total)

        if espera is not None:
            esperas_todos.append(espera)
            if tipo == "inventario":
                esperas_inventario.append(espera)
            elif tipo == "organo":
                esperas_organos.append(espera)

        if vuelo is not None:
            vuelos_todos.append(vuelo)
            if tipo == "inventario":
                vuelos_inventario.append(vuelo)
            elif tipo == "organo":
                vuelos_organos.append(vuelo)

    return {
        # Tiempos totales
        "tiempo_entrega_media_min": media_segura_valores(tiempos_todos),
        "tiempo_entrega_mediana_min": mediana_segura_valores(tiempos_todos),
        "tiempo_entrega_p50_min": calcular_percentil(tiempos_todos, 50),
        "tiempo_entrega_p75_min": calcular_percentil(tiempos_todos, 75),
        "tiempo_entrega_p90_min": calcular_percentil(tiempos_todos, 90),
        "tiempo_entrega_p95_min": calcular_percentil(tiempos_todos, 95),
        "tiempo_entrega_p99_min": calcular_percentil(tiempos_todos, 99),
        "tiempo_entrega_max_min": max_seguro_valores(tiempos_todos),

        # Inventario
        "inventario_tiempo_media_min": media_segura_valores(tiempos_inventario),
        "inventario_tiempo_mediana_min": mediana_segura_valores(tiempos_inventario),
        "inventario_tiempo_p50_min": calcular_percentil(tiempos_inventario, 50),
        "inventario_tiempo_p75_min": calcular_percentil(tiempos_inventario, 75),
        "inventario_tiempo_p90_min": calcular_percentil(tiempos_inventario, 90),
        "inventario_tiempo_p95_min": calcular_percentil(tiempos_inventario, 95),
        "inventario_tiempo_p99_min": calcular_percentil(tiempos_inventario, 99),
        "inventario_tiempo_max_min": max_seguro_valores(tiempos_inventario),

        # Órganos
        "organos_tiempo_media_min": media_segura_valores(tiempos_organos),
        "organos_tiempo_mediana_min": mediana_segura_valores(tiempos_organos),
        "organos_tiempo_p50_min": calcular_percentil(tiempos_organos, 50),
        "organos_tiempo_p75_min": calcular_percentil(tiempos_organos, 75),
        "organos_tiempo_p90_min": calcular_percentil(tiempos_organos, 90),
        "organos_tiempo_p95_min": calcular_percentil(tiempos_organos, 95),
        "organos_tiempo_p99_min": calcular_percentil(tiempos_organos, 99),
        "organos_tiempo_max_min": max_seguro_valores(tiempos_organos),

        # Esperas
        "espera_asignacion_media_min": media_segura_valores(esperas_todos),
        "espera_asignacion_p95_min": calcular_percentil(esperas_todos, 95),
        "inventario_espera_asignacion_media_min": media_segura_valores(esperas_inventario),
        "inventario_espera_asignacion_p95_min": calcular_percentil(esperas_inventario, 95),
        "organos_espera_asignacion_media_min": media_segura_valores(esperas_organos),
        "organos_espera_asignacion_p95_min": calcular_percentil(esperas_organos, 95),

        # Vuelo aproximado
        "vuelo_aprox_media_min": media_segura_valores(vuelos_todos),
        "vuelo_aprox_p95_min": calcular_percentil(vuelos_todos, 95),
        "inventario_vuelo_aprox_media_min": media_segura_valores(vuelos_inventario),
        "inventario_vuelo_aprox_p95_min": calcular_percentil(vuelos_inventario, 95),
        "organos_vuelo_aprox_media_min": media_segura_valores(vuelos_organos),
        "organos_vuelo_aprox_p95_min": calcular_percentil(vuelos_organos, 95),
    }


# ---------------------------------------------------------------------------
# MÉTRICAS DE COLA
# ---------------------------------------------------------------------------

def metricas_cola(historial):
    if not historial:
        resultado = {
            "cola_media": 0,
            "cola_mediana": 0,
            "cola_maxima": 0,
            "cola_p50": 0,
            "cola_p75": 0,
            "cola_p90": 0,
            "cola_p95": 0,
            "cola_p99": 0,
            "cola_minima": 0,
            "cola_final": 0,
            "cola_area_total": 0,
            "cola_area_media_por_minuto": 0,
            "minutos_cola_cero": 0,
            "pct_minutos_cola_cero": 0,
        }

        for umbral in UMBRALES_COLA:
            resultado[f"minutos_cola_mayor_{umbral}"] = 0
            resultado[f"pct_minutos_cola_mayor_{umbral}"] = 0

        return resultado

    n = len(historial)
    area = sum(historial)

    resultado = {
        "cola_media": area / n,
        "cola_mediana": mediana_segura_valores(historial),
        "cola_maxima": max(historial),
        "cola_p50": calcular_percentil(historial, 50),
        "cola_p75": calcular_percentil(historial, 75),
        "cola_p90": calcular_percentil(historial, 90),
        "cola_p95": calcular_percentil(historial, 95),
        "cola_p99": calcular_percentil(historial, 99),
        "cola_minima": min(historial),
        "cola_final": historial[-1],
        "cola_area_total": area,
        "cola_area_media_por_minuto": area / n,
        "minutos_cola_cero": sum(1 for x in historial if x == 0),
        "pct_minutos_cola_cero": (
            sum(1 for x in historial if x == 0) / n * 100
            if n > 0
            else 0
        ),
    }

    for umbral in UMBRALES_COLA:
        minutos = sum(1 for x in historial if x > umbral)
        resultado[f"minutos_cola_mayor_{umbral}"] = minutos
        resultado[f"pct_minutos_cola_mayor_{umbral}"] = (
            minutos / n * 100
            if n > 0
            else 0
        )

    return resultado


# ---------------------------------------------------------------------------
# MÉTRICAS DE ÓRGANOS
# ---------------------------------------------------------------------------

def metricas_organos(filas_pedidos, resultado):
    organos = [
        fila for fila in filas_pedidos
        if fila["tipo_pedido"] == "organo"
    ]

    organos_completados = [
        fila for fila in organos
        if fila["es_completado"]
    ]

    organos_pendientes = [
        fila for fila in organos
        if fila["es_pendiente"]
    ]

    organos_rechazados = [
        fila for fila in organos
        if fila["es_rechazado"]
    ]

    organos_fuera_isquemia = [
        fila for fila in organos
        if fila["fuera_isquemia"]
    ]

    organos_pendientes_corte = [
        fila for fila in organos
        if fila["pendiente_por_corte"]
    ]

    organos_a_tiempo = [
        fila for fila in organos_completados
        if fila["cumple_deadline"]
    ]

    total = len(organos)

    return {
        "organos_totales_dataset": total,
        "organos_completados_dataset": len(organos_completados),
        "organos_pendientes_dataset": len(organos_pendientes),
        "organos_rechazados_dataset": len(organos_rechazados),
        "organos_on_time_dataset": len(organos_a_tiempo),
        "organos_fuera_isquemia": len(organos_fuera_isquemia),
        "organos_pendientes_por_corte_dataset": len(organos_pendientes_corte),
        "organos_tasa_on_time_dataset": (
            len(organos_a_tiempo) / total
            if total > 0
            else 0
        ),
        "organos_tasa_fuera_isquemia": (
            len(organos_fuera_isquemia) / total
            if total > 0
            else 0
        ),
        "cumple_isquemia": len(organos_fuera_isquemia) == 0,
        "cumple_estricto": (
            total > 0
            and len(organos_a_tiempo) == total
            and len(organos_pendientes) == 0
            and len(organos_rechazados) == 0
        ),
        "organos_totales_resultado": valor_seguro(resultado, "organos_totales"),
        "organos_completados_resultado": valor_seguro(resultado, "organos_completados"),
        "organos_pendientes_resultado": valor_seguro(resultado, "organos_pendientes"),
        "organos_late_resultado": valor_seguro(resultado, "organos_late"),
        "organos_on_time_resultado": valor_seguro(resultado, "organos_on_time"),
    }


# ---------------------------------------------------------------------------
# MÉTRICAS DE FLOTA
# ---------------------------------------------------------------------------

def metricas_flota(resultado, filas_drones):
    resumen_flota = valor_seguro(resultado, "resumen_flota", {})

    total_drones = len(filas_drones)

    drones_base = [
        fila for fila in filas_drones
        if fila["role"] == "base"
    ]

    drones_hospital = [
        fila for fila in filas_drones
        if fila["role"] == "hospital"
    ]

    vuelos = [
        fila["flight_minutes"]
        for fila in filas_drones
    ]

    recargas = [
        fila["charging_minutes"]
        for fila in filas_drones
    ]

    entregas = [
        fila["deliveries_made"]
        for fila in filas_drones
    ]

    return {
        "total_drones_dataset": total_drones,
        "drones_base_dataset": len(drones_base),
        "drones_hospital_dataset": len(drones_hospital),

        "drones_available_final": resumen_flota.get("available", 0),
        "drones_mission_final": resumen_flota.get("mission", 0),
        "drones_returning_final": resumen_flota.get("returning", 0),
        "drones_charging_final": resumen_flota.get("charging", 0),
        "drones_base_available_final": resumen_flota.get("base_available", 0),
        "drones_hospital_available_final": resumen_flota.get("hospital_available", 0),

        "drones_flight_minutes_total": sum(vuelos),
        "drones_flight_minutes_media": media_segura_valores(vuelos),
        "drones_flight_minutes_max": max_seguro_valores(vuelos),
        "drones_flight_minutes_min": min_seguro_valores(vuelos),

        "drones_charging_minutes_total": sum(recargas),
        "drones_charging_minutes_media": media_segura_valores(recargas),
        "drones_charging_minutes_max": max_seguro_valores(recargas),
        "drones_charging_minutes_min": min_seguro_valores(recargas),

        "drones_deliveries_total": sum(entregas),
        "drones_deliveries_media": media_segura_valores(entregas),
        "drones_deliveries_max": max_seguro_valores(entregas),
        "drones_deliveries_min": min_seguro_valores(entregas),

        "utilizacion_vuelo_pct_resultado": valor_seguro(resultado, "utilizacion_vuelo_pct"),
        "utilizacion_operativa_pct_resultado": valor_seguro(resultado, "utilizacion_operativa_pct"),
    }


# ---------------------------------------------------------------------------
# FILA PRINCIPAL DE SIMULACIÓN
# ---------------------------------------------------------------------------

def crear_fila_simulacion(
    resultado,
    nivel_estres,
    indice_simulacion,
    config,
    tiempo_ejecucion_s,
    filas_pedidos,
    filas_drones,
):
    historial_cola = obtener_historial_cola(resultado)

    fila = {
        "escenario": nivel_estres["nombre"],
        "escenario_etiqueta": nivel_estres["etiqueta"],
        "simulacion": indice_simulacion,
        "semilla": config["semilla"],

        "minutos_simulacion": valor_seguro(resultado, "minutos_simulacion"),
        "dias_simulacion": valor_seguro(resultado, "minutos_simulacion") / 1440,

        "escenario_base": ESCENARIO_BASE,
        "escenario_clima": config.get("escenario_clima", "normal"),
        "activar_meteorologia": bool_a_int(config.get("activar_meteorologia", True)),
        "intervalo_cambio_clima_min": config.get("intervalo_cambio_clima_min", None),

        "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
        "factor_demanda_organos": nivel_estres["factor_demanda_organos"],

        "drones_base_config_json": serializar_json(DRONES_BASE_CONFIG),
        "drones_hospitalarios_config_json": serializar_json(DRONES_HOSPITALARIOS_CONFIG),
        "drones_base_config_total": sum(DRONES_BASE_CONFIG.values()),
        "drones_hospitalarios_config_total": sum(DRONES_HOSPITALARIOS_CONFIG.values()),

        "tiempo_ejecucion_s": tiempo_ejecucion_s,

        # Métricas directas del simulador
        "pedidos_generados": valor_seguro(resultado, "pedidos_generados"),
        "pedidos_procesados": valor_seguro(resultado, "pedidos_procesados"),
        "pedidos_asignados": valor_seguro(resultado, "pedidos_asignados"),
        "pedidos_completados": valor_seguro(resultado, "pedidos_completados"),
        "pedidos_rechazados": valor_seguro(resultado, "pedidos_rechazados"),
        "pedidos_en_cola": valor_seguro(resultado, "pedidos_en_cola"),
        "tasa_servicio": valor_seguro(resultado, "tasa_servicio"),
        "tasa_servicio_pct": valor_seguro(resultado, "tasa_servicio") * 100,

        "inventario_completado": valor_seguro(resultado, "inventario_completado"),
        "inventario_pendiente": valor_seguro(resultado, "inventario_pendiente"),
        "p95_inventario_min_resultado": valor_seguro(resultado, "p95_inventario_min", None),

        "p95_inventario_cumple_720_min": bool_a_int(
            valor_seguro(resultado, "p95_inventario_min", 10**9)
            <= UMBRAL_P95_INVENTARIO_MIN
        ),

        "organos_totales": valor_seguro(resultado, "organos_totales"),
        "organos_completados": valor_seguro(resultado, "organos_completados"),
        "organos_pendientes": valor_seguro(resultado, "organos_pendientes"),
        "organos_rechazados": valor_seguro(resultado, "organos_rechazados"),
        "organos_on_time": valor_seguro(resultado, "organos_on_time"),
        "organos_late": valor_seguro(resultado, "organos_late"),
        "tasa_exito_organos": valor_seguro(resultado, "tasa_exito_organos"),
        "tasa_exito_organos_pct": valor_seguro(resultado, "tasa_exito_organos") * 100,
        "p95_organos_min_resultado": valor_seguro(resultado, "p95_organos_min", None),

        "longitud_media_cola_resultado": valor_seguro(resultado, "longitud_media_cola"),
        "longitud_maxima_cola_resultado": valor_seguro(resultado, "longitud_maxima_cola"),

        "utilizacion_vuelo_pct": valor_seguro(resultado, "utilizacion_vuelo_pct"),
        "utilizacion_operativa_pct": valor_seguro(resultado, "utilizacion_operativa_pct"),
        "tiempo_total_vuelo": valor_seguro(resultado, "tiempo_total_vuelo"),
        "tiempo_total_recarga": valor_seguro(resultado, "tiempo_total_recarga"),

        "conteo_clima_json": serializar_json(valor_seguro(resultado, "conteo_clima", {})),
        "conteo_producto_completados_json": serializar_json(
            valor_seguro(resultado, "conteo_producto_completados", {})
        ),
        "conteo_producto_pendientes_json": serializar_json(
            valor_seguro(resultado, "conteo_producto_pendientes", {})
        ),
        "conteo_producto_rechazados_json": serializar_json(
            valor_seguro(resultado, "conteo_producto_rechazados", {})
        ),
    }

    fila.update(metricas_tiempos_pedidos(filas_pedidos))
    fila.update(metricas_cola(historial_cola))
    fila.update(metricas_organos(filas_pedidos, resultado))
    fila.update(metricas_flota(resultado, filas_drones))

    return fila


# ---------------------------------------------------------------------------
# RESUMEN POR ESCENARIO
# ---------------------------------------------------------------------------

def resumir_por_escenario(filas_simulaciones):
    resumen = []

    for nivel in NIVELES_ESTRES:
        nombre = nivel["nombre"]

        filas = [
            fila for fila in filas_simulaciones
            if fila["escenario"] == nombre
        ]

        if not filas:
            continue

        def col(clave):
            return [
                fila.get(clave)
                for fila in filas
                if fila.get(clave) is not None
            ]

        total_organos = sum(col("organos_totales_dataset"))
        total_organos_on_time = sum(col("organos_on_time_dataset"))
        total_organos_fuera = sum(col("organos_fuera_isquemia"))
        total_organos_corte = sum(col("organos_pendientes_por_corte_dataset"))

        total_pedidos = sum(col("pedidos_generados"))
        total_completados = sum(col("pedidos_completados"))

        resumen.append(
            {
                "escenario": nombre,
                "escenario_etiqueta": nivel["etiqueta"],
                "num_simulaciones": len(filas),

                "factor_demanda_inventario": nivel["factor_demanda_inventario"],
                "factor_demanda_organos": nivel["factor_demanda_organos"],

                "pedidos_generados_total": total_pedidos,
                "pedidos_completados_total": total_completados,
                "tasa_servicio_global_pct": (
                    total_completados / total_pedidos * 100
                    if total_pedidos > 0
                    else 0
                ),

                "tasa_servicio_media_pct": media_segura_valores(col("tasa_servicio_pct")),
                "tasa_servicio_min_pct": min_seguro_valores(col("tasa_servicio_pct")),
                "tasa_servicio_max_pct": max_seguro_valores(col("tasa_servicio_pct")),

                "inventario_p95_medio_min": media_segura_valores(col("inventario_tiempo_p95_min")),
                "inventario_p95_peor_min": max_seguro_valores(col("inventario_tiempo_p95_min")),
                "inventario_p99_medio_min": media_segura_valores(col("inventario_tiempo_p99_min")),
                "inventario_max_peor_min": max_seguro_valores(col("inventario_tiempo_max_min")),

                "organos_totales": total_organos,
                "organos_on_time_total": total_organos_on_time,
                "organos_fuera_isquemia_total": total_organos_fuera,
                "organos_pendientes_por_corte_total": total_organos_corte,

                "organos_tasa_on_time_global_pct": (
                    total_organos_on_time / total_organos * 100
                    if total_organos > 0
                    else 0
                ),

                "organos_tasa_fuera_isquemia_global_pct": (
                    total_organos_fuera / total_organos * 100
                    if total_organos > 0
                    else 0
                ),

                "simulaciones_cumplen_isquemia": sum(
                    1 for fila in filas
                    if fila.get("cumple_isquemia") is True
                ),

                "simulaciones_cumplen_estricto": sum(
                    1 for fila in filas
                    if fila.get("cumple_estricto") is True
                ),

                "organos_p95_medio_min": media_segura_valores(col("organos_tiempo_p95_min")),
                "organos_p95_peor_min": max_seguro_valores(col("organos_tiempo_p95_min")),

                "cola_media_promedio": media_segura_valores(col("cola_media")),
                "cola_p95_promedio": media_segura_valores(col("cola_p95")),
                "cola_maxima_peor_caso": max_seguro_valores(col("cola_maxima")),
                "cola_area_media": media_segura_valores(col("cola_area_media_por_minuto")),

                "utilizacion_vuelo_media_pct": media_segura_valores(col("utilizacion_vuelo_pct")),
                "utilizacion_operativa_media_pct": media_segura_valores(col("utilizacion_operativa_pct")),
                "drones_flight_minutes_total_medio": media_segura_valores(col("drones_flight_minutes_total")),
                "drones_charging_minutes_total_medio": media_segura_valores(col("drones_charging_minutes_total")),

                "tiempo_ejecucion_medio_s": media_segura_valores(col("tiempo_ejecucion_s")),
            }
        )

    return resumen


# ---------------------------------------------------------------------------
# EJECUCIÓN DE UNA SIMULACIÓN
# ---------------------------------------------------------------------------

def ejecutar_simulacion(nivel_estres, indice_simulacion):
    config = crear_configuracion(nivel_estres, indice_simulacion)

    t0 = time.time()
    resultado = run_simulation(config)
    tiempo_ejecucion_s = time.time() - t0

    filas_pedidos = crear_filas_pedidos(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
    )

    filas_drones = crear_filas_drones(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
    )

    fila_simulacion = crear_fila_simulacion(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
        tiempo_ejecucion_s,
        filas_pedidos,
        filas_drones,
    )

    filas_cola = crear_filas_cola_tiempo(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
    )

    filas_clima = crear_filas_clima(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
    )

    filas_productos = crear_filas_productos(
        resultado,
        nivel_estres,
        indice_simulacion,
        config,
    )

    return {
        "fila_simulacion": fila_simulacion,
        "filas_pedidos": filas_pedidos,
        "filas_drones": filas_drones,
        "filas_cola": filas_cola,
        "filas_clima": filas_clima,
        "filas_productos": filas_productos,
    }



# ---------------------------------------------------------------------------
# GUARDADO COMPLETO / CHECKPOINTS
# ---------------------------------------------------------------------------

def guardar_datasets(
    prefijo,
    filas_simulaciones,
    filas_pedidos,
    filas_drones,
    filas_cola,
    filas_clima,
    filas_productos,
):
    """
    Guarda todos los CSV generados hasta el momento.

    prefijo="montecarlo"   -> archivos finales
    prefijo="checkpoint"   -> guardado parcial tras cada nivel
    prefijo="interrumpido" -> guardado de emergencia si se corta el programa
    """
    resumen_escenarios = resumir_por_escenario(filas_simulaciones)

    guardar_csv(
        f"{prefijo}_simulaciones_completo.csv",
        filas_simulaciones,
    )

    guardar_csv(
        f"{prefijo}_resumen_escenarios_completo.csv",
        resumen_escenarios,
    )

    guardar_csv(
        f"{prefijo}_pedidos_completo.csv",
        filas_pedidos,
    )

    guardar_csv(
        f"{prefijo}_cola_tiempo.csv",
        filas_cola,
    )

    guardar_csv(
        f"{prefijo}_drones_completo.csv",
        filas_drones,
    )

    guardar_csv(
        f"{prefijo}_clima_completo.csv",
        filas_clima,
    )

    guardar_csv(
        f"{prefijo}_productos_completo.csv",
        filas_productos,
    )

    return resumen_escenarios


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    crear_carpeta_salida()

    filas_simulaciones = []
    filas_pedidos = []
    filas_drones = []
    filas_cola = []
    filas_clima = []
    filas_productos = []

    total_simulaciones = NUM_SIMULACIONES * len(NIVELES_ESTRES)
    contador_global = 0

    print("=" * 80)
    print(" MONTE CARLO DE DIMENSIONAMIENTO - RED SANITARIA DE DRONES")
    print("=" * 80)
    print(f" Escenario base:              {ESCENARIO_BASE}")
    print(f" Clima:                       normal")
    print(f" Semilla base:                {SEMILLA_BASE}")
    print(f" Simulaciones por nivel:      {NUM_SIMULACIONES}")
    print(f" Niveles de estrés:           {len(NIVELES_ESTRES)}")
    print(f" Total simulaciones:          {total_simulaciones}")
    print(f" Duración por simulación:     {MINUTOS_SIMULACION} min ({MINUTOS_SIMULACION / 1440:.1f} días)")
    print(f" Muestreo cola cada:          {INTERVALO_MUESTREO_COLA_MIN} min")
    print(f" Carpeta salida:              {CARPETA_SALIDA}/")
    print("=" * 80)

    t_inicio = time.time()

    try:
        for nivel in NIVELES_ESTRES:
            print(f"\n>>> Nivel: {nivel['nombre']} ({nivel['etiqueta']})")
            print(
                f"    inventario x{nivel['factor_demanda_inventario']} | "
                f"órganos x{nivel['factor_demanda_organos']}"
            )

            for i in range(1, NUM_SIMULACIONES + 1):
                contador_global += 1

                print(
                    f"  Simulación {i}/{NUM_SIMULACIONES} "
                    f"({contador_global}/{total_simulaciones})...",
                    end=" ",
                )

                datos = ejecutar_simulacion(nivel, i)

                fila = datos["fila_simulacion"]

                filas_simulaciones.append(fila)
                filas_pedidos.extend(datos["filas_pedidos"])
                filas_drones.extend(datos["filas_drones"])
                filas_cola.extend(datos["filas_cola"])
                filas_clima.extend(datos["filas_clima"])
                filas_productos.extend(datos["filas_productos"])

                print(
                    f"servicio={fila['tasa_servicio_pct']:.1f}% | "
                    f"órg={fila['organos_on_time_dataset']}/{fila['organos_totales_dataset']} | "
                    f"fuera_iso={fila['organos_fuera_isquemia']} | "
                    f"cola_max={fila['cola_maxima']} | "
                    f"P95_inv={fila['inventario_tiempo_p95_min']}"
                )

            # Checkpoint tras terminar cada nivel de estrés.
            # Si el siguiente nivel tarda demasiado o paras el programa,
            # ya tendrás guardado todo lo completado hasta aquí.
            print("\n  Guardando checkpoint parcial del nivel completado...")
            guardar_datasets(
                "checkpoint",
                filas_simulaciones,
                filas_pedidos,
                filas_drones,
                filas_cola,
                filas_clima,
                filas_productos,
            )

    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print(" EJECUCIÓN INTERRUMPIDA POR EL USUARIO")
        print("=" * 80)
        print(" Guardando CSV de emergencia con lo acumulado hasta ahora...")

        resumen_interrumpido = guardar_datasets(
            "interrumpido",
            filas_simulaciones,
            filas_pedidos,
            filas_drones,
            filas_cola,
            filas_clima,
            filas_productos,
        )

        tiempo_total = time.time() - t_inicio

        print("\nResumen parcial guardado.")
        print(f" Tiempo ejecutado:             {tiempo_total:.1f} s")
        print(f" Simulaciones completadas:     {len(filas_simulaciones)}/{total_simulaciones}")
        print(f" Filas pedidos:                {len(filas_pedidos)}")
        print(f" Filas cola temporal:          {len(filas_cola)}")
        print(f" Carpeta salida:               {CARPETA_SALIDA}/")
        print("\nArchivos de emergencia generados con prefijo:")
        print("  interrumpido_*.csv")
        print("=" * 80)

        if resumen_interrumpido:
            print("\nResumen parcial por escenario:")
            for fila in resumen_interrumpido:
                print(f"\nEscenario: {fila['escenario']} ({fila['escenario_etiqueta']})")
                print(f"  Servicio global:             {fila['tasa_servicio_global_pct']:.2f}%")
                print(f"  P95 inventario medio:        {fila['inventario_p95_medio_min']}")
                print(f"  Órganos totales:             {fila['organos_totales']}")
                print(f"  Fuera de isquemia:           {fila['organos_fuera_isquemia_total']}")
                print(f"  Cola máxima peor caso:       {fila['cola_maxima_peor_caso']}")

        return

    resumen_escenarios = guardar_datasets(
        "montecarlo",
        filas_simulaciones,
        filas_pedidos,
        filas_drones,
        filas_cola,
        filas_clima,
        filas_productos,
    )

    tiempo_total = time.time() - t_inicio

    print("\n" + "=" * 80)
    print(" RESUMEN FINAL")
    print("=" * 80)
    print(f" Tiempo total ejecución:       {tiempo_total:.1f} s")
    print(f" Filas simulaciones:           {len(filas_simulaciones)}")
    print(f" Filas pedidos:                {len(filas_pedidos)}")
    print(f" Filas drones:                 {len(filas_drones)}")
    print(f" Filas cola temporal:          {len(filas_cola)}")
    print(f" Filas clima:                  {len(filas_clima)}")
    print(f" Filas productos:              {len(filas_productos)}")
    print("-" * 80)

    for fila in resumen_escenarios:
        print(f"\nEscenario: {fila['escenario']} ({fila['escenario_etiqueta']})")
        print(f"  Servicio global:             {fila['tasa_servicio_global_pct']:.2f}%")
        print(f"  Servicio medio:              {fila['tasa_servicio_media_pct']:.2f}%")
        print(f"  P95 inventario medio:        {fila['inventario_p95_medio_min']}")
        print(f"  P95 inventario peor:         {fila['inventario_p95_peor_min']}")
        print(f"  Órganos totales:             {fila['organos_totales']}")
        print(f"  Órganos a tiempo:            {fila['organos_on_time_total']}")
        print(f"  Fuera de isquemia:           {fila['organos_fuera_isquemia_total']}")
        print(f"  Pendientes por corte:        {fila['organos_pendientes_por_corte_total']}")
        print(f"  Sims cumplen isquemia:       {fila['simulaciones_cumplen_isquemia']}/{fila['num_simulaciones']}")
        print(f"  Cola máxima peor caso:       {fila['cola_maxima_peor_caso']}")
        print(f"  Utilización operativa media: {fila['utilizacion_operativa_media_pct']}%")

    print("\nArchivos generados en:")
    print(f"  {CARPETA_SALIDA}/")
    print("\nArchivos finales con prefijo:")
    print("  montecarlo_*.csv")
    print("\nCheckpoints parciales con prefijo:")
    print("  checkpoint_*.csv")
    print("=" * 80)


if __name__ == "__main__":
    main()

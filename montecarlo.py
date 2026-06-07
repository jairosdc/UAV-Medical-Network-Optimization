"""
montecarlo_escenarios.py
========================

Monte Carlo usando siempre el escenario "personalizado".

La idea es mantener fija la arquitectura de red, la meteorología normal
y la configuración de drones, cambiando únicamente el nivel de estrés
mediante:

- factor_demanda_inventario
- factor_demanda_organos

Uso desde la raíz del proyecto:

    python -m simulators.montecarlo_escenarios
"""

import csv
from copy import deepcopy
from statistics import mean

from simulators.experimentacion import run_simulation
from simulators.escenarios import ESCENARIOS


# ---------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------------------------

NUM_SIMULACIONES = 30
SEMILLA_BASE = 67

MINUTOS_14_DIAS = 14 * 24 * 60

ESCENARIO_BASE = "personalizado"


# ---------------------------------------------------------------------------
# NIVELES DE ESTRÉS
# ---------------------------------------------------------------------------
# Todos usan:
# - escenario_clima = "normal"
# - activar_meteorologia = True
# - misma configuración de drones
#
# Solo cambia:
# - factor_demanda_inventario
# - factor_demanda_organos
# ---------------------------------------------------------------------------

NIVELES_ESTRES = [
    {
        "nombre": "estres_1_base",
        "factor_demanda_inventario": 1.0,
        "factor_demanda_organos": 1.0,
    },
    {
        "nombre": "estres_2_moderado",
        "factor_demanda_inventario": 1.5,
        "factor_demanda_organos": 1.25,
    },
    {
        "nombre": "estres_3_alto",
        "factor_demanda_inventario": 2.0,
        "factor_demanda_organos": 1.5,
    },
    {
        "nombre": "estres_4_muy_alto",
        "factor_demanda_inventario": 2.5,
        "factor_demanda_organos": 2.0,
    },
    {
        "nombre": "estres_5_extremo",
        "factor_demanda_inventario": 3.0,
        "factor_demanda_organos": 2.5,
    },
]


# ---------------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DRONES DE BASE
# ---------------------------------------------------------------------------
# Estos drones son los que afectan al inventario.
# Si el P95 de inventario sale muy alto, se toca esto.
# ---------------------------------------------------------------------------

DRONES_BASE_CONFIG = {
    "BASE NOROESTE": 3,
    "BASE NORTE CAPITAL": 3,
    "BASE ESTE CORREDOR": 3,
    "BASE SUR FUENLABRADA": 3,
}


# ---------------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DRONES HOSPITALARIOS
# ---------------------------------------------------------------------------
# Estos drones son los que afectan al transporte de órganos.
# ---------------------------------------------------------------------------

DRONES_HOSPITALARIOS_CONFIG = {
    # Norte / norte capital
    "Hospital Universitario La Paz": 2,
    "Hospital Universitario Ramón y Cajal": 2,

    # Centro / centro-este
    "Hospital General Universitario Gregorio Marañón": 2,

    # Sur / suroeste
    "Hospital Universitario 12 de Octubre": 2,
    "Hospital Universitario de Fuenlabrada": 1,
    "Hospital Universitario Fundación Alcorcón": 1,

    # Oeste / noroeste
    "Hospital Universitario Puerta de Hierro Majadahonda": 2,

    # Este / corredor del Henares
    "Hospital Universitario de Torrejón": 1,
    "Hospital Universitario Príncipe de Asturias": 1,

    # Sierra / hospitales periféricos críticos
    "Hospital Asociado Universitario Guadarrama": 2,
    "Hospital La Fuenfría": 2,
}


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def valor_seguro(resultado, clave, defecto=0):
    valor = resultado.get(clave, defecto)
    return defecto if valor is None else valor


def obtener_pendientes_vencidos(resultado):
    """
    Cuenta órganos pendientes cuyo deadline ya ha vencido dentro
    del horizonte de simulación.

    Si el órgano queda pendiente pero su deadline está después del final
    de la simulación, se considera efecto de corte.
    """
    detalle = resultado.get("detalle_organos_pendientes", [])
    minutos_simulacion = resultado.get("minutos_simulacion", 0)

    pendientes_vencidos = 0
    pendientes_por_corte = 0

    for pedido in detalle:
        deadline = pedido.get("deadline_min")

        if deadline is None:
            continue

        if deadline <= minutos_simulacion:
            pendientes_vencidos += 1
        else:
            pendientes_por_corte += 1

    return pendientes_vencidos, pendientes_por_corte


def cumple_organos_isquemia(resultado):
    """
    Criterio clínico:
    - ningún órgano entregado tarde,
    - ningún órgano pendiente con deadline vencido.

    Los pendientes por corte no se consideran fallo clínico todavía.
    """
    pendientes_vencidos, _ = obtener_pendientes_vencidos(resultado)

    return (
        valor_seguro(resultado, "organos_late") == 0
        and pendientes_vencidos == 0
    )


def cumple_organos_estricto(resultado):
    """
    Criterio estricto:
    - todos los órganos entregados a tiempo,
    - ningún órgano tarde,
    - ningún órgano pendiente.
    """
    return (
        valor_seguro(resultado, "organos_totales") > 0
        and valor_seguro(resultado, "organos_on_time") == valor_seguro(resultado, "organos_totales")
        and valor_seguro(resultado, "organos_late") == 0
        and valor_seguro(resultado, "organos_pendientes") == 0
    )


def crear_configuracion(nivel_estres, indice_simulacion):
    """
    Crea una configuración limpia para una simulación concreta.

    Siempre parte de ESCENARIOS["personalizado"].
    Solo cambia la semilla y los factores de estrés.
    """
    config = deepcopy(ESCENARIOS[ESCENARIO_BASE])

    semilla = SEMILLA_BASE + indice_simulacion

    config["minutos_simulacion"] = MINUTOS_14_DIAS
    config["semilla"] = semilla

    # Clima siempre en modo normal.
    config["escenario_clima"] = "normal"
    config["activar_meteorologia"] = True
    config["intervalo_cambio_clima_min"] = 300

    # Solo cambiamos el estrés.
    config["factor_demanda_inventario"] = nivel_estres["factor_demanda_inventario"]
    config["factor_demanda_organos"] = nivel_estres["factor_demanda_organos"]

    # Fijamos la flota de bases.
    config["drones_por_base"] = 0
    config["drones_por_base_config"] = deepcopy(DRONES_BASE_CONFIG)

    # Fijamos la flota hospitalaria.
    config["drones_por_hospital"] = 0
    config["drones_por_hospital_config"] = deepcopy(DRONES_HOSPITALARIOS_CONFIG)

    # Silenciamos salida interna.
    config["verbose"] = False
    config["generar_graficas"] = False
    config["imprimir_eventos_drones"] = False
    config["imprimir_eventos_hospital"] = False
    config["imprimir_eventos_clima"] = False

    return config


def ejecutar_simulacion(nivel_estres, indice_simulacion):
    """
    Ejecuta una simulación y devuelve una fila plana de resultados.
    """
    config = crear_configuracion(nivel_estres, indice_simulacion)
    resultado = run_simulation(config)

    pendientes_vencidos, pendientes_por_corte = obtener_pendientes_vencidos(resultado)

    fila = {
        "escenario": nivel_estres["nombre"],
        "simulacion": indice_simulacion,
        "semilla": config["semilla"],

        "factor_demanda_inventario": nivel_estres["factor_demanda_inventario"],
        "factor_demanda_organos": nivel_estres["factor_demanda_organos"],
        "escenario_clima": config["escenario_clima"],

        "minutos_simulacion": valor_seguro(resultado, "minutos_simulacion"),
        "total_drones": valor_seguro(resultado, "total_drones"),
        "drones_base_total": resultado.get("resumen_flota", {}).get("base_total", 0),
        "drones_hospital_total": resultado.get("resumen_flota", {}).get("hospital_total", 0),

        "pedidos_generados": valor_seguro(resultado, "pedidos_generados"),
        "pedidos_completados": valor_seguro(resultado, "pedidos_completados"),
        "pedidos_en_cola": valor_seguro(resultado, "pedidos_en_cola"),
        "tasa_servicio": valor_seguro(resultado, "tasa_servicio"),

        "inventario_completado": valor_seguro(resultado, "inventario_completado"),
        "inventario_pendiente": valor_seguro(resultado, "inventario_pendiente"),
        "p95_inventario_min": valor_seguro(resultado, "p95_inventario_min", None),

        "organos_totales": valor_seguro(resultado, "organos_totales"),
        "organos_completados": valor_seguro(resultado, "organos_completados"),
        "organos_pendientes": valor_seguro(resultado, "organos_pendientes"),
        "organos_pendientes_vencidos": pendientes_vencidos,
        "organos_pendientes_por_corte": pendientes_por_corte,
        "organos_on_time": valor_seguro(resultado, "organos_on_time"),
        "organos_late": valor_seguro(resultado, "organos_late"),
        "tasa_exito_organos": valor_seguro(resultado, "tasa_exito_organos"),
        "p95_organos_min": valor_seguro(resultado, "p95_organos_min", None),

        "cumple_organos_isquemia": cumple_organos_isquemia(resultado),
        "cumple_organos_estricto": cumple_organos_estricto(resultado),

        "longitud_media_cola": valor_seguro(resultado, "longitud_media_cola"),
        "longitud_maxima_cola": valor_seguro(resultado, "longitud_maxima_cola"),

        "utilizacion_vuelo_pct": valor_seguro(resultado, "utilizacion_vuelo_pct"),
        "utilizacion_operativa_pct": valor_seguro(resultado, "utilizacion_operativa_pct"),
    }

    return fila


def guardar_csv(nombre_archivo, filas):
    if not filas:
        return

    columnas = list(filas[0].keys())

    with open(nombre_archivo, "w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas)


def filtrar_numericos(filas, clave):
    valores = []

    for fila in filas:
        valor = fila.get(clave)

        if isinstance(valor, (int, float)):
            valores.append(valor)

    return valores


def media_segura(filas, clave):
    valores = filtrar_numericos(filas, clave)
    return mean(valores) if valores else None


def max_seguro(filas, clave):
    valores = filtrar_numericos(filas, clave)
    return max(valores) if valores else None


def min_seguro(filas, clave):
    valores = filtrar_numericos(filas, clave)
    return min(valores) if valores else None


def porcentaje_seguro(valor):
    return valor * 100 if valor is not None else None


def resumir_por_escenario(filas_detalle):
    resumen = []

    for nivel in NIVELES_ESTRES:
        nombre_escenario = nivel["nombre"]

        filas = [
            fila for fila in filas_detalle
            if fila["escenario"] == nombre_escenario
        ]

        if not filas:
            continue

        organos_totales = sum(fila["organos_totales"] for fila in filas)
        organos_on_time = sum(fila["organos_on_time"] for fila in filas)
        organos_late = sum(fila["organos_late"] for fila in filas)
        organos_pendientes = sum(fila["organos_pendientes"] for fila in filas)
        organos_pendientes_vencidos = sum(
            fila["organos_pendientes_vencidos"] for fila in filas
        )
        organos_pendientes_por_corte = sum(
            fila["organos_pendientes_por_corte"] for fila in filas
        )

        tasa_exito_global_organos = (
            organos_on_time / organos_totales
            if organos_totales > 0
            else 0
        )

        tasa_servicio_media = media_segura(filas, "tasa_servicio")
        tasa_servicio_min = min_seguro(filas, "tasa_servicio")

        resumen.append(
            {
                "escenario": nombre_escenario,
                "factor_demanda_inventario": nivel["factor_demanda_inventario"],
                "factor_demanda_organos": nivel["factor_demanda_organos"],
                "escenario_clima": "normal",

                "num_simulaciones": len(filas),

                "tasa_servicio_media_pct": porcentaje_seguro(tasa_servicio_media),
                "tasa_servicio_min_pct": porcentaje_seguro(tasa_servicio_min),

                "p95_inventario_medio_min": media_segura(filas, "p95_inventario_min"),
                "p95_inventario_max_min": max_seguro(filas, "p95_inventario_min"),

                "organos_totales": organos_totales,
                "organos_on_time": organos_on_time,
                "organos_late": organos_late,
                "organos_pendientes": organos_pendientes,
                "organos_pendientes_vencidos": organos_pendientes_vencidos,
                "organos_pendientes_por_corte": organos_pendientes_por_corte,
                "tasa_exito_global_organos_pct": tasa_exito_global_organos * 100,

                "simulaciones_cumplen_isquemia": sum(
                    1 for fila in filas
                    if fila["cumple_organos_isquemia"]
                ),
                "simulaciones_cumplen_estricto": sum(
                    1 for fila in filas
                    if fila["cumple_organos_estricto"]
                ),

                "p95_organos_medio_min": media_segura(filas, "p95_organos_min"),
                "p95_organos_max_min": max_seguro(filas, "p95_organos_min"),

                "cola_media_promedio": media_segura(filas, "longitud_media_cola"),
                "cola_maxima_peor_caso": max_seguro(filas, "longitud_maxima_cola"),

                "utilizacion_operativa_media_pct": media_segura(
                    filas,
                    "utilizacion_operativa_pct",
                ),
            }
        )

    return resumen


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    filas_detalle = []

    print("=" * 70)
    print(" MONTE CARLO - RED SANITARIA DE DRONES")
    print("=" * 70)
    print(f" Escenario base:             {ESCENARIO_BASE}")
    print(f" Clima:                      normal")
    print(f" Semilla base:               {SEMILLA_BASE}")
    print(f" Simulaciones por nivel:     {NUM_SIMULACIONES}")
    print(f" Duración por simulación:    {MINUTOS_14_DIAS} min (14 días)")
    print(f" Niveles de estrés:          {len(NIVELES_ESTRES)}")
    print("=" * 70)

    for nivel in NIVELES_ESTRES:
        print(f"\n>>> Nivel: {nivel['nombre']}")
        print(
            f"    inventario x{nivel['factor_demanda_inventario']} | "
            f"órganos x{nivel['factor_demanda_organos']}"
        )

        for i in range(1, NUM_SIMULACIONES + 1):
            print(f"  Simulación {i}/{NUM_SIMULACIONES}...", end=" ")

            fila = ejecutar_simulacion(
                nivel_estres=nivel,
                indice_simulacion=i,
            )

            filas_detalle.append(fila)

            print(
                f"servicio={fila['tasa_servicio'] * 100:.1f}% | "
                f"órganos={fila['organos_on_time']}/{fila['organos_totales']} | "
                f"late={fila['organos_late']} | "
                f"pend={fila['organos_pendientes']} | "
                f"vencidos={fila['organos_pendientes_vencidos']} | "
                f"corte={fila['organos_pendientes_por_corte']} | "
                f"P95 inv={fila['p95_inventario_min']}"
            )

    resumen = resumir_por_escenario(filas_detalle)

    guardar_csv("montecarlo_detalle_personalizado_14dias.csv", filas_detalle)
    guardar_csv("montecarlo_resumen_personalizado_14dias.csv", resumen)

    print("\n" + "=" * 70)
    print(" RESUMEN FINAL")
    print("=" * 70)

    for fila in resumen:
        print(f"\nNivel: {fila['escenario']}")
        print(f"  Inventario x:              {fila['factor_demanda_inventario']}")
        print(f"  Órganos x:                 {fila['factor_demanda_organos']}")
        print(f"  Clima:                     {fila['escenario_clima']}")
        print(f"  Tasa servicio media:       {fila['tasa_servicio_media_pct']:.2f}%")
        print(f"  Tasa servicio mínima:      {fila['tasa_servicio_min_pct']:.2f}%")
        print(f"  P95 inventario medio:      {fila['p95_inventario_medio_min']:.2f} min")
        print(f"  P95 inventario peor caso:  {fila['p95_inventario_max_min']:.2f} min")
        print(f"  Órganos totales:           {fila['organos_totales']}")
        print(f"  Órganos a tiempo:          {fila['organos_on_time']}")
        print(f"  Órganos tarde:             {fila['organos_late']}")
        print(f"  Pendientes:                {fila['organos_pendientes']}")
        print(f"  Pendientes vencidos:       {fila['organos_pendientes_vencidos']}")
        print(f"  Pendientes por corte:      {fila['organos_pendientes_por_corte']}")
        print(f"  Éxito global órganos:      {fila['tasa_exito_global_organos_pct']:.2f}%")
        print(
            f"  Sims cumplen isquemia:     "
            f"{fila['simulaciones_cumplen_isquemia']}/{fila['num_simulaciones']}"
        )
        print(
            f"  Sims cumplen estricto:     "
            f"{fila['simulaciones_cumplen_estricto']}/{fila['num_simulaciones']}"
        )
        print(f"  Cola máxima peor caso:     {fila['cola_maxima_peor_caso']}")

    print("\nArchivos generados:")
    print("  - montecarlo_detalle_personalizado_14dias.csv")
    print("  - montecarlo_resumen_personalizado_14dias.csv")
    print("=" * 70)


if __name__ == "__main__":
    main()
import random

# ── parametros_globales.py ────────────────────────────────────────────────────
CHARGE_RATE_PERCENT_PER_MIN = 3.5


# ── procesar_recarga_dron.py ──────────────────────────────────────────────────
def procesar_recarga_dron(dron, minutos_transcurridos: int = 1):
    if dron["status"] != "charging":
        return

    bateria_proyectada = dron["battery_percent"] + (CHARGE_RATE_PERCENT_PER_MIN * minutos_transcurridos)

    if bateria_proyectada >= 100.0:
        dron["battery_percent"]  = 100.0
        dron["status"]           = "available"
        dron["busy_until_min"]   = 0
        dron["current_call_id"]  = None
    else:
        dron["battery_percent"]  = bateria_proyectada


# ── Simulación ────────────────────────────────────────────────────────────────
def simular_recarga(n_drones: int = 5):
    drones = [
        {
            "id":              f"D-{i+1:02d}",
            "battery_percent": round(random.uniform(5, 80), 1),
            "status":          "charging",
            "busy_until_min":  0,
            "current_call_id": None,
        }
        for i in range(n_drones)
    ]

    errores = []

    for dron in drones:
        bateria_inicial = dron["battery_percent"]
        minutos = 0

        while dron["status"] == "charging":
            procesar_recarga_dron(dron)
            minutos += 1

            if minutos > 500:
                errores.append(f"{dron['id']}: bucle infinito detectado")
                break

        # Validaciones
        if dron["battery_percent"] != 100.0:
            errores.append(f"{dron['id']}: batería final es {dron['battery_percent']:.1f}%, se esperaba 100%")

        if dron["status"] != "available":
            errores.append(f"{dron['id']}: estado final es '{dron['status']}', se esperaba 'available'")

        if dron["busy_until_min"] != 0:
            errores.append(f"{dron['id']}: busy_until_min no se reseteó a 0")

        if dron["current_call_id"] is not None:
            errores.append(f"{dron['id']}: current_call_id no se reseteó a None")

        minutos_esperados = (100.0 - bateria_inicial) / CHARGE_RATE_PERCENT_PER_MIN
        if abs(minutos - minutos_esperados) > 1:
            errores.append(f"{dron['id']}: tardó {minutos} min, se esperaban ~{minutos_esperados:.1f} min")

    if errores:
        print("❌ FALLO — se encontraron errores en la recarga:")
        for e in errores:
            print(f"   · {e}")
    else:
        print("✅ OK — la recarga de todos los drones funciona correctamente")


if __name__ == "__main__":
    simular_recarga(n_drones=5)

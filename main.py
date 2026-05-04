from simulators.experimentacion import run_simulation


def main():
    config = {
        "minutos_simulacion": 50000,
        "drones_por_base": 1,
        "drones_por_hospital": 1,
        "semilla": None,

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,

        "generar_graficas": False,
        "verbose": True,
    }

    resultado = run_simulation(config)

    print("\nDICCIONARIO RESULTADO")
    print("-" * 60)

    for clave, valor in resultado.items():
        print(f"{clave}: {valor}")


if __name__ == "__main__":
    main()
from simulators.experimentacion import run_simulation
from simulators.escenarios import ESCENARIOS


def main():
    # Escenarios disponibles:
    #
    # "normal"
    #   Demanda normal, clima normal, flota estándar.
    #
    # "alta_demanda"
    #   Más consumo hospitalario y más órganos, pero clima normal.
    #
    # "lluvia_alta_demanda"
    #   Alta demanda combinada con clima lluvioso.
    #
    # "baja_demanda_clima_adverso"
    #   Menor demanda de inventario, pero clima adverso y menos drones por base.
    #
    # "estres_extremo"
    #   Mucha demanda, clima adverso y flota ajustada. Escenario duro.

    nombre_escenario = "normal"

    config = ESCENARIOS[nombre_escenario].copy()

    print("=" * 60)
    print(f"Ejecutando escenario: {nombre_escenario}")
    print("=" * 60)

    resultado = run_simulation(config)

    print("\nResumen final:")
    print(f"Pedidos generados:     {resultado['pedidos_generados']}")
    print(f"Pedidos completados:   {resultado['pedidos_completados']}")
    print(f"Pedidos en cola:       {resultado['pedidos_en_cola']}")
    print(f"Órganos totales:       {resultado['organos_totales']}")
    print(f"Órganos completados:   {resultado['organos_completados']}")
    print(f"Órganos pendientes:    {resultado['organos_pendientes']}")
    print(f"Utilización vuelo:     {resultado['utilizacion_vuelo_pct']:.2f}%")
    print(f"Utilización operativa: {resultado['utilizacion_operativa_pct']:.2f}%")


if __name__ == "__main__":
    main()
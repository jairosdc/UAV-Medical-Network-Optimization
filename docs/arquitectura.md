# Arquitectura del Sistema

Esta sección describe la arquitectura técnica, la conexión entre los módulos de software y el flujo lógico de eventos dentro del simulador DES tras la reorganización del repositorio en carpetas profesionales.

## Flujo Lógico y Conexiones de los Módulos

El simulador se basa en un diseño estructurado por carpetas donde las responsabilidades están delimitadas en subdirectorios específicos (`src/` para el núcleo, `scripts/` para ejecutables, `apps/` para la interfaz visual). El siguiente diagrama ilustra la interacción y dependencias de importación entre los diferentes componentes del software:

```text
                               +-----------------------------+
                               | src/uav_medical_network/    |
                               |   modelos.py                |
                               +--------------+--------------+
                                              | (entidades, dataclasses)
                                              v
+-----------------------------+  (nodos)      +-----------------------------+
| src/uav_medical_network/    +-------------->| src/uav_medical_network/    |
|   config.py                 |               |   red.py                    |
+-----------------------------+               +--------------+--------------+
                                                             | (haversine, batería, despacho)
                                                             v
+-----------------------------+               +-----------------------------+
| src/uav_medical_network/    +-------------->| src/uav_medical_network/    |
|   clima.py                  |  (clima)      |   flota.py                  |
+-----------------------------+               +--------------+--------------+
                                                             | (controlador de drones)
                                                             v
+-----------------------------+               +-----------------------------+
| src/uav_medical_network/    +-------------->| src/uav_medical_network/    |
|   generador.py              |  (pedidos)    |   simulacion.py             |
+-----------------------------+               +--------------+--------------+
                                                             | (motor DES)
                                                             v
                                              +-----------------------------+
                                              | src/uav_medical_network/    |
                                              |   telemetria.py             |
                                              +--------------+--------------+
                                                             | (salida JSON)
                                                             v
                                              +-----------------------------+
                                              | apps/radar_app.py           |
                                              +-----------------------------+

                                              [scripts/run_simulation.py]
                                              [scripts/run_montecarlo.py]
                                              [scripts/generar_graficas.py]
                                              [scripts/generar_mapa.py]
                                              [scripts/diagnostico.py]
```

---

## Detalle de Responsabilidades por Módulo

### 1. Núcleo del Simulador (en `src/uav_medical_network/`)
*   **[config.py](file:///../src/uav_medical_network/config.py):** Define las constantes globales del sistema (velocidades, límites de viento, consumo de carga) y las coordenadas geográficas de los 36 hospitales y las 4 bases operativas.
*   **[modelos.py](file:///../src/uav_medical_network/modelos.py):** Contiene el modelo de datos de las entidades básicas del simulador (`Node`, `Drone`, `DeliveryCall`, `Producto`, `Inventario` y `GestorPrioridad`). Implementa la lógica local de consumo de inventario hospitalario y recarga de batería individual.
*   **[red.py](file:///../src/uav_medical_network/red.py):** Implementa las funciones físicas de la red. Calcula las distancias terrestres entre nodos mediante la aproximación esférica de Haversine, calcula la autonomía restante del dron dada una carga transportada y ejecuta la lógica de emparejamiento óptimo (despacho) entre pedidos en cola y drones disponibles.
*   **[clima.py](file:///../src/uav_medical_network/clima.py):** Modela las variaciones estocásticas de las condiciones del tiempo atmosférico. Contiene perfiles con probabilidades asociadas y un factor de reducción de la velocidad para reflejar el impacto de lluvias o ráfagas de viento en el avance del dron.
*   **[generador.py](file:///../src/uav_medical_network/generador.py):** Genera la agenda inicial de eventos para toda la simulación. Utiliza una distribución de Poisson para modelar los consumos intrahospitalarios de productos médicos y la aparición aleatoria de donaciones de órganos urgentes.
*   **[flota.py](file:///../src/uav_medical_network/flota.py):** Orquesta el ciclo de vida y estado de la flota de drones. Maneja las transiciones de estado de los drones (`available` -> `mission` -> `returning` -> `charging`) y actualiza los contadores de estadísticas operativas globales.
*   **[simulacion.py](file:///../src/uav_medical_network/simulacion.py):** Contiene el bucle central de simulación de eventos discretos. Consume los eventos ordenados por tiempo y prioridad, delega las decisiones operativas al controlador de flota y registra las métricas acumuladas.
*   **[telemetria.py](file:///../src/uav_medical_network/telemetria.py):** Registra cada segmento de vuelo de forma secuencial y exporta un archivo estructurado `telemetria_vuelos.json` en la raíz del proyecto.
*   **[graficas.py](file:///../src/uav_medical_network/graficas.py):** Módulo interno que renderiza las gráficas rápidas resultantes de ejecuciones individuales (main) mediante matplotlib.

### 2. Aplicaciones Interactivas (en `apps/`)
*   **[radar_app.py](file:///../apps/radar_app.py):** Interfaz gráfica interactiva de reproducción temporal en la cual Streamlit consume la telemetría generada y proyecta en tiempo real el comportamiento espacial en un mapa dinámico 3D.

### 3. Puntos de Entrada y Consola (en `scripts/`)
*   **[run_simulation.py](file:///../scripts/run_simulation.py):** Configura y ejecuta una simulación única para depuración rápida de código.
*   **[run_montecarlo.py](file:///../scripts/run_montecarlo.py):** Automatiza la ejecución en bucle de múltiples simulaciones estocásticas con semillas aleatorias para evaluar el comportamiento bajo distintos factores de estrés en la demanda de la red.
*   **[generar_graficas.py](file:///../scripts/generar_graficas.py):** Procesa los archivos CSV resultantes de Monte Carlo y genera reportes gráficos de nivel de servicio.
*   **[diagnostico.py](file:///../scripts/diagnostico.py):** Evalúa la cobertura puramente física y estática de las bases de drones basándose en el alcance energético máximo.
*   **[generar_mapa.py](file:///../scripts/generar_mapa.py):** Crea una vista de folium interactiva offline del grafo de hospitales y bases.

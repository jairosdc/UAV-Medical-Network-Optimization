# Arquitectura del Sistema

Esta sección describe la arquitectura técnica, la conexión entre los módulos de software y el flujo lógico de eventos dentro del simulador DES.

## Flujo Lógico y Conexiones de los Módulos

El simulador se basa en un diseño modular plano donde las responsabilidades están claramente delimitadas en archivos fuente específicos. El siguiente diagrama ilustra la interacción y dependencias de importación entre los diferentes componentes del software:

```text
                               +-------------+
                               |  modelos.py |
                               +------+------+
                                      | (entidades, dataclasses)
                                      v
+-------------+  (nodos)       +------+------+
|  config.py  +--------------->|   red.py    |
+-------------+                +------+------+
                                      | (haversine, batería, despacho)
                                      v
+-------------+                +------+------+
|  clima.py   +--------------->|  flota.py   |
+-------------+  (clima)       +------+------+
                                      | (controlador de drones)
                                      v
+-------------+                +------+------+
|generador.py +--------------->|simulacion.py|<------- [ main.py / montecarlo.py ]
+-------------+  (pedidos)     +------+------+
                                      | (motor DES)
                                      v
                               +------+------+
                               |telemetria.py|
                               +------+------+
                                      | (salida JSON)
                                      v
                               +------+------+
                               |radar_app.py |
                               +-------------+
```

---

## Detalle de Responsabilidades por Módulo

### 1. Núcleo Geográfico y Físico
*   **[config.py](file:///../config.py):** Define las constantes globales del sistema (velocidades, límites de viento, consumo de carga) y las coordenadas geográficas de los 36 hospitales y las 4 bases operativas.
*   **[modelos.py](file:///../modelos.py):** Contiene el modelo de datos de las entidades básicas del simulador (`Node`, `Drone`, `DeliveryCall`, `Producto`, `Inventario` y `GestorPrioridad`). Implementa la lógica local de consumo de inventario hospitalario y recarga de batería individual.
*   **[red.py](file:///../red.py):** Implementa las funciones físicas de la red. Calcula las distancias terrestres entre nodos mediante la aproximación esférica de Haversine, calcula la autonomía restante del dron dada una carga transportada y ejecuta la lógica de emparejamiento óptimo (despacho) entre pedidos en cola y drones disponibles.

### 2. Generadores Meteorológicos y de Eventos
*   **[clima.py](file:///../clima.py):** Modela las variaciones estocásticas de las condiciones del tiempo atmosférico. Contiene perfiles con probabilidades asociadas y un factor de reducción de la velocidad para reflejar el impacto de lluvias o ráfagas de viento en el avance del dron.
*   **[generador.py](file:///../generador.py):** Genera la agenda inicial de eventos para toda la simulación. Utiliza una distribución de Poisson para modelar los consumos intrahospitalarios de productos médicos y la aparición aleatoria de donaciones de órganos urgentes.

### 3. Motor del Simulador y Control
*   **[flota.py](file:///../flota.py):** Orquesta el ciclo de vida y estado de la flota de drones. Maneja las transiciones de estado de los drones (`available` -> `mission` -> `returning` -> `charging`) y actualiza los contadores de estadísticas operativas globales.
*   **[simulacion.py](file:///../simulacion.py):** Contiene el bucle central de simulación de eventos discretos. Consume los eventos ordenados por tiempo y prioridad, delega las decisiones operativas al controlador de flota y registra las métricas acumuladas.
*   **[telemetria.py](file:///../telemetria.py):** Registra cada segmento de vuelo de forma secuencial y exporta un archivo estructurado `telemetria_vuelos.json`.

### 4. Herramientas de Análisis y Visualización
*   **[main.py](file:///../main.py):** Configura y ejecuta una simulación única para depuración rápida de código.
*   **[montecarlo.py](file:///../montecarlo.py):** Automatiza la ejecución en bucle de múltiples simulaciones estocásticas con semillas aleatorias para evaluar el comportamiento bajo distintos factores de estrés en la demanda de la red.
*   **[graficas.py](file:///../graficas.py):** Procesa los archivos CSV resultantes de Monte Carlo y genera reportes gráficos de nivel de servicio.
*   **[diagnostico.py](file:///../diagnostico.py):** Evalúa la cobertura puramente física y estática de las bases de drones basándose en el alcance energético máximo.
*   **[generar_mapa.py](file:///../generar_mapa.py):** Crea una vista de folium interactiva offline del grafo de hospitales y bases.
*   **[radar_app.py](file:///../radar_app.py):** Interfaz gráfica interactiva de reproducción temporal en la cual Streamlit consume la telemetría generada y proyecta en tiempo real el comportamiento espacial en un mapa dinámico 3D.

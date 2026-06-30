# UAV Medical Network Optimization

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-green)](pyproject.toml)

Este proyecto implementa un **Simulador de Eventos Discretos (DES)** diseñado para evaluar la viabilidad y optimizar el rendimiento de una red de vehículos aéreos no tripulados (drones) destinados a la logística médica en la Comunidad de Madrid. El sistema modela de forma realista la geografía de la red hospitalaria madrileña, las restricciones operativas físicas de los drones, y el impacto de factores externos como la meteorología adversa.

---

## 🎯 Objetivo del Proyecto

El objetivo principal de esta plataforma es analizar cuantitativamente si una flota de drones de transporte puede optimizar la distribución de inventario clínico crítico y acelerar el traslado de órganos vitales entre centros médicos. Para ello, el simulador somete al sistema a diversas condiciones operativas extremas mediante experimentos estocásticos para dimensionar adecuadamente la cantidad de drones y bases necesarias.

---

## 🚀 Características Principales

*   **Motor DES Estocástico:** Simulación paso a paso (minuto a minuto) basada en colas de eventos prioritarios.
*   **Red de la Comunidad de Madrid:** Modelado real de 36 hospitales públicos de Madrid y 4 bases de drones estratégicamente distribuidas.
*   **Modelado Físico de Drones:** Autonomía de batería no lineal ajustada dinámicamente según la carga transportada ($Payload$), tiempos de recarga realistas y velocidad de crucero.
*   **Gestión de Inventario (s, Q):** Implementación de política clásica de inventarios en cada hospital. Al caer por debajo del umbral de seguridad ($s$), se activa de forma automática una solicitud de reposición de cantidad ($Q$) hacia la base más cercana.
*   **Transporte Crítico de Órganos:** Asignación dedicada de drones hospitalarios con prioridad absoluta y ventanas de isquemia estrictas (tiempos límite antes del daño del tejido).
*   **Meteorología Estocástica:** Estados climáticos simulados mediante cadenas de Markov/perfiles probabilísticos que penalizan la velocidad de vuelo del dron (lluvia, viento y calor extremo).
*   **Experimentos Monte Carlo:** Ejecución de simulaciones repetidas bajo múltiples niveles de demanda para generar estadísticas fiables y curvas de confianza.
*   **Radar Interactivo (FlyRadar):** Interfaz visual construida en Streamlit y PyDeck para monitorizar en tiempo real el vuelo de los drones, la batería y el estado de la red.

---

## 💻 Instalación

### Requisitos Previos

*   Python 3.10 o superior instalado en el sistema.

### Instalación en Windows

1.  Clonar el repositorio:
    ```bash
    git clone https://github.com/jairosdc/UAV-Medical-Network-Optimization.git
    cd UAV-Medical-Network-Optimization
    ```
2.  Crear y activar el entorno virtual:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
3.  Instalar las dependencias necesarias:
    ```bash
    pip install -r requirements.txt
    ```

### Instalación en macOS / Linux

1.  Clonar el repositorio:
    ```bash
    git clone https://github.com/jairosdc/UAV-Medical-Network-Optimization.git
    cd UAV-Medical-Network-Optimization
    ```
2.  Crear y activar el entorno virtual:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  Instalar las dependencias necesarias:
    ```bash
    pip install -r requirements.txt
    ```

---

## ⚡ Ejecución Rápida

El proyecto consta de varios puntos de entrada según la tarea a realizar:

### 1. Ejecutar una simulación individual estándar
Ejecuta la configuración del escenario predeterminado en `scripts/run_simulation.py` y muestra un resumen estadístico detallado por consola.
```bash
python scripts/run_simulation.py
```

### 2. Ejecutar simulación estadística Monte Carlo
Lanza múltiples ejecuciones estocásticas paralelas para realizar un análisis de estrés en el dimensionamiento de la flota.
```bash
python scripts/run_montecarlo.py --simulaciones 20 --salida datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv
```

### 3. Generar gráficas de presentación
Lee los resultados del archivo CSV acumulativo de Monte Carlo y genera las gráficas de rendimiento y nivel de servicio de la red.
```bash
python scripts/generar_graficas.py --input datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv --output graficas_presentacion
```

### 4. Lanzar la aplicación interactiva de visualización (Radar)
Lanza el panel visual interactivo para visualizar los vuelos de drones en tiempo real sobre el mapa de Madrid.
```bash
streamlit run apps/radar_app.py
```

### 5. Diagnóstico de cobertura base-hospital
Analiza la viabilidad geométrica de las rutas base-hospital-base basándose únicamente en la capacidad energética del dron con carga máxima.
```bash
python scripts/diagnostico.py
```

### 6. Generar mapa estático interactivo del grafo de la red
Crea un archivo HTML interactivo con las ubicaciones de todos los hospitales, bases y las distancias del grafo.
```bash
python scripts/generar_mapa.py
```

### 7. Ejecutar tests unitarios
Lanza la suite de pruebas unitarias para validar las reglas de batería, despacho, red y motor.
```bash
python -m pytest
```

---

## 📁 Estructura del Proyecto

El repositorio está organizado de forma profesional para separar el núcleo lógico de los puntos de entrada ejecutables y las aplicaciones:

*   **`src/uav_medical_network/`**: Paquete Python que contiene el motor del simulador.
    *   `config.py`: Parámetros físicos del dron, límites meteorológicos, y coordenadas de hospitales y bases.
    *   `modelos.py`: Definiciones de datos (`Node`, `Drone`, `DeliveryCall`, `Producto`, `Inventario` y `GestorPrioridad`).
    *   `red.py`: Lógica geográfica, cálculo de distancias Haversine, perfiles de batería y algoritmo de despacho óptimo.
    *   `flota.py`: Controlador principal de asignación de misiones y actualización de estados del dron.
    *   `generador.py`: Generador estocástico de consumos hospitalarios y apariciones espontáneas de órganos.
    *   `clima.py`: Simulador estocástico de perfiles climáticos (normal, lluvioso, adverso) con afectación de velocidad.
    *   `simulacion.py`: Bucle DES central del motor que consume la cola de eventos y controla los escenarios.
    *   `telemetria.py`: Registro temporal de vuelos para su posterior renderizado en la app de visualización.
    *   `graficas.py`: Generador integrado de visualizaciones individuales rápidas.
*   **`apps/`**: Aplicaciones interactivas de frontend.
    *   `radar_app.py`: Panel Streamlit que contiene el visor interactivo 2D/3D (FlyRadar) para reproducir trayectorias.
*   **`scripts/`**: Puntos de entrada ejecutables desde terminal.
    *   `run_simulation.py`: Script para lanzar una simulación individual de prueba.
    *   `run_montecarlo.py`: Orquestador de simulaciones Monte Carlo para análisis estadísticos multivariable.
    *   `generar_graficas.py`: Procesa los CSV de Monte Carlo y genera las gráficas finales.
    *   `diagnostico.py`: Verifica la cobertura física estática de las bases de drones.
    *   `generar_mapa.py`: Exporta la red de Madrid a un mapa HTML interactivo offline en `Grafo/`.
*   **`docs/`**: Documentación detallada del proyecto (Arquitectura, Modelo Matemático y Resultados).
*   **`data/sample/`**: Ejemplos reducidos de datos de simulación para pruebas rápidas.
*   **`tests/`**: Suite de pruebas unitarias con pytest.
*   **`graficas_presentacion/`**: Carpeta donde se exportan los resultados gráficos del script de visualización.

---

## 📊 Escenarios Disponibles

El motor de simulación incluye configuraciones predefinidas de red para análisis comparativos:

1.  `normal`: Demanda habitual de inventario, tasa promedio de órganos, meteorología favorable y flota estándar.
2.  `alta_demanda`: Incremento de la tasa de fallos de stock en hospitales y mayor tasa de transplantes urgentes.
3.  `lluvia_alta_demanda`: Alta demanda de inventarios/órganos combinada con un perfil meteorológico lluvioso que ralentiza los tiempos de vuelo.
4.  `baja_demanda_clima_adverso`: Baja demanda generalizada, pero con meteorología adversa extrema y flota de drones reducida por base.
5.  `estres_extremo`: Demanda máxima simultánea de inventarios y órganos, clima adverso persistente y cantidad mínima de drones activos.
6.  `personalizado`: Permite configurar manualmente la cantidad de drones base y hospitalarios por cada nodo de la red.

---

## 📈 Métricas Principales de Rendimiento

El sistema registra múltiples indicadores clave de rendimiento (KPIs):

*   **Tasa de Servicio (%):** Proporción de pedidos totales de inventario entregados con éxito sobre los solicitados.
*   **Éxito Clínico (%):** Porcentaje de órganos transportados a tiempo, entregados antes del límite establecido por la ventana de isquemia.
*   **Órganos Fuera de Isquemia:** Cantidad de órganos cuya entrega tardó más de los minutos tolerables de isquemia clínica.
*   **P95 de Inventario (min):** Tiempo por debajo del cual se completan el 95% de las solicitudes de reabastecimiento sanitario.
*   **Longitud Máxima/Media de Cola:** Número de pedidos acumulados en cola esperando la disponibilidad de un dron adecuado.
*   **Utilización de Drones (%):** Fracción del tiempo total en que los drones han estado en vuelo operativo frente al tiempo inactivo o en carga.

---

## 🛰️ Radar Interactivo (FlyRadar)

La aplicación web integrada permite una reproducción visual interactiva de los vuelos:
```bash
streamlit run apps/radar_app.py
```
*   **Monitorización:** Visualiza hospitales, bases aéreas y las trayectorias dinámicas de los drones.
*   **Filtros de Misión:** Permite ver la naturaleza del vuelo (Misión de Órgano, Misión de Inventario, Regreso a Base).
*   **Telemetría en Vivo:** Muestra el porcentaje de batería estimado del dron en tiempo real y el estado meteorológico actual.
*   **Control del Tiempo:** Permite avanzar, retroceder y pausar el flujo del tiempo de simulación.

---

## ⚠️ Limitaciones del Modelo

Este software ha sido diseñado con fines estrictamente académicos e investigativos y cuenta con las siguientes simplificaciones:

*   **Cálculo Geográfico:** Las distancias se estiman mediante la fórmula de Haversine (línea recta sobre la superficie terrestre), sin modelar orografía, altitudes ni zonas urbanas de exclusión aérea.
*   **Meteorología:** El clima se simula de forma estocástica e instantánea para toda la región, sin considerar microclimas locales ni frentes meteorológicos móviles reales.
*   **Simplificación Aérea:** No se incluye simulación de colisiones, gestión del espacio aéreo (ATM), ni congestión tridimensional de trayectorias.
*   **Demanda Hospitalaria:** Los patrones de consumo y aparición de órganos son procesos de Poisson paramétricos ideales, no datos reales basados en historiales clínicos de los centros médicos.
*   **Operaciones Médicas:** La manipulación de carga, empaquetado térmico y tiempos de despegue/aterrizaje se asumen constantes o instantáneos en el simulador.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para ver el texto completo.

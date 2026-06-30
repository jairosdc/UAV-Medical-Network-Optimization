# Interpretación de Resultados y Métricas

Este documento proporciona una guía detallada para analizar e interpretar los reportes generados por la simulación estocástica y las pruebas Monte Carlo.

---

## 1. Guía de Métricas de Rendimiento

Para evaluar la eficiencia y fiabilidad de la red logística de drones, el simulador reporta los siguientes Indicadores Clave de Rendimiento (KPIs):

### Tasa de Servicio de Inventario ($TS$)
Mide la capacidad de reabastecimiento de insumos médicos estándar (sangre, sueros, etc.) en los hospitales antes de que sufran desabastecimiento.
$$TS = \left( \frac{\text{Pedidos de Inventario Completados}}{\text{Pedidos de Inventario Totales Generados}} \right) \cdot 100$$
*   **Interpretación:** Un valor inferior al $95\%$ indica insuficiencia de drones en las bases de reabastecimiento o una tasa de recarga lenta ante la demanda.

### Éxito Clínico de Transporte de Órganos ($EC$)
Es la métrica más crítica. Mide la proporción de misiones urgentes de órganos que alcanzaron el hospital de destino antes del límite impuesto por la isquemia del órgano.
$$EC = \left( \frac{\text{Órganos Entregados a Tiempo}}{\text{Órganos Totales Generados}} \right) \cdot 100$$
*   **Interpretación:** Cualquier valor inferior al $100\%$ representa un fallo grave en la red que requiere el rediseño del número de drones hospitalarios asignados a los centros médicos principales.

### Tiempos de Entrega (P95 y P99)
Representan los percentiles 95 y 99 de los tiempos transcurridos desde que se genera una alarma de stock hasta que la carga es depositada en el hospital.
*   **P95 de Inventario:** El 95% de los pedidos de inventario se resolvieron en un tiempo menor o igual a este valor.
*   **Umbral Clínico:** Para mantener la seguridad asistencial, se establece que el P95 de inventario debe ser menor a **300 minutos** (5 horas). Si el percentil excede este límite, la red se considera no viable bajo ese escenario.

### Tasa de Utilización de la Flota ($U$)
Representa la fracción de tiempo total en que la flota de drones está activa realizando tareas productivas.
$$U_{operativa} = \left( \frac{\text{Tiempo total de vuelo} + \text{Tiempo total de recarga}}{\text{Número de drones} \cdot \text{Duración de la simulación}} \right) \cdot 100$$
*   **Interpretación:** Si la utilización operativa supera el $70\%$, la flota se encuentra en un punto crítico con riesgo elevado de colapso ante cualquier fluctuación de demanda o episodio de clima severo.

---

## 2. Identificación de Cuellos de Botella y Rutas Críticas

Al analizar los resultados de Monte Carlo, preste especial atención a:

1.  **Longitud Máxima de Cola:** Un crecimiento constante en la longitud de la cola a lo largo del tiempo indica saturación.
2.  **Tiempo de Espera en Asignación:** Si los drones pasan la mayor parte del tiempo volando y los pedidos esperan decenas de minutos en cola antes de asignarse un dron, el factor limitante es el tamaño de la flota.
3.  **Rutas Críticas de Órganos:** Las misiones origen-destino de larga distancia (por ejemplo, desde hospitales periféricos hacia centros especializados en el centro de Madrid) son propensas a fallos de isquemia si coinciden con viento fuerte que reduzca la velocidad efectiva del dron.

---

## 3. Instrucciones para Regenerar Resultados

Los resultados definitivos del análisis de dimensionamiento se obtienen mediante la simulación Monte Carlo. Debido al carácter estocástico del generador, se recomiendan al menos 20 iteraciones por escenario para obtener promedios estables.

### Paso 1: Ejecutar la Simulación Monte Carlo
Lanza el experimento estadístico que simula 2 semanas operativas bajo cuatro niveles de estrés de demanda. El resultado se guardará en un archivo CSV consolidado.
```bash
python montecarlo.py --simulaciones 20 --salida datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv
```

### Paso 2: Generar las Gráficas y Tablas Comparativas
Una vez generado el CSV, el script de graficado procesará el fichero para renderizar las figuras PNG de presentación y extraer tablas formateadas con los promedios estadísticos por escenario.
```bash
python graficas.py --input datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv --output graficas_presentacion
```

Los outputs generados por estos scripts se almacenan en:
*   `datasets_montecarlo_dimensionamiento_1semana/tabla_montecarlo.csv` (Dataset crudo).
*   `graficas_presentacion/png/` (Figuras listas para insertar en reportes).
*   `graficas_presentacion/tablas/` (CSV formateados con promedios y desglose de rutas de órganos).
*   Un ejemplo de tamaño reducido se encuentra disponible en `data/sample/tabla_montecarlo_sample.csv` para pruebas locales rápidas de generación de gráficas.

# Modelo Matemático y Lógica del Simulador

Este documento detalla los modelos físicos, probabilísticos y algorítmicos implementados en el núcleo del simulador.

---

## 1. Distancia Geográfica (Fórmula de Haversine)

Para calcular la distancia en línea recta sobre la corteza terrestre entre dos coordenadas geográficas $(\phi_1, \lambda_1)$ y $(\phi_2, \lambda_2)$ se implementa la fórmula de Haversine:

$$d = 2 R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$

Donde:
*   $R = 6371.0\text{ km}$ (radio medio de la Tierra).
*   $\Delta\phi = \phi_2 - \phi_1$ (diferencia de latitudes en radianes).
*   $\Delta\lambda = \lambda_2 - \lambda_1$ (diferencia de longitudes en radianes).

---

## 2. Autonomía de Batería y Consumo Energético

La autonomía energética del dron decrece de forma lineal respecto al peso de la carga transportada ($Payload$).

### Autonomía Teórica ($D_{max}$)
$$D_{max}(w) = D_{vacío} - \left(\frac{22.0 \cdot w}{W_{max}}\right)\text{ km}$$

Donde:
*   $w$: Peso real de la carga útil transportada ($\text{kg}$).
*   $W_{max} = 4.7\text{ kg}$ (capacidad máxima de carga del dron).
*   $D_{vacío} = 94.0\text{ km}$ (autonomía máxima teórica del dron sin carga).
*   $22.0\text{ km}$ representa la penalización máxima de alcance al volar a plena carga.

### Consumo de Batería Porcentual ($C_{pct}$)
El consumo de batería en un trayecto de distancia $d$ con una carga $w$ se calcula como:
$$C_{pct}(w, d) = \left(\frac{d}{D_{max}(w)}\right) \cdot 100.0$$

### Batería Restante ($B_{final}$)
$$B_{final} = B_{inicial} - C_{pct}(w, d)$$
Para que un vuelo sea viable, se debe cumplir la condición de reserva de seguridad:
$$B_{final} \ge B_{seguridad} \quad (\text{donde } B_{seguridad} = 5\%)$$

---

## 3. Política de Inventario Hospitalario $(s, Q)$

Los insumos médicos en los hospitales se gestionan de forma individual mediante la política de revisión continua $(s, Q)$:

1.  **Revisión Continua:** Cada consumo intrahospitalario unitario resta 1 unidad al stock físico actual ($I_{físico}$).
2.  **Stock Total Estimado ($I_{estimado}$):**
    $$I_{estimado} = I_{físico} + I_{camino}$$
    Donde $I_{camino}$ es el inventario que ya ha sido solicitado pero está en tránsito a bordo de un dron de reabastecimiento.
3.  **Regla de Reorden:** Si el stock total estimado cae por debajo o igual al umbral crítico de reorden $s$:
    $$I_{estimado} \le s \implies \text{Generar pedido de reposición de cantidad } Q$$
    A su vez, se incrementa de forma instantánea $I_{camino} \leftarrow I_{camino} + Q$ para evitar pedidos duplicados mientras el dron realiza el trayecto.

---

## 4. Proceso Estocástico de Demanda

Las solicitudes de envío médico se modelan a través de procesos puntuales estocásticos independientes:

### Consumo de Inventario
Para cada hospital $h$ y producto sanitario $p$, el consumo sigue un proceso de Poisson homogéneo con tasa horaria efectiva $\lambda_{eff}$:
$$\lambda_{eff}(t) = \lambda_{base} \cdot f_{horario}(t) \cdot F_{demanda\_inv}$$
Donde:
*   $\lambda_{base}$: Tasa de eventos base por hora (definida por tipo de insumo).
*   $f_{horario}(t)$: Factor multiplicador según la franja horaria del día (refleja picos de actividad diurnos y valles nocturnos).
*   $F_{demanda\_inv}$: Multiplicador de estrés global de la simulación.

### Aparición de Órganos
La donación de órganos urgentes en la red sigue un proceso de Poisson con tasa de ocurrencia global $\mu_{eff}$:
$$\mu_{eff} = \mu_{base} \cdot F_{demanda\_org}$$

---

## 5. Priorización Clínica y Ventanas de Isquemia

Cada pedido generado posee un nivel de urgencia clínica con reglas asociadas:

| Prioridad | Tipo de Envío | Producto | Límite Temporal ($Deadline$) |
|---|---|---|---|
| **0** | Crítico (Órgano) | Corazón, Pulmón, Riñón, Páncreas | Ventana de Isquemia ($t_{isquemia}$) |
| **1** | Alta Prioridad | Sangre, Fármaco UCI | Sin límite estricto (minimizar colas) |
| **2** | Media Prioridad | Antibióticos, Plasma, Suero | Sin límite estricto |
| **3** | Baja Prioridad | Analgésicos, Material General | Sin límite estricto |

### Ventana de Isquemia Clínica (Misiones Prioridad 0)
El órgano debe ser entregado en el hospital destino antes de que expire el tiempo de isquemia fría tolerable para evitar necrosis:
$$t_{llegada} \le t_{aparición} + t_{isquemia} \implies \text{Éxito clínico}$$
Si $t_{llegada} > t_{aparición} + t_{isquemia}$, el envío se marca como **fuera de isquemia (fracaso clínico)**.

---

## 6. Algoritmo de Despacho y Asignación de Drones

Cuando se procesa un pedido pendiente, el despachador evalúa la flota de drones para encontrar candidatos que cumplan con la reserva de seguridad de batería.

### Drones de Base (Pedidos de Inventario, Prioridad 1, 2, 3)
*   **Rol:** El dron debe ser de tipo `role="base"`.
*   **Ruta obligatoria:** Base $\to$ Hospital Destino $\to$ Base.
*   **Consumo total de batería:**
    $$Consumo_{total} = C_{pct}(Payload, d_{base\_hosp}) + C_{pct}(0.0, d_{hosp\_base})$$

### Drones de Hospital (Pedidos de Órgano, Prioridad 0)
*   **Rol:** El dron debe ser de tipo `role="hospital"`.
*   **Ruta obligatoria:** Posición actual del dron $\to$ Hospital Origen del órgano $\to$ Hospital Destino del órgano. El dron se estaciona en el hospital destino y no vuelve de forma obligatoria a una base.
*   **Consumo total de batería:**
    $$Consumo_{total} = C_{pct}(0.0, d_{dron\_origen}) + C_{pct}(Payload, d_{origen\_destino})$$

### Criterio de Selección (Ordenamiento de Candidatos)
Si existen múltiples drones viables (batería restante final $\ge 5\%$), se selecciona al mejor ordenando la lista de candidatos según la prioridad del pedido:

1.  **Prioridad 0 (Órgano):** Minimizar el tiempo de llegada al origen ($t_{llegada\_origen}$), después minimizar la distancia al origen ($d_{dron\_origen}$) y finalmente maximizar la batería de reserva.
2.  **Prioridad 1 (Crítico):** Minimizar la distancia del dron al origen del pedido.
3.  **Prioridad 2 (Urgente):** Minimizar la distancia total del vuelo.
4.  **Prioridad 3 (Rutinario):** Maximizar la batería de reserva final del dron tras completar la misión.

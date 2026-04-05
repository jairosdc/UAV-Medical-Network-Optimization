"""
generador_pedidos.py
====================
Genera pedidos hospitalarios siguiendo un Proceso de Poisson No Homogéneo (NHPP).

IDEA PRINCIPAL (explicación simple):
-------------------------------------
En un proceso de Poisson, cada tipo de producto tiene una tasa λ (lambda)
que nos dice "cuántos pedidos de este producto esperamos por hora".

El proyecto exige que esa tasa cambie según la hora del día:
- Por la mañana (9-14h) hay mucha actividad → λ alto
- De madrugada (0-6h) hay poca actividad → λ bajo

Además, TÚ quieres que cada producto tenga su propia λ,
porque la sangre no se pide con la misma frecuencia que los analgésicos.
Eso es exactamente lo que hace este archivo.

CÓMO FUNCIONA EL ALGORITMO (método de adelgazamiento / "thinning"):
--------------------------------------------------------------------
1. Calculamos la tasa máxima de todos los productos juntos → λ_total_max
2. Cada minuto lanzamos una "moneda" con probabilidad λ_total_max → ¿llega algo?
3. Si llega algo, elegimos qué producto es (proporcional a sus tasas)
4. Aceptamos o rechazamos según la tasa real de ese momento del día
Este método es matemáticamente equivalente a simular un NHPP puro.

CÓMO USARLO DESDE main.py:
---------------------------
    from generador_pedidos import GeneradorPedidos

    gen = GeneradorPedidos(hospitales=red.listar_hospitales(), semilla=42)

    for minuto in range(duracion_simulacion):
        pedido = gen.generar_pedido(minuto_actual=minuto)
        if pedido is not None:
            flota.asignar_pedido(pedido, minuto)
"""

import random
import numpy as np
from collections import defaultdict
from models.models import DeliveryCall


# =============================================================================
# TASAS λ POR TIPO DE PRODUCTO (pedidos esperados POR HORA)
# =============================================================================
# Aquí defines cuántos pedidos de cada producto esperas por hora.
# Ajusta estos valores cuando tengáis datos reales hospitalarios.
#
# Formato: "nombre_producto": tasa_base_por_hora
# La tasa_base es para horario normal (se multiplica por el factor horario).

TASAS_PRODUCTOS = {
    # Críticos (prioridad 1) — poco frecuentes pero urgentes
    "organo":      0.05,   
    "sangre":      0.30,   
    "farmaco_uci": 0.20,   

    # Urgentes (prioridad 2)
    "antibiotico": 0.80,   
    "suero":       0.60,
    "plasma":      0.25,

    # Rutinarios (prioridad 3) — los más frecuentes
    "analgesico":          1.20,   
    "material_sanitario":  1.00,
    "medicamento_general": 0.90,
}

# Prioridad de cada producto (1=alta, 2=media, 3=baja)
PRIORIDAD_PRODUCTO = {
    "organo": 1, "sangre": 1, "farmaco_uci": 1,
    "antibiotico": 2, "suero": 2, "plasma": 2,
    "analgesico": 3, "material_sanitario": 3, "medicamento_general": 3,
}

# Peso en kg (mínimo, máximo) de cada producto
PESO_PRODUCTO = {
    "organo":              (0.5, 2.0),
    "sangre":              (0.5, 3.0),
    "farmaco_uci":         (0.2, 1.0),
    "antibiotico":         (0.5, 1.5),
    "suero":               (0.5, 2.0),
    "plasma":              (0.3, 1.5),
    "analgesico":          (0.5, 2.0),
    "material_sanitario":  (1.0, 4.5),
    "medicamento_general": (0.5, 3.0),
}


# =============================================================================
# FACTOR HORARIO — cómo cambia la demanda a lo largo del día
# =============================================================================
# Este es el corazón del NHPP: la tasa no es constante, varía con la hora.
# El factor multiplica la tasa base de cada producto.
#
# Ejemplo: sangre tiene tasa_base = 0.30 pedidos/hora
#   - A las 10h (factor = 1.5) → λ_real = 0.30 × 1.5 = 0.45 pedidos/hora
#   - A las 3h  (factor = 0.4) → λ_real = 0.30 × 0.4 = 0.12 pedidos/hora

FACTORES_HORARIOS = [
    # (hora_inicio, hora_fin, factor_multiplicador)
    (0,  6,  0.48),   # madrugada: poca actividad rutinaria
    (6,  9,  1.0),   # mañana temprana: empieza la actividad
    (9,  14, 1.6),   # mañana pico: máxima actividad hospitalaria
    (14, 16, 1.13),   # mediodía: actividad normal
    (16, 20, 1.3),   # tarde: segunda ola de actividad
    (20, 24, 0.6),   # noche: caída gradual
]

# Función auxiliar para obtener el factor horario según el minuto del día
def _factor_horario(minuto_del_dia: int) -> float:
    hora = (minuto_del_dia % 1440) / 60.0
    for hora_inicio, hora_fin, factor in FACTORES_HORARIOS:
        if hora_inicio <= hora < hora_fin:
            return factor
    return 1.0  # valor por defecto (no debería ocurrir)

# Función para calcular la tasa real por minuto de cada producto
def _tasa_por_minuto(producto: str, minuto_del_dia: int, factor_estres: float) -> float:
    
    tasa_base = TASAS_PRODUCTOS[producto]
    factor_hora = _factor_horario(minuto_del_dia)
    return (tasa_base * factor_hora * factor_estres) / 60.0


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class GeneradorPedidos:

    def __init__(self, hospitales: list, semilla: int = None, factor_estres: float = 1.0):
        self.hospitales = hospitales
        self.factor_estres = factor_estres
        self._siguiente_id = 1
        
        # Diccionario para almacenar los pedidos mapeados por minuto de llegada
        self.agenda_pedidos = defaultdict(list)

        if semilla is not None:
            np.random.seed(semilla)
            random.seed(semilla)

        self._pregenerar_escenario_diario()

    def _pregenerar_escenario_diario(self):
        """
        Calcula la topología temporal exacta de todos los pedidos del día basándose en
        la distribución uniforme condicionada a la métrica del proceso de Poisson.
        """
        for producto, tasa_base in TASAS_PRODUCTOS.items():
            for hora_inicio, hora_fin, factor in FACTORES_HORARIOS:
                
                # 1. Definir los parámetros del intervalo
                duracion_horas = hora_fin - hora_inicio
                minuto_inicio_intervalo = hora_inicio * 60
                minuto_fin_intervalo = hora_fin * 60
                
                # Tasa escalar en este tramo (pedidos esperados en el tramo completo)
                tasa_tramo = tasa_base * factor * self.factor_estres * duracion_horas
                
                # 2. Generar N ~ Poisson(λ * Δt)
                numero_llegadas = np.random.poisson(tasa_tramo)
                
                if numero_llegadas == 0:
                    continue
                
                # 3. Generar instantes exactos T ~ U(t_a, t_b) condicionados a N
                minutos_llegada = np.random.uniform(
                    low=minuto_inicio_intervalo, 
                    high=minuto_fin_intervalo, 
                    size=numero_llegadas
                )
                
                # 4. Ensamblar los objetos DeliveryCall en los minutos discretizados
                for minuto_exacto in minutos_llegada:
                    minuto_discreto = int(np.floor(minuto_exacto))
                    pedido = self._construir_objeto_pedido(producto, minuto_discreto)
                    self.agenda_pedidos[minuto_discreto].append(pedido)

    def _construir_objeto_pedido(self, producto: str, minuto: int) -> DeliveryCall:
        """Instancia la estructura de datos del pedido con parámetros físicos aleatorios."""
        origen, destino = random.sample(self.hospitales, 2)
        peso_min, peso_max = PESO_PRODUCTO[producto]
        carga_kg = round(random.uniform(peso_min, peso_max), 2)

        pedido = DeliveryCall(
            call_id=self._siguiente_id,
            timestamp_min=minuto,
            origin_hospital=origen,
            destination_hospital=destino,
            payload_kg=carga_kg,
            priority=PRIORIDAD_PRODUCTO[producto],
        )
        self._siguiente_id += 1
        return pedido

    def generar_pedido(self, minuto_actual: int) -> "DeliveryCall | None":
        """
        Consulta si existe un evento programado para el integrador temporal actual.
        Al estar precalculado, la complejidad de resolución es O(1).
        
        Args:
            minuto_actual: minuto de simulación evaluado.
        """
        lista_pedidos_minuto = self.agenda_pedidos.get(minuto_actual)
        
        if not lista_pedidos_minuto:
            return None
            
        # Si por colisión estocástica hay más de un pedido en el mismo minuto discreto,
        # retornamos uno y desplazamos el restante al siguiente diferencial de tiempo.
        pedido_a_emitir = lista_pedidos_minuto.pop(0)
        
        if lista_pedidos_minuto:
            self.agenda_pedidos[minuto_actual + 1].extend(lista_pedidos_minuto)
            
        return pedido_a_emitir
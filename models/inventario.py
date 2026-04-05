import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple

# =============================================================================
# CONFIGURACIÓN MAESTRA DE INVENTARIO Y POLÍTICAS (s, Q)
# =============================================================================
# Valores ajustados para simular un hospital general estándar.
# Las tasas (lambda_int) representan el consumo interno esperado en unidades/hora.

CONFIG_HOSPITALES = {
    # Prioridad 1 (Críticos) - Stock bajo, consumo lento, reposición rápida
    "sangre":              {"stock_inicial": 50,   "s": 15,  "Q": 30,  "lambda_int": 0.5},
    "farmaco_uci":         {"stock_inicial": 30,   "s": 10,  "Q": 20,  "lambda_int": 0.2},
    
    # Prioridad 2 (Urgentes)
    "antibiotico":         {"stock_inicial": 300,  "s": 80,  "Q": 150, "lambda_int": 3.0},
    "suero":               {"stock_inicial": 500,  "s": 150, "Q": 250, "lambda_int": 5.0},
    "plasma":              {"stock_inicial": 80,   "s": 20,  "Q": 40,  "lambda_int": 0.8},
    
    # Prioridad 3 (Rutinarios) - Alto volumen de rotación
    "analgesico":          {"stock_inicial": 800,  "s": 200, "Q": 400, "lambda_int": 8.0},
    "material_sanitario":  {"stock_inicial": 1000, "s": 300, "Q": 500, "lambda_int": 10.0},
    "medicamento_general": {"stock_inicial": 600,  "s": 150, "Q": 300, "lambda_int": 6.0},
}

# Los almacenes (bases) deben poseer una magnitud escalar significativamente mayor
# para soportar la absorción de los sumideros (hospitales). Factor de escala estático: x50.
FACTOR_ESCALA_BASE = 50


@dataclass
class EstadoProducto:
    stock_fisico: int
    s: int
    Q: int
    lambda_int: float
    stock_en_transito: int = 0
    
    @property
    def posicion_inventario(self) -> int:
        """IP(t) = I(t) + T(t)"""
        return self.stock_fisico + self.stock_en_transito


class InventarioNodo:
    """Clase base topológica para gestionar los vectores de estado de un nodo V."""
    def __init__(self, nombre: str, es_base: bool = False):
        self.nombre = nombre
        self.es_base = es_base
        self.productos: Dict[str, EstadoProducto] = {}
        self._inicializar_matriz_estado()

    def _inicializar_matriz_estado(self):
        multiplicador = FACTOR_ESCALA_BASE if self.es_base else 1
        
        for prod, conf in CONFIG_HOSPITALES.items():
            # Desacoplamiento de memoria: cada nodo instancia su propio objeto de estado
            self.productos[prod] = EstadoProducto(
                stock_fisico=conf["stock_inicial"] * multiplicador,
                s=conf["s"] * multiplicador if not self.es_base else 0, # Las bases no hacen pedidos
                Q=conf["Q"],
                lambda_int=conf["lambda_int"] if not self.es_base else 0.0 # Las bases no consumen internamente
            )

    def procesar_consumo_horario(self) -> List[Tuple[str, int]]:
        """
        Calcula la perturbación estocástica N ~ Poisson(λ) sobre el inventario.
        Aplica exclusivamente a subgrafos hospitalarios.
        
        Retorna:
            Lista de tuplas (nombre_producto, cantidad_a_pedir_Q) que violan la restricción (s).
        """
        if self.es_base:
            return [] # Invariancia topológica: las bases solo distribuyen, no consumen.

        pedidos_emitidos = []
        
        for nombre_prod, estado in self.productos.items():
            consumo_real = np.random.poisson(estado.lambda_int)
            
            # Operador de frontera: el stock no puede pertenecer a Z- (evitar negativos físicos)
            estado.stock_fisico = max(0, estado.stock_fisico - consumo_real)
            
            # Evaluación del espacio de soluciones de la política (s, Q)
            if estado.posicion_inventario <= estado.s:
                pedidos_emitidos.append((nombre_prod, estado.Q))
                
        return pedidos_emitidos

    def registrar_salida_mercancia(self, producto: str, cantidad: int):
        """Reduce el stock físico de un nodo emisor (Base)."""
        if producto in self.productos:
            estado = self.productos[producto]
            estado.stock_fisico = max(0, estado.stock_fisico - cantidad)

    def registrar_pedido_en_transito(self, producto: str, cantidad: int):
        """Aumenta el T(t) del nodo receptor para estabilizar el IP(t)."""
        if producto in self.productos:
            self.productos[producto].stock_en_transito += cantidad

    def recepcionar_mercancia(self, producto: str, cantidad: int):
        """Transformación de estado: El dron aterriza. Transito -> Físico."""
        if producto in self.productos:
            estado = self.productos[producto]
            estado.stock_fisico += cantidad
            estado.stock_en_transito = max(0, estado.stock_en_transito - cantidad)
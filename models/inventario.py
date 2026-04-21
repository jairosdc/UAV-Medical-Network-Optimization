from dataclasses import dataclass

from typing import Dict, List

# Diccionario de estado inicial
# Stock inicial = aprox 1-2 dias de consumo (realista para un hospital)
# Tasa media consumo/hospital: sangre ~7/dia, antibiotico ~19/dia, analgesico ~29/dia...
# Umbral s = ~85% del stock inicial para activar reposicion antes de agotar
CONFIG_INVENTARIO = {
    "sangre":              {"inicial": 20,   "s": 8,   "Q": 15},
    "farmaco_uci":         {"inicial": 12,   "s": 5,   "Q": 10},
    "antibiotico":         {"inicial": 60,   "s": 25,  "Q": 40},
    "suero":               {"inicial": 80,   "s": 30,  "Q": 50},
    "plasma":              {"inicial": 25,   "s": 10,  "Q": 15},
    "analgesico":          {"inicial": 100,  "s": 40,  "Q": 60},
    "material_sanitario":  {"inicial": 150,  "s": 60,  "Q": 80},
    "medicamento_general": {"inicial": 90,   "s": 35,  "Q": 55},
}

# Constante escalar para el inventario inicial de los almacenes
FACTOR_ESCALA_ALMACEN = 50

@dataclass
class Producto:
    stock_fisico: int # stock de un producto en el instante t
    umbral_s: int 
    cantidad_a_pedir_Q: int
    stock_en_camino: int = 0
    
    @property
    def stock_total_estimado(self) -> int:

        # Suma el stock en la estantería más el stock que está en el aire para no hacer dobles reposiciones.
        return self.stock_fisico + self.stock_en_camino


class Inventario:
    
    def __init__(self, es_almacen_central: bool = False):
        # Es almacen: True o False
        self.es_almacen = es_almacen_central
        # Inicializamos diccionario
        self.productos: Dict[str, Producto] = {}
        self._inicializar_stocks()

    def _inicializar_stocks(self):
        
        multiplicador = FACTOR_ESCALA_ALMACEN if self.es_almacen else 1
        
        # Iteramos sobre cada producto y sus parámetros en el diccionario global.
        for nombre, datos in CONFIG_INVENTARIO.items():
            
            # Instanciamos un nuevo objeto 'Producto' y lo guardamos en el diccionario del nodo.
            self.productos[nombre] = Producto(
                stock_fisico = datos["inicial"] * multiplicador,
                # Si es almacen quitamos el umbral para que no haga reposición sobre almacenes    
                umbral_s = 0 if self.es_almacen else datos["s"],
                # Asignamos la cantidad de lote de reposición estipulada.
                cantidad_a_pedir_Q = datos["Q"]
            )

    def registrar_consumo(self, nombre_producto: str, cantidad_consumida: int) -> int:
        
        if self.es_almacen or nombre_producto not in self.productos:
            return 0  # No se hace nada, retorna 0 pedidos.
        prod = self.productos[nombre_producto]
        # Evitamos que haya stock negativo
        prod.stock_fisico = max(0, prod.stock_fisico - cantidad_consumida)
        
        # Evaluamos de forma continua el stock
        if prod.stock_total_estimado <= prod.umbral_s:
            prod.stock_en_camino += prod.cantidad_a_pedir_Q
            return prod.cantidad_a_pedir_Q
        return 0

    def enviar_dron(self, nombre_producto: str, cantidad: int):
        if nombre_producto in self.productos:
            prod = self.productos[nombre_producto]
            prod.stock_fisico = max(0, prod.stock_fisico - cantidad)

    def recibir_dron(self, nombre_producto: str, cantidad: int):
        
        if nombre_producto in self.productos:
            prod = self.productos[nombre_producto]
            prod.stock_fisico += cantidad
            prod.stock_en_camino = max(0, prod.stock_en_camino - cantidad)
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Productos que SI pertenecen al inventario
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Productos que NO deben entrar nunca en inventario
# ---------------------------------------------------------------------------
# Los órganos son eventos críticos interhospitalarios.
# No tienen stock inicial, ni umbral s, ni cantidad Q.
# Si aparecen aquí por error, el programa debe avisar claramente.

ORGANOS_NO_INVENTARIABLES = {
    "corazon",
    "pulmon",
    "rinon",
    "pancreas",
    "higado",
}


# Los almacenes centrales tienen mucho más stock que los hospitales.
FACTOR_ESCALA_ALMACEN = 50


@dataclass
class Producto:
    stock_fisico: int
    umbral_s: int
    cantidad_a_pedir_Q: int
    stock_en_camino: int = 0

    @property
    def stock_total_estimado(self):
        return self.stock_fisico + self.stock_en_camino


class Inventario:
    """
    Inventario de un hospital o de un almacén central.

    En hospitales:
    - se consume stock,
    - se activa reposición al caer bajo el umbral s.

    En almacenes:
    - no se activa reposición,
    - solo se descuenta stock cuando sale un dron.

    Importante:
    - Los órganos NO pertenecen al inventario.
    - Los órganos deben gestionarse como pedidos especiales hospital-hospital.
    """

    def __init__(self, es_almacen_central: bool = False):
        self.es_almacen = es_almacen_central
        self.productos = {}

        self._inicializar_stocks()

    def _inicializar_stocks(self):
        multiplicador = FACTOR_ESCALA_ALMACEN if self.es_almacen else 1

        for nombre, datos in CONFIG_INVENTARIO.items():
            self.productos[nombre] = Producto(
                stock_fisico=datos["inicial"] * multiplicador,
                umbral_s=0 if self.es_almacen else datos["s"],
                cantidad_a_pedir_Q=datos["Q"]
            )

    def _validar_no_es_organo(self, nombre_producto: str):
        """
        Evita que un órgano sea tratado como inventario.

        Si esto salta, significa que en algún punto del código se está intentando:
        - consumir un órgano,
        - descontar un órgano de un almacén,
        - recibir un órgano como stock hospitalario.

        Eso sería incorrecto en este modelo.
        """
        if nombre_producto in ORGANOS_NO_INVENTARIABLES:
            raise ValueError(
                f"ERROR DE MODELO: '{nombre_producto}' es un órgano y no debe "
                f"gestionarse como inventario. Debe tratarse como un pedido "
                f"especial interhospitalario."
            )

    def registrar_consumo(self, nombre_producto: str, cantidad_consumida: int):
        """
        Registra consumo interno de un producto hospitalario.

        Solo aplica a productos inventariables.
        Los órganos no pueden consumirse desde inventario.
        """

        self._validar_no_es_organo(nombre_producto)

        # Los almacenes no tienen consumo.
        if self.es_almacen:
            return 0

        if nombre_producto not in self.productos:
            return 0

        producto = self.productos[nombre_producto]

        producto.stock_fisico = max(
            0,
            producto.stock_fisico - cantidad_consumida
        )

        if producto.stock_total_estimado <= producto.umbral_s:
            producto.stock_en_camino += producto.cantidad_a_pedir_Q
            return producto.cantidad_a_pedir_Q

        return 0

    def enviar_dron(self, nombre_producto: str, cantidad: int):
        """
        Descuenta stock cuando un dron sale con un producto.

        Solo aplica a productos inventariables.
        Los órganos no pueden salir desde inventario.

        Devuelve:
        - True si el producto existía y se pudo descontar.
        - False si el producto no existe.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto not in self.productos:
            return False

        producto = self.productos[nombre_producto]
        producto.stock_fisico = max(0, producto.stock_fisico - cantidad)

        return True

    def recibir_dron(self, nombre_producto: str, cantidad: int):
        """
        Aumenta stock cuando llega un dron con reposición.

        Solo aplica a productos inventariables.
        Los órganos no pueden recibirse como stock.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto not in self.productos:
            return False

        producto = self.productos[nombre_producto]

        producto.stock_fisico += cantidad
        producto.stock_en_camino = max(
            0,
            producto.stock_en_camino - cantidad
        )

        return True
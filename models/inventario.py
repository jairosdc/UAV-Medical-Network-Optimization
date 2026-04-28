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

    Además:
    - Se registra si un producto ha llegado a stock cero.
    - Ese indicador permite saber si una reposición llegó tarde.
    """

    def __init__(self, es_almacen_central: bool = False):
        self.es_almacen = es_almacen_central
        self.productos = {}

        # stockout_activo[producto] = True significa:
        # "este producto llegó a cero antes de recibir reposición".
        self.stockout_activo = {}

        self._inicializar_stocks()

    def _inicializar_stocks(self):
        multiplicador = FACTOR_ESCALA_ALMACEN if self.es_almacen else 1

        for nombre, datos in CONFIG_INVENTARIO.items():
            self.productos[nombre] = Producto(
                stock_fisico=datos["inicial"] * multiplicador,
                umbral_s=0 if self.es_almacen else datos["s"],
                cantidad_a_pedir_Q=datos["Q"],
            )

            self.stockout_activo[nombre] = False

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

        Devuelve:
        - 0 si no hay que reponer.
        - Q si el producto cae bajo el umbral s y se debe generar reposición.

        Si el stock físico llega a cero, se activa stockout_activo.
        """

        self._validar_no_es_organo(nombre_producto)

        # Los almacenes centrales no consumen productos.
        if self.es_almacen:
            return 0

        if nombre_producto not in self.productos:
            return 0

        producto = self.productos[nombre_producto]

        producto.stock_fisico = max(
            0,
            producto.stock_fisico - cantidad_consumida
        )

        # Si el producto llega a cero, el hospital ha sufrido stockout.
        if producto.stock_fisico == 0:
            self.stockout_activo[nombre_producto] = True

        # Política (s, Q):
        # si el stock total estimado cae bajo el umbral, se lanza reposición.
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

        producto.stock_fisico = max(
            0,
            producto.stock_fisico - cantidad
        )

        # También puede haber stockout en almacén si se agota.
        # En principio no debería pasar por FACTOR_ESCALA_ALMACEN,
        # pero lo registramos por coherencia.
        if producto.stock_fisico == 0:
            self.stockout_activo[nombre_producto] = True

        return True

    def recibir_dron(self, nombre_producto: str, cantidad: int):
        """
        Aumenta stock cuando llega un dron con reposición.

        Solo aplica a productos inventariables.
        Los órganos no pueden recibirse como stock.

        Devuelve:
        - True si el producto existía y se recibió.
        - False si el producto no existe.
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

        # Una vez recibida la reposición, se limpia el stockout.
        self.limpiar_stockout(nombre_producto)

        return True

    def hay_stockout_activo(self, nombre_producto: str) -> bool:
        """
        Devuelve True si ese producto ha llegado a cero antes de recibir reposición.

        Esto sirve para decidir si un pedido de inventario llegó tarde.
        """

        self._validar_no_es_organo(nombre_producto)

        return self.stockout_activo.get(nombre_producto, False)

    def limpiar_stockout(self, nombre_producto: str):
        """
        Limpia el indicador de stockout después de recibir reposición.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto in self.stockout_activo:
            self.stockout_activo[nombre_producto] = False

    def obtener_stock_fisico(self, nombre_producto: str) -> int:
        """
        Devuelve el stock físico actual de un producto.

        Si el producto no existe, devuelve 0.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto not in self.productos:
            return 0

        return self.productos[nombre_producto].stock_fisico

    def obtener_stock_en_camino(self, nombre_producto: str) -> int:
        """
        Devuelve el stock actualmente en camino de un producto.

        Si el producto no existe, devuelve 0.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto not in self.productos:
            return 0

        return self.productos[nombre_producto].stock_en_camino

    def obtener_stock_total_estimado(self, nombre_producto: str) -> int:
        """
        Devuelve stock físico + stock en camino.

        Si el producto no existe, devuelve 0.
        """

        self._validar_no_es_organo(nombre_producto)

        if nombre_producto not in self.productos:
            return 0

        return self.productos[nombre_producto].stock_total_estimado
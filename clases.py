import random
import heapq
import numpy as np

class Dron:
    def __init__(self, id_dron, nodo_origen, bateria_maxima=100.0, velocidad_media=90, capacidad_carga=4.7):
        """
        Constructor de la clase Dron basándose en las necesidades operativas (Wingcopter 198).
        """
        self.id = id_dron
        self.posicion_actual = nodo_origen
        self.bateria_maxima = bateria_maxima
        self.bateria_actual = bateria_maxima
        self.velocidad_media = velocidad_media
        self.capacidad_carga = capacidad_carga
        self.estado_operativo = "disponible"

    def calcular_tiempo_mision(self, distancia, factor_meteorologico):
        # Establecemos el tiempo por misión
        # El clima podría reducir la velocidad real aquí más adelante
        velocidad_real = self.velocidad_media 
        tiempo = distancia / velocidad_real
        return tiempo
    
    def autonomia(self, carga):
     
        autonomia_total = 94 - (22 * carga / 4.7)
        return autonomia_total

    def estimar_consumo(self, distancia, carga, factor_meteorologico=1.0):
        # Aplicamos la parte de consumo de tu Fórmula 3: (100 * d * k_met) / A(C)
        bateria_consumida = (100 * distancia * factor_meteorologico) / self.autonomia(carga)
        return bateria_consumida

    def asignar_mision(self, destino, distancia, carga, factor_meteorologico=1.0, parametro_seguridad=10):
        # Calculamos cuánto va a gastar el viaje
        consumo = self.estimar_consumo(distancia, carga, factor_meteorologico)
        
        if self.bateria_actual >= (consumo + parametro_seguridad):
            self.estado_operativo = "en_mision"
            # Restamos el consumo calculado a la batería actual
            self.bateria_actual -= consumo 
            self.posicion_actual = destino
            return True
        else:
            # No hay batería suficiente, necesita recargar
            return False

    def recargar_bateria(self):
        # Recarga instantanea, debemos establecer un cooldown
        self.estado_operativo = "recargando"
        self.bateria_actual = self.bateria_maxima
        self.estado_operativo = "disponible"

    def __str__(self):
        return f"Dron {self.id} | Posición: {self.posicion_actual} | Batería: {self.bateria_actual:.2f}% | Estado: {self.estado_operativo}"  

# ================================================================
#  SISTEMA LOGÍSTICO DE DRONES MÉDICOS
#  Esqueleto de clases — Semana 1
# ================================================================

class Hospital:

    def __init__(self, id_hospital, almacen_asignado,
                 stock_inicial, umbrales_s, cantidades_q):
        self.id               = id_hospital
        self.almacen_asignado = almacen_asignado  # objeto Almacen
        self.inventario       = stock_inicial      # {producto: stock_actual}
        self.umbral_s         = umbrales_s         # {producto: stock_mínimo}
        self.cantidad_Q       = cantidades_q       # {producto: unidades_a_pedir}
        self.pedidos_activos  = []                 # pedidos en estado "en_camino"

    # Recibe un diccionario {producto: unidades_consumidas} generado con Poisson
    # y resta esas cantidades del inventario. Solo descuenta, no pide reposición.
    def simular_consumo_interno(self, consumos):
        pass

    # Mira el inventario y devuelve la lista de productos que están por debajo
    # del umbral s y que todavía no tienen un pedido en camino.
    def revisar_inventario(self):
        pass

    # Crea un pedido rutinario para reponer un producto y lo manda al almacén.
    # Si ya hay un pedido de ese producto en camino, no crea uno nuevo.
    def generar_pedido_reposicion(self, producto, tiempo_actual=0.0):
        pass

    # Crea un pedido crítico para un órgano con un tiempo límite de isquemia
    # y lo manda al almacén con máxima prioridad.
    def generar_emergencia_organo(self, tipo_organo, tiempo_isquemia, tiempo_actual=0.0):
        pass

    # Registra la llegada de un pedido: suma las unidades al inventario
    # y marca el pedido como entregado.
    def recibir_pedido(self, pedido, tiempo_actual=0.0):
        pass

    def __str__(self):
        pass


# ----------------------------------------------------------------

class Pedido:
    """
    Sistema de prioridades (3 criterios encadenados):
        1. Prioridad clínica:  crítico (3) > urgente (2) > rutinario (1)
        2. Tiempo restante hasta deadline (menor = más urgente)
        3. Orden de llegada FIFO (llegó antes = más urgente)
    """

    PRIORIDADES = {
        "critico":   3,
        "urgente":   2,
        "rutinario": 1,
    }

    contador_global = 0

    def __init__(self, categoria, hospital_destino, producto, cantidad, peso_total,
                 tiempo_creacion=0.0, tiempo_limite=None):
        Pedido.contador_global += 1
        self.id               = f"PED-{Pedido.contador_global}"
        self.numero_llegada   = Pedido.contador_global

        self.categoria        = categoria.lower()
        self.hospital_destino = hospital_destino  # objeto Hospital
        self.producto         = producto
        self.cantidad         = cantidad
        self.peso_total       = peso_total        # kg

        self.prioridad        = Pedido.PRIORIDADES.get(self.categoria, 1)

        self.tiempo_creacion  = tiempo_creacion
        self.tiempo_limite    = tiempo_limite     # None si no tiene deadline
        self.tiempo_entrega   = None

        self.estado           = "pendiente"       # pendiente | en_camino | entregado

    # Cambia el estado del pedido (pendiente → en_camino → entregado).
    def actualizar_estado(self, nuevo_estado):
        pass

    # Registra la hora exacta en que el pedido llegó al hospital.
    def marcar_entregado(self, tiempo_actual):
        pass

    # Devuelve los minutos que quedan hasta el deadline.
    # Si no tiene deadline devuelve infinito para que nunca se considere urgente por tiempo.
    def tiempo_restante(self, tiempo_actual):
        pass

    # Devuelve una tupla con los tres criterios de prioridad para ordenar la cola del almacén.
    def clave_ordenacion(self, tiempo_actual):
        pass

    # Devuelve True si al pedido le quedan menos de margen_alerta minutos para su deadline.
    # Útil para que el simulador fuerce el despacho antes de que sea demasiado tarde.
    def esta_en_riesgo(self, tiempo_actual, margen_alerta=15):
        pass

    # Devuelve cuántos minutos tardó el pedido desde que se creó hasta que llegó.
    def tiempo_en_transito(self):
        pass

    # Devuelve True si el pedido llegó antes de su deadline, False si llegó tarde,
    # y None si no tiene deadline o todavía no ha llegado.
    def entregado_a_tiempo(self):
        pass

    def __str__(self):
        pass


# ----------------------------------------------------------------

class Almacen:

    def __init__(self, id_almacen, nodo_ubicacion, inventario_inicial):
        self.id                 = id_almacen
        self.ubicacion          = nodo_ubicacion
        self.inventario         = inventario_inicial  # {producto: stock_actual}
        self.flota_drones       = []                  # lista de objetos Dron
        self.pedidos_pendientes = []                  # cola de objetos Pedido
        self.hospitales         = []                  # hospitales a los que sirve

    # Añade un dron a la flota de este almacén.
    def registrar_dron(self, dron):
        pass

    # Recibe un pedido de un hospital y lo mete en la cola ordenado por prioridad.
    def recibir_pedido_hospital(self, pedido):
        pass

    # Busca el primer dron disponible que pueda cargar el peso requerido.
    # Devuelve el dron si lo encuentra, o None si no hay ninguno disponible.
    def _buscar_dron_disponible(self, peso_requerido):
        pass

    # Recorre la cola de pedidos e intenta asignar un dron a cada uno.
    # Los pedidos que no puedan salir (sin dron o sin stock) se quedan en la cola.
    def procesar_despachos(self):
        pass

    def __str__(self):
        pass


# ----------------------------------------------------------------

class RedLogistica:
    """
    Grafo completo G = (V, E)
    V : 2 almacenes + 8 hospitales
    E : rutas directas entre todos los nodos
    """

    # Toda la infraestructura del grafo (nodos, distancias, dependencias hospital-almacén)
    # se define en un fichero separado datos_red.py y se importa aquí.

    def __init__(self):
        # Construye el diccionario de distancias en ambas direcciones automáticamente
        self.distancias = {}
        for (origen, destino), km in self._DISTANCIAS_BASE.items():
            self.distancias[(origen, destino)] = km
            self.distancias[(destino, origen)] = km

    # Devuelve la distancia en km entre dos nodos cualesquiera de la red.
    def obtener_distancia(self, nodo_a, nodo_b):
        pass

    # Devuelve el id del almacén principal asignado a un hospital.
    def obtener_almacen_asignado(self, id_hospital):
        pass

    # Devuelve la lista de hospitales que sirve un almacén.
    def obtener_hospitales_de_almacen(self, id_almacen):
        pass

    # Devuelve un diccionario {destino: km} desde un nodo.
    # Es el formato que necesita procesar_despachos() para saber a qué distancia está cada hospital.
    def distancias_desde(self, nodo_origen):
        pass

    def __str__(self):
        pass


# ----------------------------------------------------------------

class ModeloMeteorologico:
    """
    Estados discretos que cambian hora a hora según probabilidades AEMET.
    Cada estado afecta velocidad y consumo del dron mediante factores multiplicativos.
    """

    # Los estados meteorológicos, sus factores y las probabilidades horarias
    # se definen en un fichero separado datos_meteorologia.py y se importan aquí.

    def __init__(self, semilla=None):
        self.rng           = random.Random(semilla)       # para reproducibilidad en Montecarlo
        self.rng_np        = np.random.default_rng(semilla)
        self.estado_actual = "normal"
        self.historial     = []   # lista de (tiempo, estado) para analizar al final

    # Sortea un nuevo estado según las probabilidades del tramo horario actual.
    # Se llama cada 60 minutos desde el simulador. De esta forma conseguimos que el sistema improvise ante cambio de condiciones
    def actualizar_estado(self, tiempo_actual):

        pass

    # Metodo para el futuro
    # Devuelve el factor por el que se multiplica la velocidad del dron ahora mismo.
    # def factor_velocidad(self):
    #   pass

    # Metodo para el futuro
    # Devuelve el factor por el que se multiplica el consumo de batería ahora mismo.
    # def factor_consumo(self):
    #    pass

class Simulador:

    pass
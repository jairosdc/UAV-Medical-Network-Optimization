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
        return f"Dron {self.id} | Posición: {self.posicion_actual} | Batería: {self.bateria_actual:.1f}% | Estado: {self.estado_operativo}"
    

class Hospital:
    def __init__(self, id_hospital, almacen_asignado, stock_inicial, umbrales_s, cantidades_q):
        self.id = id_hospital
        self.almacen_asignado = almacen_asignado

        # Los tres son diccionarios simples
        self.inventario = stock_inicial
        self.umbral_s = umbrales_s
        self.cantidad_Q = cantidades_q

        self.pedidos_activos = [] # Recoge los pedidos que han salido hacia 

    def simular_consumo_interno(self):
        pass

    def revisar_inventario(self):
        # Devuelve lista de productos que necesitan reposición
        productos_bajos = []
        for producto, stock in self.inventario.items():
            if stock < self.umbral_s[producto]:
                productos_bajos.append(producto)
        return productos_bajos

    def generar_pedido_reposicion(self, producto):
        # Generamos el pedido de reposición verificando si ese producto ya ha sido pedido y esta camino del hospital
        pass

    def generar_emergencia_organo(self, tipo_organo, tiempo_isquemia):
        pass

    def recibir_pedido(self, producto, cantidad):
        self.inventario[producto] += cantidad

    def __str__(self):
        return f"Hospital {self.id} | Almacén: {self.almacen_asignado} | Stock: {self.inventario}"
    
class Pedido: 

    def __init__(self, tipo):
        self.tipo = tipo # Organo o rutinario

    pass

class Almacen:

    pass

class RedLogistica:

    pass

class ModeloMeteorologico:

    pass

class Simulador:

    pass
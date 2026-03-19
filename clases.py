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
        self.almacen_asignado = almacen_asignado  # Objeto Almacen al que pertenece

        # Inventario, umbrales de reposición y cantidades de pedido por producto
        self.inventario  = stock_inicial   # {producto: stock_actual}
        self.umbral_s    = umbrales_s      # {producto: stock_mínimo antes de pedir}
        self.cantidad_Q  = cantidades_q    # {producto: unidades a pedir cuando se repone}

        # Pedidos que ya han salido del almacén hacia este hospital
        self.pedidos_activos = []          # Lista de objetos Pedido en estado "en_camino"

    # Inventario y consumo

    def simular_consumo_interno(self, consumos):
        """
        Descuenta del inventario el consumo de un turno de simulación.

        consumos : dict {producto: unidades_consumidas}
        
        Si un producto cae por debajo de su umbral se avisa por consola,
        pero no se lanza el pedido aquí: eso lo hace revisar_inventario().
        """
        for producto, cantidad in consumos.items():
            if producto not in self.inventario:
                print(f"⚠️  Hospital {self.id}: producto '{producto}' no existe en inventario.")
                continue

            self.inventario[producto] = max(0, self.inventario[producto] - cantidad)

            if self.inventario[producto] < self.umbral_s.get(producto, 0):
                print(f"📉 Hospital {self.id}: '{producto}' bajo umbral "
                      f"(stock={self.inventario[producto]}, umbral={self.umbral_s[producto]}).")

    def revisar_inventario(self):
        """
        Devuelve la lista de productos que necesitan reposición rutinaria,
        ignorando los que ya tienen un pedido activo en camino.
        """
        # Productos que ya tienen pedido activo → no volvemos a pedir
        productos_pedidos = {
            p.producto for p in self.pedidos_activos if p.estado == "en_camino"
        }

        productos_bajos = []
        for producto, stock in self.inventario.items():
            if stock < self.umbral_s[producto] and producto not in productos_pedidos:
                productos_bajos.append(producto)

        return productos_bajos

    # Generar pedidos

    def generar_pedido_reposicion(self, producto, tiempo_actual=0.0):
        """
        Crea un Pedido rutinario para reponer 'producto' y lo envía al almacén asignado.
        Devuelve el objeto Pedido creado, o None si ya hay uno activo para ese producto.
        """
        # Evitamos duplicar pedidos para el mismo producto
        for pedido in self.pedidos_activos:
            if pedido.producto == producto and pedido.estado == "en_camino":
                print(f"Hospital {self.id}: ya hay un pedido activo de '{producto}'.")
                return None

        cantidad  = self.cantidad_Q[producto]
        peso_unit = 0.5                          # kg por unidad por defecto (ajustable)
        peso_total = round(cantidad * peso_unit, 2)

        pedido = Pedido(
            categoria        = "rutinario",
            hospital_destino = self,
            producto         = producto,
            cantidad         = cantidad,
            peso_total       = peso_total,
            tiempo_creacion  = tiempo_actual,
            tiempo_limite    = None              # Reposición rutinaria sin deadline fijo
        )

        self.pedidos_activos.append(pedido)
        self.almacen_asignado.recibir_pedido_hospital(pedido)

        print(f"📦 Hospital {self.id}: pedido rutinario generado → {pedido}")
        return pedido

    def generar_emergencia_organo(self, tipo_organo, tiempo_isquemia, tiempo_actual=0.0):
        """
        Crea un Pedido crítico para un órgano con tiempo de isquemia como deadline.

        tipo_organo     : str  (ej. "corazon", "rinon")
        tiempo_isquemia : float  minutos disponibles antes de que el órgano no sea viable
        tiempo_actual   : float  minuto de simulación en que ocurre la emergencia
        """
        peso_organo = 1.0   # kg estimado por defecto (ajustable por tipo)

        pedido = Pedido(
            categoria        = "critico",
            hospital_destino = self,
            producto         = tipo_organo,
            cantidad         = 1,
            peso_total       = peso_organo,
            tiempo_creacion  = tiempo_actual,
            tiempo_limite    = tiempo_actual + tiempo_isquemia
        )

        self.pedidos_activos.append(pedido)
        self.almacen_asignado.recibir_pedido_hospital(pedido)

        print(f"🚨 Hospital {self.id}: EMERGENCIA de órgano '{tipo_organo}' "
              f"| Isquemia: {tiempo_isquemia} min | {pedido}")
        return pedido

    # ------------------------------------------------------------------ #
    #  RECEPCIÓN DE PEDIDOS                                                #
    # ------------------------------------------------------------------ #

    def recibir_pedido(self, pedido, tiempo_actual=0.0):
        """
        Registra la llegada de un pedido: actualiza inventario y marca el pedido entregado.
        Acepta tanto el objeto Pedido como una llamada legacy (producto, cantidad).
        """
        # Soporte para llamada legacy: recibir_pedido("ibuprofeno", 10)
        if isinstance(pedido, str):
            producto = pedido
            cantidad = tiempo_actual   # segundo argumento era la cantidad en la versión anterior
            self.inventario[producto] = self.inventario.get(producto, 0) + cantidad
            print(f"✅ Hospital {self.id}: recibidas {cantidad} u. de '{producto}' (modo legacy).")
            return

        # Camino principal: recibimos un objeto Pedido
        pedido.marcar_entregado(tiempo_actual)
        self.inventario[pedido.producto] = (
            self.inventario.get(pedido.producto, 0) + pedido.cantidad
        )

        # Retiramos el pedido de la lista de activos
        if pedido in self.pedidos_activos:
            self.pedidos_activos.remove(pedido)

        print(f"✅ Hospital {self.id}: {pedido.producto} x{pedido.cantidad} recibido "
              f"| Stock ahora: {self.inventario[pedido.producto]} u. | {pedido}")

    # ------------------------------------------------------------------ #
    #  REPRESENTACIÓN                                                      #
    # ------------------------------------------------------------------ #

    def __str__(self):
        activos = len(self.pedidos_activos)
        return (f"Hospital {self.id} | Almacén: {self.almacen_asignado.id} "
                f"| Stock: {self.inventario} | Pedidos activos: {activos}")
    
class Pedido:
    """
    Representa una solicitud de transporte entre un almacén y un hospital.
    
    El sistema de prioridades funciona en tres niveles (del más al menos importante):
        1. Prioridad clínica:   crítico (3) > urgente (2) > rutinario (1)
        2. Tiempo restante:     si empatan en prioridad, gana quien tenga menos tiempo hasta su deadline
        3. Orden de llegada:    si también empatan en tiempo, gana quien llegó antes (FIFO)
    """

    # Tabla de prioridades clínicas según categoría de producto
    # Cuanto mayor el número, más urgente
    PRIORIDADES = {
        "critico":   3,   # Órganos, sangre, fármacos UCI
        "urgente":   2,   # Antibióticos, sueros
        "rutinario": 1    # Analgésicos, material sanitario
    }

    # Contador global para el FIFO: nos dice quién llegó antes
    contador_global = 0

    def __init__(self, categoria, hospital_destino, producto, cantidad, peso_total,
                 tiempo_creacion=0.0, tiempo_limite=None):
        """
        categoria       : "critico", "urgente" o "rutinario"
        hospital_destino: objeto Hospital al que va el pedido
        producto        : nombre del producto (ej: "sangre_A+", "ibuprofeno")
        cantidad        : número de unidades
        peso_total      : peso en kg del paquete (para elegir dron)
        tiempo_creacion : momento de la simulación en que se crea (en minutos)
        tiempo_limite   : minutos máximos hasta entrega (isquemia para órganos, etc.)
        """

        # --- Identificación ---
        Pedido.contador_global += 1
        self.id = f"PED-{Pedido.contador_global}"
        self.numero_llegada = Pedido.contador_global  # Sirve para el criterio FIFO

        # --- Datos del envío ---
        self.categoria = categoria.lower()
        self.hospital_destino = hospital_destino
        self.producto = producto
        self.cantidad = cantidad
        self.peso_total = peso_total

        # --- Sistema de prioridades ---
        # Si la categoría no existe en la tabla, asignamos la mínima prioridad
        self.prioridad = Pedido.PRIORIDADES.get(self.categoria, 1)

        # --- Tiempos (para métricas y desempates) ---
        self.tiempo_creacion = tiempo_creacion
        self.tiempo_limite = tiempo_limite      # None si no tiene deadline fijo
        self.tiempo_entrega = None              # Se rellena cuando llega al hospital

        # --- Estado del pedido ---
        self.estado = "pendiente"   # pendiente → en_camino → entregado

    # ------------------------------------------------------------------ #
    #  MÉTODOS DE ESTADO                                                   #
    # ------------------------------------------------------------------ #

    def actualizar_estado(self, nuevo_estado):
        """Cambia el estado del pedido. Estados válidos: pendiente, en_camino, entregado."""
        self.estado = nuevo_estado

    def marcar_entregado(self, tiempo_actual):
        """Registra la hora de entrega y actualiza el estado."""
        self.estado = "entregado"
        self.tiempo_entrega = tiempo_actual

    # ------------------------------------------------------------------ #
    #  MÉTODOS DE PRIORIDAD Y DESEMPATE                                    #
    # ------------------------------------------------------------------ #

    def tiempo_restante(self, tiempo_actual):
        """
        Devuelve el tiempo que queda hasta el deadline.
        Si no tiene deadline, devuelve infinito (nunca urgente por tiempo).
        """
        if self.tiempo_limite is None:
            return float('inf')
        return self.tiempo_limite - tiempo_actual

    def clave_ordenacion(self, tiempo_actual):
        """
        Devuelve una tupla que permite ordenar pedidos aplicando los tres criterios
        del documento de forma encadenada.

        La ordenación final en la cola debe ser DESCENDENTE por esta clave,
        de modo que el pedido más urgente quede primero.

        Criterio 1 — Prioridad clínica:      mayor número = más urgente  → negamos para invertir
        Criterio 2 — Tiempo restante:         menos tiempo = más urgente  → lo dejamos directo
        Criterio 3 — Orden de llegada (FIFO): llegó antes = más urgente   → lo dejamos directo
        """
        return (
            -self.prioridad,                        # Criterio 1: -3 < -2 < -1  →  crítico primero
            self.tiempo_restante(tiempo_actual),    # Criterio 2: menos tiempo restante, antes
            self.numero_llegada                     # Criterio 3: número más bajo llegó antes
        )

    def esta_en_riesgo(self, tiempo_actual, margen_alerta=15):
        """
        Devuelve True si el pedido está a menos de 'margen_alerta' minutos de su deadline.
        Útil para que el simulador genere avisos o fuerce el despacho.
        """
        if self.tiempo_limite is None:
            return False
        return self.tiempo_restante(tiempo_actual) <= margen_alerta

    # ------------------------------------------------------------------ #
    #  MÉTODOS DE MÉTRICAS                                                 #
    # ------------------------------------------------------------------ #

    def tiempo_en_transito(self):
        """Minutos desde la creación hasta la entrega. None si aún no ha llegado."""
        if self.tiempo_entrega is None:
            return None
        return self.tiempo_entrega - self.tiempo_creacion

    def entregado_a_tiempo(self):
        """
        Devuelve True si el pedido llegó antes de su deadline.
        Devuelve None si no tiene deadline o aún no se ha entregado.
        """
        if self.tiempo_limite is None or self.tiempo_entrega is None:
            return None
        return self.tiempo_entrega <= self.tiempo_limite

    # ------------------------------------------------------------------ #
    #  REPRESENTACIÓN                                                      #
    # ------------------------------------------------------------------ #

    def __str__(self):
        iconos = {"critico": "🚨", "urgente": "⚠️", "rutinario": "📦"}
        icono = iconos.get(self.categoria, "📦")
        deadline = f"{self.tiempo_limite} min" if self.tiempo_limite else "sin límite"
        return (f"{icono} {self.id} | {self.categoria.upper()} (prior. {self.prioridad}) | "
                f"→ Hosp {self.hospital_destino.id} | {self.producto} x{self.cantidad} | "
                f"Deadline: {deadline} | Estado: {self.estado}")


class Almacen:
    def __init__(self, id_almacen, nodo_ubicacion, inventario_inicial):
        self.id = id_almacen
        self.ubicacion = nodo_ubicacion
        self.inventario = inventario_inicial # Diccionario {producto: stock_actual}
        
        # Interconexiones clave
        self.flota_drones = []       # Lista de objetos Dron asignados a este almacén
        self.pedidos_pendientes = [] # Cola de objetos Pedido
        self.hospitales = []         # Hospitales a los que sirve el almacen

    def registrar_dron(self, dron):
        # Se añade un dron a la flota de ese almacén
        self.flota_drones.append(dron)

    def recibir_pedido_hospital(self, pedido):
        """Recibe un pedido y lo encola ordenado por prioridad."""
        self.pedidos_pendientes.append(pedido)
        # Ordenamos la lista para que las emergencias (prioridad 1) queden al principio
        self.pedidos_pendientes.sort(key=lambda p: p.prioridad, reverse=True)
        print(f"Almacén {self.id} ha recibido el {pedido}")

    def _buscar_dron_disponible(self, peso_requerido):
        """Método interno para buscar el primer dron disponible que pueda con la carga."""
        for dron in self.flota_drones:
            if dron.estado_operativo == "disponible" and dron.capacidad_carga >= peso_requerido:
                return dron
        return None

    def procesar_despachos(self, distancias_red, factor_meteo=1.0):
        """
        Intenta despachar todos los pedidos pendientes. 
        'distancias_red' es un diccionario que nos dice a qué distancia está cada hospital.
        """
        pedidos_no_despachados = []

        for pedido in self.pedidos_pendientes:
            # 1. Comprobar stock (si es rutinario)
            if pedido.tipo == "rutinario" and self.inventario.get(pedido.producto, 0) < pedido.cantidad:
                print(f"⚠️ Sin stock en Almacén {self.id} para {pedido.producto}.")
                pedidos_no_despachados.append(pedido)
                continue

            # 2. Buscar un dron adecuado
            dron = self._buscar_dron_disponible(pedido.peso_total)
            
            if dron:
                # Obtenemos la distancia al hospital destino (simulando que consultamos la RedLogistica)
                distancia = distancias_red.get(pedido.hospital_destino.id, 15.0) # 15km por defecto si no se encuentra
                
                # 3. Intentar asignar la misión al dron
                mision_ok = dron.asignar_mision(
                    destino=pedido.hospital_destino.id,
                    distancia=distancia,
                    carga=pedido.peso_total,
                    factor_meteorologico=factor_meteo
                )

                if mision_ok:
                    # Actualizamos estados y restamos stock
                    pedido.actualizar_estado("en_camino")
                    if pedido.tipo == "rutinario":
                        self.inventario[pedido.producto] -= pedido.cantidad
                    
                    print(f"✅ {pedido.id} despachado en Dron {dron.id} hacia Hosp {pedido.hospital_destino.id}.")
                else:
                    # El dron estaba disponible pero no tenía batería para ESTE viaje
                    print(f"🔋 Dron {dron.id} sin batería suficiente para el {pedido.id}. Necesita recargar.")
                    pedidos_no_despachados.append(pedido)
            else:
                print(f"🚁 No hay drones con capacidad disponible para el {pedido.id}.")
                pedidos_no_despachados.append(pedido)

        # Mantenemos en la cola solo los pedidos que no pudieron salir
        self.pedidos_pendientes = pedidos_no_despachados

    def __str__(self):
        drones_disp = sum(1 for d in self.flota_drones if d.estado_operativo == "disponible")
        return f"Almacén {self.id} | Stock: {self.inventario} | Drones Disp: {drones_disp}/{len(self.flota_drones)} | En cola: {len(self.pedidos_pendientes)}"

class RedLogistica:

    pass

class ModeloMeteorologico:

    pass

class Simulador:

    pass
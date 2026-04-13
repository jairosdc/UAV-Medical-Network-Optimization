class GestorPrioridad:
    def __init__(self):
        # Lista plana donde guardaremos los objetos 'DeliveryCall'
        self.pedidos_pendientes = []

    def añadir_pedido(self, pedido):
        # Push de la cola
        self.pedidos_pendientes.append(pedido)

    def obtener_siguiente_pedido(self):
        if not self.pedidos_pendientes:
            return None

        # Establecemos la relación de orden total:
        # 1. Prioridad clínica (menor valor = mayor criticidad).
        # 2. Instante temporal (FIFO en caso de misma prioridad).
        # 3. Identificador de llamada (desempate determinista si ocurren en el mismo minuto).
        self.pedidos_pendientes.sort(key=lambda p: (
            p.priority, 
            p.timestamp_min,
            p.call_id
        ))

        # El método pop(0) extrae el nodo con mayor precedencia tras la evaluación topológica
        return self.pedidos_pendientes.pop(0)

    def size(self):
        return len(self.pedidos_pendientes)
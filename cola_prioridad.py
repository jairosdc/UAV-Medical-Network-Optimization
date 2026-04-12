class GestorPrioridad:
    def __init__(self):
        # Lista plana donde guardaremos los objetos 'Pedido'
        self.pedidos_pendientes = []

    def añadir_pedido(self, pedido):
        # Push de la cola
        self.pedidos_pendientes.append(pedido)

    def obtener_siguiente_pedido(self):
        # Usa el sistema de desempate establecido en el documento, como aun no hay tiempo de isquemia se usa FIFO
        if not self.pedidos_pendientes:
            return None

        # Ordenamos la lista antes de extraer:
        self.pedidos_pendientes.sort(key=lambda p: (
            p.prioridad_clinica, 
            p.limite_isquemia_minuto if p.limite_isquemia_minuto is not None else float('inf'),
            p.minuto_creacion
        ))

        # El método pop(0) extrae el que ha quedado primero tras el sorteo
        return self.pedidos_pendientes.pop(0)

    def size(self):
        return len(self.pedidos_pendientes)
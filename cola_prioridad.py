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

            # Orden total: Prioridad -> Deadline (EDF) -> Tiempo de llegada FIFO -> ID
            self.pedidos_pendientes.sort(key=lambda p: (
                p.priority, 
                p.deadline_min,    # Los órganos desempatarán por quién caduca antes
                p.timestamp_min,
                p.call_id
            ))

            return self.pedidos_pendientes.pop(0)

    def size(self):
        return len(self.pedidos_pendientes)
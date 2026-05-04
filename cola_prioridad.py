class GestorPrioridad:
    def __init__(self):
        self.pedidos_pendientes = []

    def añadir_pedido(self, pedido):
        self.pedidos_pendientes.append(pedido)

    def obtener_siguiente_pedido(self):
        if not self.pedidos_pendientes:
            return None

        self.pedidos_pendientes.sort(
            key=lambda p: (
                p.priority,
                p.deadline_min,
                p.timestamp_min,
                p.call_id
            )
        )

        return self.pedidos_pendientes.pop(0)

    def extraer_ronda_ordenada(self):
        """
        Extrae todos los pedidos pendientes en una ronda ordenada.

        Esto evita ordenar la cola una vez por cada pedido.
        """
        if not self.pedidos_pendientes:
            return []

        pedidos = self.pedidos_pendientes
        self.pedidos_pendientes = []

        pedidos.sort(
            key=lambda p: (
                p.priority,
                p.deadline_min,
                p.timestamp_min,
                p.call_id
            )
        )

        return pedidos

    def size(self):
        return len(self.pedidos_pendientes)
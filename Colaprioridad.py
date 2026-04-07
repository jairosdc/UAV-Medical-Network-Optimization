class Cola:
    def __init__(self):
        self.elementos = []

    def empty(self):
        return len(self.elementos) == 0

    def push(self, elemento):
        self.elementos.append(elemento)

    def pop(self):
        if self.empty():
            raise IndexError("No se puede eliminar porque la cola está vacía")
        return self.elementos.pop(0)

    def front(self):
        if self.empty():
            raise IndexError("No se puede eliminar porque la cola está vacía")
        return self.elementos[0]

    def size(self):
        return len(self.elementos)

    def mostrar(self):
        print("Estado de la cola", self.elementos)


# ─────────────────────────────────────────────
# Cola de prioridad: una Cola interna por nivel
# ─────────────────────────────────────────────

class ColaPrioridad:

    NIVELES = ["urgente", "alta", "media", "baja"]

    def __init__(self):
        # Una cola independiente por cada nivel de prioridad
        self._colas = {nivel: Cola() for nivel in self.NIVELES}

    def empty(self):
        return all(c.empty() for c in self._colas.values())

    def size(self):
        return sum(c.size() for c in self._colas.values())

    def push(self, elemento, prioridad: str):
        """Añade un elemento en la cola correspondiente a su prioridad."""
        prioridad = prioridad.lower()
        if prioridad not in self.NIVELES:
            raise ValueError(f"Prioridad '{prioridad}' no válida. Usa: {self.NIVELES}")
        self._colas[prioridad].push(elemento)

    def pop(self):
        """Extrae el elemento más prioritario. Dentro del mismo nivel respeta el orden de llegada."""
        if self.empty():
            raise IndexError("No se puede eliminar porque la cola está vacía")
        for nivel in self.NIVELES:          # recorre de mayor a menor prioridad
            if not self._colas[nivel].empty():
                return self._colas[nivel].pop()

    def front(self):
        """Devuelve el siguiente elemento sin extraerlo."""
        if self.empty():
            raise IndexError("No se puede consultar porque la cola está vacía")
        for nivel in self.NIVELES:
            if not self._colas[nivel].empty():
                return self._colas[nivel].front()

    def mostrar(self):
        """Muestra todos los elementos agrupados por nivel."""
        print("─" * 40)
        pos = 1
        for nivel in self.NIVELES:
            cola = self._colas[nivel]
            if not cola.empty():
                for elem in cola.elementos:
                    prefijo = "→" if pos == 1 else " "
                    print(f" {prefijo} {pos}. [{nivel.upper()}] {elem}")
                    pos += 1
        if pos == 1:
            print("  (la cola está vacía)")
        print("─" * 40)
from dataclasses import dataclass
from typing import Optional

# =============================================================================
# 1. ENTIDADES
# =============================================================================
@dataclass
class Pedido:
    id_pedido: int
    minuto_creacion: int
    origen: str
    destino: str
    carga_kg: float
    prioridad_clinica: int

@dataclass
class Producto:
    stock_fisico: int
    umbral_s: int
    cantidad_a_pedir_Q: int
    stock_en_camino: int = 0
    
    @property
    def stock_total_estimado(self) -> int:
        return self.stock_fisico + self.stock_en_camino

# =============================================================================
# 2. INVENTARIO
# =============================================================================
class Inventario:
    def __init__(self, nombre: str):
        self.nombre = nombre
        # Inicializamos un hospital con stock límite para forzar pedidos
        self.productos = {
            "sangre": Producto(stock_fisico=15, umbral_s=15, cantidad_a_pedir_Q=30),
            "analgesico": Producto(stock_fisico=55, umbral_s=50, cantidad_a_pedir_Q=100)
        }

    def registrar_consumo(self, producto: str, cantidad: int) -> int:
        if producto not in self.productos: return 0
        prod = self.productos[producto]
        
        prod.stock_fisico = max(0, prod.stock_fisico - cantidad)
        
        if prod.stock_total_estimado <= prod.umbral_s:
            prod.stock_en_camino += prod.cantidad_a_pedir_Q
            return prod.cantidad_a_pedir_Q
        return 0

# =============================================================================
# 3. COLA DE PRIORIDAD
# =============================================================================
class GestorPrioridad:
    def __init__(self):
        self.pedidos = []

    def push(self, pedido: Pedido):
        self.pedidos.append(pedido)
        # Orden estricto: Prioridad Clínica (1 es mejor) -> Orden de llegada (Minuto)
        self.pedidos.sort(key=lambda p: (p.prioridad_clinica, p.minuto_creacion))

    def mostrar_estado(self):
        if not self.pedidos:
            return "[Cola Vacía]"
        return " | ".join([f"Prio {p.prioridad_clinica}: {p.destino} ({p.origen})" for p in self.pedidos])

# =============================================================================
# 4. FÁBRICA DE PEDIDOS (HELPER)
# =============================================================================
class FabricaPedidos:
    def __init__(self):
        self.id_actual = 1
        
    def crear_reposicion(self, hospital, prod, cant, min_actual):
        prio = 1 if prod == "sangre" else 3
        pedido = Pedido(self.id_actual, min_actual, "BASE_CENTRAL", hospital.nombre, 2.0, prio)
        self.id_actual += 1
        return pedido

    def crear_emergencia(self, origen, destino, prod, min_actual):
        pedido = Pedido(self.id_actual, min_actual, origen, destino, 1.5, 1) # Órgano siempre es prio 1
        self.id_actual += 1
        return pedido

# =============================================================================
# 5. SIMULADOR DETERMINISTA (VALIDACIÓN)
# =============================================================================
def ejecutar_validacion():
    print("=== INICIANDO VALIDACIÓN DEL NÚCLEO LOGÍSTICO ===\n")
    
    hospital_a = Inventario("Hospital_A")
    cola = GestorPrioridad()
    fabrica = FabricaPedidos()
    
    # Agenda pre-programada (Sustituye al random de Poisson para el test)
    agenda_eventos = {
        1: [{"tipo": "consumo", "producto": "analgesico", "cantidad": 10}],
        2: [],
        3: [{"tipo": "consumo", "producto": "sangre", "cantidad": 1}],
        4: [{"tipo": "emergencia", "producto": "organo", "origen": "Hospital_B", "destino": "Hospital_A"}],
        5: []
    }

    # Bucle del Simulador
    for minuto in range(1, 6):
        print(f"--- MINUTO {minuto} ---")
        eventos_minuto = agenda_eventos.get(minuto, [])
        
        for ev in eventos_minuto:
            if ev["tipo"] == "consumo":
                print(f"[*] Evento: Hospital_A consume {ev['cantidad']} de {ev['producto']}")
                cant_pedir = hospital_a.registrar_consumo(ev['producto'], ev['cantidad'])
                
                if cant_pedir > 0:
                    print(f"    [!] ALERTA: Rotura de umbral 's'. Solicitando {cant_pedir} unidades a la Base.")
                    pedido = fabrica.crear_reposicion(hospital_a, ev['producto'], cant_pedir, minuto)
                    cola.push(pedido)
            
            elif ev["tipo"] == "emergencia":
                print(f"[*] Evento: EMERGENCIA! Órgano desde {ev['origen']} hacia {ev['destino']}")
                pedido = fabrica.crear_emergencia(ev['origen'], ev['destino'], ev['producto'], minuto)
                cola.push(pedido)

        # Imprimir el estado interno de las estructuras
        print(f"    Inventario Sangre: {hospital_a.productos['sangre'].stock_fisico}")
        print(f"    Inventario Analgésico: {hospital_a.productos['analgesico'].stock_fisico}")
        print(f"    Estado Cola: {cola.mostrar_estado()}\n")

if __name__ == "__main__":
    ejecutar_validacion()
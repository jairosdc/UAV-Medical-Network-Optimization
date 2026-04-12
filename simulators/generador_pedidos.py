import random
import numpy as np
from collections import defaultdict

# Tasas base horarias (lambda)
TASAS_PRODUCTOS = {
    "organo": 0.05, "sangre": 0.30, "farmaco_uci": 0.20,
    "antibiotico": 0.80, "suero": 0.60, "plasma": 0.25,
    "analgesico": 1.20, "material_sanitario": 1.00, "medicamento_general": 0.90
}

# Prioridades clínicas
PRIORIDADES = {
    "organo": 1, "sangre": 1, "farmaco_uci": 1,
    "antibiotico": 2, "suero": 2, "plasma": 2,
    "analgesico": 3, "material_sanitario": 3, "medicamento_general": 3
}

FACTORES_HORARIOS = [
    (0, 6, 0.48), (6, 9, 1.0), (9, 14, 1.6), 
    (14, 16, 1.13), (16, 20, 1.3), (20, 24, 0.6)
]

class GeneradorEscenario:
    def __init__(self, hospitales, semilla=None):
        self.hospitales = hospitales
        self.agenda_eventos = defaultdict(list)
        if semilla:
            np.random.seed(semilla)
            random.seed(semilla)
        
        self._pregenerar_dia()

    def _pregenerar_dia(self):
        """Calcula todos los eventos de consumo y emergencias del día de golpe."""
        for h_inicio, h_fin, factor in FACTORES_HORARIOS:
            duracion_h = h_fin - h_inicio
            t_inicio_min = h_inicio * 60
            t_fin_min = h_fin * 60

            for producto, tasa_base in TASAS_PRODUCTOS.items():
                # Calculamos cuántas veces ocurrirá este evento en este tramo
                tasa_tramo = tasa_base * factor * duracion_h
                n_eventos = np.random.poisson(tasa_tramo)

                # Repartimos los eventos aleatoriamente en el tiempo del tramo
                minutos_evento = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos)

                for m in minutos_evento:
                    min_discreto = int(m)
                    # Decidimos qué hospital sufre el evento
                    hospital = random.choice(self.hospitales)
                    
                    # Guardamos el evento en la agenda
                    self.agenda_eventos[min_discreto].append({
                        "hospital": hospital,
                        "producto": producto,
                        "es_emergencia": (producto == "organo")
                    })

    def actualizar_minuto(self, minuto_actual, inventarios, cola, fabrica_pedidos):
        """
        Se ejecuta cada minuto. 
        Si hay un evento, lo procesa según sea consumo o emergencia.
        """
        eventos = self.agenda_eventos.get(minuto_actual, [])
        
        for ev in eventos:
            hospital = ev["hospital"]
            prod = ev["producto"]

            if ev["es_emergencia"]:
                # FLUJO EMERGENCIAS: Hospital a Hospital (Punto a Punto)
                origen = hospital # El que tiene el órgano
                destino = random.choice([h for h in self.hospitales if h != origen])
                
                # Creamos el pedido y lo mandamos a la cola directamente
                pedido = fabrica_pedidos.crear_emergencia(origen, destino, prod, minuto_actual)
                cola.añadir_pedido(pedido)
            
            else:
                # FLUJO CONSUMO: El hospital gasta una unidad de su inventario
                inventario_h = inventarios[hospital.nombre]
                unidades_a_pedir = inventario_h.registrar_consumo(prod, 1)

                # Si el inventario dice que hay que reponer (rompe stock s,Q)
                if unidades_a_pedir > 0:
                    # Creamos pedido de la Base al Hospital (Reposición)
                    pedido = fabrica_pedidos.crear_reposicion(hospital, prod, unidades_a_pedir, minuto_actual)
                    cola.añadir_pedido(pedido)
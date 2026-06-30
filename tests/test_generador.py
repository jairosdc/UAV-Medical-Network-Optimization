import math
from uav_medical_network.generador import GeneradorPedidos
from uav_medical_network.config import HOSPITALS, BASES, CARGA_MAXIMA_KG
from uav_medical_network.modelos import Inventario, GestorPrioridad

def test_generador_crea_organos_correctamente():
    hosp_list = list(HOSPITALS.values())
    base_list = list(BASES.values())
    
    # Crear un generador de pedidos con tasas muy altas de órganos para forzar su creación
    gen = GeneradorPedidos(
        hospitales=hosp_list,
        bases=base_list,
        semilla=123,
        duracion_min=1440,
        factor_demanda_inventario=0.0,
        factor_demanda_organos=10.0
    )
    
    # Obtener eventos agendados
    agenda = gen._agenda
    eventos_organo = []
    for minuto, lista in agenda.items():
        for ev in lista:
            if ev["tipo"] == "organo":
                eventos_organo.append(ev)
                
    assert len(eventos_organo) > 0
    
    # Probar que al procesarlo se crea un DeliveryCall tipo "organo"
    cola = GestorPrioridad()
    # Un inventario ficticio
    inventarios = {h.nombre: Inventario(es_almacen_central=False) for h in hosp_list}
    
    # Procesar minutos donde hay órganos
    for minuto, lista in agenda.items():
        gen.procesar_minuto(minuto, inventarios, cola)
        if cola.size() > 0:
            break
            
    pedido = cola.obtener_siguiente_pedido()
    assert pedido is not None
    assert pedido.tipo_pedido == "organo"
    assert pedido.producto in {"corazon", "pulmon", "rinon", "pancreas"}
    assert pedido.priority == 0
    assert pedido.deadline_min < math.inf

def test_division_de_pedidos_por_carga_maxima():
    hosp_list = list(HOSPITALS.values())
    base_list = list(BASES.values())
    
    gen = GeneradorPedidos(
        hospitales=hosp_list,
        bases=base_list,
        semilla=123,
        duracion_min=60,
    )
    
    hospital = hosp_list[0]
    # Usaremos "suero" (peso 0.60 kg por unidad)
    # Pedir 10 unidades = 6.0 kg. Como CARGA_MAXIMA_KG = 4.7 kg, debe dividirse en 2 vuelos.
    # Primer vuelo llevará 7 unidades (4.2 kg), segundo vuelo llevará 3 unidades (1.8 kg)
    pedidos = gen._crear_pedidos_reposicion(hospital, "suero", 10, 1)
    
    assert len(pedidos) == 2
    assert pedidos[0].unidades == 7
    assert pedidos[0].payload_kg == 4.2
    assert pedidos[1].unidades == 3
    assert pedidos[1].payload_kg == 1.8
    assert all(p.tipo_pedido == "inventario" for p in pedidos)

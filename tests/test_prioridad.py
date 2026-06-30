import math
from modelos import GestorPrioridad, DeliveryCall

def test_orden_de_prioridad_clinica():
    gestor = GestorPrioridad()
    
    # Crear un pedido rutinario (prioridad 3)
    p_rutinario = DeliveryCall(
        call_id=1,
        timestamp_min=10,
        origin_hospital="BASE NORTE CAPITAL",
        destination_hospital="Hospital Universitario La Paz",
        payload_kg=1.0,
        priority=3,
        producto="analgesico",
        deadline_min=math.inf,
        tipo_pedido="inventario"
    )
    
    # Crear un pedido de órgano (prioridad 0)
    p_organo = DeliveryCall(
        call_id=2,
        timestamp_min=12,
        origin_hospital="Hospital Universitario La Paz",
        destination_hospital="Hospital Universitario Ramón y Cajal",
        payload_kg=2.0,
        priority=0,
        producto="corazon",
        deadline_min=250.0,
        tipo_pedido="organo"
    )
    
    # Añadir ambos a la cola en orden inverso de prioridad
    gestor.añadir_pedido(p_rutinario)
    gestor.añadir_pedido(p_organo)
    
    # Extraer el primero: debe ser el de órgano (prioridad 0)
    primer_pedido = gestor.obtener_siguiente_pedido()
    assert primer_pedido.call_id == 2
    assert primer_pedido.tipo_pedido == "organo"
    
    # Extraer el segundo
    segundo_pedido = gestor.obtener_siguiente_pedido()
    assert segundo_pedido.call_id == 1

def test_prioridad_mismo_nivel_menor_deadline():
    gestor = GestorPrioridad()
    
    # Dos pedidos de la misma prioridad (0)
    p_tardio = DeliveryCall(
        call_id=10,
        timestamp_min=5,
        origin_hospital="H1",
        destination_hospital="H2",
        payload_kg=2.0,
        priority=0,
        producto="rinon",
        deadline_min=1000.0,
        tipo_pedido="organo"
    )
    
    p_urgente = DeliveryCall(
        call_id=11,
        timestamp_min=5,
        origin_hospital="H1",
        destination_hospital="H3",
        payload_kg=2.0,
        priority=0,
        producto="corazon",
        deadline_min=150.0,
        tipo_pedido="organo"
    )
    
    gestor.añadir_pedido(p_tardio)
    gestor.añadir_pedido(p_urgente)
    
    # Debe salir antes el del menor deadline (p_urgente, deadline 150)
    siguiente = gestor.obtener_siguiente_pedido()
    assert siguiente.call_id == 11
    assert siguiente.deadline_min == 150.0

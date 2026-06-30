from red import ServicioRed
from config import HOSPITALS, BASES

def test_distancia_entre_hospitales_positiva():
    red_serv = ServicioRed()
    
    # Obtener dos hospitales cualesquiera
    hosp_nombres = list(HOSPITALS.keys())
    assert len(hosp_nombres) >= 2
    
    h1 = red_serv.obtener_hospital(hosp_nombres[0])
    h2 = red_serv.obtener_hospital(hosp_nombres[1])
    
    dist = red_serv.distancia_entre_nodos_km(h1, h2)
    assert dist > 0.0

def test_base_mas_cercana_a():
    red_serv = ServicioRed()
    
    hosp_nombres = list(HOSPITALS.keys())
    hosp_nombre = hosp_nombres[0]
    
    nombre_base, dist = red_serv.base_mas_cercana_a(hosp_nombre)
    
    assert nombre_base in BASES
    assert dist > 0.0

def test_listar_nodos_no_vacios():
    red_serv = ServicioRed()
    
    hospitales = red_serv.listar_hospitales()
    bases = red_serv.listar_bases()
    
    assert len(hospitales) > 0
    assert len(bases) > 0
    assert "BASE NORTE CAPITAL" in bases

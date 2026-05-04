import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Grafo.generar_mapa import generar_mapa

def test_generar_mapa_crea_archivo():
    # Arrange
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Grafo', 'grafo.html'))
    
    # Act
    generar_mapa()
    
    # Assert
    assert os.path.exists(output_path), "El archivo grafo.html no se generó."
    
    # Verificamos que contenga contenido folium/html básico
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "cartocdn.com" in content or "dark" in content.lower(), "Falta el estilo de cartodb."
        assert "leaflet" in content.lower(), "No parece ser un mapa de folium."
        assert "🏥" in content or "🚁" in content, "No se encontraron marcadores (hospitales o bases) en el mapa."

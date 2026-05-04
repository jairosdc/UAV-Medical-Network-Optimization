#CÍDIGO PARA PODER GENERAR EL MAPA CADA VEZ QUE SE HAGAN CAMBIOS EN EL ARCHIVO hospitales_almacenes_data.py

import sys
import os
import folium
from folium import plugins
from branca.element import Element

# Asegurarse de que el directorio padre esté en el path para importar
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hospitales_almacenes_data import HOSPITALS, BASES

def generar_mapa():
    # 1. Crear el mapa base
    m = folium.Map(
        location=[40.43, -3.695],
        zoom_start=11,
        tiles="cartodbdark_matter"
    )

    # 2. Añadir el MiniMap
    minimap = plugins.MiniMap(tile_layer='openstreetmap', position='bottomright')
    m.add_child(minimap)

    # 3. Colores vibrantes para los hospitales (se repetirán si hay más hospitales que colores)
    colores_hospitales = [
        "#A8E6CF", "#DDA0DD", "#F7DC6F", "#85C1E9", "#F1948A",
        "#FFD700", "#00FA9A", "#00FFFF", "#FF69B4", "#7B68EE",
        "#32CD32", "#FF8C00", "#FF1493", "#00BFFF", "#7FFFD4"
    ]

    # 4. Iterar sobre los hospitales
    for i, (key, node) in enumerate(HOSPITALS.items()):
        color = colores_hospitales[i % len(colores_hospitales)]
        
        # HTML del Popup
        popup_html = f"""
        <div style="font-family:'Segoe UI',sans-serif;min-width:280px;max-width:330px;
                    background:#111;color:white;padding:6px;border-radius:5px;">
            <h4 style="margin:0 0 8px;color:{color};
                       border-bottom:2px solid {color};padding-bottom:4px;">
                🏥 {node.nombre}
            </h4>
            <p style="margin:3px 0;"><b>📍 Tipo:</b> {node.tipo.capitalize()}</p>
            <p style="margin:3px 0;"><b>🗺️ Coords:</b> {node.lat:.5f}, {node.lon:.5f}</p>
        </div>
        """
        iframe = folium.IFrame(html=popup_html, width=320, height=140)
        popup = folium.Popup(iframe, max_width=340)

        # Círculo exterior (brillo)
        folium.CircleMarker(
            location=[node.lat, node.lon],
            radius=22,
            color=color,
            weight=1.5,
            fill=False,
            opacity=0.4
        ).add_to(m)

        # Círculo interior (núcleo)
        folium.CircleMarker(
            location=[node.lat, node.lon],
            radius=18, # original tenia 18 para el grande o 10, dejemos 18
            color=color,
            weight=2.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=popup,
            tooltip=f"🏥 {node.nombre}"
        ).add_to(m)

        # Label con el nombre flotando al lado
        folium.Marker(
            location=[node.lat + 0.003, node.lon], # un poco más arriba
            icon=folium.DivIcon(
                html=f'<div style="font-size:11px;font-weight:bold;color:{color};text-shadow:1px 1px 4px #000,-1px -1px 4px #000;white-space:nowrap;">{node.nombre}</div>',
                icon_size=(180, 22),
                icon_anchor=(90, 11)
            )
        ).add_to(m)

    # 5. Iterar sobre las bases
    colores_bases = {
        "BASE NORTE": "#00FF88",
        "BASE CENTRO": "#00CFFF",
        "BASE SUR": "#FF9F00"
    }

    for key, node in BASES.items():
        base_color = colores_bases.get(key, "#FF0000")

        popup_html = f"""
        <div style="font-family:'Segoe UI',sans-serif;min-width:260px;max-width:320px;
                    background:#111;color:white;padding:6px;border-radius:5px;">
            <h4 style="color:{base_color};margin:0 0 8px;
                       border-bottom:2px solid {base_color};padding-bottom:4px;">
                🚁 {node.nombre}
            </h4>
            <p style="margin:3px 0;"><b>🗺️ Coords:</b> {node.lat:.5f}, {node.lon:.5f}</p>
        </div>
        """
        iframe = folium.IFrame(html=popup_html, width=300, height=100)
        popup = folium.Popup(iframe, max_width=320)

        folium.Marker(
            location=[node.lat, node.lon],
            popup=popup,
            tooltip=f"🚁 {node.nombre}",
            icon=folium.DivIcon(
                html=f'<div style="font-size:28px;text-align:center;filter:drop-shadow(0 0 10px {base_color});">🚁</div>',
                icon_size=(36, 36),
                icon_anchor=(18, 18)
            )
        ).add_to(m)

    # 6. Leyenda flotante personalizada
    leyenda_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
         background:rgba(8,8,18,0.95);border:1px solid #FFD700;
         border-radius:10px;padding:15px 19px;
         font-family:'Segoe UI',sans-serif;color:white;font-size:12px;
         min-width:250px;box-shadow:0 4px 24px rgba(0,0,0,0.7);">
      <b style="color:#FFD700;font-size:14px;">🗺️ Red de Hospitales y Bases (Actualizado)</b>
      <hr style="border-color:#333;margin:8px 0;">
      <b style="color:#aaa;">Hospitales:</b> Marcadores de colores vibrantes<br>
      <hr style="border-color:#333;margin:8px 0;">
      <b style="color:#aaa;">Bases de drones:</b><br>
      <span style="color:#00FF88;">🚁</span> BASE NORTE<br>
      <span style="color:#00CFFF;">🚁</span> BASE CENTRO<br>
      <span style="color:#FF9F00;">🚁</span> BASE SUR<br>
      <hr style="border-color:#333;margin:8px 0;">
      <i style="color:#888;font-size:10px;">Clic en hospitales/bases → detalles</i>
    </div>
    """
    m.get_root().html.add_child(Element(leyenda_html))

    # Guardar mapa
    output_path = os.path.join(os.path.dirname(__file__), "grafo.html")
    m.save(output_path)
    print(f"Mapa generado con éxito en: {output_path}")

if __name__ == "__main__":
    generar_mapa()

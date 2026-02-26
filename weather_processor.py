import json
import os
import sys

# Agregar la carpeta 'lib' local al path para mantener la raíz limpia
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from aemet_client import AEMETClient

# Especificaciones del dron (extraidas de especificaciones_dron.txt)
MAX_TEMP = 45.0
MIN_TEMP = 0.0
# En la API AEMET velmedia y racha usualmente vienen en km/h o m/s. 
# Si el limite AEMET esta en m/s es directo. 
# Hay estaciones (como Retiro) donde racha es m/s y velmedia m/s. Trabajaremos en m/s = directo.
MAX_WIND_AVG = 15.0 # m/s
MAX_WIND_GUST = 20.0 # m/s
# Lluvia: asumimos > 12.7 mm en un dia como no operativo
MAX_PRECIP = 12.7 

def limpiar_float(valor_str):
    if not isinstance(valor_str, str):
        return valor_str
    try:
        if valor_str.lower() == 'ip': 
            return 0.0
        return float(valor_str.replace(',', '.'))
    except ValueError:
        return None

def analizar_viabilidad(datos_clima):
    total_dias = len(datos_clima)
    if total_dias == 0:
        return None

    dias_operativos = 0
    dias_tierra = 0
    causas_suelo = {
        'temperatura_alta': 0,
        'temperatura_baja': 0,
        'viento_medio': 0,
        'viento_racha': 0,
        'lluvia_fuerte': 0
    }

    for dia in datos_clima:
        # Asegurar datos limpios
        tmax = limpiar_float(dia.get('tmax'))
        tmin = limpiar_float(dia.get('tmin'))
        velmedia = limpiar_float(dia.get('velmedia'))
        racha = limpiar_float(dia.get('racha'))
        prec = limpiar_float(dia.get('prec'))

        vuelo_cancelado = False

        if tmax is not None and tmax > MAX_TEMP:
            causas_suelo['temperatura_alta'] += 1
            vuelo_cancelado = True
        
        if tmin is not None and tmin < MIN_TEMP:
            causas_suelo['temperatura_baja'] += 1
            vuelo_cancelado = True
            
        if velmedia is not None and velmedia > MAX_WIND_AVG:
            causas_suelo['viento_medio'] += 1
            vuelo_cancelado = True
            
        if racha is not None and racha > MAX_WIND_GUST:
            causas_suelo['viento_racha'] += 1
            vuelo_cancelado = True
            
        if prec is not None and prec > MAX_PRECIP:
            causas_suelo['lluvia_fuerte'] += 1
            vuelo_cancelado = True

        if vuelo_cancelado:
            dias_tierra += 1
        else:
            dias_operativos += 1

    return {
        'dias_analizados': total_dias,
        'dias_operacional': dias_operativos,
        'dias_no_vuelo': dias_tierra,
        'viabilidad_porcentaje': (dias_operativos / total_dias) * 100,
        'causas_cancelacion': causas_suelo
    }

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    
    # Permitir al usuario cambiar los meses pasando un número por consola (ej. python weather_processor.py 60)
    meses_historial = 6
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        meses_historial = int(sys.argv[1])
    
    print(f"Iniciando Fase 3: Extrayendo últimos {meses_historial} meses de datos (Estación 3195 Madrid Retiro)...")
    client = AEMETClient()
    datos = client.fetch_historical_data("3195", months_back=meses_historial)
    
    with open("datos_retiro_5y.json", "w", encoding='utf-8') as f:
        json.dump(datos, f)
        
    print(f"\nDatos descargados: {len(datos)} dias.")
    
    if len(datos) > 0:
        print("\nIniciando Fase 4: Analizando viabilidad frente a especificaciones_dron.txt...")
        resultado = analizar_viabilidad(datos)
        
        print("========== REPORTE DE VIABILIDAD OPERATIVA UAV ==========")
        print(f"Total dias analizados: {resultado['dias_analizados']}")
        print(f"Dias de Operacion Exitosa (SLA): {resultado['dias_operacional']}")
        print(f"Dias de Operacion En Tierra: {resultado['dias_no_vuelo']}")
        print(f"VIABILIDAD OPERATIVA GENERAL: {resultado['viabilidad_porcentaje']:.2f}%")
        print("---------------------------------------------------------")
        print("Desglose de Causas de Cancelacion:")
        print(f" - Temperatura extrema (>45C): {resultado['causas_cancelacion']['temperatura_alta']}")
        print(f" - Temperatura baja (<0C): {resultado['causas_cancelacion']['temperatura_baja']}")
        print(f" - Viento Promedio excesivo (>15m/s): {resultado['causas_cancelacion']['viento_medio']}")
        print(f" - Rachas de Viento (>20m/s): {resultado['causas_cancelacion']['viento_racha']}")
        print(f" - Precipitaciones severas (>12.7mm/dia): {resultado['causas_cancelacion']['lluvia_fuerte']}")
        print("=========================================================")
        
        with open("reporte_viabilidad.txt", "w", encoding='utf-8') as f:
            f.write("========== REPORTE DE VIABILIDAD OPERATIVA UAV ==========\n")
            f.write(f"Total dias analizados: {resultado['dias_analizados']}\n")
            f.write(f"Dias de Operacion Exitosa (SLA): {resultado['dias_operacional']}\n")
            f.write(f"Dias de Operacion En Tierra: {resultado['dias_no_vuelo']}\n")
            f.write(f"VIABILIDAD GENERAL: {resultado['viabilidad_porcentaje']:.2f}%\n")
            f.write("\nCausas:\n")
            for k, v in resultado['causas_cancelacion'].items():
                f.write(f" - {k}: {v}\n")

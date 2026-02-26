import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class AEMETClient:
    BASE_URL = "https://opendata.aemet.es/opendata/api"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("AEMET_API_KEY")
        if not self.api_key:
            raise ValueError("AEMET_API_KEY no encontrada en las variables de entorno ni pasada como argumento.")
        self.headers = {"api_key": self.api_key}

    def fetch_climate_data_batch(self, station_id, start_date, end_date):
        """
        Obtiene los datos climatológicos diarios para una estación en un rango de fechas.
        Rango máximo seguro en AEMET: usualmente menos de 5 años por petición (se recomienda 1-2 años).
        start_date, end_date: datetime objects
        """
        fmt = "%Y-%m-%dT%H:%M:%SUTC"
        start_str = start_date.strftime(fmt)
        end_str = end_date.strftime(fmt)
        
        endpoint = f"/valores/climatologicos/diarios/datos/fechaini/{start_str}/fechafin/{end_str}/estacion/{station_id}"
        url = self.BASE_URL + endpoint
        
        # 1. Solicitar el enlace de descarga (metadata)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        metadata = response.json()
        
        if metadata.get("estado") == 200 and "datos" in metadata:
            datos_url = metadata["datos"]
            # 2. Descargar los datos reales
            datos_response = requests.get(datos_url)
            datos_response.raise_for_status()
            
            # Si aemet devuelve vacio la lista a veces se porta mal
            try:
                data = datos_response.json()
                if isinstance(data, list):
                    return data
                return []
            except ValueError:
                return []
        else:
            print(f"Advertencia (AEMET): {metadata.get('descripcion', 'Error desconocido')}")
            return []

    def fetch_historical_data(self, station_id, months_back=60):
        """
        Descarga iterativamente los últimos N meses dividiendo las consultas
        para evitar límites de la API (Max. 6 meses por petición).
        """
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=months_back)
        
        all_data = []
        current_start = start_date
        
        while current_start < end_date:
            # Paginación segura de 5 meses para no tocar el límite de 6 meses
            current_end = min(current_start + relativedelta(months=5, days=-1), end_date)
            # Asegurar que el end de horario sea 23:59:59
            current_end = current_end.replace(hour=23, minute=59, second=59)
            
            print(f"Descargando datos para {station_id}: {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
            
            intentos = 0
            while intentos < 3:
                try:
                    batch_data = self.fetch_climate_data_batch(station_id, current_start, current_end)
                    all_data.extend(batch_data)
                    break # Éxito, salir del bucle de intentos
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        print("Rate limit alcanzado (429). Esperando 10 segundos...")
                        time.sleep(10)
                        intentos += 1
                    else:
                        print(f"Error HTTP: {e}")
                        break
                except Exception as e:
                    print(f"Error al descargar bache {current_start.strftime('%Y-%m-%d')}: {e}")
                    break
            
            # Respetar rate limits básicos
            time.sleep(2)
            
            # Avanzar al día siguiente
            current_start = current_end + timedelta(seconds=1)
            
        return all_data

if __name__ == "__main__":
    # Test rápido si se ejecuta directamente
    import sys
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    try:
        client = AEMETClient()
        # Estación Madrid, Retiro
        datos = client.fetch_historical_data("3195", years_back=1)
        print(f"Obtenidos {len(datos)} registros diarios.")
    except Exception as e:
        print(e)
        sys.exit(1)

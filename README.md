# UAV Medical Network Optimization

Simulador de una red de drones para transporte medico entre almacenes y
hospitales, y para misiones directas hospital-hospital como organos.

## Que incluye

- Red de hospitales y bases con distancias Haversine.
- Inventario hospitalario con politica de reposicion `(s, Q)`.
- Generador estocastico de consumos y eventos criticos.
- Cola de prioridad por urgencia, deadline y orden de llegada.
- Asignacion de drones segun bateria, carga, distancia, prioridad y clima.
- Motor de eventos discretos para vuelo, entrega, regreso y recarga.
- CLI para listar nodos, simular una mision o ejecutar una flota completa.

## Instalacion

```powershell
cd "C:\Users\User\Desktop\PROYECTO I\UAV-Medical-Network-Optimization-completo"
python -m pip install -r requirements.txt
```

`numpy` es necesario para el generador de pedidos. `matplotlib` solo se usa si
se piden graficas con `--graphs`. `pytest` es para ejecutar la suite de tests.

## Comandos principales

Listar hospitales:

```powershell
python main.py --list-hospitals
```

Mision individual:

```powershell
python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 3 --battery 100 --ignore-weather
```

Mision individual con clima simulado:

```powershell
python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 3 --battery 100 --date 2024-01-15
```

Simulacion de flota de 24 horas:

```powershell
python main.py --mode fleet --minutes 1440 --drones-per-base 2 --seed 42
```

Demo corta con pedidos desde el primer tramo:

```powershell
python main.py --mode fleet --minutes 60 --drones-per-base 1 --seed 42 --stock-near-threshold --verbose
```

Test de saturacion:

```powershell
python main.py --mode fleet --minutes 300 --call-probability 0.8 --drones-per-base 1 --stock-near-threshold --verbose
```

## Tests

```powershell
python -m unittest discover -s tests -p "test*.py"
```

Si `matplotlib` no esta instalado, el test de visualizaciones se salta de forma
controlada.

## Estructura

- `main.py`: punto de entrada y CLI.
- `controllers/`: controladores de mision individual y flota.
- `models/`: dataclasses y modelo de inventario.
- `services/`: red, bateria, recarga, asignacion y visualizaciones.
- `simulators/`: clima y generacion de pedidos.
- `tests/`: pruebas y demos de componentes.
- `hospitales_almacenes_data.py`: nodos de hospitales y bases.
- `parametros_globales.py`: parametros fisicos y de simulacion.

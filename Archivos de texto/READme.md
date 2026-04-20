# 🚁 Simulador de Red de Drones Hospitalarios

Este proyecto simula una red de drones para el transporte de material entre hospitales, incluyendo:

- Gestión de flota de drones
- Simulación de llamadas (envíos)
- Consumo y recarga de batería
- Red de hospitales y bases
- (Opcional) integración meteorológica

---

# 🧪 Tests básicos del sistema

Este documento recoge todos los comandos necesarios para comprobar que el sistema funciona correctamente.

---

## ⚙️ 1. Requisito previo

Antes de ejecutar los comandos:

cd C:\Users\User\Desktop\simulador\proyecto1

Y ejecutar siempre:

python main.py ...

---

## 🧪 2. Listar hospitales

Comando:
python main.py --list-hospitals

Qué hace:
Muestra todos los hospitales disponibles en la red.

Qué valida:
- main.py funciona
- NetworkService funciona
- network_data.py está bien conectado

Resultado esperado:
Hospitales disponibles:
 - La Paz
 - Gregorio Marañón
 - 12 de Octubre
 ...

---

## 🧪 3. Modo single (misión normal)

Comando:
python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 3 --battery 100 --ignore-weather

Qué hace:
Simula una misión entre dos hospitales con condiciones normales.

Qué valida:
- SimulationController
- cálculo de rutas
- cálculo de batería
- integración general

Resultado esperado:
========== RESULTADO MISIÓN ==========
Viable: SÍ
Base seleccionada: ...
Distancia total: X km
Tiempo estimado: X min
Batería final estimada: X%
Clima OK: True

---

## 🧪 4. Misión NO viable (batería insuficiente)

Comando:
python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 5 --battery 10 --ignore-weather

Qué hace:
Simula una misión con batería insuficiente.

Qué valida:
- lógica de restricciones
- validación de batería

Resultado esperado:
Viable: NO

--- Motivos / observaciones ---
 - Batería insuficiente

Si siempre sale "Viable: SÍ" → hay un bug en la lógica

---

## 🧪 5. Test con clima

Comando:
python main.py --mode single --origin "La Paz" --destination "Gregorio Marañón" --payload 3 --battery 100 --date 2024-01-15

Qué hace:
Simula una misión teniendo en cuenta condiciones meteorológicas.

Qué valida:
- weather_service
- aemet_client

Resultado esperado:
Clima OK: True
o
Clima OK: False

Si siempre da True → el clima no está conectado realmente

---

## 🧪 6. Simulación de flota (básico)

Comando:
python main.py --mode fleet --minutes 60

Qué hace:
Simula la red de drones durante 60 minutos.

Qué valida:
- FleetController
- RandomCallsSimulator
- flujo general

Resultado esperado:
========== FIN SIMULACIÓN ==========
Total llamadas: X
Asignadas: X
Rechazadas: X
Completadas: X

Si Total llamadas = 0 → el generador de llamadas falla

---

## 🧪 7. Simulación con eventos (verbose)

Comando:
python main.py --mode fleet --minutes 60 --call-probability 0.5 --verbose

Qué hace:
Muestra eventos en tiempo real: llamadas, asignaciones, estados.

Resultado esperado:
[t=0001] CALL ... Drone D1 ...
[t=0060] STATUS | available=X | mission=X | charging=X

Qué valida:
- asignación de drones
- estados de drones
- impresión correcta

---

## 🧪 8. Test de estrés (saturación)

Comando:
python main.py --mode fleet --minutes 300 --call-probability 0.8 --drones-per-base 1 --verbose

Qué hace:
Fuerza saturación del sistema.

Resultado esperado:
Muchas llamadas rechazadas.

Qué valida:
- límites del sistema
- capacidad real de la flota

---

## 🧪 9. Test de batería y carga

Comando:
python main.py --mode fleet --minutes 200 --call-probability 0.6 --verbose

Qué hace:
Permite observar consumo de batería y recarga.

Resultado esperado:
drones con:
status=charging

Qué valida:
- battery_service
- charging_service

---

# 🚨 Señales de error (red flags)

Si ves esto, algo está mal:

- Siempre viable en modo single → no hay validación real
- Nunca se asignan drones → dispatcher roto
- Batería nunca baja → battery_service no se usa
- Nunca aparece "charging" → charging_service no conectado
- Siempre hay drones disponibles → update_time no funciona

---

# 🧠 Objetivo real de estos tests

No estás solo probando prints.

Estás validando:

- generación de eventos
- asignación de recursos
- evolución temporal
- restricciones físicas (batería)
- restricciones externas (clima)

---

# 🚀 Siguiente paso

Una vez que estos tests funcionen:

→ Revisar simulation_controller.py
→ Revisar fleet_controller.py

Ahí es donde se valida si el sistema es realista o solo simulado superficialmente.
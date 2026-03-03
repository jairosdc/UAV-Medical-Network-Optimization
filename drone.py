def autonomia(carga):
   
    return 94 - (22 * carga) / 4.7

def bateria_restante(carga, distancia, bateria_actual):
   
    consumo = (distancia / autonomia(carga)*100)
    return bateria_actual - consumo

print(bateria_restante(3, 8, 100))

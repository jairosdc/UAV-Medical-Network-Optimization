# Información en cada uno de los archivos ahora vigentes

En este markdown se especifica lo que hace y tiene cada uno de los archivos

## clases_models

Esta clase tiene lo que serian los init de todas las clases, no tiene logica de programación, simplemente guarda los datos de estado de todos los objetos globales que tenemos en juego en el proyecto

## Inventario

Este archivo contiene El modelo de inventario de hospitales y almacenes y la logica de reposición a los hospitales de los almacenes

## cargar_drone_service

Este archivo contiene la que sería la logica de carga del dron, cuando tiene menos de x% de bateria se pone a cargar y en este archivo se establece esta logica de carga

## Funcionamiento_bateria_service

Este archivo tiene toda la logica de consumo de bateria del dron y si puede volar o no en funcion de la bateria que le queda

## grafo_distancias_service

Este archivo calcula las distancias entre todos los hospitales y almacenes 

## meteorologia_service

Este archivo debe ser revisado, debemos establecer un modelo meteorologico pero antes de eso vamos a buscar que el simulador haga una simulacion mas simple y ya le añadiremos variables meteorologicas. En concreto este archivo accede a la api de la aemet y traspasa al simulador el tiempo que hace en cada momento con los parametros maximos que admite que se pueda volar. esto necesita una revision exhaustiva

## Optimizador_asignacion_service

Este archivo es muy importante, calcula cual es el mejor dron para que haga el servicio entre hospitales

## Generador_pedidos

Este archivo es muy importante y debe ser revisado tambien. En principio alberga las tasas de consumo de los elementos, el nivel de prioridad de cada elemento, y cual es el estres del sistema en 6 tramos horarios. Por otra parte establece la logica de generacion de pedidos entre hospitales pero esa logica hay que revisarla

## aemet_client

alberga la api de la aemet

## clases

alberga las clases iniciales, sirve de bloque pero en principio no hay que usarlo ni nada, pero por si acaso no lo vamos a borrar

## grafo

contiene el grafo en la web

## hospitales_almacenes_data

contiene un diccionario de los hospitales y donde se encuentran, latitud altitud, barrio y nombre. Lo mismo para almacenes ahi se albergan todos, entonces si queremos añadir o quitar alguno se hace ahi (ez)

## main

simulador inicial, hay que revisarlo tambien

## Parametros_globales

Contiene los parametros globales que se usaran en muchos de los archivos
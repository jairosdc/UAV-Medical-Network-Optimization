establecemos los siguientes parámetros:

- $C \equiv \text{Carga que lleva el drone}$
- $D \equiv \text{Distancia que recorrerá el drone}$
- $B_0 \equiv \text{Batería que tiene el drone justo antes de salir}$


$$
A(c) \equiv \text{Autonomía que tiene el drone en funcion de la carga}
$$
$$
A(C) = 94 - \frac{22C}{4.7}
$$

$$
B(C, D, B_0) \equiv \text{Batería que le quedará al drone tras haber recorrido una distancia $D$ con una carga $C$}
$$

$$
B(C, D, B_0) = B_0 - \frac{100D}{A(C)}
$$
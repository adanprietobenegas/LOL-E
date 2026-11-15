"""Atajo: el cliente falso vive ahora en demo_cliente.py (en la raíz, porque la demostración de la app lo usa y viaja dentro del programa). Este archivo sirve para que
`import cliente_falso` siga funcionando en las herramientas y las pruebas: devuelve el mismo módulo."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import demo_cliente

sys.modules[__name__] = demo_cliente

"""Dominio PURO de la verificacion biometrica de identidad (C-09).

Logica de negocio sin framework ni infraestructura (D1, test_architecture):
- ``matching``: distancia coseno + decision de match con umbral conservador.
- ``liveness``: gate del liveness hibrido (pasivo + retos activos) como
  prerrequisito obligatorio de la comparacion 1:1.
- ``retries``: maquina de reintentos acotada (max 2) con escalacion al 3.º fallo,
  sin abort ni sancion automatica (L2.5).
- ``custody``: hash + firma del clip y derivacion HMAC de la clave de sesion
  rotativa (contratos puros; la cripto concreta la opera infraestructura).

El motor de vision (MediaPipe / ONNX) y el KMS viven en infraestructura/cliente;
aqui solo se modelan los CONTRATOS y las REGLAS, sin importar cripto ni red.
"""

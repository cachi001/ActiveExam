"""Casos de uso de la cadena de custodia de evidencia (C-12).

Orquestan las 4 etapas sobre los PUERTOS del dominio: etapa 2 sincrona en el backend
(verifica HMAC del cliente + re-hash + deposito WORM + audit log + encola) y el
worker asincrono (etapas 3/4: firma maestra + re-inferencia firmada). La deteccion de
hash divergente emite el evento critico de manipulacion (RN-CC-03).
"""

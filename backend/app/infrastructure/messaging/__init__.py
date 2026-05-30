"""Adaptadores de mensajeria detras de un PUERTO abstracto.

DECISION PENDIENTE (critica): la pieza de cola/transporte/backplane NO esta
decidida por C-04. La define la PoC de carga **C-03** por metrica.

- ``port.py`` define el puerto abstracto (``MessageQueuePort``).
- ``postgres_queue.py`` es el adaptador por OMISION (hipotesis A4 = Postgres
  como cola via ``SELECT ... FOR UPDATE SKIP LOCKED`` + ``LISTEN/NOTIFY``),
  alineado con DD-19 (empezar simple, no over-provisionar).

El adaptador es SWAPPABLE: si C-03 promueve RabbitMQ+Celery o Redis, se agrega
un nuevo adaptador que implemente el mismo puerto y se selecciona por config
(``MESSAGING_BACKEND``). NO se levanta Redis/RabbitMQ por defecto en el compose.
"""

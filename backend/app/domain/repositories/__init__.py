"""Puertos de repositorio (PUROS): interfaces del dominio para la persistencia.

Hexagonal (`08` Patrones, D6): el dominio define el CONTRATO de persistencia como
puertos (ABCs) y la infraestructura provee los ADAPTADORES SQLAlchemy en
``app.infrastructure.persistence.repositories``. El dominio NO importa SQLAlchemy.

Invariantes codificadas en los puertos (D5, DD-07):
- El puerto del Audit log es SOLO-APPEND (sin update/delete): coherente con el
  trigger de la base.
- El puerto del Consentimiento NO expone update: coherente con su inmutabilidad.
"""

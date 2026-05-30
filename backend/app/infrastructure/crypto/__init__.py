"""Adaptadores criptograficos de infraestructura (C-12).

Aqui vive la dependencia del SDK criptografico real (``cryptography`` /
``PyNaCl`` para RSA-2048/Ed25519). El dominio (``app.domain.evidence``) define los
PUERTOS; estos adaptadores los implementan inyectando la clave maestra que custodia
Vault. NUNCA se hardcodea una clave (regla dura).
"""

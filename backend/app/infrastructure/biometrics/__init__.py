"""Adaptadores de infraestructura de la verificacion biometrica (C-09).

- ``KmsCipher``: contrato de cifrado/descifrado at-rest del embedding (KMS, D5).
- ``EncryptedReferenceReader``: lee el embedding de referencia cifrado y lo
  descifra via KMS para la comparacion server-side.
- ``VaultSecretProvider``: entrega el secreto maestro inyectado (Vault/tmpfs),
  NUNCA hardcodeado.

El cifrado concreto (KMS/Vault Transit) se cablea en produccion; aqui se deja el
contrato + un adaptador determinista para tests sin red.
"""

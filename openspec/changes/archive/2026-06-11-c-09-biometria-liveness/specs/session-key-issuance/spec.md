# Spec — session-key-issuance

> Emisión de la clave de sesión rotativa (HMAC) cuando la verificación es exitosa, que firma los eventos posteriores (RN-BIO-02).

## ADDED Requirements

### Requirement: Emisión de la clave de sesión rotativa al verificar
El sistema SHALL emitir una clave de sesión rotativa (HMAC) únicamente cuando la comparación 1:1 re-inferida en el backend da una distancia menor que el umbral; esa clave SHALL habilitar el examen y servir para firmar los eventos y la evidencia posteriores (RN-BIO-02, US-004 CA-4).

#### Scenario: Verificación exitosa emite la clave de sesión
- **WHEN** la re-inferencia server-side confirma la comparación 1:1 bajo el umbral
- **THEN** el backend emite la clave de sesión rotativa y habilita el examen

#### Scenario: Verificación fallida no emite clave
- **WHEN** la comparación 1:1 no es exitosa
- **THEN** el backend no emite clave de sesión y el examen no queda habilitado en ese intento

#### Scenario: La clave de sesión firma la telemetría posterior
- **WHEN** se emite la clave de sesión rotativa tras verificar la identidad
- **THEN** los eventos y la evidencia posteriores quedan firmados con esa clave, atando la telemetría a la identidad verificada

"""Cadena de custodia de 4 etapas acumulativas (PURO, RN-CC-02/03, DD-07).

Materializa el Flujo 4 como logica de dominio pura (stdlib): hash SHA-256 del
artefacto de evidencia, verificacion del hash en cada handoff (etapa 2 backend,
etapa 3 worker) y el ensamblaje ACUMULATIVO de la ``Evidencia`` (las firmas se
ENCADENAN, no se reemplazan). La divergencia de hash en CUALQUIER etapa levanta
``ManipulacionDetectada`` para que la aplicacion emita el evento critico
"evidencia corrupta o manipulada" (RN-CC-03) y NUNCA la descarte en silencio.

CAMBIO C-24 (DD-24-01, DD-24-03): el artefacto de evidencia pasa de CLIP de
video (5-10 s) a SCREENSHOT (frame unico PNG/JPEG). El contrato de la cadena NO
cambia: hash SHA-256 del binario de imagen en cliente (etapa 1), re-hash en
backend (etapa 2) y re-hash + firma maestra en worker (etapa 3). Lo que SI cambia
es la re-inferencia (etapa 4): pasa de un pipeline TEMPORAL (sobre el clip) a
una inferencia ESTATICA sobre el frame (deteccion de rostros/objetos en la imagen,
sin secuencia temporal). Tradeoff L2.5 aceptado explicitamente: se pierde
re-verificacion de liveness/movimiento; se gana minimizacion de datos
(Ley 25.326, proporcionalidad). Ver design.md de c-24-evidencia-screenshots.

La firma maestra ASIMETRICA (RSA-2048/Ed25519) y la re-inferencia server-side son
operaciones de infraestructura: aqui solo viven sus PUERTOS abstractos. El dominio
no conoce ``cryptography`` ni el modelo de vision (PUREZA / D1). La clave maestra la
custodia Vault y NUNCA se hardcodea: el adaptador la recibe inyectada.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from app.domain.entities.evidence import Evidencia

# Severidad del evento de manipulacion (conforme al contrato de eventos C-10).
SEVERIDAD_CRITICA = "critica"
TIPO_EVIDENCIA_MANIPULADA = "evidencia_corrupta_o_manipulada"


class ManipulacionDetectada(ValueError):
    """Hash divergente en alguna etapa de la cadena (RN-CC-03).

    Lleva la ``etapa`` ("backend" | "worker") donde se detecto la divergencia para
    que la aplicacion registre la traza forense y emita el evento critico."""

    def __init__(self, etapa: str, esperado: str, calculado: str) -> None:
        super().__init__(
            f"hash divergente en etapa '{etapa}': "
            f"esperado={esperado[:12]}... calculado={calculado[:12]}..."
        )
        self.etapa = etapa
        self.esperado = esperado
        self.calculado = calculado


class MasterSignerPort(ABC):
    """Puerto de firma maestra ASIMETRICA (RSA-2048/Ed25519, clave de Vault).

    La clave privada la custodia Vault (inyectada en el adaptador); el dominio solo
    invoca firmar/verificar. ``verificar`` usa la clave PUBLICA para que un perito
    externo (C-18) valide sin acceder al secreto (RN-CC, D6)."""

    @abstractmethod
    def firmar(self, mensaje: bytes) -> str:
        """Firma ``mensaje`` con la clave maestra privada. Devuelve la firma (hex/b64)."""

    @abstractmethod
    def verificar(self, mensaje: bytes, firma: str) -> bool:
        """Verifica ``firma`` sobre ``mensaje`` con la clave PUBLICA (perito externo)."""


class ServerInferencePort(ABC):
    """Puerto de re-inferencia server-side (la version CONFIABLE del analisis).

    CAMBIO C-24 (DD-24-01, DD-24-03): la re-inferencia pasa de un pipeline TEMPORAL
    (sobre el clip de video) a una inferencia ESTATICA sobre el FRAME (imagen PNG/JPEG).
    El worker ejecuta deteccion de rostros y objetos sobre el frame exacto (sin
    secuencia temporal). Esta es la etapa 4 de la cadena de custodia sobre el nuevo
    binario imagen.

    Tradeoff L2.5 aceptado (design.md c-24): no hay re-verificacion de liveness ni
    contexto temporal; la evidencia es suficiente y proporcional para revision humana.

    El motor concreto (DD-17) vive en infra; el dominio solo ve el contrato
    (bytes del artefacto -> dict de salida del modelo)."""

    @abstractmethod
    def inferir(self, artefacto_bytes: bytes) -> dict[str, str]:
        """Ejecuta la re-inferencia server-side sobre el artefacto (frame PNG/JPEG
        en C-24, o clip en versiones anteriores) y devuelve el output del modelo.

        El output DEBE incluir al menos las claves 'labels' y 'confidences' (como
        JSON serializable) para que pueda compararse con lo reportado por el cliente
        en la notificacion de evidencia (tarea 3.3, senal forense de discrepancia).
        """


def hash_clip(clip_bytes: bytes) -> str:
    """SHA-256 (hex) del binario del artefacto (screenshot desde C-24, clip antes).

    El nombre se mantiene por retrocompatibilidad; el algoritmo es identico."""
    return hashlib.sha256(clip_bytes).hexdigest()


def verificar_hash(*, etapa: str, esperado: str, clip_bytes: bytes) -> str:
    """Recalcula el hash del clip y lo compara con el ``esperado`` de la etapa previa.

    Devuelve el hash recalculado si coincide; levanta ``ManipulacionDetectada`` si
    diverge (RN-CC-03). La manipulacion NUNCA se descarta en silencio: el caller
    captura la excepcion y emite el evento critico + traza forense."""
    calculado = hash_clip(clip_bytes)
    if not _comparacion_constante(esperado, calculado):
        raise ManipulacionDetectada(etapa=etapa, esperado=esperado, calculado=calculado)
    return calculado


def aplicar_etapa2(
    evidencia: Evidencia,
    *,
    clip_bytes: bytes,
) -> Evidencia:
    """Etapa 2 (backend): re-hashea el clip y, si coincide con ``hash_cliente``,
    fija ``hash_backend`` de forma ACUMULATIVA (sin tocar los campos de cliente).

    Asume que la firma HMAC del cliente ya fue validada por la aplicacion (zero
    trust). Levanta ``ManipulacionDetectada`` si el hash diverge."""
    if not evidencia.hash_cliente:
        raise ValueError("etapa 2 requiere hash_cliente de la etapa 1")
    hash_backend = verificar_hash(
        etapa="backend", esperado=evidencia.hash_cliente, clip_bytes=clip_bytes
    )
    return replace(evidencia, hash_backend=hash_backend)


def aplicar_firma_maestra(
    evidencia: Evidencia,
    *,
    clip_bytes: bytes,
    signer: MasterSignerPort,
) -> Evidencia:
    """Etapa 3 (worker): 3.a verificacion de hash contra ``hash_backend`` y firma
    maestra ASIMETRICA del hash. Fija ``firma_maestra`` ACUMULATIVA.

    Levanta ``ManipulacionDetectada`` si el hash diverge (RN-CC-03)."""
    if not evidencia.hash_backend:
        raise ValueError("etapa 3 requiere hash_backend de la etapa 2")
    verificado = verificar_hash(
        etapa="worker", esperado=evidencia.hash_backend, clip_bytes=clip_bytes
    )
    firma_maestra = signer.firmar(verificado.encode("utf-8"))
    return replace(evidencia, firma_maestra=firma_maestra)


def aplicar_reinferencia(
    evidencia: Evidencia,
    *,
    clip_bytes: bytes,
    inferencia: ServerInferencePort,
    signer: MasterSignerPort,
) -> Evidencia:
    """Etapa 4 (C-24 DD-24-03): re-inferencia server-side ESTATICA sobre el frame +
    firma del output + comparacion con lo reportado por el cliente (senal forense).

    CAMBIO C-24: la inferencia opera sobre un FRAME UNICO (imagen PNG/JPEG), no sobre
    un clip temporal. El output del modelo (labels, confidences) se compara con los
    labels reportados por el cliente en la notificacion de evidencia. Una discrepancia
    es una SENAL FORENSE de posible tampering: se registra firmada junto al output.
    NO dispara sancion automatica (L2.5 — la decision es siempre humana).

    El output firmado es la VERSION CONFIABLE del analisis (no la del cliente,
    RN-GLB-01). Se persiste como ``output_reinferencia`` con su firma, de forma
    acumulativa (sin tocar las etapas previas).
    """
    salida = inferencia.inferir(clip_bytes)

    # Comparar con los labels reportados por el cliente (si existen en meta, tarea 3.3).
    # La discrepancia se registra como senal forense firmada; NO causa sancion (L2.5).
    labels_cliente = evidencia.meta.get("labels_cliente") if evidencia.meta else None
    discrepancia: dict[str, object] = {}
    if labels_cliente is not None:
        labels_servidor = salida.get("labels", "")
        if labels_cliente != labels_servidor:
            discrepancia = {
                "discrepancia_labels": True,
                "labels_cliente": labels_cliente,
                "labels_servidor": labels_servidor,
                # Nota: discrepancia es senal forense, NO implica sancion automatica (L2.5).
            }

    payload = _canonico_output(salida)
    firma_output = signer.firmar(payload.encode("utf-8"))
    output: dict[str, object] = {**salida, "firma_output": firma_output, **discrepancia}
    return replace(evidencia, output_reinferencia=output)


def cadena_completa(evidencia: Evidencia) -> bool:
    """True sii las CUATRO etapas coexisten (RN-CC-02): hash+firma cliente,
    hash backend, firma maestra y output de re-inferencia firmado. Insumo para C-18."""
    return bool(
        evidencia.hash_cliente
        and evidencia.firma_cliente
        and evidencia.hash_backend
        and evidencia.firma_maestra
        and evidencia.output_reinferencia.get("firma_output")
    )


def _canonico_output(salida: dict[str, str]) -> str:
    """Serializa el output de re-inferencia de forma determinista para firmarlo."""
    return "|".join(f"{k}={salida[k]}" for k in sorted(salida))


def _comparacion_constante(a: str, b: str) -> bool:
    """Compara dos hashes hex en tiempo constante (anti timing-attack)."""
    import hmac

    return hmac.compare_digest(a, b)

# Proposal — C-01 `acuerdo-proctoring-dpia`

> **Naturaleza del change**: gate **organizacional de Fase 0**, governance **CRÍTICO**, **NO-CÓDIGO**. No produce software de dominio. Sus entregables son documentos legales/administrativos firmados y aprobados. Sin ellos, el proyecto **no sale de Fase 0** y ningún otro change puede comenzar.

## Why

El factor de riesgo dominante del proyecto **no es tecnológico sino organizacional y legal**: la brecha entre expectativas del cliente y capacidades reales (L-004) y el tratamiento de datos biométricos bajo la Ley 25.326 (L-001, L-002). Antes de escribir una sola línea de código de dominio se deben **congelar las decisiones estructurales** (los 14 ADRs Tier 1 + las 5 revisiones A4), **calibrar contractualmente las expectativas** (Acuerdo de Nivel de Proctoring L2.5) y **validar legalmente el tratamiento** (DPIA por el DPO/área legal). Saltar esta fase es la causa número uno de fracaso de un sistema de proctoring: o se construye sobre una base legal frágil, o se entrega algo que no coincide con lo que el patrocinador creía comprar.

Este change es el **gate de entrada** de todo el roadmap: bloquea C-02..C-20.

## What Changes

Este change **no modifica código**. Formaliza y deja firmados/aprobados los siguientes artefactos de governance:

- **Acuerdo de Nivel de Proctoring (nivel L2.5)** firmado por patrocinador + dirección académica + proveedor (DD-01 / DD-14). Calibra expectativas, declara finalidad acotada, delimita responsabilidad y fija los límites deliberados del sistema (sin video continuo, sin lockdown, **sin sanción automática**).
- **DPIA (Evaluación de Impacto en Protección de Datos)** completo y **aprobado por el DPO/área legal** antes de codificar dominio (Ley 25.326, Decreto 1558/2001, AAIP). Incluye base legal del tratamiento, análisis de proporcionalidad (lección caso SRFP), derechos del titular y registro de la base ante la AAIP.
- **Acta de aprobación formal de los 19 ADRs**: 14 ADRs Tier 1 (**DD-01…DD-14**) + 5 revisiones del análisis independiente A4 (**DD-15…DD-19**). Cada ADR queda marcado como `Aprobado` y se vuelve decisión congelada que gobierna las fases siguientes.
- **Clasificación formal del embedding facial como dato sensible por defecto** ("responsabilidad reforzada"), resolviendo IN-04 a favor de SU-08, documentada y firmada por el DPO (aunque la Resolución AAIP 4/2019 podría no exigirlo siempre).
- **Decisión documentada sobre la vía alternativa de verificación sin biometría** (proctor humano en vivo) para garantizar consentimiento genuinamente libre, y sobre la **existencia de población menor de 18** (y, de haberla, requerir flujo de consentimiento parental y retención diferenciada antes de Fase 1).
- **Inscripción de las bases de datos ante el Registro Nacional de Bases de Datos de la AAIP** iniciada/planificada por legal.

**BREAKING (gate)**: hasta que los entregables estén firmados/aprobados, **ningún change posterior puede iniciar implementación**. Es un bloqueo deliberado, no una regresión técnica.

## Capabilities

> Estas "capabilities" son de **governance/compliance documental**, no de software. Cada una representa un artefacto formal cuyo estado (firmado/aprobado) es verificable. No introducen código ni endpoints; fijan el contrato organizacional y legal sobre el que se construirá el sistema.

### New Capabilities

- `proctoring-level-agreement`: el Acuerdo de Nivel de Proctoring L2.5 como contrato vivo — expectativas calibradas, finalidad acotada, límites deliberados y RACI de responsabilidad (DD-01, DD-14).
- `dpia-legal-compliance`: el DPIA y el paquete de cumplimiento Ley 25.326 — base legal, proporcionalidad, derechos del titular, inscripción AAIP, soberanía de datos.
- `adr-approval-baseline`: la línea base de decisiones de arquitectura aprobada — los 19 ADRs (DD-01…DD-19) congelados como contrato técnico de las fases siguientes.
- `sensitive-data-classification`: la clasificación formal del embedding como dato sensible por defecto y las consecuencias de "responsabilidad reforzada" (cifrado at-rest, minimización, no reutilización) — resolución de IN-04 / SU-08.
- `alternative-verification-path`: la decisión sobre la vía alternativa sin biometría y el tratamiento de población menor de 18, que condiciona el flujo de consentimiento de C-08.

### Modified Capabilities

<!-- Ninguna. No existen specs previas en openspec/specs/ y este change no modifica requisitos de capacidades existentes. -->

(Ninguna — es el primer change del proyecto; no hay specs previas que modificar.)

## Impact

- **Bloquea**: todos los changes del roadmap (C-02…C-20). Es el gate de salida de Fase 0 junto con C-02 (designación de revisores) y C-03 (PoC de carga).
- **Dependencias entrantes**: ninguna. Puede iniciarse de inmediato y corre en paralelo a C-02.
- **Decisiones que congela** (consumidas downstream):
  - DD-01/DD-04 → nivel L2.5 y anti-tampering pasivo (C-04, C-11).
  - DD-03/DD-18 + clasificación sensible → biometría/liveness y manejo del embedding (C-09).
  - DD-05/DD-06→DD-15 → TimescaleDB + Postgres-como-cola (C-03, C-10).
  - DD-08→DD-16 → SSE + backplane para el panel (C-03, C-15).
  - DD-07 → cadena de custodia WORM (C-12, C-18).
  - DD-09 → Keycloak (C-06).
  - DD-13 + DPIA → privacidad por diseño, retención, DSR (C-08, C-17, C-19).
- **Actores/sistemas afectados**: patrocinador, dirección académica, DPO/área legal, AAIP (registro de bases), equipo técnico (recibe los ADRs congelados como contrato). No afecta código ni infraestructura todavía.
- **Riesgos mitigados**: L-001 (cambio regulatorio), L-002 (caso en justicia ordinaria), L-004 (brecha de expectativas), y el riesgo legal de tratar biometría sin base validada.

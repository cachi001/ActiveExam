# Gate operativo — Medir antes de cualquier cierre masivo (C-72 tarea 8.7)

El auto-cierre (sección 4) finaliza sesiones activas vencidas (`finalizada_en IS NULL`
y `now > deadline_efectivo + gracia`). **Antes** de activarlo de forma masiva en
producción hay que medir cuántas sesiones caen en el barrido, para no certificar de
golpe un volumen inesperado sin revisión humana (L2.5, regla #5).

`deadline_efectivo = min(creada_en + tiempo_limite_min, cierre)` — ambos pueden ser
NULL (sin límite / sin ventana). Gracia por defecto: `DEADLINE_GRACIA_SEG` (60 s).

## Medición (correr contra la DB de PRODUCCIÓN, solo lectura)

```sql
-- Cuántas sesiones activas vencidas serían cerradas por el barrido.
SELECT count(*) AS candidatas_a_cierre
FROM proctoring_session ps
JOIN examen_contenido ec ON ec.id = ps.examen_contenido_id
WHERE ps.finalizada_en IS NULL
  AND now() > LEAST(
        ps.creada_en + make_interval(mins => ec.tiempo_limite_min),
        ec.cierre
      ) + make_interval(secs => 60);  -- = DEADLINE_GRACIA_SEG
```

Desglose por examen (para ver si el volumen se concentra en uno):

```sql
SELECT ps.examen_contenido_id, count(*) AS candidatas
FROM proctoring_session ps
JOIN examen_contenido ec ON ec.id = ps.examen_contenido_id
WHERE ps.finalizada_en IS NULL
  AND now() > LEAST(
        ps.creada_en + make_interval(mins => ec.tiempo_limite_min),
        ec.cierre
      ) + make_interval(secs => 60)
GROUP BY ps.examen_contenido_id
ORDER BY candidatas DESC;
```

## Criterio de activación

- **Cero candidatas** → activar sin fricción.
- **Volumen esperable** (sesiones que el alumno abandonó y no volvió) → activar; el
  auto-cierre solo cierra, no sanciona (el score prioriza, el veredicto es humano).
- **Volumen anómalo** (pico inesperado) → NO activar el barrido masivo; investigar
  primero (¿un examen mal configurado? ¿un incidente de conectividad?). El cierre
  lazy por-request (al tocar cada sesión) sigue funcionando mientras tanto.

> En la DB `dev` (slim) las tablas de sesión son efímeras (las crean las fixtures de
> test), por eso esta medición no aplica ahí: es un gate de producción.

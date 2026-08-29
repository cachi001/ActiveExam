"""0103 - repuebla `evento_score_config` y baja los pesos por defecto.

Revision ID: 0103
Revises: 0102
Create Date: 2026-08-29

## Por que

Dos problemas distintos que se arreglan juntos.

**1. La tabla quedo vacia.** El seed original vive en la migracion 0011, que ya
corrio (alembic esta en 0102), asi que al recrear/limpiar la base de desarrollo
las filas se perdieron y no vuelven solas. Sintoma: Configuracion > Scoring dice
"No hay configuracion de scoring cargada" y el administrador no puede tocar
ningun peso. El scoring seguia funcionando por la red de seguridad de
`PESOS_SEVERIDAD` (application/proctoring/scoring.py), asi que nada fallaba a la
vista — solo dejaba de ser configurable.

**2. Los pesos por defecto eran altos.** Decision del dueno (29/8/2026): bajarlos.
Con los originales, DOS eventos "alta" (50 + 50) llegaban a 100 y saturaban el
score; un solo `corte_conectividad_prolongado` (100) mandaba la sesion a revision
por si solo, aunque un corte de internet no es una senal de fraude. Los nuevos
dejan que haga falta un PATRON de eventos, no un incidente aislado.

| tipo                          | antes | ahora |
|-------------------------------|-------|-------|
| perdida_de_foco               |     5 |     3 |
| mirada_desviada_sostenida     |    20 |    11 |
| salida_pantalla_completa      |    20 |    11 |
| rostro_ausente                |    20 |    12 |
| cambio_pestana                |    20 |    12 |
| copiar_pegar                  |    20 |    15 |
| monitor_adicional             |    50 |    31 |
| multiples_rostros             |    50 |    35 |
| corte_conectividad_prolongado |   100 |    61 |

## Por que estos numeros y no mas bajos

El peso NO es libre: la severidad le fija una banda, y esa banda es institucional
(`RANGOS_SEVERIDAD` en el front, `SEVERITY_RANGES` en
`app/domain/scoring/risk_score.py`) — baja 1-10, media 11-30, alta 31-60, critica
61-100. Un evento "alta" no puede pesar 25 sin dejar de ser "alta". Asi que cada
uno baja hasta el piso de SU banda, o cerca.

Referencia para leerlos: el umbral de revision valido arranca en 70 (el backend
valida [70, 100]). Con estos pesos hace falta un PATRON: dos "multiples rostros"
llegan a 70; un corte de conectividad solo, que antes pesaba 100 y mandaba la
sesion a revision por si mismo, ahora suma 61 y no alcanza.

## Por que UPSERT y no `DO NOTHING`

Primero se escribio con `ON CONFLICT DO NOTHING`, para no pisar ajustes de un
administrador. Estaba mal, y se vio probando la migracion contra una base LIMPIA:
la 0011 siembra los pesos VIEJOS antes, asi que `DO NOTHING` no hacia nada y una
base nueva nacia con 20/50/100 otra vez. El arreglo solo funcionaba en la base de
desarrollo, donde la tabla estaba vacia por casualidad.

Como estos son los defaults del producto (decision del dueno: "que queden como
seed asi"), la migracion los IMPONE con `DO UPDATE`. Corre una sola vez; los
ajustes que un administrador haga DESPUES se conservan.

No toca `recarga_pagina` (2) ni `reanudacion_tardia` (11): ya estan bajos y no
formaban parte de la decision.

L2.5: el score PRIORIZA la revision humana, nunca sanciona. Bajar los pesos
cambia cuantas sesiones se miran primero, no la consecuencia de mirarlas.

ROLLBACK: `downgrade` NO borra nada. Las filas son configuracion del sistema y
borrarlas dejaria la pantalla de scoring vacia otra vez, que es justo el defecto
que esta migracion viene a corregir.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


#: (tipo_evento, severidad, peso, descripcion).
#:
#: Los pesos NO son libres: la migracion 0021 puso un CHECK a nivel DB que ata
#: cada peso a la banda de su severidad (baja 1-10, media 11-30, alta 31-60,
#: critica 61-100). Un valor fuera de banda revienta con 23514 al migrar — que es
#: como se descubrio que los primeros numeros de esta migracion eran invalidos.
_SEEDS: list[tuple[str, str, int, str]] = [
    ("perdida_de_foco", "baja", 3, "La ventana del examen perdio el foco del sistema operativo."),
    ("mirada_desviada_sostenida", "media", 11, "Patron de mirada sostenido hacia un punto fijo fuera de pantalla."),
    ("salida_pantalla_completa", "media", 11, "El estudiante salio del modo de pantalla completa."),
    ("rostro_ausente", "media", 12, "No se detecto rostro en el encuadre por mas de 3 segundos."),
    ("cambio_pestana", "media", 12, "El estudiante cambio o abrio otra pestana durante el examen."),
    ("copiar_pegar", "media", 15, "Se detecto una accion de copiar o pegar (sin capturar contenido)."),
    ("monitor_adicional", "alta", 31, "Se detecto un segundo monitor conectado al equipo."),
    ("multiples_rostros", "alta", 35, "Se detectaron multiples rostros simultaneos en camara."),
    (
        # Sigue siendo "critica" (su banda es 61-100) aunque un corte de internet
        # no sea una senal de fraude. Bajarle la severidad seria mas correcto,
        # pero el catalogo del cliente tambien la declara critica y hay que
        # cambiar las dos puntas a la vez: queda anotado, no se hace de costado.
        "corte_conectividad_prolongado",
        "critica",
        61,
        "Se perdio la conexion con el servidor por un periodo prolongado.",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for tipo, severidad, peso, descripcion in _SEEDS:
        conn.execute(
            sa.text(
                "INSERT INTO evento_score_config "
                "(tipo_evento, severidad, peso, descripcion, activo) "
                "VALUES (:tipo, :sev, :peso, :desc, true) "
                "ON CONFLICT (tipo_evento) DO UPDATE SET "
                "  severidad = EXCLUDED.severidad, "
                "  peso = EXCLUDED.peso, "
                "  descripcion = EXCLUDED.descripcion, "
                "  updated_at = now()"
            ),
            {"tipo": tipo, "sev": severidad, "peso": peso, "desc": descripcion},
        )


def downgrade() -> None:
    """No-op deliberado: ver el docstring del modulo.

    Borrar estas filas dejaria la pantalla de Scoring sin configuracion, que es
    exactamente el defecto que esta migracion corrige.
    """

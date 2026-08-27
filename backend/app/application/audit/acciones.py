"""Catálogo canónico de acciones auditadas (dominio CRÍTICO).

Fuente ÚNICA de verdad de TODO lo que se registra en el audit log. Es un StrEnum:
cada miembro ES su string, así se usa directo en ``registrar_seguro(accion=...)`` y
queda retro-compatible con los literales previos. Organizado por categoría.
"""

from __future__ import annotations

from enum import StrEnum


class ModuloAuditoria(StrEnum):
    """Módulos de dominio para filtrar el audit log en la UI."""

    USUARIOS = "USUARIOS"
    MATERIAS = "MATERIAS"
    EXAMENES = "EXAMENES"
    SESIONES = "SESIONES"
    CONSENTIMIENTO = "CONSENTIMIENTO"
    BIOMETRIA = "BIOMETRIA"
    EVIDENCIA = "EVIDENCIA"
    REVISION = "REVISION"
    MOODLE = "MOODLE"
    CONFIGURACION = "CONFIGURACION"


# Etiqueta legible por módulo — fuente ÚNICA que consume tanto el export a
# Excel/PDF como el endpoint de catálogo (GET /admin/audit-catalogo) que puebla
# el filtro de Auditoría en el frontend. Si se agrega un ModuloAuditoria nuevo
# y no se le agrega label acá, el filtro lo muestra con su valor crudo (fallback
# seguro) en vez de romper — pero conviene completarlo.
MODULO_LABELS: dict[ModuloAuditoria, str] = {
    ModuloAuditoria.USUARIOS: "Usuarios",
    ModuloAuditoria.MATERIAS: "Materias",
    ModuloAuditoria.EXAMENES: "Exámenes",
    ModuloAuditoria.SESIONES: "Sesiones",
    ModuloAuditoria.CONSENTIMIENTO: "Consentimiento",
    ModuloAuditoria.BIOMETRIA: "Biometría",
    ModuloAuditoria.EVIDENCIA: "Evidencia",
    ModuloAuditoria.REVISION: "Revisión",
    ModuloAuditoria.MOODLE: "Moodle",
    ModuloAuditoria.CONFIGURACION: "Configuración",
}


class EntidadAuditoria(StrEnum):
    """Tipo de entidad de dominio afectada por la acción auditada.

    Permite navegar al detalle de la entidad desde la pantalla de Auditoría
    (combinado con ``entidad_id``).
    """

    USUARIO = "USUARIO"
    MATERIA = "MATERIA"
    COMISION = "COMISION"
    EXAMEN = "EXAMEN"
    INSCRIPCION = "INSCRIPCION"
    SESION = "SESION"
    CONSENTIMIENTO = "CONSENTIMIENTO"
    BIOMETRIA = "BIOMETRIA"
    EVIDENCIA = "EVIDENCIA"
    CONFIGURACION = "CONFIGURACION"
    SISTEMA = "SISTEMA"


class TipoAccionAuditoria(StrEnum):
    """Tipo de acción simplificado para filtrado en la UI (cuatro valores canónicos).

    El campo ``accion`` existente conserva el detalle dot-notation (user.create,
    materia.delete…); este enum es la capa de clasificación para los filtros.
    """

    CREAR = "CREAR"
    EDITAR = "EDITAR"
    ELIMINAR = "ELIMINAR"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"


class AccionAuditoria(StrEnum):
    """Acciones auditadas del sistema, agrupadas por dominio."""

    # ── Usuarios ─────────────────────────────────────────────────────────
    USUARIO_ALTA = "user.create"
    USUARIO_EDICION = "user.update"
    USUARIO_BAJA = "user.delete"
    USUARIO_REACTIVACION = "user.reactivate"

    # ── Catálogo académico (materias / comisiones / exámenes) ────────────
    MATERIA_ALTA = "materia.create"
    MATERIA_EDICION = "materia.update"
    MATERIA_BAJA = "materia.delete"
    MATERIA_ACTIVACION = "materia.set_activa"
    COMISION_ALTA = "comision.create"
    COMISION_EDICION = "comision.update"
    COMISION_BAJA = "comision.delete"
    COMISION_ACTIVACION = "comision.set_activa"
    # C-73 §9: quién queda a cargo de la comisión decide quién devuelve la nota a
    # Moodle y qué exámenes puede tocar ese docente. Se audita como cambio sensible.
    COMISION_DOCENTE = "comision.set_docente"
    # c-79: quién coordina la materia decide qué comisiones/tutores/exámenes puede
    # tocar (acotado por materia_coordinador, N:M). Cambio sensible, se audita.
    MATERIA_COORDINADOR = "materia.set_coordinador"
    # c-78: quien es PROFESOR de la materia decide quien arma sus examenes y su
    # banco (materia_profesor, N:M). Cambio sensible, se audita igual que el
    # coordinador. No otorga el veredicto de integridad (D11).
    MATERIA_PROFESOR = "materia.set_profesor"
    EXAMEN_IMPORTACION = "examen.import"
    EXAMEN_MOODLE_TARGET = "examen.moodle_target"
    EXAMEN_CONFIG_ACTUALIZACION = "examen.config_update"
    EXAMEN_SELECCION_PREGUNTAS = "examen.seleccion_preguntas"
    # c-78 D1: baja lógica del examen (setea eliminado_en, NO borra la fila) y su
    # reverso. Mismo par que USUARIO_BAJA/USUARIO_REACTIVACION. El prefijo
    # "examen." ya las mapea a ModuloAuditoria.EXAMENES y EntidadAuditoria.EXAMEN.
    EXAMEN_BAJA = "examen.baja"
    EXAMEN_REACTIVAR = "examen.reactivar"
    # Baja lógica de una pregunta del banco y su reverso. Mismo par que el examen:
    # marca `eliminada_en`, no borra la fila. Se audita porque saca contenido de
    # circulación y hay que poder responder quién lo hizo y cuándo.
    PREGUNTA_BANCO_BAJA = "pregunta_banco.baja"
    PREGUNTA_BANCO_REACTIVAR = "pregunta_banco.reactivar"
    # c-78 D9: publicar las notas es una accion explicita y de IDA. Queda
    # auditada por si despues hay reclamo sobre cuando se vieron las notas.
    EXAMEN_PUBLICAR_NOTAS = "examen.publicar_notas"
    # c-78 E-06 (14.2): duplicar un examen crea uno nuevo con las mismas
    # preguntas. Se audita sobre la COPIA, con el id del original en el proposito:
    # asi el detalle de la copia explica de donde salio su contenido.
    EXAMEN_DUPLICACION = "examen.duplicar"
    # c-78 E-06 (14.4): las comisiones que rinden un examen se administran desde
    # el examen. Cada alta crea una replica y cada baja la saca del lote — se
    # audita porque cambia QUIENES rinden una evaluacion real.
    EXAMEN_COMISION_AGREGADA = "examen.comision_agregada"
    EXAMEN_COMISION_QUITADA = "examen.comision_quitada"
    # c-78 E-07: el examen deja el borrador y pasa a estar disponible para los
    # alumnos. Se audita porque a partir de ese momento se puede rendir.
    EXAMEN_HABILITAR = "examen.habilitar"
    # c-78 E-07: el docente incorpora al examen preguntas nuevas del banco. El
    # pool esta congelado a proposito, asi que ampliarlo es una decision suya y
    # cambia que puede tocarle a los proximos alumnos.
    EXAMEN_POOL_ACTUALIZADO = "examen.pool_actualizado"

    # ── Write-back de nota a Moodle (cadena de custodia — regla dura #6, L2.5) ──
    # La sincronización manual del admin ESCRIBE una nota académica real en el
    # campus. Debe quedar trazada (quién sincronizó qué examen y con qué resultado).
    MOODLE_SYNC = "moodle.sync"
    # c-78 D14: alguien AFIRMA que cargó la nota a mano en el campus. Se audita
    # porque es una afirmación humana sobre una nota académica, sin confirmación
    # del sistema que la respalde.
    MOODLE_NOTA_MANUAL = "moodle.nota_marcada_manual"

    # ── Credencial PERSONAL de Moodle del docente (C-73 §13) ──────────────
    # Distinta de la config institucional del campus (modulo=CONFIGURACION,
    # ver CONFIG_ACTUALIZACION): esto es cada docente conectando/renovando SU
    # propia cuenta. Reemplaza el string suelto "moodle_credencial_update" (guion
    # bajo, sin modulo — quedaba invisible al filtrar Auditoría por MOODLE).
    MOODLE_CREDENCIAL_CONECTAR = "moodle_credencial.conectar"
    MOODLE_CREDENCIAL_DESCONECTAR = "moodle_credencial.desconectar"
    MOODLE_CREDENCIAL_RENOVAR = "moodle_credencial.renovar"
    #: Umbral de intentos fallidos SEGUIDOS alcanzado (IntentosFallidosTracker,
    #: en memoria — no hay tabla de intentos). Señal de "alguien está probando
    #: contraseñas", no un registro de cada fallo individual.
    MOODLE_CREDENCIAL_INTENTOS_FALLIDOS = "moodle_credencial.intentos_fallidos"

    # ── Inscripciones ────────────────────────────────────────────────────
    INSCRIPCION_ALTA = "inscripcion.create"
    INSCRIPCION_BAJA = "inscripcion.delete"

    # ── Configuración del sistema ────────────────────────────────────────
    CONFIG_ACTUALIZACION = "config_update"

    # ── Consentimiento ───────────────────────────────────────────────────
    CONSENT_OTORGADO = "consent.otorgado"
    CONSENT_VIA_ALTERNATIVA = "consent_alternative_chosen"

    # ── Biometría / enrolamiento ─────────────────────────────────────────
    BIOMETRIA_VERIFICACION = "biometria.verificacion"
    # c-78 (F-07): el alta se registraba con un string suelto en
    # guardar_embedding_referencia.py, esquivando este catálogo que dice ser la
    # fuente ÚNICA. El VALOR no cambia (las filas ya escritas siguen matcheando).
    ENROLLMENT_ALTA = "enrollment.embedding_referencia.alta"
    ENROLLMENT_RENOVACION = "enrollment.embedding_referencia.renovacion"

    # ── Evidencia y cadena de custodia ───────────────────────────────────
    EVIDENCIA_ACCESO = "acceso_evidencia"
    EVIDENCIA_DEPOSITO = "deposito_evidencia"
    EVIDENCIA_MANIPULACION = "manipulacion_detectada"
    EVIDENCIA_FIRMA_MAESTRA = "firma_maestra_y_reinferencia"

    # ── Retención / eliminación ──────────────────────────────────────────
    RETENCION_SESION_ELIMINADA = "retention.session.deleted"
    RETENCION_SESION_DIFERIDA = "retention.session.hold_deferred"
    RETENCION_BIOMETRIA_EGRESO = "retention.biometric.egress"
    # Purga de CAPTURAS (imagen) vencidas por retencion_capturas_dias — dispara el
    # endpoint admin explicito (nunca sola, sin cron). Borra la IMAGEN unicamente:
    # el evento, su screenshot_sha256 y el puntero WORM sobreviven (cadena de
    # custodia). Es un borrado de evidencia: se audita SIEMPRE, incluso con 0
    # capturas purgadas (deja constancia de que se corrio y con que politica).
    RETENCION_CAPTURAS_PURGADAS = "retention.capturas.purgadas"

    # ── Derechos del titular (DSR) ───────────────────────────────────────
    DSR_ACCESO_INFORME = "derecho_acceso.informe_devolucion"

    # ── Sesiones (C-76 tarea 20 — cierra el modulo SESIONES, antes muerto) ──
    # Eliminacion de sesion modo='test' (diagnostico, SIN evidencia academica
    # real) y archivado/desarchivado de una fila de resultados (gap detectado
    # en la tarea 14, nunca auditado). El prefijo "sesion." las mapea a
    # ModuloAuditoria.SESIONES en `modulo_de_accion` (ver abajo).
    SESION_TEST_ELIMINADA = "sesion.test.delete"
    RESULTADO_ARCHIVAR = "sesion.resultado.archivar"



# Prefijos de acciones DINÁMICAS (llevan un sufijo variable). Se componen así:
#   f"{PREFIJO_REVISION_DECISION}{decision}" -> "review.decision.anulado"
#   f"{PREFIJO_VERIFY_CHAIN}{status}"        -> "verify_chain.ok"
#   f"{PREFIJO_DSR}{tipo}"                   -> "dsr.rectification"
PREFIJO_REVISION_DECISION = "review.decision."
PREFIJO_VERIFY_CHAIN = "verify_chain."
PREFIJO_DSR = "dsr."


def modulo_de_accion(accion: str | None) -> str | None:
    """Deriva el módulo de auditoría a partir del prefijo de la ``accion``.

    Fuente ÚNICA de la clasificación accion → módulo. Se usa como FALLBACK en el
    ``append`` del repositorio: cuando un caller construye el ``AuditEntry`` sin
    pasar ``modulo`` (muchos lo hacían directo, dejando modulo=NULL → la entrada NO
    aparecía al filtrar por su módulo en Auditoría), el prefijo determinístico de la
    acción lo resuelve acá. Devuelve None solo si la acción no matchea ninguna
    familia conocida (se registra igual, sin módulo).
    """
    a = accion or ""
    if a.startswith("user."):
        return ModuloAuditoria.USUARIOS
    if a.startswith(("materia.", "comision.", "inscripcion.")):
        return ModuloAuditoria.MATERIAS
    if a == "moodle.sync" or a.startswith("moodle_credencial."):
        return ModuloAuditoria.MOODLE
    if a.startswith("examen."):
        return ModuloAuditoria.EXAMENES
    if a.startswith("config"):
        return ModuloAuditoria.CONFIGURACION
    if a.startswith("consent"):
        return ModuloAuditoria.CONSENTIMIENTO
    if a.startswith(("biometria", "enrollment")):
        return ModuloAuditoria.BIOMETRIA
    if a.startswith(PREFIJO_REVISION_DECISION):
        return ModuloAuditoria.REVISION
    # C-76 tarea 20: eliminacion de sesion de test + archivado de resultado.
    # Antes ModuloAuditoria.SESIONES no tenia NINGUN prefijo mapeado acá (filtro
    # muerto, siempre 0 resultados en Auditoría) — este es el primero.
    if a.startswith("sesion."):
        return ModuloAuditoria.SESIONES
    # Evidencia y cadena de custodia: acceso/depósito de evidencia, manipulación,
    # firma maestra, verificación de cadena, retención/borrado y derechos del titular
    # (DSR) — el frontend los agrupa todos bajo "Evidencia de sesiones".
    if a.startswith(
        (
            "acceso_evidencia",
            "deposito_evidencia",
            "manipulacion_detectada",
            "firma_maestra",
            PREFIJO_VERIFY_CHAIN,
            "retention",
            PREFIJO_DSR,
            "derecho_acceso",
        )
    ):
        return ModuloAuditoria.EVIDENCIA
    return None


def entidad_de_accion(accion: str | None) -> str | None:
    """Deriva el TIPO de entidad afectada a partir del prefijo de la ``accion``.

    Mismo mecanismo que ``modulo_de_accion`` (mismo FALLBACK en ``append()`` del
    repositorio) pero para ``entidad``. Sin esto, un caller que pasa ``entidad_id``
    pero se olvida de ``entidad`` (pasó en comisión/materia — C-79) deja la fila
    sin clasificar: Auditoría no sabe a qué tipo de página llevar "Ver detalle" y
    no muestra ningún botón, aunque el id sí esté guardado.

    Deriva el TIPO (MATERIA, USUARIO, SESION...), nunca el id — el id solo lo
    tiene quien registra la acción, no se puede inventar acá. Devuelve None si la
    acción no matchea ninguna familia conocida (se registra igual, sin entidad).
    """
    a = accion or ""
    if a.startswith("user."):
        return EntidadAuditoria.USUARIO
    if a.startswith("materia."):
        return EntidadAuditoria.MATERIA
    if a.startswith("comision."):
        return EntidadAuditoria.COMISION
    if a.startswith("inscripcion."):
        return EntidadAuditoria.INSCRIPCION
    if a.startswith("examen.") or a == "moodle.sync":
        return EntidadAuditoria.EXAMEN
    if a.startswith("config"):
        return EntidadAuditoria.CONFIGURACION
    if a.startswith("consent") or a.startswith(("biometria", "enrollment")):
        # El titular de un consentimiento/verificación/foto de referencia es
        # siempre el usuario dueño de la acción — es la única entidad con
        # página propia que tiene sentido acá (no hay pantalla de "sesión de
        # biometría" separada del perfil del alumno).
        return EntidadAuditoria.USUARIO
    # "sesion.test.delete" queda AFUERA a propósito: la sesión ya no existe
    # cuando se registra ese evento (se borró) — "Ver detalle" daría 404, igual
    # que "retention.session.deleted".
    if a.startswith(PREFIJO_REVISION_DECISION) or a == AccionAuditoria.RESULTADO_ARCHIVAR:
        return EntidadAuditoria.SESION
    if a.startswith((PREFIJO_DSR, "derecho_acceso")):
        # DSR opera siempre sobre un usuario titular concreto.
        return EntidadAuditoria.USUARIO
    if a.startswith(
        ("acceso_evidencia", "deposito_evidencia", "manipulacion_detectada", "firma_maestra", PREFIJO_VERIFY_CHAIN)
    ):
        return EntidadAuditoria.SESION
    return None

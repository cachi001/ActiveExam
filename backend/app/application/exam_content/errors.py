"""Errores de aplicación del módulo exam_content (importación Moodle)."""

from __future__ import annotations


class MoodleXmlInvalidoError(Exception):
    """El XML no pudo parsearse (malformado o no es XML)."""


class MoodleXmlVacioError(Exception):
    """El XML es válido pero no contiene preguntas de tipo soportado."""


class LimitePreguntasExcedidoError(Exception):
    """El XML trae más preguntas válidas de las que el examen admite.

    No se truncan: importar en silencio las primeras N dejaría al docente con un
    examen distinto del que subió, sin enterarse de cuáles se perdieron. Se
    rechaza la importación entera con el conteo para que decida.
    """

    def __init__(self, importables: int, limite: int) -> None:
        super().__init__(
            f"El archivo trae {importables} preguntas válidas y el tope es {limite}. "
            f"Quitá {importables - limite} del archivo o subí el tope."
        )
        self.importables = importables
        self.limite = limite


class SorteoInsuficienteError(Exception):
    """Una categoría no tiene suficientes preguntas para el sorteo pedido (C-74 §3).

    No se trunca en silencio: el docente decide si agrega más preguntas al banco
    o baja la cantidad requerida. Incluye el conteo disponible vs. pedido.
    """

    def __init__(self, categoria_id: str, disponibles: int, pedidas: int) -> None:
        super().__init__(
            f"Categoría {categoria_id} tiene {disponibles} pregunta(s) disponibles "
            f"en este examen, se pidieron {pedidas}."
        )
        self.categoria_id = categoria_id
        self.disponibles = disponibles
        self.pedidas = pedidas


class ExamenNoEncontradoError(Exception):
    """No existe un examen de contenido con el id indicado."""


class ComisionNoEncontradaError(Exception):
    """No existe una comisión con el id indicado."""


class MateriaNoEncontradaError(Exception):
    """No existe una materia con el id indicado."""


class MateriaNoVaciaError(Exception):
    """La materia tiene inscriptos y/o exámenes: no se puede eliminar (C-72 §16).

    Solo se permite borrar materias 100% vacías; si tiene contenido o gente, se
    ofrece desactivar en su lugar.
    """


class ComisionNoVaciaError(Exception):
    """La comisión tiene inscriptos y/o exámenes: no se puede eliminar (C-72 §16)."""


class MateriaInactivaError(Exception):
    """La materia está desactivada (congelada): no admite inscripciones nuevas ni
    iniciar rendición (C-72 §17). Los ya inscriptos conservan su acceso."""


class ComisionInactivaError(Exception):
    """La comisión está desactivada (congelada): no admite inscripciones nuevas por
    su código de matriculación ni iniciar la rendición de sus exámenes (C-72 §17).

    Espejo de ``MateriaInactivaError`` un nivel más abajo: congelar UNA comisión no
    congela la materia ni las demás comisiones. Los ya inscriptos conservan su acceso.
    """


class UsuarioNoEncontradoError(Exception):
    """No existe un usuario activo con el id indicado."""


class InscripcionNoEncontradaError(Exception):
    """No existe una inscripción del usuario a la comisión indicada."""


class InscripcionConActividadError(Exception):
    """El alumno ya rindió (tiene una sesión de examen en la comisión): no se puede
    dar de baja la inscripción, porque huerfanaría la sesión/evidencia/nota
    (cadena de custodia). Se conserva el registro; la baja queda bloqueada."""


class CodigoMatriculacionInvalidoError(Exception):
    """El codigo_matriculacion enviado no corresponde a ninguna comisión (C-70).

    Se eleva en la auto-matriculación del alumno cuando el código no mapea a una
    comisión existente. El endpoint lo traduce a 404 (no se crea ninguna inscripción).
    """


class PerfilIncompletoError(Exception):
    """El alumno intentó matricularse sin el perfil completo (C-71).

    Regla del owner: TODO (matricularse, rendir) requiere el perfil completo =
    consentimiento vigente 'otorgado' + referencia biométrica vigente, resuelto
    server-side (el gate no se puede saltear desde el cliente). El endpoint lo
    traduce a 403 y NO crea inscripción. ``razon`` describe qué falta.
    """

    def __init__(self, razon: str) -> None:
        super().__init__(razon)
        self.razon = razon

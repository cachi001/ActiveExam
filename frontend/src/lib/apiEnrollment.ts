// Métodos de enrollment / perfil del alumno extraídos de api.ts
// (refactor c-76: partir god-file). Gate de rendición (puedeRendir), enrollment,
// vía alternativa, referencia biométrica, DNI y foto de perfil. Se spreadean en
// `api` (./api); ningún método usa `this`. La fuente de verdad del estado sigue
// siendo apiCore (enrollmentAlumno es un binding vivo de ES module).
import {
  API_BASE, BIOMETRIC_VALIDITY_MONTHS, VISION_ENGINE_VERSION,
  delay, realFetch, calcularExpiracion, calcularVigencia, commitEnrollment,
  _estadosViaAlternativa, consentVersionVigente, syncEnrollmentState,
  enrollmentAlumno, setEnrollmentAlumno,
} from './apiCore';
import { authProvider } from './authProvider';
import type { EstadoEnrollment, EscaneDNI, ReferenciasBiometrica } from './types';

export const enrollmentApi = {
  // -------------------------------------------------------------------------
  // Enrollment biométrico del perfil — C-22
  // -------------------------------------------------------------------------

  /**
   * Gate de rendición (C-22): el alumno puede rendir si tiene el PERFIL COMPLETO
   * (consentimiento de perfil vigente o vía alternativa + biometría vigente). El
   * consentimiento de perfil es el único gate de consentimiento — el acuse
   * por-examen se eliminó por redundante. El gate NUNCA sanciona: deriva/flaggea (L2.5).
   */
  async puedeRendir(examenId?: string): Promise<{ puede: boolean; razon?: string; codigo?: string }> {
    // El gate debe decidir con estado FRESCO del servidor, NO con el cache local
    // (localStorage `ae_demo_enrollment`), que puede mentir tras un reset de DB o un
    // cambio de usuario en el mismo browser → flash de "disponible" stale. syncEnrollmentState
    // refetcha del backend (modo real), re-sincroniza la versión del consentimiento (C-67)
    // y recalcula `perfil_completo` antes de evaluar el gate.
    const e = await syncEnrollmentState();
    setEnrollmentAlumno(e);

    // C-63: verificar vía alternativa pendiente / habilitada antes del gate de perfil
    if (examenId) {
      const estadoAlt = _estadosViaAlternativa.get(examenId);
      if (estadoAlt === 'pendiente_proctor') {
        return {
          puede: false,
          codigo: 'via_alternativa_pendiente',
          razon: 'Tu verificación alternativa está pendiente de aprobación de un proctor.',
        };
      }
      if (estadoAlt === 'via_alternativa_habilitada' || estadoAlt === 'habilitado_por_proctor') {
        // Proctor habilitó — puede rendir sin biometría.
        return { puede: true };
      }
    }
    // También verificar estado del perfil para vía alternativa habilitada (enrollment)
    const estadoAltPerfil = _estadosViaAlternativa.get('perfil');
    if (estadoAltPerfil === 'via_alternativa_habilitada' || estadoAltPerfil === 'habilitado_por_proctor') {
      // El proctor habilitó el perfil — puede rendir sin biometría (C-63 D-04)
      return { puede: true };
    }

    // Capa 1: perfil completo (C-22)
    if (!e.perfil_completo) {
      const faltantes: string[] = [];
      let codigo = 'perfil_incompleto';

      if (!e.consentimiento) {
        faltantes.push('consentimiento informado');
      } else if (!e.consentimiento.via_alternativa && e.consentimiento.version !== consentVersionVigente()) {
        faltantes.push('renovación del consentimiento (nueva versión disponible)');
        codigo = 'consentimiento_version_desactualizada';
      }

      if (!e.consentimiento?.via_alternativa) {
        if (!e.biometria) {
          faltantes.push('captura biométrica de referencia');
        } else if (e.biometria.vigencia === 'caducada') {
          faltantes.push('renovación de la referencia biométrica (caducada)');
          codigo = 'biometria_caducada';
        } else if (e.biometria.vigencia === 'renovacion_requerida') {
          faltantes.push('renovación de la referencia biométrica (requerida por deriva)');
          codigo = 'biometria_renovacion_requerida';
        }
      }

      // C-63: si hay vía alternativa pendiente en el perfil, mostrar ese código
      if (estadoAltPerfil === 'pendiente_proctor') {
        return {
          puede: false,
          codigo: 'via_alternativa_pendiente',
          razon: 'Tu verificación alternativa está pendiente de aprobación de un proctor.',
        };
      }

      return {
        puede: false,
        codigo,
        razon: faltantes.length > 0
          ? `Perfil incompleto: falta ${faltantes.join(' y ')}.`
          : 'Perfil incompleto.',
      };
    }

    // El perfil completo (Capa 1) es el único gate de consentimiento. El acuse
    // por-examen se eliminó por redundante: el consentimiento de perfil ya
    // verifica y bloquea la rendición.
    return { puede: true };
  },


  /** Retorna el estado de enrollment completo del perfil (C-22). */
  async getEnrollment(): Promise<EstadoEnrollment> {
    // En modo REAL la fuente de verdad es el backend: si la DB se reseteó (tmpfs),
    // el cache local en localStorage queda mintiendo "ya hiciste todo". syncEnrollmentState
    // pisa el estado local con lo que dice el servidor en cada carga.
    return syncEnrollmentState();
  },

  // -------------------------------------------------------------------------
  // Vía alternativa — C-63
  // -------------------------------------------------------------------------

  /**
   * Registra una solicitud de vía alternativa sin biometría (C-63).
   * El alumno queda en estado pendiente_proctor hasta que un proctor habilite.
   * Retorna { estado, puede_rendir } — puede_rendir=false mientras sea pendiente.
   */
  async solicitarViaAlternativa(examId: string): Promise<{ estado: string; puede_rendir: boolean }> {
    const token = authProvider.getToken?.() ?? '';
    const resp = await fetch(`${API_BASE}/consent/alternative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ exam_id: examId }),
    });
    if (!resp.ok) throw new Error(`solicitarViaAlternativa: ${resp.status}`);
    return resp.json();
  },

  /**
   * Consulta el estado actual de la solicitud de vía alternativa (C-63).
   * Retorna { estado } si existe, null si no hay solicitud.
   */
  async estadoViaAlternativa(examId: string): Promise<{ estado: string } | null> {
    const token = authProvider.getToken?.() ?? '';
    const resp = await fetch(`${API_BASE}/consent/gate?exam_id=${encodeURIComponent(examId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    if (
      data.resolucion === 'via_alternativa_pendiente' ||
      data.resolucion === 'via_alternativa_habilitada'
    ) {
      return { estado: data.resolucion };
    }
    return null;
  },

  /**
   * Persiste la referencia biométrica capturada en el enrollment del perfil (C-56).
   *
   * C-56: cuando USE_REAL_BACKEND=1, llama a POST /api/v1/enrollment/embedding-referencia
   * con el array de 128 floats. El backend lo cifra at-rest con Fernet y devuelve
   * un `referencia_id` opaco. El store persiste el `referencia_id` (no el embedding crudo).
   *
   * DATOS SENSIBLES (Ley 25.326):
   * - `embedding`: cifrado at-rest server-side (Fernet/AES-128-CBC + HMAC-SHA256).
   *   Finalidad acotada a verificación de identidad 1:1.
   *   Marcado para eliminación al egreso; holds legales difieren.
   * El cliente es SENSOR NO CONFIABLE: el backend re-infiere y firma (C-12).
   * D3 (C-56): el backend acepta el embedding client-side (NO re-infiere en enrollment).
   * La re-inferencia aplica durante el examen (C-09 D2).
   */
  async guardarReferenciaBiometrica(params: {
    imagen: string | null;
    embedding: number[] | null;
  }): Promise<ReferenciasBiometrica & { referencia_id?: string }> {
    // En modo real exigimos un embedding 128-d válido. Si face-api no detectó
    // rostro y devolvió null (o length distinto), antes el código caía al
    // bloque demo de abajo y NO posteaba al backend: el usuario veía "Referencia
    // capturada" pero el servidor nunca la recibía → luego en el examen
    // estadoReferenciaBiometrica devolvía false y aparecía "no enrolado".
    // Ahora fallamos fuerte para que la UI muestre error y el alumno reintente.
    if (!params.embedding || params.embedding.length !== 128) {
        throw new Error(
          'No se pudo extraer el descriptor facial de la captura. ' +
            'Asegurate de que tu rostro esté bien encuadrado, con buena luz, ' +
            'y reintentá la captura.',
        );
      }
      try {
        const data = await realFetch<{ referencia_id: string }>(
          '/enrollment/embedding-referencia',
          {
            method: 'POST',
            body: JSON.stringify({ embedding: params.embedding }),
          },
        );
        // Construir la referencia con el referencia_id opaco del backend.
        const ahora = new Date().toISOString();
        const expiracion = calcularExpiracion(ahora, BIOMETRIC_VALIDITY_MONTHS);
        const ref: ReferenciasBiometrica & { referencia_id?: string } = {
          captura_completada: true,
          imagen: null,          // C-56: el embedding se persiste en el backend, no la imagen
          embedding: null,       // C-56: el embedding crudo NO se persiste en el cliente
          fecha_captura: ahora,
          fecha_expiracion: expiracion,
          vigencia_meses: BIOMETRIC_VALIDITY_MONTHS,
          version_motor: VISION_ENGINE_VERSION,
          vigencia: calcularVigencia(expiracion, false),
          renovacion_anticipada_requerida: false,
          referencia_id: data.referencia_id,
        };
        commitEnrollment({ ...enrollmentAlumno, biometria: ref });
        return ref;
      } catch (err) {
        // Si el backend falla, NO hacer fallback demo: propagar el error
        // para que el componente pueda mostrar el mensaje y reintentar.
        const msg = err instanceof Error ? err.message : String(err);
        // 401 = token vencido (sesión larga). Mensaje claro y accionable.
        if (/\b401\b/.test(msg) || /unauthorized/i.test(msg)) {
          throw new Error('Tu sesión expiró. Cerrá sesión y volvé a iniciar sesión, y reintentá la captura.');
        }
        throw new Error(`No se pudo guardar la referencia: ${msg}`);
      }
  },

  /**
   * Guarda el escaneo de DNI como dato sensible (demo) — C-22.
   * Solo activo si ENABLE_DNI_SCAN === true. No bloquea el perfil completo.
   *
   * DATO SENSIBLE (Ley 25.326):
   * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
   * eliminado al egreso, holds legales difieren la eliminación.
   */
  async guardarEscaneDNI(frente: string, dorso: string): Promise<EscaneDNI> {
    await delay(400);
    const escan: EscaneDNI = {
      captura_completada: true,
      imagen_frente: frente,
      imagen_dorso: dorso,
      fecha_captura: new Date().toISOString(),
    };
    commitEnrollment({ ...enrollmentAlumno, dni: escan });
    return escan;
  },

  /**
   * Simula la deriva del embedding y marca la referencia para renovación anticipada.
   * En producción este flag lo setea el backend tras detectar deriva sostenida en la
   * verificación silenciosa continua. La deriva NO sanciona ni invalida la rendición
   * en curso (L2.5 — decisión disciplinaria siempre humana).
   */
  async simularDerivaEmbedding(): Promise<void> {
    await delay(200);
    if (!enrollmentAlumno.biometria) return;
    const bioActualizada: ReferenciasBiometrica = {
      ...enrollmentAlumno.biometria,
      renovacion_anticipada_requerida: true,
      vigencia: 'renovacion_requerida',
    };
    commitEnrollment({ ...enrollmentAlumno, biometria: bioActualizada });
  },

  /** Elimina la referencia biométrica para forzar renovación (demo / testing). */
  async resetearReferenciaBiometrica(): Promise<void> {
    await delay(150);
    commitEnrollment({ ...enrollmentAlumno, biometria: null });
  },

  /**
   * Persiste la foto de perfil del alumno (C-56).
   *
   * C-56: cuando USE_REAL_BACKEND=1, llama a POST /api/v1/enrollment/foto-perfil
   * con la imagen en base64. El backend la sube al bucket no-WORM (SSE-S3), calcula
   * el hash SHA-256, persiste los metadatos en foto_referencia y devuelve el
   * `foto_referencia_id` opaco. El store persiste el ID (no el dataUrl completo).
   *
   * DATO PERSONAL (Ley 25.326): finalidad acotada (identidad en enrollment).
   * Cifrado at-rest server-side, eliminado al egreso del estudiante.
   * Demo: solo en memoria de la sesión.
   *
   * @returns foto_referencia_id (UUID opaco) en modo real, undefined en demo.
   */
  async guardarFotoPerfil(dataUrl: string): Promise<string | undefined> {
    try {
      const data = await realFetch<{ foto_referencia_id: string }>(
        '/enrollment/foto-perfil',
        {
          method: 'POST',
          body: JSON.stringify({ imagen_base64: dataUrl }),
        },
      );
      // El dataUrl no se persiste en el store (solo el ID opaco).
      return data.foto_referencia_id;
    } catch (err) {
      // Propagar el error para que el componente pueda mostrar el mensaje y reintentar.
      throw new Error(`Error al guardar foto de perfil: ${err instanceof Error ? err.message : String(err)}`);
    }
  },
};

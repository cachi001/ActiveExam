/**
 * PerfilHeaderCard — encabezado del perfil del alumno.
 *
 * Presentación pura: recibe `principal` y renderiza el avatar condicional
 * (foto circular si existe, inicial si no) y los datos personales en un grid 2×2.
 * No accede al store ni llama APIs.
 *
 * Spec: profile-header-card (C-42)
 */
import { motion } from 'motion/react';
import { Button, Card } from '../../../ui/components';
import { INSTITUTION } from '../../../config/institution';
import type { Principal } from '../../../lib/types';

interface PerfilHeaderCardProps {
  principal: Principal | null;
  /**
   * Callback opcional para rehacer la foto de perfil. Cuando se pasa, se muestra
   * un botón pequeño "Cambiar foto" junto al avatar. Si se omite, no aparece —
   * por defecto el header es de solo lectura.
   */
  onRehacerFoto?: () => void;
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  },
};

export function PerfilHeaderCard({ principal, onRehacerFoto }: PerfilHeaderCardProps) {
  return (
    <Card>
      {/* Fila superior: avatar + nombre + roles + acciones */}
      <motion.div
        className="flex items-center gap-md mb-lg"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Avatar condicional: foto circular si existe, inicial si no */}
        {principal?.foto_perfil ? (
          <img
            src={principal.foto_perfil}
            className="w-14 h-14 rounded-full object-cover shrink-0"
            alt={`Foto de perfil de ${[principal.nombre, principal.apellido].filter(Boolean).join(' ')}`}
          />
        ) : (
          <div className="w-14 h-14 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-headline-sm shrink-0">
            {principal?.nombre.charAt(0) ?? '?'}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-label-lg font-semibold text-on-surface">
            {[principal?.nombre, principal?.apellido].filter(Boolean).join(' ') || '—'}
          </p>
          <p className="text-label-sm text-on-surface-variant">{principal?.roles.join(', ') ?? '—'}</p>
        </div>
        {onRehacerFoto && (
          <Button
            variant="ghost"
            size="sm"
            icon="photo_camera"
            onClick={onRehacerFoto}
            className="text-label-sm text-on-surface-variant shrink-0"
            aria-label={principal?.foto_perfil ? 'Cambiar foto de perfil' : 'Tomar foto de perfil'}
          >
            <span className="hidden sm:inline">
              {principal?.foto_perfil ? 'Cambiar foto' : 'Tomar foto'}
            </span>
          </Button>
        )}
      </motion.div>

      {/* Grid 2×2 de datos personales */}
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 gap-md"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <motion.div variants={itemVariants}>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Legajo</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.id_institucional ?? '—'}</p>
        </motion.div>
        <motion.div variants={itemVariants}>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Email institucional</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.email ?? '—'}</p>
        </motion.div>
        <motion.div variants={itemVariants}>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Institución</p>
          <p className="text-label-md text-on-surface font-semibold">{INSTITUTION.nombreCorto}</p>
        </motion.div>
        <motion.div variants={itemVariants}>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Jurisdicción</p>
          <p className="text-label-md text-on-surface font-semibold">{principal?.jurisdiccion ?? '—'}</p>
        </motion.div>
      </motion.div>
    </Card>
  );
}

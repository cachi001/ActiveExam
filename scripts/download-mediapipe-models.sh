#!/usr/bin/env bash
# download-mediapipe-models.sh
#
# Descarga los tres modelos de MediaPipe Tasks API y copia los archivos WASM
# necesarios para el harness de diagnóstico admin (/admin/detection-test).
#
# Uso: ./scripts/download-mediapipe-models.sh
#      (ejecutar desde la raíz del proyecto, después de npm install en frontend/)
#
# Versión de @mediapipe/tasks-vision: 0.10.14
# Los modelos deben coincidir con la versión del paquete npm.
#
# Soberanía de datos (RD-7): modelos y WASM se sirven LOCALMENTE desde
# frontend/public/mediapipe/. NUNCA desde CDN externo en runtime.

set -euo pipefail

DEST_DIR="frontend/public/mediapipe"
WASM_DEST_DIR="${DEST_DIR}/wasm"
WASM_SRC_DIR="frontend/node_modules/@mediapipe/tasks-vision/wasm"
# Versión de tasks-vision fijada — debe coincidir con package.json
TASKS_VERSION="0.10.14"

# URLs versionadas de storage.googleapis.com/mediapipe-models (descarga única al setup)
FACE_DETECTOR_URL="https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
FACE_LANDMARKER_URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
POSE_LANDMARKER_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

# Nombres de destino locales
FACE_DETECTOR_FILE="face_detector_short_range.task"
FACE_LANDMARKER_FILE="face_landmarker.task"
POSE_LANDMARKER_FILE="pose_landmarker_lite.task"

echo "=== MediaPipe Model + WASM Downloader ==="
echo "Versión tasks-vision: ${TASKS_VERSION}"
echo "Destino modelos: ${DEST_DIR}/"
echo "Destino WASM: ${WASM_DEST_DIR}/"
echo ""

mkdir -p "${DEST_DIR}"
mkdir -p "${WASM_DEST_DIR}"

download_model() {
  local url="$1"
  local dest_file="$2"
  local dest_path="${DEST_DIR}/${dest_file}"

  echo "Descargando: ${dest_file}"
  echo "  URL: ${url}"

  if command -v curl &>/dev/null; then
    curl -L --progress-bar -o "${dest_path}" "${url}"
  elif command -v wget &>/dev/null; then
    wget -q --show-progress -O "${dest_path}" "${url}"
  else
    echo "ERROR: Se requiere curl o wget para descargar los modelos." >&2
    exit 1
  fi

  local size
  size=$(du -sh "${dest_path}" | cut -f1)
  echo "  Tamaño: ${size} → ${dest_path}"
  echo ""
}

download_model "${FACE_DETECTOR_URL}" "${FACE_DETECTOR_FILE}"
download_model "${FACE_LANDMARKER_URL}" "${FACE_LANDMARKER_FILE}"
download_model "${POSE_LANDMARKER_URL}" "${POSE_LANDMARKER_FILE}"

echo "=== Copiando archivos WASM desde node_modules (self-hosted, RD-7) ==="
if [ -d "${WASM_SRC_DIR}" ]; then
  cp "${WASM_SRC_DIR}"/*.wasm "${WASM_DEST_DIR}/" 2>/dev/null || true
  cp "${WASM_SRC_DIR}"/*.js "${WASM_DEST_DIR}/" 2>/dev/null || true
  echo "  WASM copiados desde ${WASM_SRC_DIR}:"
  ls -lh "${WASM_DEST_DIR}"/ 2>/dev/null || echo "  (ninguno encontrado)"
else
  echo "  ADVERTENCIA: ${WASM_SRC_DIR} no encontrado."
  echo "  Asegurate de haber corrido 'npm install' en frontend/ antes de este script."
fi
echo ""

echo "=== Setup completado ==="
echo ""
echo "Archivos en ${DEST_DIR}/:"
ls -lh "${DEST_DIR}"/*.task 2>/dev/null || echo "(ninguno — descarga fallida)"
echo ""
echo "Archivos WASM en ${WASM_DEST_DIR}/:"
ls -lh "${WASM_DEST_DIR}"/ 2>/dev/null || echo "(ninguno)"
echo ""
echo "NOTA: Estos archivos están en .gitignore (no se suben al repositorio)."
echo "      Volvé a ejecutar este script si cambiás de entorno o limpiás el directorio."

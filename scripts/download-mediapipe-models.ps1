# download-mediapipe-models.ps1
#
# Descarga los tres modelos de MediaPipe Tasks API y copia los archivos WASM
# necesarios para el harness de diagnóstico admin (/admin/detection-test).
#
# Uso: .\scripts\download-mediapipe-models.ps1
#      (ejecutar desde la raíz del proyecto, después de npm install en frontend/)
#
# Versión de @mediapipe/tasks-vision: 0.10.14
# Los modelos deben coincidir con la versión del paquete npm.
#
# Soberanía de datos (RD-7): modelos y WASM se sirven LOCALMENTE desde
# frontend/public/mediapipe/. NUNCA desde CDN externo en runtime.

$ErrorActionPreference = "Stop"

$DestDir = "frontend\public\mediapipe"
$WasmDestDir = "$DestDir\wasm"
$WasmSrcDir = "frontend\node_modules\@mediapipe\tasks-vision\wasm"
$TasksVersion = "0.10.14"

# URLs versionadas de storage.googleapis.com/mediapipe-models (descarga única al setup)
$Models = @(
    @{
        Url  = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
        File = "face_detector_short_range.task"
    },
    @{
        Url  = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
        File = "face_landmarker.task"
    },
    @{
        Url  = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
        File = "pose_landmarker_lite.task"
    }
)

Write-Host "=== MediaPipe Model + WASM Downloader ===" -ForegroundColor Cyan
Write-Host "Version tasks-vision: $TasksVersion"
Write-Host "Destino modelos: $DestDir\"
Write-Host "Destino WASM: $WasmDestDir\"
Write-Host ""

# Crear directorios si no existen
if (-not (Test-Path $DestDir)) {
    New-Item -ItemType Directory -Path $DestDir | Out-Null
}
if (-not (Test-Path $WasmDestDir)) {
    New-Item -ItemType Directory -Path $WasmDestDir | Out-Null
}

foreach ($model in $Models) {
    $destPath = Join-Path $DestDir $model.File
    Write-Host "Descargando: $($model.File)" -ForegroundColor Yellow
    Write-Host "  URL: $($model.Url)"

    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $model.Url -OutFile $destPath -UseBasicParsing
        $ProgressPreference = 'Continue'

        $size = (Get-Item $destPath).Length
        $sizeMb = [math]::Round($size / 1MB, 2)
        Write-Host "  Tamano: ${sizeMb} MB -> $destPath" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR al descargar $($model.File): $_" -ForegroundColor Red
        Write-Host "  Verificá tu conexión a internet o intentá de nuevo." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "=== Copiando archivos WASM desde node_modules (self-hosted, RD-7) ===" -ForegroundColor Cyan
if (Test-Path $WasmSrcDir) {
    $wasmFiles = Get-ChildItem -Path $WasmSrcDir -Include "*.wasm","*.js" -Recurse
    foreach ($f in $wasmFiles) {
        $destFile = Join-Path $WasmDestDir $f.Name
        Copy-Item -Path $f.FullName -Destination $destFile -Force
        $sizeMb = [math]::Round($f.Length / 1MB, 2)
        Write-Host "  Copiado: $($f.Name) ($sizeMb MB)" -ForegroundColor Green
    }
} else {
    Write-Host "  ADVERTENCIA: $WasmSrcDir no encontrado." -ForegroundColor Yellow
    Write-Host "  Asegurate de haber corrido 'npm install' en frontend/ antes de este script." -ForegroundColor Yellow
}
Write-Host ""

Write-Host "=== Setup completado ===" -ForegroundColor Green
Write-Host ""
Write-Host "Archivos en ${DestDir}:"
Get-ChildItem -Path $DestDir -Filter "*.task" | ForEach-Object {
    $sizeMb = [math]::Round($_.Length / 1MB, 2)
    Write-Host "  $($_.Name) ($sizeMb MB)"
}
Write-Host ""
Write-Host "Archivos WASM en ${WasmDestDir}:"
if (Test-Path $WasmDestDir) {
    Get-ChildItem -Path $WasmDestDir | ForEach-Object {
        $sizeMb = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  $($_.Name) ($sizeMb MB)"
    }
}
Write-Host ""
Write-Host "NOTA: Estos archivos estan en .gitignore (no se suben al repositorio)." -ForegroundColor DarkYellow
Write-Host "      Volvé a ejecutar este script si cambias de entorno o limpiás el directorio." -ForegroundColor DarkYellow

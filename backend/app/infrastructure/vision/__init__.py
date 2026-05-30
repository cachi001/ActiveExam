"""Motor de vision server-side ABSTRAIDO detras de interfaz (DD-17, C-09).

El puerto ``VisionEnginePort`` (dominio) lo implementa aqui un adaptador. El MVP
usa la re-inferencia sobre el clip; la ruta a un modelo pasivo self-hosted (ONNX)
es Fase 2 (DD-18). El adaptador concreto contra MediaPipe/ONNX se cablea en
produccion; este modulo deja el contrato y un adaptador que delega en un cargador
de clips inyectable, sin atar el dominio al motor concreto.
"""

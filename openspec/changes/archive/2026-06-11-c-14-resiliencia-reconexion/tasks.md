# Tasks — C-14 `resiliencia-reconexion`

> Construyen la resiliencia de red sin pérdida (frontend / transport) con TDD, sobre el canal WS y los ganchos de C-10. Cero pérdida de eventos confirmados; exactly-once lógico; no penalizar al estudiante por su red. El evento crítico por corte largo es señal, NUNCA sanción (L2.5).

## 1. Buffer IndexedDB (capability `indexeddb-event-buffer`)

- [x] 1.1 Implementar el buffer circular en IndexedDB y cablear la escritura de cada evento antes del envío; Done: test de evento persistido en buffer
- [x] 1.2 Test de que los eventos se guardan en el buffer mientras el WS está caído; Done: test rojo→verde
- [x] 1.3 Test de que el buffer sobrevive a refresh/cierre de pestaña (resistente a cortes); Done: test de persistencia tras reload
- [x] 1.4 Acotar el buffer como circular para cortes largos; Done: test de no crecer sin techo

## 2. Reconexión con backoff y handshake (capability `reconnect-backoff`)

- [x] 2.1 Implementar el reconnector con backoff exponencial; Done: test de intervalos crecientes
- [x] 2.2 Añadir jitter del 20% a cada reintento (evita thundering herd, RN-HB-05); Done: test de distribución con jitter
- [x] 2.3 Implementar el handshake de reconexión enviando `last_event_id` (contra el gancho de C-10); Done: test de handshake con último id confirmado
- [x] 2.4 Verificar que el backend reenvía los eventos posteriores a `last_event_id`; Done: test de reenvío de faltantes

## 3. Replay ordenado y deduplicación (capability `ordered-replay-dedup`)

- [x] 3.1 Implementar el drenaje del buffer en orden al reconectar; Done: test de replay ordenado
- [x] 3.2 Verificar la deduplicación por `event_id` en el backend (contra la persistencia de C-10); Done: test de reenvío de id ya persistido no duplica
- [x] 3.3 Test de replay completo con solape (eventos confirmados + nuevos) → exactly-once lógico; Done: test sin pérdida ni duplicados
- [x] 3.4 Marcar como confirmados y purgar del buffer solo los eventos efectivamente persistidos; Done: test de purga post-confirmación

## 4. Política por duración del corte (capability `outage-duration-policy`)

- [x] 4.1 Usar la ausencia de heartbeats (/5s de C-10) como reloj del corte; Done: test de detección de duración
- [x] 4.2 Implementar corte < 5 min → replay sin pérdida; Done: test de corte corto sin pérdida
- [x] 4.3 Implementar corte > 5 min → evento crítico al reconectar (RN-HB-04, RN-EV-04); Done: test de evento crítico emitido
- [x] 4.4 Test de que el evento crítico por corte largo NO deriva sanción automática (L2.5, RN-RV-07); Done: test verifica solo señal al panel

## 5. Integración

- [x] 5.1 Test e2e del Flujo 5: WS cae → buffer → backoff+jitter → handshake(last_event_id) → reenvío → drenaje ordenado → dedup → exactly-once; Done: e2e verde
- [x] 5.2 Instrumentar métricas (tamaño de buffer, reconexiones, eventos reenviados, duplicados deduplicados, cortes > 5 min) (DD-12, RN-GLB-05); Done: métricas visibles

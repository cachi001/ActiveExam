# capacidad-y-observabilidad-examen Specification

## Purpose
Que el sistema aguante el examen real y que, si algo sale mal, quede registro de qué pasó.

Tres cosas medidas contra producción el 26/8/2026, no estimadas: el pool de conexiones
estaba dimensionado con una cuenta escrita a mano que ya no correspondía, `/metrics` no lo
guardaba nadie, y el servicio dormido se comía el primer ingreso del examen.
## Requirements
### Requirement: El pool de conexiones se dimensiona desde el entorno real

El sistema SHALL derivar el máximo de conexiones a la base de los datos reales del
despliegue: cuántos procesos sirven y cuánto admite la base.

El sistema SHALL permitir configurar el tamaño del pool por variables de entorno, sin
editar código ni reconstruir la imagen.

El sistema SHALL reservar un margen de conexiones para administración, fuera del reparto
entre procesos: agotar la base entera deja el problema sin diagnóstico posible en el
momento en que hace falta.

#### Scenario: Un solo proceso contra la base

- **WHEN** se calcula el pool para un proceso
- **THEN** puede usar el presupuesto entero de la base menos la reserva de administración

#### Scenario: Varios procesos reparten el presupuesto

- **WHEN** se calcula el pool para N procesos
- **THEN** el techo total de conexiones no supera lo que la base admite menos la reserva

#### Scenario: El pool se configura sin tocar el código

- **WHEN** el despliegue declara un tamaño de pool por variables de entorno
- **THEN** el engine lo usa; una variable mal escrita cae al valor por defecto sin impedir
  el arranque

### Requirement: El arranque avisa si el pool no entra en la base

El sistema SHALL verificar, al arrancar, que el pool configurado entre en el
`max_connections` real de la base, y SHALL registrar un aviso con los números concretos
cuando no entre.

El conteo de procesos MUST NOT depender únicamente de una variable de entorno: un servidor
lanzado con varios workers por parámetro no declara ninguna, y contar mal subestima el
techo por un factor igual a la cantidad de workers.

La verificación MUST NOT impedir que la aplicación levante.

#### Scenario: Configuración que excede la base

- **WHEN** el techo de conexiones supera lo disponible
- **THEN** se registra un aviso que incluye el techo, el límite de la base y el tamaño de
  pool sugerido

#### Scenario: Configuración correcta

- **WHEN** el techo entra en lo disponible
- **THEN** no se emite ninguna advertencia

#### Scenario: La base no responde la consulta

- **WHEN** no se puede leer el `max_connections`
- **THEN** la aplicación arranca igual

### Requirement: Las métricas del examen se pueden grabar y revisar después

El sistema SHALL ofrecer una forma de scrapear `/metrics` a intervalo regular y guardar el
resultado en disco, sin depender de infraestructura de monitoreo externa.

La grabación SHALL producir, al cerrarse, un resumen con el pico de requests por segundo,
el pico de memoria y la cantidad de errores de servidor.

Un scrape fallido MUST NOT terminar la grabación.

#### Scenario: Tasas a partir de contadores acumulados

- **WHEN** se comparan dos muestras consecutivas
- **THEN** se reportan requests por segundo y uso de CPU derivados de la diferencia

#### Scenario: El proceso se reinicia durante la grabación

- **WHEN** los contadores de una muestra son menores que los de la anterior
- **THEN** se marca como reinicio y no se reportan tasas negativas

#### Scenario: Un scrape falla

- **WHEN** una consulta a `/metrics` no responde
- **THEN** la grabación continúa con la siguiente muestra

### Requirement: El servicio se puede despertar antes del examen

El sistema SHALL ofrecer una forma de despertar el backend y confirmar que responde, antes
de habilitar el ingreso de los alumnos.

Es un requisito operativo, no de código: con el servicio dormido, el primer ingreso desde
el campus se pierde — llega como envío de datos, el alumno ve la pantalla de arranque del
hosting y al recargar recibe un error.

#### Scenario: Servicio dormido

- **WHEN** se ejecuta el procedimiento de despertado contra un servicio dormido
- **THEN** reintenta hasta obtener respuesta e informa cuánto tardó

#### Scenario: Servicio ya despierto

- **WHEN** el servicio ya responde
- **THEN** el procedimiento confirma de inmediato, sin efectos sobre los datos


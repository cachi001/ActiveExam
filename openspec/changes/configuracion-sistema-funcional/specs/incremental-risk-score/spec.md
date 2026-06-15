# incremental-risk-score

## MODIFIED Requirements

### Requirement: Ponderación por severidad, frecuencia y persistencia
El peso de cada evento en el score SHALL combinar su **severidad**, su **frecuencia** y su **persistencia**; un patrón sostenido SHALL pesar más que un pico aislado (RN-SC-02, RN-SC-03). El factor de severidad SHALL provenir de los **pesos persistidos** en la configuración (`evento_score_config`), leídos vivos desde la base de datos, NO de un mapa de severidad hardcodeado; el mapa por defecto SHALL usarse solo como red de seguridad de degradación graceful.

#### Scenario: Patrón sostenido pesa más que pico aislado
- **WHEN** una sesión presenta un patrón anómalo sostenido en el tiempo y otra un pico aislado equivalente en severidad
- **THEN** el score de la sesión con patrón sostenido es mayor que el de la del pico aislado

#### Scenario: Severidad modula el peso
- **WHEN** se ponderan eventos de severidad crítica frente a eventos de severidad media
- **THEN** los de severidad crítica contribuyen con mayor peso al score

#### Scenario: El peso de severidad proviene de la config persistida
- **WHEN** un `admin_sistema` cambia el `peso` de un tipo de evento y se puntúa una sesión nueva
- **THEN** la contribución de ese tipo de evento al score SHALL reflejar el peso persistido editado, no la constante hardcodeada

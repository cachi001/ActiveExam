## ADDED Requirements

### Requirement: FormField component
El módulo `ui/components.tsx` SHALL exportar un componente `FormField` que agrupa label, control (slot), hint opcional y mensaje de error opcional en un layout vertical consistente. El hint se oculta cuando hay error. El label usa el estilo `text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold` del design system.

Props:
- `label: string` — texto del label (obligatorio)
- `hint?: string` — texto de ayuda debajo del control (opcional)
- `error?: string` — mensaje de error; cuando está presente, reemplaza el hint y usa `text-error`
- `children: ReactNode` — el control del formulario (input, select, checkbox group, etc.)
- `className?: string` — clase adicional para el wrapper externo

#### Scenario: Renders label and control
- **WHEN** se renderiza `<FormField label="Nombre"><input /></FormField>`
- **THEN** se muestra el label "NOMBRE" en estilo uppercase y el control debajo

#### Scenario: Renders hint when no error
- **WHEN** se renderiza `<FormField label="X" hint="Ayuda">...</FormField>` sin error
- **THEN** se muestra el texto "Ayuda" en `text-on-surface-variant`

#### Scenario: Error replaces hint
- **WHEN** se renderiza `<FormField label="X" hint="Ayuda" error="Campo requerido">...</FormField>`
- **THEN** se muestra "Campo requerido" en `text-error` y NO se muestra "Ayuda"

### Requirement: RangeInput component
El módulo `ui/components.tsx` SHALL exportar un componente `RangeInput` que encapsula un `<input type="range">` con label dinámico (muestra el valor actual y la unidad), hint opcional y callback `onChange`. Usa `FormField` internamente. El color del track usa el token `accent-primary` (no hardcoded hex).

Props:
- `label: string` — nombre del campo (ej: "Duración")
- `value: number` — valor actual (controlado)
- `min: number`, `max: number` — rango
- `step?: number` — paso (default 1)
- `unit?: string` — unidad del valor (ej: "minutos", "%")
- `hint?: string` — texto de ayuda
- `onChange: (v: number) => void` — callback al mover el slider

El label dinámico tiene formato `"${label}: ${value}${unit}"` (ej: "Duración: 90 minutos").

#### Scenario: Label shows current value
- **WHEN** se renderiza `<RangeInput label="Duración" value={90} min={30} max={180} unit="minutos" onChange={fn} />`
- **THEN** el label muestra "Duración: 90 minutos"

#### Scenario: Label updates on change
- **WHEN** el usuario mueve el slider y dispara `onChange(120)`
- **THEN** el componente padre actualiza el valor y el label muestra "Duración: 120 minutos"

#### Scenario: Track color uses design system token
- **WHEN** se renderiza cualquier RangeInput
- **THEN** el track del slider usa la clase `accent-primary` (no un valor hex literal)

### Requirement: ConfigureExam uses form primitives
La pantalla `ConfigureExam` SHALL usar `FormField` y `RangeInput` del design system en lugar del componente `Field` local y los `<input type="range">` ad-hoc. Los sliders de "Duración" y "Umbral de cola de revisión" MUST ser instancias de `RangeInput`.

#### Scenario: Duration field is a RangeInput
- **WHEN** se renderiza ConfigureExam
- **THEN** el campo de duración usa el componente `RangeInput` con `unit="minutos"`

#### Scenario: Threshold field is a RangeInput
- **WHEN** se renderiza ConfigureExam
- **THEN** el campo de umbral de revisión usa el componente `RangeInput` con `unit="%"`

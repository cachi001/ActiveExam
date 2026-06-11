## ADDED Requirements

### Requirement: Button accepts size prop
El componente `Button` SHALL aceptar una prop opcional `size?: 'sm' | 'md' | 'lg'` con default `'md'`. El tamaño controla la altura y el padding horizontal usando tokens del design system. La prop `className` externa MUST seguir aplicándose (sin colisión de clases de tamaño si el consumidor no la usa para overrides de tamaño).

Tabla de valores:
- `sm` → `h-9 px-md` (36px × 16px padding)
- `md` → `h-12 px-lg` (48px × 24px padding) — comportamiento actual
- `lg` → `h-14 px-xl` (56px × 32px padding)

#### Scenario: Default size is md
- **WHEN** se renderiza `<Button>` sin prop `size`
- **THEN** el botón tiene clase `h-12` y `px-lg`

#### Scenario: Size sm renders compact button
- **WHEN** se renderiza `<Button size="sm">`
- **THEN** el botón tiene clase `h-9` y `px-md`

#### Scenario: Size lg renders large button
- **WHEN** se renderiza `<Button size="lg">`
- **THEN** el botón tiene clase `h-14` y `px-xl`

#### Scenario: External className does not duplicate size classes
- **WHEN** se renderiza `<Button size="sm" className="text-label-sm">`
- **THEN** el botón tiene `h-9 px-md text-label-sm` sin clases de tamaño duplicadas

### Requirement: Button stacks have gap
Los bloques de botones `w-full` apilados verticalmente SHALL tener un gap mínimo de `gap-sm` (12px) entre sí para evitar que se peguen visualmente.

#### Scenario: AdminDashboard quick actions have gap
- **WHEN** se renderiza la sección "Acciones rápidas" de AdminDashboard
- **THEN** los tres botones tienen separación visual de al menos 12px entre ellos

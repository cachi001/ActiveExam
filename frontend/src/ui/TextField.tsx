import { forwardRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Icon } from './components';

export interface TextFieldProps {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'search';
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  icon?: string;           // Material Symbol name — ícono izquierdo dentro del input
  error?: string;          // mensaje de error debajo del input
  hint?: string;           // texto de ayuda debajo del input (solo si no hay error)
  disabled?: boolean;
  required?: boolean;
  autoComplete?: string;
  className?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField(
    {
      label,
      name,
      type = 'text',
      value,
      onChange,
      placeholder,
      icon,
      error,
      hint,
      disabled = false,
      required = false,
      autoComplete,
      className = '',
    },
    ref,
  ) {
    const [showPassword, setShowPassword] = useState(false);

    const isPassword = type === 'password';
    const inputType = isPassword ? (showPassword ? 'text' : 'password') : type;

    const inputPaddingLeft = icon ? 'pl-10' : 'pl-4';
    const inputPaddingRight = isPassword ? 'pr-10' : 'pr-4';
    const errorBorder = error ? 'border-error focus:border-error focus:ring-error/15' : '';

    return (
      <div className={`flex flex-col gap-1 ${className}`}>
        <label
          htmlFor={name}
          className="text-sm font-medium text-on-surface-variant mb-1"
        >
          {label}
        </label>

        <div className="relative">
          {/* Ícono izquierdo */}
          {icon && (
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px] flex items-center">
              <Icon name={icon} className="text-[20px]" />
            </span>
          )}

          <input
            ref={ref}
            id={name}
            name={name}
            type={inputType}
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            disabled={disabled}
            required={required}
            autoComplete={autoComplete}
            className={[
              'bg-white border border-outline-variant rounded-md py-3 shadow-xs',
              'focus:outline-none focus:ring-4 focus:ring-primary/15 focus:border-primary',
              'hover:border-outline transition-colors duration-150',
              'w-full disabled:opacity-50',
              inputPaddingLeft,
              inputPaddingRight,
              errorBorder,
            ]
              .filter(Boolean)
              .join(' ')}
          />

          {/* Toggle ver/ocultar contraseña */}
          {isPassword && (
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              tabIndex={-1}
              className="absolute right-0 inset-y-0 flex items-center px-3 text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <Icon
                name={showPassword ? 'visibility_off' : 'visibility'}
                className="text-[20px]"
              />
            </button>
          )}
        </div>

        {/* Error / hint */}
        {error && (
          <p className="text-label-sm text-error mt-0.5">{error}</p>
        )}
        {!error && hint && (
          <p className="text-label-sm text-on-surface-variant mt-0.5">{hint}</p>
        )}
      </div>
    );
  },
);

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import MoodleImportPage from './MoodleImportPage';

describe('MoodleImportPage', () => {
  it('renders without crashing', () => {
    render(<MoodleImportPage />);
    expect(screen.getByText('Importar examen desde Moodle XML')).toBeTruthy();
  });

  it('shows file input and submit button', () => {
    render(<MoodleImportPage />);
    expect(screen.getByLabelText(/Archivo XML de Moodle/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Importar/i })).toBeTruthy();
  });

  it('button is disabled without a file selected', () => {
    render(<MoodleImportPage />);
    const btn = screen.getByRole('button', { name: /Importar/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('shows optional titulo input', () => {
    render(<MoodleImportPage />);
    expect(screen.getByLabelText(/Título del examen/i)).toBeTruthy();
  });
});

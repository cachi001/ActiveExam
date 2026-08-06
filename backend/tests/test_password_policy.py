"""Tests de la política de contraseñas (Media: 8+ con mayús, minús y dígito).

Función pura `validar_password_fuerte` — no toca DB, no toca red.
"""

from __future__ import annotations

import pytest

from app.domain.auth.password_policy import (
    PasswordDebilError,
    validar_password_fuerte,
)


class TestPasswordFuerte:
    def test_password_valida_no_lanza(self) -> None:
        # Cumple: 8+ chars, mayúscula, minúscula y dígito.
        validar_password_fuerte("Abcdef12")

    def test_password_valida_larga_con_simbolos(self) -> None:
        validar_password_fuerte("MiClave-Segura99")

    @pytest.mark.parametrize(
        "password",
        [
            "Abc12",        # menos de 8
            "abcdef12",     # sin mayúscula
            "ABCDEF12",     # sin minúscula
            "Abcdefgh",     # sin dígito
            "",             # vacía
            "12345678",     # solo dígitos
        ],
    )
    def test_password_debil_lanza(self, password: str) -> None:
        with pytest.raises(PasswordDebilError):
            validar_password_fuerte(password)

    def test_mensaje_lista_requisitos_incumplidos(self) -> None:
        # "abc" incumple: longitud, mayúscula y dígito.
        with pytest.raises(PasswordDebilError) as exc:
            validar_password_fuerte("abc")
        msg = str(exc.value).lower()
        assert "8" in msg
        assert "mayúscula" in msg or "mayuscula" in msg
        assert "número" in msg or "numero" in msg or "dígito" in msg or "digito" in msg

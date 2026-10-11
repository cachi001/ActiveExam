"""Un usuario tiene exactamente UN rol — nunca varios (decisión del dueño, 9/9/2026).

Roles múltiples rompía la separación de poderes que el dominio construyó a
propósito (quien pone la nota no decide si hubo fraude — ver `roles.py`).
Tests puros sobre los schemas Pydantic: no tocan la base de datos.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.presentation.api.v1.users.router import CrearUsuarioRequest, EditarUsuarioRequest


class TestCrearUsuarioUnSoloRol:
    def test_un_rol_es_valido(self):
        req = CrearUsuarioRequest(email="a@b.com", roles=["tutor"])
        assert req.roles == ["tutor"]

    def test_dos_roles_rechazado(self):
        with pytest.raises(ValidationError, match="exactamente un rol"):
            CrearUsuarioRequest(email="a@b.com", roles=["tutor", "coordinador"])

    def test_cero_roles_rechazado(self):
        with pytest.raises(ValidationError, match="exactamente un rol"):
            CrearUsuarioRequest(email="a@b.com", roles=[])


class TestEditarUsuarioUnSoloRol:
    def test_un_rol_es_valido(self):
        req = EditarUsuarioRequest(roles=["profesor"])
        assert req.roles == ["profesor"]

    def test_dos_roles_rechazado(self):
        with pytest.raises(ValidationError, match="exactamente un rol"):
            EditarUsuarioRequest(roles=["admin_sistema", "estudiante"])

    def test_cero_roles_rechazado(self):
        with pytest.raises(ValidationError, match="exactamente un rol"):
            EditarUsuarioRequest(roles=[])

    def test_roles_ausente_no_valida_nada(self):
        """None = "no tocar los roles" (PATCH parcial) — no debe exigir longitud."""
        req = EditarUsuarioRequest(email="nuevo@b.com")
        assert req.roles is None

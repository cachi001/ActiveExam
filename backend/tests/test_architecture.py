"""Tests estructurales de la arquitectura por capas (monorepo-scaffolding).

Verifica el Requirement "Arbol del backend por capas con dominio puro aislado":
ningun modulo bajo ``app.domain`` importa FastAPI, SQLAlchemy ni adaptadores de
``app.infrastructure``. Falla el test = el dominio se contamino de framework.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"

# Prefijos de import PROHIBIDOS en la capa de dominio (debe ser pura).
_FORBIDDEN_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "uvicorn",
    "starlette",
    "pydantic_settings",
    "app.infrastructure",
    "app.presentation",
    "app.application",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_layer_is_pure() -> None:
    py_files = list(_DOMAIN_DIR.rglob("*.py"))
    assert py_files, "La capa de dominio deberia existir (al menos __init__.py)."

    violations: list[str] = []
    for path in py_files:
        for module in _imported_modules(path.read_text(encoding="utf-8")):
            if module.startswith(_FORBIDDEN_PREFIXES):
                violations.append(f"{path.name}: importa '{module}'")

    assert not violations, "Dominio contaminado por framework/infra: " + "; ".join(
        violations
    )

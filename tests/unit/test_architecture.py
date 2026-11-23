"""Layer boundaries, checked from the source so they cannot drift from the docs.

Requests flow routes -> services -> repositories -> SQLite. SQL is written only in
repository modules and in storage infrastructure (migrations, backup, readiness).
LEGACY_SQL lists the modules that still hold SQL from before this rule was enforced: a new
module with SQL fails, and a listed module that no longer has any must be removed, so the
list only shrinks.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "sentio"

SQL_ALLOWED = (
    "repositories/",
    "auth/repositories.py",
    "auth/recovery.py",  # RecoveryRepository
    "maintenance/",  # backup, readiness, account cleanup: storage infrastructure
    "shared/",  # transaction helpers
    "evaluation/",  # offline experiments, not request paths
)

LEGACY_SQL = {
    "ingestion/pipeline.py",
    "ingestion/recovery.py",
    "intelligence/service.py",
    "session/manager.py",
}


def _modules():
    for path in sorted(PACKAGE.rglob("*.py")):
        yield path.relative_to(PACKAGE).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _writes_sql(tree):
    """Imports SQLAlchemy's text() or calls sqlalchemy.text(), anywhere in the module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy"):
            if any(alias.name == "text" for alias in node.names):
                return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "text"
            and isinstance(node.value, ast.Name)
            and node.value.id == "sqlalchemy"
        ):
            return True
    return False


def _imports_sqlalchemy(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            a.name.startswith("sqlalchemy") for a in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy"):
            return True
    return False


def test_sql_lives_in_repositories():
    with_sql = {
        name for name, tree in _modules() if not name.startswith(SQL_ALLOWED) and _writes_sql(tree)
    }
    new = with_sql - LEGACY_SQL
    cleaned = LEGACY_SQL - with_sql
    assert not new, f"Move this SQL into a repository module: {sorted(new)}"
    assert not cleaned, f"No SQL left here; remove from LEGACY_SQL: {sorted(cleaned)}"


def test_routes_do_not_touch_sqlalchemy():
    offenders = [
        name
        for name, tree in _modules()
        if name.startswith("api/routes/") and _imports_sqlalchemy(tree)
    ]
    assert not offenders, f"Routes must call services or repositories: {offenders}"


def test_engine_is_reached_through_the_public_property():
    """`persister.engine`, not the private `_engine`, outside the class that owns it."""
    offenders = sorted(
        {
            name
            for name, tree in _modules()
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "_engine"
            and not (isinstance(node.value, ast.Name) and node.value.id == "self")
        }
    )
    assert not offenders, f"Use persister.engine instead of persister._engine: {offenders}"

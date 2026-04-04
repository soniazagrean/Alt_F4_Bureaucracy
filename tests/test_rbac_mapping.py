from types import SimpleNamespace

from app.dependencies.security import RBACRole, map_user_to_rbac_role


def _user(role: str):
    return SimpleNamespace(role=SimpleNamespace(value=role))


def test_map_admin_roles():
    assert map_user_to_rbac_role(_user("admin")) == RBACRole.ADMIN
    assert map_user_to_rbac_role(_user("system")) == RBACRole.ADMIN


def test_map_operator_roles():
    assert map_user_to_rbac_role(_user("archivist")) == RBACRole.OPERATOR
    assert map_user_to_rbac_role(_user("inspector")) == RBACRole.OPERATOR
    assert map_user_to_rbac_role(_user("operator")) == RBACRole.OPERATOR


def test_map_auditor_roles():
    assert map_user_to_rbac_role(_user("viewer")) == RBACRole.AUDITOR
    assert map_user_to_rbac_role(_user("auditor")) == RBACRole.AUDITOR

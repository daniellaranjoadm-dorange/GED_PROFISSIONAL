from apps.contas.models import Role, RolePermission, UserRole


def grant_rbac(user, *codes):
    role, _ = Role.objects.get_or_create(nome=f"TEST_{user.username}")
    UserRole.objects.get_or_create(user=user, role=role)
    for code in codes:
        RolePermission.objects.get_or_create(role=role, codigo=code)

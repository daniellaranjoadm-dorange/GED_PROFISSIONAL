from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Role, RolePermission, UserRole, Usuario


class UsuarioAdmin(UserAdmin):
    model = Usuario

    list_display = ["username", "email", "is_master", "is_staff", "is_active"]
    list_filter = ["is_master", "is_staff", "is_active"]

    fieldsets = UserAdmin.fieldsets + (
        ("Permissões Avançadas", {
            "fields": ("is_master",)  # removidos cargo e departamento
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Permissões Avançadas", {
            "fields": ("is_master",)  # removidos cargo e departamento
        }),
    )


admin.site.register(Usuario, UsuarioAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao")
    search_fields = ("nome", "descricao")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "role__nome")
    autocomplete_fields = ("user", "role")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "codigo", "descricao")
    list_filter = ("role",)
    search_fields = ("codigo", "descricao")

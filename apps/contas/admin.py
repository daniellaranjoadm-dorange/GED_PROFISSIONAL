from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


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

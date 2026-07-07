from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Mezcal


class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Rol', {'fields': ('rol',)}),
    )
    list_display = ('username', 'email', 'rol', 'is_staff')


admin.site.register(Mezcal)
admin.site.register(Usuario, UsuarioAdmin)


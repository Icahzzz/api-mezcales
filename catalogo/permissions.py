from rest_framework import permissions


class EsAdministradorOSoloLectura(permissions.BasePermission):
    """
    Cualquiera (incluso Invitado, sin cuenta) puede ver (GET).
    Solo un Administrador puede crear, editar o borrar.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.rol == 'administrador'
        )


class EsPropietarioOAdministrador(permissions.BasePermission):
    """
    Cualquiera (incluso Invitado, sin cuenta) puede ver (GET).
    Un Usuario solo puede crear/editar/borrar SUS PROPIOS registros.
    Un Administrador puede crear/editar/borrar cualquiera.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.rol == 'administrador':
            return True
        return obj.usuario == request.user

from rest_framework.routers import DefaultRouter
from .views import (
    MezcalViewSet, ResenaViewSet, CalificacionViewSet,
    CarritoViewSet, OrdenViewSet, UsuarioViewSet,
)

router = DefaultRouter()
router.register(r'mezcales', MezcalViewSet, basename='mezcal')
router.register(r'resenas', ResenaViewSet, basename='resena')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')
router.register(r'carrito', CarritoViewSet, basename='carrito')
router.register(r'ordenes', OrdenViewSet, basename='orden')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = router.urls

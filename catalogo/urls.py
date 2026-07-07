from rest_framework.routers import DefaultRouter
from .views import (
    MezcalViewSet, ResenaViewSet, CalificacionViewSet,
    CarritoViewSet, OrdenViewSet,
)

router = DefaultRouter()
router.register(r'mezcales', MezcalViewSet, basename='mezcal')
router.register(r'resenas', ResenaViewSet, basename='resena')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')
router.register(r'carrito', CarritoViewSet, basename='carrito')
router.register(r'ordenes', OrdenViewSet, basename='orden')

urlpatterns = router.urls
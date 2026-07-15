from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    CategoriaViewSet, MezcalViewSet, PromocionViewSet, ResenaViewSet, CalificacionViewSet,
    CarritoViewSet, OrdenViewSet, UsuarioViewSet, ReporteVentasViewSet,
)
from .ia_views import chatbot_view, sugerencias_view, personalizacion_view

router = DefaultRouter()
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'mezcales', MezcalViewSet, basename='mezcal')
router.register(r'promociones', PromocionViewSet, basename='promocion')
router.register(r'resenas', ResenaViewSet, basename='resena')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')
router.register(r'carrito', CarritoViewSet, basename='carrito')
router.register(r'ordenes', OrdenViewSet, basename='orden')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'reporte-ventas', ReporteVentasViewSet, basename='reporte-ventas')

urlpatterns = router.urls + [
    path('ia/chat/', chatbot_view, name='ia-chat'),
    path('ia/sugerencias/', sugerencias_view, name='ia-sugerencias'),
    path('ia/personalizacion/', personalizacion_view, name='ia-personalizacion'),
]

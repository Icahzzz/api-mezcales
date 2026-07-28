from django.urls import path
from rest_framework.routers import DefaultRouter

from .ia_views import (
    chatbot_view,
    personalizacion_view,
    recomendaciones_view,
    sugerencias_view,
)
from .views import (
    CalificacionViewSet,
    CarritoViewSet,
    CategoriaViewSet,
    MezcalViewSet,
    OrdenViewSet,
    PromocionViewSet,
    RegistroView,
    ReporteVentasViewSet,
    ResenaViewSet,
    UsuarioViewSet,
    me_view,
)

router = DefaultRouter()

# Catálogo
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'mezcales', MezcalViewSet, basename='mezcal')
router.register(r'promociones', PromocionViewSet, basename='promocion')

# Usuarios y opiniones
router.register(r'resenas', ResenaViewSet, basename='resena')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')

# Compra
router.register(r'carrito', CarritoViewSet, basename='carrito')
router.register(r'ordenes', OrdenViewSet, basename='orden')

# Administración
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'reporte-ventas', ReporteVentasViewSet, basename='reporte-ventas')

urlpatterns = router.urls + [
    path('registro/', RegistroView.as_view(), name='registro'),
    path('me/', me_view, name='me'),

    # IA
    path('ia/chat/', chatbot_view, name='ia-chat'),
    path('ia/sugerencias/', sugerencias_view, name='ia-sugerencias'),
    path('ia/personalizacion/', personalizacion_view, name='ia-personalizacion'),
    path('ia/recomendar/', recomendaciones_view, name='ia-recomendar'),
]
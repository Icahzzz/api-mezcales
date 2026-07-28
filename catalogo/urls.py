from django.urls import include, path
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

# Router para vistas CRUD del Admin
router = DefaultRouter()

# 1. Catálogo e Inventario
router.register(r'categorias', CategoriaViewSet, basename='admin-categoria')
router.register(r'mezcales', MezcalViewSet, basename='admin-mezcal')
router.register(r'promociones', PromocionViewSet, basename='admin-promocion')

# 2. Gestión de Ventas y Compras
router.register(r'compras', OrdenViewSet, basename='admin-compras')  # <-- Permite /api/compras/
router.register(r'ordenes', OrdenViewSet, basename='admin-orden')    # <-- Mantiene /api/ordenes/ por si lo usas en otro lado
router.register(r'carrito', CarritoViewSet, basename='admin-carrito')

# 3. Usuarios y Clientes
router.register(r'usuarios', UsuarioViewSet, basename='admin-usuario')
router.register(r'resenas', ResenaViewSet, basename='admin-resena')
router.register(r'calificaciones', CalificacionViewSet, basename='admin-calificacion')

# 4. Reportes y Métricas
router.register(r'reporte-ventas', ReporteVentasViewSet, basename='admin-reporte-ventas')  # <-- Permite /api/reporte-ventas/


urlpatterns = [
    # API Root navegable para el panel de administración
    path('', include(router.urls)),

    # Autenticación y perfil administrativo
    path('registro/', RegistroView.as_view(), name='admin-registro'),
    path('me/', me_view, name='admin-me'),

    # Integración con Inteligencia Artificial (Asistente/Sugerencias)
    path('ia/chat/', chatbot_view, name='admin-ia-chat'),
    path('ia/sugerencias/', sugerencias_view, name='admin-ia-sugerencias'),
    path('ia/personalizacion/', personalizacion_view, name='admin-ia-personalizacion'),
    path('ia/recomendar/', recomendaciones_view, name='admin-ia-recomendar'),
]
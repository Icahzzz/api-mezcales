from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.views.generic import TemplateView
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from .models import (
    Calificacion,
    Carrito,
    CarritoItem,
    Categoria,
    Mezcal,
    Orden,
    OrdenItem,
    Promocion,
    Resena,
    Usuario,
)
from .permissions import EsAdministradorOSoloLectura, EsPropietarioOAdministrador
from .serializers import (
    CalificacionSerializer,
    CarritoSerializer,
    CategoriaSerializer,
    MezcalSerializer,
    OrdenSerializer,
    PromocionSerializer,
    RegistroSerializer,
    ResenaSerializer,
    UsuarioSerializer,
)

# =====================================================
# PERMISOS AUXILIARES
# =====================================================
class EsAdministrador(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            getattr(request.user, 'rol', None) == "administrador"
        )


# =====================================================
# MEZCALES & CATEGORIAS & PROMOCIONES
# =====================================================
class MezcalViewSet(viewsets.ModelViewSet):
    queryset = Mezcal.objects.all()
    serializer_class = MezcalSerializer
    permission_classes = [EsAdministradorOSoloLectura]


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by("nombre")
    serializer_class = CategoriaSerializer
    permission_classes = [EsAdministradorOSoloLectura]


class PromocionViewSet(viewsets.ModelViewSet):
    queryset = Promocion.objects.select_related("mezcal").all().order_by("-fecha_inicio")
    serializer_class = PromocionSerializer
    permission_classes = [EsAdministradorOSoloLectura]


# =====================================================
# RESEÑAS Y CALIFICACIONES
# =====================================================
class ResenaViewSet(viewsets.ModelViewSet):
    queryset = Resena.objects.all()
    serializer_class = ResenaSerializer
    permission_classes = [EsPropietarioOAdministrador]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class CalificacionViewSet(viewsets.ModelViewSet):
    queryset = Calificacion.objects.all()
    serializer_class = CalificacionSerializer
    permission_classes = [EsPropietarioOAdministrador]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


# =====================================================
# CARRITO DE COMPRAS
# =====================================================
class CarritoViewSet(viewsets.ModelViewSet):
    serializer_class = CarritoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Carrito.objects.filter(usuario=self.request.user)

    @action(detail=False, methods=["GET"])
    def mio(self, request):
        carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
        return Response(self.get_serializer(carrito).data)

    @action(detail=False, methods=["POST"])
    def agregar_item(self, request):
        carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
        mezcal_id = request.data.get("mezcal")
        cantidad = int(request.data.get("cantidad", 1))

        item, creado = CarritoItem.objects.get_or_create(
            carrito=carrito,
            mezcal_id=mezcal_id,
            defaults={"cantidad": cantidad}
        )
        if not creado:
            item.cantidad += cantidad
            item.save()

        return Response(self.get_serializer(carrito).data)

    @action(detail=False, methods=["POST"])
    def quitar_item(self, request):
        mezcal_id = request.data.get("mezcal")
        CarritoItem.objects.filter(carrito__usuario=request.user, mezcal_id=mezcal_id).delete()
        carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
        return Response(self.get_serializer(carrito).data)

    # -----------------------------------------------------------------
    # ACCIÓN SINCRONIZAR (Soporte para App Móvil / Cliente)
    # URL: POST /api/carritos/sincronizar/
    # -----------------------------------------------------------------
    @action(detail=False, methods=["POST"], url_path="sincronizar")
    def sincronizar(self, request):
        carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
        items_data = request.data.get("items", [])

        with transaction.atomic():
            carrito.items.all().delete()  # Limpiar ítems previos para sincronizar estado exacto
            for item_data in items_data:
                mezcal_id = item_data.get("mezcal") or item_data.get("mezcal_id")
                cantidad = int(item_data.get("cantidad", 1))

                if mezcal_id:
                    CarritoItem.objects.create(
                        carrito=carrito,
                        mezcal_id=mezcal_id,
                        cantidad=cantidad
                    )

        return Response(self.get_serializer(carrito).data, status=status.HTTP_200_OK)


# =====================================================
# ÓRDENES (GESTIÓN COMPLETA + SINCRONIZACIÓN Y PAGO)
# =====================================================
class OrdenViewSet(viewsets.ModelViewSet):
    """
    - Admin: Ve todas las órdenes, acepta/rechaza pagos en efectivo y cambia su estado.
    - Cliente: Ve únicamente sus órdenes.
    """
    serializer_class = OrdenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'rol', None) == 'administrador':
            return Orden.objects.all().select_related('usuario').order_by('-creado_en')
        return Orden.objects.filter(usuario=user).order_by('-creado_en')

    # -----------------------------------------------------------------
    # SINCRONIZACIÓN DE ORDEN PENDIENTE DESDE LA APP MÓVIL
    # URL: POST /api/ordenes/sincronizar/
    # -----------------------------------------------------------------
    @action(detail=False, methods=['POST'], url_path='sincronizar')
    def sincronizar_orden(self, request):
        items_data = request.data.get('items', [])
        if not items_data:
            return Response({'error': 'El carrito está vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Obtener o crear una orden en estado 'pendiente' para el usuario actual
            orden, creado = Orden.objects.get_or_create(
                usuario=request.user,
                estado='pendiente',
                defaults={'total': 0, 'metodo_pago': 'efectivo'}
            )

            # Limpiar los ítems antiguos de esta orden pendiente
            orden.items.all().delete()

            total = 0
            for item in items_data:
                mezcal_id = item.get('mezcal') or item.get('mezcal_id')
                cantidad = int(item.get('cantidad', 1))

                try:
                    mezcal = Mezcal.objects.get(id=mezcal_id)
                    precio = mezcal.precio
                    total += precio * cantidad

                    OrdenItem.objects.create(
                        orden=orden,
                        mezcal=mezcal,
                        cantidad=cantidad,
                        precio_unitario=precio
                    )
                except Mezcal.DoesNotExist:
                    continue

            orden.total = total
            orden.save()

        return Response(self.get_serializer(orden).data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # 1. PAGO DE ORDEN DESDE APP MÓVIL
    # URL: POST /api/ordenes/pagar/
    # -----------------------------------------------------------------
    @action(detail=False, methods=['POST'], url_path='pagar')
    def pagar(self, request):
        orden_id = (
            request.data.get('orden_id') or 
            request.data.get('id') or 
            request.data.get('orden') or
            request.query_params.get('orden_id') or 
            request.query_params.get('id')
        )

        if not orden_id:
            return Response(
                {'error': 'Se requiere el parámetro "orden_id" o "id".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if getattr(request.user, 'rol', None) == 'administrador':
                orden = Orden.objects.get(id=orden_id)
            else:
                orden = Orden.objects.get(id=orden_id, usuario=request.user)
        except (Orden.DoesNotExist, ValueError):
            return Response({'error': 'Orden no encontrada o ID no válido.'}, status=status.HTTP_404_NOT_FOUND)

        if orden.estado != 'pendiente':
            return Response(
                {'error': f'La orden ya se encuentra en estado "{orden.estado}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            for item in orden.items.all():
                if item.cantidad > item.mezcal.stock:
                    return Response(
                        {'error': f'Stock insuficiente para {item.mezcal.nombre}. Disponible: {item.mezcal.stock}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                item.mezcal.stock -= item.cantidad
                item.mezcal.save()

            orden.estado = 'recibido'
            orden.save()

        return Response(self.get_serializer(orden).data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # 2. ACEPTAR PAGO EN EFECTIVO (Solo Administrador)
    # URL: POST /api/ordenes/<id>/aceptar/
    # -----------------------------------------------------------------
    @action(detail=True, methods=['POST'], url_path='aceptar')
    def aceptar_efectivo(self, request, pk=None):
        if getattr(request.user, 'rol', None) != 'administrador':
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        orden = self.get_object()

        metodo_pago = getattr(orden, 'metodo_pago', 'efectivo')
        if str(metodo_pago).lower() != 'efectivo':
            return Response(
                {'error': 'Esta acción solo aplica para órdenes con método de pago en efectivo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if orden.estado != 'pendiente':
            return Response(
                {'error': f'La orden ya fue procesada anteriormente. Estado actual: {orden.estado}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            for item in orden.items.all():
                if item.cantidad > item.mezcal.stock:
                    return Response(
                        {'error': f'Stock insuficiente para {item.mezcal.nombre}. Disponible: {item.mezcal.stock}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                item.mezcal.stock -= item.cantidad
                item.mezcal.save()

            orden.estado = 'recibido'
            orden.save()

        return Response(self.get_serializer(orden).data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # 3. RECHAZAR PAGO EN EFECTIVO (Solo Administrador)
    # URL: POST /api/ordenes/<id>/rechazar/
    # -----------------------------------------------------------------
    @action(detail=True, methods=['POST'], url_path='rechazar')
    def rechazar_efectivo(self, request, pk=None):
        if getattr(request.user, 'rol', None) != 'administrador':
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        orden = self.get_object()

        if orden.estado in ['entregado', 'cancelado']:
            return Response(
                {'error': f'No se puede rechazar una orden en estado "{orden.estado}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        orden.estado = 'cancelado'
        orden.save()
        return Response(self.get_serializer(orden).data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # 4. CAMBIO DE ESTADOS GENERALES / PATCH
    # -----------------------------------------------------------------
    def partial_update(self, request, *args, **kwargs):
        if getattr(request.user, 'rol', None) != 'administrador':
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        instance = self.get_object()
        nuevo_estado = request.data.get('estado')

        estados_validos = [choice[0] for choice in Orden.Estado.choices]
        if nuevo_estado not in estados_validos:
            return Response(
                {'estado': [f'Valor no válido. Opciones: {estados_validos}']}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        metodo_pago = getattr(instance, 'metodo_pago', 'efectivo')
        if str(metodo_pago).lower() == 'efectivo' and instance.estado == 'pendiente' and nuevo_estado in ['repartiendo', 'entregado']:
            return Response(
                {'error': 'Debes aceptar el pago en efectivo antes de enviar o entregar la orden.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            estados_activos = ['recibido', 'repartiendo', 'entregado', 'pagado']
            if instance.estado == 'pendiente' and nuevo_estado in estados_activos:
                for item in instance.items.all():
                    if item.cantidad > item.mezcal.stock:
                        return Response(
                            {'error': f'Stock insuficiente para {item.mezcal.nombre}. Disponible: {item.mezcal.stock}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    item.mezcal.stock -= item.cantidad
                    item.mezcal.save()

            instance.estado = nuevo_estado
            instance.save()

        return Response(OrdenSerializer(instance).data, status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # 5. CANCELACIÓN DE ÓRDENES
    # URL: POST /api/ordenes/<id>/cancelar/
    # -----------------------------------------------------------------
    @action(detail=True, methods=['POST'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        orden = self.get_object()
        if orden.estado in ['entregado', 'cancelado']:
            return Response({'error': 'No se puede cancelar en este estado.'}, status=status.HTTP_400_BAD_REQUEST)

        orden.estado = 'cancelado'
        orden.save()
        return Response(self.get_serializer(orden).data, status=status.HTTP_200_OK)


# =====================================================
# OTROS ENDPOINTS (REGISTRO, USUARIOS, REPORTES, PERFIL)
# =====================================================
class RegistroView(CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [EsAdministrador]


class ReporteVentasViewSet(viewsets.ViewSet):
    permission_classes = [EsAdministrador]

    def list(self, request):
        ordenes = Orden.objects.filter(estado__in=['pagado', 'entregado', 'recibido'])
        total_ventas = ordenes.aggregate(total=Sum("total"))["total"] or 0
        total_ordenes = ordenes.count()
        ticket = (total_ventas / total_ordenes) if total_ordenes else 0

        top = (
            OrdenItem.objects
            .filter(orden__estado__in=['pagado', 'entregado', 'recibido'])
            .values("mezcal__nombre")
            .annotate(cantidad=Sum("cantidad"))
            .order_by("-cantidad")[:10]
        )

        return Response({
            "kpis": {
                "total_ventas": total_ventas,
                "total_ordenes": total_ordenes,
                "ticket_promedio": ticket
            },
            "top_articulos": list(top)
        })


class AdminPOSView(TemplateView):
    template_name = "catalogo/admin_pos/index.html"


@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    if request.method == "GET":
        return Response(UsuarioSerializer(request.user).data)
    
    serializer = UsuarioSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)
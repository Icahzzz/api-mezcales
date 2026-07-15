from rest_framework import viewsets, permissions, status
from .models import Categoria, Mezcal, Promocion, Resena, Calificacion, Carrito, CarritoItem, Orden, OrdenItem, Usuario
from .serializers import (
    CategoriaSerializer, MezcalSerializer, PromocionSerializer, ResenaSerializer, CalificacionSerializer,
    CarritoSerializer, CarritoItemSerializer, OrdenSerializer,
)
from .serializers import UsuarioSerializer
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Count
from .serializers import RegistroSerializer
from rest_framework.generics import CreateAPIView
from .permissions import EsAdministradorOSoloLectura, EsPropietarioOAdministrador
from django.views.generic import TemplateView


class MezcalViewSet(viewsets.ModelViewSet):
    queryset = Mezcal.objects.all()
    serializer_class = MezcalSerializer
    permission_classes = [EsAdministradorOSoloLectura]


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('nombre')
    serializer_class = CategoriaSerializer
    permission_classes = [EsAdministradorOSoloLectura]


class PromocionViewSet(viewsets.ModelViewSet):
    queryset = Promocion.objects.select_related('mezcal').all().order_by('-fecha_inicio')
    serializer_class = PromocionSerializer
    permission_classes = [EsAdministradorOSoloLectura]

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

class CarritoViewSet(viewsets.ModelViewSet):
    serializer_class = CarritoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Carrito.objects.filter(usuario=self.request.user)

    @action(detail=False, methods=['get'])
    def mio(self, request):
        carrito, creado = Carrito.objects.get_or_create(usuario=request.user)
        serializer = self.get_serializer(carrito)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def agregar_item(self, request):
        carrito, creado = Carrito.objects.get_or_create(usuario=request.user)
        mezcal_id = request.data.get('mezcal')
        cantidad = int(request.data.get('cantidad', 1))

        item, item_creado = CarritoItem.objects.get_or_create(
            carrito=carrito, mezcal_id=mezcal_id,
            defaults={'cantidad': cantidad}
        )
        if not item_creado:
            item.cantidad += cantidad
            item.save()

        serializer = self.get_serializer(carrito)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def quitar_item(self, request):
        mezcal_id = request.data.get('mezcal')
        CarritoItem.objects.filter(
            carrito__usuario=request.user, mezcal_id=mezcal_id
        ).delete()
        carrito = Carrito.objects.get(usuario=request.user)
        serializer = self.get_serializer(carrito)
        return Response(serializer.data)
    
class OrdenViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrdenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'rol') and user.rol == 'administrador':
            return Orden.objects.all().select_related('usuario').order_by('-creado_en')
        return Orden.objects.filter(usuario=user)

    def partial_update(self, request, *args, **kwargs):
        """Permite al administrador cambiar el estado de una orden."""
        user = request.user
        if not (hasattr(user, 'rol') and user.rol == 'administrador'):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        estado = request.data.get('estado')
        if estado not in [c[0] for c in Orden.Estado.choices]:
            return Response({'estado': ['Valor no válido.']}, status=status.HTTP_400_BAD_REQUEST)
        instance.estado = estado
        instance.save()
        return Response(OrdenSerializer(instance).data)

    @action(detail=False, methods=['post'])
    def pagar(self, request):
        try:
            carrito = Carrito.objects.get(usuario=request.user)
        except Carrito.DoesNotExist:
            return Response({'error': 'No tienes un carrito.'}, status=status.HTTP_400_BAD_REQUEST)

        items_carrito = carrito.items.all()
        if not items_carrito:
            return Response({'error': 'Tu carrito está vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        for item in items_carrito:
            if item.cantidad > item.mezcal.stock:
                return Response(
                    {'error': f'Stock insuficiente para {item.mezcal.nombre}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        with transaction.atomic():
            total = sum(item.cantidad * item.mezcal.precio for item in items_carrito)
            orden = Orden.objects.create(usuario=request.user, total=total, estado=Orden.Estado.PAGADO)

            for item in items_carrito:
                OrdenItem.objects.create(
                    orden=orden,
                    mezcal=item.mezcal,
                    cantidad=item.cantidad,
                    precio_unitario=item.mezcal.precio,
                )
                item.mezcal.stock -= item.cantidad
                item.mezcal.save()

            items_carrito.delete()

        serializer = self.get_serializer(orden)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class RegistroView(CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

class EsAdministrador(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.rol == 'administrador'
        )


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [EsAdministrador]

    def create(self, request, *args, **kwargs):
        data = request.data
        password = str(data.get('password', '')).strip()
        if not password:
            return Response({'password': ['La contraseña es requerida.']}, status=status.HTTP_400_BAD_REQUEST)
        u = Usuario(
            username=data.get('username', ''),
            email=data.get('email', ''),
            rol=data.get('rol', 'usuario'),
            is_active=str(data.get('is_active', 'true')).lower() in ('true', '1'),
        )
        u.set_password(password)
        u.save()
        return Response(UsuarioSerializer(u).data, status=status.HTTP_201_CREATED)


class ReporteVentasViewSet(viewsets.ViewSet):
    permission_classes = [EsAdministrador]

    def list(self, request):
        ordenes_pagadas = Orden.objects.filter(estado=Orden.Estado.PAGADO)
        total_ventas = ordenes_pagadas.aggregate(total=Sum('total'))['total'] or 0
        total_ordenes = ordenes_pagadas.count()
        ticket_promedio = (total_ventas / total_ordenes) if total_ordenes else 0

        top_articulos = (
            OrdenItem.objects
            .filter(orden__estado=Orden.Estado.PAGADO)
            .values('mezcal__nombre')
            .annotate(cantidad_vendida=Sum('cantidad'))
            .order_by('-cantidad_vendida')[:10]
        )

        ventas_por_usuario = (
            Orden.objects
            .filter(estado=Orden.Estado.PAGADO)
            .values('usuario__username')
            .annotate(total_compras=Count('id'), total_gastado=Sum('total'))
            .order_by('-total_gastado')[:10]
        )

        return Response({
            'kpis': {
                'total_ventas': total_ventas,
                'total_ordenes': total_ordenes,
                'ticket_promedio': ticket_promedio,
            },
            'top_articulos': list(top_articulos),
            'ventas_por_usuario': list(ventas_por_usuario),
        })


class AdminPOSView(TemplateView):
    template_name = 'catalogo/admin_pos/index.html'


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    """Devuelve el perfil del usuario autenticado (para verificar rol en el frontend)."""
    return Response(UsuarioSerializer(request.user).data)

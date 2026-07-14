from rest_framework import viewsets, permissions, status
from .models import Mezcal, Resena, Calificacion, Carrito, CarritoItem, Orden, OrdenItem, Usuario
from .serializers import (
    MezcalSerializer, ResenaSerializer, CalificacionSerializer,
    CarritoSerializer, CarritoItemSerializer, OrdenSerializer,
)
from .serializers import UsuarioSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .serializers import RegistroSerializer
from rest_framework.generics import CreateAPIView
from .permissions import EsAdministradorOSoloLectura, EsPropietarioOAdministrador


class MezcalViewSet(viewsets.ModelViewSet):
    queryset = Mezcal.objects.all()
    serializer_class = MezcalSerializer
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
        return Orden.objects.filter(usuario=self.request.user)

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

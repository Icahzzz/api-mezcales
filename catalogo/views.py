from .models import Mezcal, Orden, OrdenItem, Usuario, ConversacionIA
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Count, Avg
from django.views.generic import TemplateView

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from .models import (Usuario,Categoria,Mezcal,Promocion,Resena,Calificacion,Carrito,CarritoItem,Orden,OrdenItem)

from .permissions import (EsAdministradorOSoloLectura,EsPropietarioOAdministrador
)

from .serializers import (
    RegistroSerializer,
    UsuarioSerializer,
    CategoriaSerializer,
    MezcalSerializer,
    PromocionSerializer,
    ResenaSerializer,
    CalificacionSerializer,
    CarritoSerializer,
    OrdenSerializer
)


# =====================================================
# MEZCALES
# =====================================================

class MezcalViewSet(viewsets.ModelViewSet):

    queryset = Mezcal.objects.all()
    serializer_class = MezcalSerializer
    permission_classes = [EsAdministradorOSoloLectura]


# =====================================================
# CATEGORIAS
# =====================================================

class CategoriaViewSet(viewsets.ModelViewSet):

    queryset = Categoria.objects.all().order_by("nombre")
    serializer_class = CategoriaSerializer
    permission_classes = [EsAdministradorOSoloLectura]


# =====================================================
# PROMOCIONES
# =====================================================

class PromocionViewSet(viewsets.ModelViewSet):

    queryset = Promocion.objects.select_related(
        "mezcal"
    ).all().order_by("-fecha_inicio")

    serializer_class = PromocionSerializer
    permission_classes = [EsAdministradorOSoloLectura]


# =====================================================
# RESEÑAS
# =====================================================

class ResenaViewSet(viewsets.ModelViewSet):

    queryset = Resena.objects.all()
    serializer_class = ResenaSerializer
    permission_classes = [EsPropietarioOAdministrador]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


# =====================================================
# CALIFICACIONES
# =====================================================

class CalificacionViewSet(viewsets.ModelViewSet):

    queryset = Calificacion.objects.all()
    serializer_class = CalificacionSerializer
    permission_classes = [EsPropietarioOAdministrador]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


# =====================================================
# CARRITO
# =====================================================

class CarritoViewSet(viewsets.ModelViewSet):

    serializer_class = CarritoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Carrito.objects.filter(usuario=self.request.user)

    @action(detail=False, methods=["GET"])
    def mio(self, request):

        carrito, creado = Carrito.objects.get_or_create(
            usuario=request.user
        )

        serializer = self.get_serializer(carrito)

        return Response(serializer.data)

    @action(detail=False, methods=["POST"])
    def agregar_item(self, request):

        carrito, creado = Carrito.objects.get_or_create(
            usuario=request.user
        )

        mezcal = request.data.get("mezcal")
        cantidad = int(request.data.get("cantidad", 1))

        item, creado = CarritoItem.objects.get_or_create(
            carrito=carrito,
            mezcal_id=mezcal,
            defaults={
                "cantidad": cantidad
            }
        )

        if not creado:
            item.cantidad += cantidad
            item.save()

        serializer = self.get_serializer(carrito)

        return Response(serializer.data)

    @action(detail=False, methods=["POST"])
    def quitar_item(self, request):

        mezcal = request.data.get("mezcal")

        CarritoItem.objects.filter(
            carrito__usuario=request.user,
            mezcal_id=mezcal
        ).delete()

        carrito, creado = Carrito.objects.get_or_create(
            usuario=request.user
        )

        serializer = self.get_serializer(carrito)

        return Response(serializer.data)

    @action(detail=False, methods=["POST"])
    def sincronizar(self, request):

        carrito, creado = Carrito.objects.get_or_create(
            usuario=request.user
        )

        carrito.items.all().delete()

        items = request.data.get("items", [])

        for item in items:

            CarritoItem.objects.create(
                carrito=carrito,
                mezcal_id=item["mezcal"],
                cantidad=item["cantidad"]
            )

        serializer = self.get_serializer(carrito)

        return Response(serializer.data)


# =====================================================
# ORDENES
# =====================================================

class OrdenViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = OrdenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        if self.request.user.rol == "administrador":
            return Orden.objects.all().order_by("-creado_en")

        return Orden.objects.filter(
            usuario=self.request.user
        )

    @action(detail=False, methods=["POST"])
    def pagar(self, request):

        carrito, creado = Carrito.objects.get_or_create(
            usuario=request.user
        )

        items = carrito.items.all()

        if not items.exists():
            return Response(
                {
                    "error": "El carrito está vacío."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():

            total = 0

            # 1. Validar stock y calcular total real con descuento
            for item in items:
                if item.cantidad > item.mezcal.stock:
                    return Response(
                        {
                            "error": f"Stock insuficiente para {item.mezcal.nombre}"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                precio_unitario = item.mezcal.precio_con_descuento()
                total += item.cantidad * precio_unitario

            # 2. Crear la orden
            orden = Orden.objects.create(
                usuario=request.user,
                total=total,
                estado=Orden.Estado.PAGADO
            )

            # 3. Crear los items de la orden y actualizar stock
            for item in items:
                precio_unitario = item.mezcal.precio_con_descuento()

                OrdenItem.objects.create(
                    orden=orden,
                    mezcal=item.mezcal,
                    cantidad=item.cantidad,
                    precio_unitario=precio_unitario
                )

                item.mezcal.stock -= item.cantidad
                item.mezcal.save()

            # 4. Vaciar el carrito
            items.delete()

        serializer = OrdenSerializer(orden)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

# =====================================================
# REGISTRO
# =====================================================

class RegistroView(CreateAPIView):

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# ADMINISTRADOR
# =====================================================

class EsAdministrador(permissions.BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated
            and request.user.rol == "administrador"
        )


class UsuarioViewSet(viewsets.ModelViewSet):

    queryset = Usuario.objects.all()

    serializer_class = UsuarioSerializer

    permission_classes = [EsAdministrador]


# =====================================================
# REPORTES
# =====================================================

class ReporteVentasViewSet(viewsets.ViewSet):

    permission_classes = [EsAdministrador]

    def list(self, request):

        ordenes = Orden.objects.filter(
            estado=Orden.Estado.PAGADO
        )

        total_ventas = (
            ordenes.aggregate(
                total=Sum("total")
            )["total"] or 0
        )

        total_ordenes = ordenes.count()

        ticket = (
            total_ventas / total_ordenes
            if total_ordenes else 0
        )

        top = (
            OrdenItem.objects
            .filter(orden__estado=Orden.Estado.PAGADO)
            .values("mezcal__nombre")
            .annotate(cantidad=Sum("cantidad"))
            .order_by("-cantidad")[:10]
        )

        usuarios = (
            Orden.objects
            .filter(estado=Orden.Estado.PAGADO)
            .values("usuario__username")
            .annotate(
                compras=Count("id"),
                gastado=Sum("total")
            )
            .order_by("-gastado")
        )

        mejores = (
            Mezcal.objects
            .annotate(
                promedio=Avg("calificaciones__valor"),
                num_calificaciones=Count("calificaciones")
            )
            .filter(num_calificaciones__gt=0)
            .values(
                "nombre",
                "promedio",
                "num_calificaciones"
            )
            .order_by("-promedio")
        )

        return Response({

            "kpis":{

                "total_ventas": total_ventas,
                "total_ordenes": total_ordenes,
                "ticket_promedio": ticket

            },

            "top_articulos": list(top),

            "ventas_por_usuario": list(usuarios),

            "productos_valorados": list(mejores)

        })


# =====================================================
# ADMIN POS
# =====================================================

class AdminPOSView(TemplateView):

    template_name = "catalogo/admin_pos/index.html"


# =====================================================
# USUARIO ACTUAL
# =====================================================

@api_view(["GET", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):

    if request.method == "GET":

        serializer = UsuarioSerializer(request.user)

        return Response(serializer.data)

    serializer = UsuarioSerializer(
        request.user,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():

        serializer.save()

        return Response(serializer.data)

    return Response(
        serializer.errors,
        status=400
    )


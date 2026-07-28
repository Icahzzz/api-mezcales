from rest_framework import serializers
from .models import Categoria, Mezcal, Promocion, Resena, Calificacion, Carrito, CarritoItem, Orden, OrdenItem, Usuario
from django.contrib.auth.password_validation import validate_password
from decimal import Decimal
from django.utils import timezone


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        usuario = Usuario.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return usuario


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion', 'activo']
        read_only_fields = ['id']


class MezcalSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')
    tiene_promocion = serializers.SerializerMethodField()
    precio_final = serializers.SerializerMethodField()
    descuento = serializers.SerializerMethodField()
    tipo_descuento = serializers.SerializerMethodField()
    promocion_texto = serializers.SerializerMethodField()

    class Meta:
        model = Mezcal
        fields = [
            'id',
            'nombre',
            'descripcion',
            'categoria',
            'categoria_nombre',
            'tipo',
            'region',
            'precio',
            'precio_final',
            'tiene_promocion',
            'descuento',
            'tipo_descuento',
            'promocion_texto',
            'stock',
            'imagen',
            'activo',
            'creado_en',
        ]
        read_only_fields = ['id', 'creado_en']

    def _promocion_activa(self, obj):
        hoy = timezone.now().date()
        return obj.promociones.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy
        ).first()

    def get_tiene_promocion(self, obj):
        return self._promocion_activa(obj) is not None

    def get_descuento(self, obj):
        promo = self._promocion_activa(obj)
        return promo.valor_descuento if promo else None

    def get_tipo_descuento(self, obj):
        promo = self._promocion_activa(obj)
        return promo.tipo_descuento if promo else None

    def get_precio_final(self, obj):
        promo = self._promocion_activa(obj)
        if promo is None:
            return obj.precio

        if promo.tipo_descuento == 'porcentaje':
            return obj.precio - (
                obj.precio * promo.valor_descuento / Decimal("100")
            )

        return max(
            Decimal("0"),
            obj.precio - promo.valor_descuento
        )

    def get_promocion_texto(self, obj):
        promo = self._promocion_activa(obj)
        if promo is None:
            return ""

        if promo.tipo_descuento == 'porcentaje':
            return f"{promo.valor_descuento}% OFF"

        return f"-${promo.valor_descuento}"


class PromocionSerializer(serializers.ModelSerializer):
    mezcal_nombre = serializers.ReadOnlyField(source='mezcal.nombre')
    mezcal_imagen = serializers.SerializerMethodField()

    class Meta:
        model = Promocion
        fields = [
            'id', 'nombre', 'descripcion', 'tipo_descuento', 'valor_descuento',
            'fecha_inicio', 'fecha_fin', 'activo', 'mezcal', 'mezcal_nombre', 'mezcal_imagen',
        ]
        read_only_fields = ['id']

    def get_mezcal_imagen(self, obj):
        if obj.mezcal and obj.mezcal.imagen:
            request = self.context.get('request')
            url = obj.mezcal.imagen.url
            return request.build_absolute_uri(url) if request else url
        return None

    def validate(self, data):
        inicio = data.get('fecha_inicio') or getattr(self.instance, 'fecha_inicio', None)
        fin = data.get('fecha_fin') or getattr(self.instance, 'fecha_fin', None)
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError("La fecha fin no puede ser menor que la fecha inicio.")
        return data


class ResenaSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source='usuario.username')
    mezcal_nombre = serializers.ReadOnlyField(source='mezcal.nombre')

    class Meta:
        model = Resena
        fields = ['id', 'usuario', 'mezcal', 'mezcal_nombre', 'comentario', 'creado_en']
        read_only_fields = ['id', 'usuario', 'creado_en']

    def validate(self, data):
        usuario = self.context['request'].user
        mezcal = data.get('mezcal')
        if Resena.objects.filter(usuario=usuario, mezcal=mezcal).exists():
            raise serializers.ValidationError("Ya has dejado una reseña para este mezcal.")
        return data


class CalificacionSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = Calificacion
        fields = ['id', 'usuario', 'mezcal', 'valor', 'creado_en']
        read_only_fields = ['id', 'usuario', 'creado_en']

    def validate(self, data):
        usuario = self.context['request'].user
        mezcal = data.get('mezcal')
        if Calificacion.objects.filter(usuario=usuario, mezcal=mezcal).exists():
            raise serializers.ValidationError("Ya has calificado este mezcal.")
        return data

    def validate_valor(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("La calificación debe estar entre 1 y 5.")
        return value


class CarritoItemSerializer(serializers.ModelSerializer):
    mezcal_nombre = serializers.ReadOnlyField(source='mezcal.nombre')
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CarritoItem
        fields = ['id', 'mezcal', 'mezcal_nombre', 'cantidad', 'subtotal']
        read_only_fields = ['id']

    def get_subtotal(self, obj):
        precio = getattr(obj.mezcal, 'precio_con_descuento', None)
        if callable(precio):
            return obj.cantidad * obj.mezcal.precio_con_descuento()
        return obj.cantidad * obj.mezcal.precio


class CarritoSerializer(serializers.ModelSerializer):
    items = CarritoItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Carrito
        fields = ['id', 'usuario', 'items', 'total', 'creado_en']
        read_only_fields = ['id', 'usuario', 'creado_en']

    def get_total(self, obj):
        total_acumulado = Decimal("0")
        for item in obj.items.all():
            precio_func = getattr(item.mezcal, 'precio_con_descuento', None)
            if callable(precio_func):
                precio = item.mezcal.precio_con_descuento()
            else:
                precio = item.mezcal.precio
            total_acumulado += item.cantidad * precio
        return total_acumulado


class OrdenItemSerializer(serializers.ModelSerializer):
    mezcal_nombre = serializers.ReadOnlyField(source="mezcal.nombre")
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = OrdenItem
        fields = [
            "id",
            "mezcal",
            "mezcal_nombre",
            "imagen",
            "cantidad",
            "precio_unitario",
        ]

    def get_imagen(self, obj):
        if obj.mezcal and obj.mezcal.imagen:
            request = self.context.get('request')
            url = obj.mezcal.imagen.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class OrdenSerializer(serializers.ModelSerializer):
    items = OrdenItemSerializer(many=True, read_only=True)
    usuario = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = Orden
        fields = ['id', 'usuario', 'total', 'estado', 'items', 'creado_en']
        read_only_fields = ['id', 'usuario', 'total', 'estado', 'items', 'creado_en']


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'email',
            'rol',
            'is_active',
            'date_joined'
        ]
        read_only_fields = [
            'id',
            'rol',
            'is_active',
            'date_joined'
        ]


class IARequestSerializer(serializers.Serializer):
    pregunta = serializers.CharField()

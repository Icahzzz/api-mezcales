from rest_framework import serializers
from .models import Categoria, Mezcal, Promocion, Resena, Calificacion, Carrito, CarritoItem, Orden, OrdenItem
from django.contrib.auth.password_validation import validate_password
from .models import Usuario


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

    class Meta:
        model = Mezcal
        fields = [
            'id', 'nombre', 'descripcion', 'categoria', 'categoria_nombre', 'tipo', 'region',
            'precio', 'stock', 'imagen', 'activo', 'creado_en',
        ]
        read_only_fields = ['id', 'creado_en']


class PromocionSerializer(serializers.ModelSerializer):
    mezcal_nombre = serializers.ReadOnlyField(source='mezcal.nombre')

    class Meta:
        model = Promocion
        fields = [
            'id', 'nombre', 'descripcion', 'tipo_descuento', 'valor_descuento',
            'fecha_inicio', 'fecha_fin', 'activo', 'mezcal', 'mezcal_nombre',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        inicio = data.get('fecha_inicio') or getattr(self.instance, 'fecha_inicio', None)
        fin = data.get('fecha_fin') or getattr(self.instance, 'fecha_fin', None)
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError("La fecha fin no puede ser menor que la fecha inicio.")
        return data

class ResenaSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = Resena
        fields = ['id', 'usuario', 'mezcal', 'comentario', 'creado_en']
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
        return obj.cantidad * obj.mezcal.precio


class CarritoSerializer(serializers.ModelSerializer):
    items = CarritoItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Carrito
        fields = ['id', 'usuario', 'items', 'total', 'creado_en']
        read_only_fields = ['id', 'usuario', 'creado_en']

    def get_total(self, obj):
        return sum(item.cantidad * item.mezcal.precio for item in obj.items.all())

class OrdenItemSerializer(serializers.ModelSerializer):
    mezcal_nombre = serializers.ReadOnlyField(source='mezcal.nombre')

    class Meta:
        model = OrdenItem
        fields = ['id', 'mezcal', 'mezcal_nombre', 'cantidad', 'precio_unitario']
        read_only_fields = ['id', 'precio_unitario']


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
        fields = ['id', 'username', 'email', 'rol', 'is_active', 'date_joined']

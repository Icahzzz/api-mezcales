from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        INVITADO = 'invitado', 'Invitado'
        USUARIO = 'usuario', 'Usuario'
        ADMINISTRADOR = 'administrador', 'Administrador'

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.USUARIO,
    )

    def __str__(self):
        return f"{self.username} ({self.rol})"


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nombre
    
class Mezcal(models.Model):
    class Tipo(models.TextChoices):
        JOVEN = 'joven', 'Joven'
        REPOSADO = 'reposado', 'Reposado'
        ANEJO = 'anejo', 'Añejo'
        ANCESTRAL = 'ancestral', 'Ancestral'

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='mezcales')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.JOVEN)
    region = models.CharField(max_length=100, blank=True)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='mezcales/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mezcal"
        verbose_name_plural = "Mezcales"

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

    def promocion_activa(self):
        from django.utils import timezone
        hoy = timezone.now().date()

        return self.promociones.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy
        ).first()

    def precio_con_descuento(self):
        from decimal import Decimal

        promo = self.promocion_activa()

        if promo is None:
            return self.precio

        if promo.tipo_descuento == 'porcentaje':
            return self.precio - (self.precio * promo.valor_descuento / Decimal("100"))

        return max(Decimal("0"), self.precio - promo.valor_descuento)

class Promocion(models.Model):
    class TipoDescuento(models.TextChoices):
        PORCENTAJE = 'porcentaje', 'Porcentaje'
        MONTO_FIJO = 'monto_fijo', 'Monto fijo'

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    tipo_descuento = models.CharField(max_length=20, choices=TipoDescuento.choices, default=TipoDescuento.PORCENTAJE)
    valor_descuento = models.DecimalField(max_digits=8, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=True)
    mezcal = models.ForeignKey(Mezcal, on_delete=models.CASCADE, related_name='promociones', null=True, blank=True)

    class Meta:
        verbose_name = "Promocion"
        verbose_name_plural = "Promociones"

    def __str__(self):
        return self.nombre
    
class Resena(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='resenas')
    mezcal = models.ForeignKey(Mezcal, on_delete=models.CASCADE, related_name='resenas')
    comentario = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'mezcal')

    def __str__(self):
        return f"Reseña de {self.usuario.username} sobre {self.mezcal.nombre}"


class Calificacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='calificaciones')
    mezcal = models.ForeignKey(Mezcal, on_delete=models.CASCADE, related_name='calificaciones')
    valor = models.PositiveSmallIntegerField()  # 1 a 5
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'mezcal')

    def __str__(self):
        return f"{self.usuario.username} calificó {self.mezcal.nombre} con {self.valor}"
    
class Carrito(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='carrito')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carrito de {self.usuario.username}"


class CarritoItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    mezcal = models.ForeignKey(Mezcal, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('carrito', 'mezcal')

    def __str__(self):
        return f"{self.cantidad} x {self.mezcal.nombre}"
    
class Orden(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PAGADO = 'pagado', 'Pagado'
        CANCELADO = 'cancelado', 'Cancelado'

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ordenes')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Orden #{self.id} de {self.usuario.username} ({self.estado})"


class OrdenItem(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='items')
    mezcal = models.ForeignKey(Mezcal, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.mezcal.nombre} (orden #{self.orden.id})"
class ConversacionIA(models.Model):

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="conversaciones_ia"
    )

    pregunta = models.TextField()

    respuesta = models.TextField()

    creado_en = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.usuario.username

import json

from groq import Groq

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated

from django.db.models import Sum, Count, Avg

from decouple import config

from .models import Mezcal, Orden, OrdenItem, Usuario


class EsAdministrador(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == "administrador"
        )


def obtener_cliente():
    api_key = config("GROQ_API_KEY", default="")
    if not api_key:
        raise ValueError("No existe GROQ_API_KEY en el archivo .env")
    return Groq(api_key=api_key)


def preguntar_ia(system, prompt, temperature=0.6):
    client = obtener_cliente()
    respuesta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        max_tokens=800,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return respuesta.choices[0].message.content


def limpiar_json(texto):
    texto = texto.strip()
    if texto.startswith("```json"):
        texto = texto.replace("```json", "", 1)
    if texto.startswith("```"):
        texto = texto.replace("```", "", 1)
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()


# ============================================================
# ENDPOINTS SOLO PARA ADMINISTRADOR (datos internos del negocio)
# ============================================================

@api_view(["POST"])
@permission_classes([EsAdministrador])
def chatbot_view(request):
    mensaje = request.data.get("mensaje", "").strip()
    historial = request.data.get("historial", [])
    if not mensaje:
        return Response({"error": "Campo mensaje requerido."}, status=400)

    activos = Mezcal.objects.filter(activo=True).count()
    ventas = Orden.objects.filter(estado="pagado").aggregate(total=Sum("total"))["total"] or 0
    stock_bajo = Mezcal.objects.filter(activo=True, stock__lt=10).count()

    system = f"""Eres un asistente experto en una tienda de mezcales artesanales.
Ayudas únicamente al administrador.
Puedes responder preguntas sobre: ventas, inventario, promociones, marketing, clientes, reportes.

Estado actual del negocio:
Artículos activos: {activos}
Ventas acumuladas: ${float(ventas):,.2f} MXN
Productos con poco stock: {stock_bajo}

Responde siempre en español. Sé claro y profesional."""

    conversacion = ""
    for h in historial[-10:]:
        if h.get("role") == "user":
            conversacion += f"Usuario: {h.get('content')}\n"
        elif h.get("role") == "assistant":
            conversacion += f"Asistente: {h.get('content')}\n"
    conversacion += f"\nUsuario: {mensaje}"

    try:
        respuesta = preguntar_ia(system, conversacion, temperature=0.7)
        return Response({"respuesta": respuesta})
    except ValueError as e:
        return Response({"error": str(e)}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([EsAdministrador])
def sugerencias_view(request):
    stock_bajo = list(Mezcal.objects.filter(activo=True, stock__lt=10).values("nombre", "stock"))
    top = list(
        OrdenItem.objects.filter(orden__estado="pagado")
        .values("mezcal__nombre")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")[:5]
    )
    sin_ventas = list(
        Mezcal.objects.filter(activo=True).exclude(
            id__in=OrdenItem.objects.filter(orden__estado="pagado").values("mezcal_id")
        ).values("nombre")[:5]
    )
    ordenes = Orden.objects.filter(estado="pagado").count()

    prompt = f"""Analiza la siguiente información.

Stock bajo:
{json.dumps(stock_bajo, ensure_ascii=False)}

Productos más vendidos:
{json.dumps(top, ensure_ascii=False)}

Productos sin ventas:
{json.dumps(sin_ventas, ensure_ascii=False)}

Órdenes pagadas: {ordenes}

Devuelve únicamente un JSON válido con este formato.
{{"sugerencias":[{{"tipo":"","titulo":"","descripcion":"","prioridad":""}}]}}

No escribas texto adicional."""

    system = "Eres un consultor experto en retail. Solo respondes JSON válido. Nunca agregues explicaciones."

    try:
        respuesta = preguntar_ia(system, prompt, temperature=0.3)
        respuesta = limpiar_json(respuesta)
        return Response(json.loads(respuesta))
    except ValueError as e:
        return Response({"error": str(e)}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([EsAdministrador])
def personalizacion_view(request):
    usuario_id = request.query_params.get("usuario_id")

    if usuario_id:
        try:
            usuario = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            return Response({"error": "Usuario no encontrado."}, status=404)

        compras = list(
            OrdenItem.objects.filter(orden__usuario=usuario, orden__estado="pagado")
            .values("mezcal__nombre", "mezcal__tipo", "mezcal__region")
            .annotate(cantidad=Sum("cantidad"))
            .order_by("-cantidad")[:10]
        )
        gasto = Orden.objects.filter(usuario=usuario, estado="pagado").aggregate(total=Sum("total"))["total"] or 0

        prompt = f"""Analiza este cliente.

Nombre: {usuario.username}
Compras: {json.dumps(compras, ensure_ascii=False)}
Gasto total: ${float(gasto):,.2f}

Devuelve únicamente JSON.
{{"nombre_cliente":"","perfil":"","recomendaciones":[{{"mezcal_sugerido":"","razon":""}}],"estrategia_fidelizacion":""}}"""

    else:
        segmentos = list(
            Orden.objects.filter(estado="pagado")
            .values("usuario__username")
            .annotate(ordenes=Count("id"), total=Sum("total"))
            .order_by("-total")[:10]
        )
        prompt = f"""Analiza estos segmentos.
{json.dumps(segmentos, ensure_ascii=False)}

Devuelve únicamente JSON.
{{"segmentos":[{{"nombre":"","descripcion":"","estrategia":""}}],"recomendacion_global":""}}"""

    system = "Eres un experto en CRM. Solo respondes JSON válido."

    try:
        respuesta = preguntar_ia(system, prompt, temperature=0.4)
        respuesta = limpiar_json(respuesta)
        return Response(json.loads(respuesta))
    except ValueError as e:
        return Response({"error": str(e)}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ============================================================
# ENDPOINT PARA CUALQUIER USUARIO AUTENTICADO (solo datos públicos)
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recomendaciones_view(request):
    mensaje = request.data.get("mensaje", "").strip()
    presupuesto = request.data.get("presupuesto")

    if not mensaje:
        return Response({"error": "Campo mensaje requerido."}, status=400)

    # Solo datos públicos del catálogo (nada de cifras de negocio)
    catalogo = list(
        Mezcal.objects.filter(activo=True)
        .annotate(promedio_calificacion=Avg("calificaciones__valor"))
        .values("nombre", "tipo", "region", "precio", "promedio_calificacion")
    )

    mas_vendidos = list(
        OrdenItem.objects.filter(orden__estado="pagado")
        .values("mezcal__nombre")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")[:5]
    )

    contexto_presupuesto = f"\nPresupuesto del cliente: ${float(presupuesto):,.2f} MXN" if presupuesto else ""

    system = f"""Eres un asistente de ventas de una tienda de mezcales artesanales.
Ayudas a los clientes a elegir el mezcal ideal según sus gustos y presupuesto.
No reveles cifras internas del negocio (ventas totales, ingresos, stock exacto).
Solo recomienda productos activos del catálogo.

Catálogo disponible:
{json.dumps(catalogo, ensure_ascii=False, default=str)}

Productos más vendidos (populares entre clientes):
{json.dumps(mas_vendidos, ensure_ascii=False)}
{contexto_presupuesto}

Responde en español, de forma amigable y breve. Recomienda productos específicos del catálogo con su precio."""

    try:
        respuesta = preguntar_ia(system, mensaje, temperature=0.6)
        return Response({"respuesta": respuesta})
    except ValueError as e:
        return Response({"error": str(e)}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
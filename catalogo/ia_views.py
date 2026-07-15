import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.conf import settings
from rest_framework import permissions


class EsAdministrador(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.rol == 'administrador'
        )
from .models import Mezcal, Orden, OrdenItem, Usuario


def _client():
    from openai import OpenAI
    key = getattr(settings, 'OPENAI_API_KEY', '')
    if not key:
        raise ValueError('OPENAI_API_KEY no está configurada en el archivo .env')
    return OpenAI(api_key=key)


@api_view(['POST'])
@permission_classes([EsAdministrador])
def chatbot_view(request):
    mensaje = request.data.get('mensaje', '').strip()
    historial = request.data.get('historial', [])
    if not mensaje:
        return Response({'error': 'Campo mensaje requerido.'}, status=400)

    activos = Mezcal.objects.filter(activo=True).count()
    ventas = Orden.objects.filter(estado='pagado').aggregate(t=Sum('total'))['t'] or 0
    stock_bajo = Mezcal.objects.filter(activo=True, stock__lt=10).count()

    system = (
        "Eres un asistente experto de la tienda de mezcales artesanales. "
        "Ayudas al administrador con análisis de ventas, gestión de inventario, "
        "estrategias de marketing y conocimiento sobre mezcales.\n"
        f"Estado actual: {activos} artículos activos, "
        f"${float(ventas):,.2f} MXN en ventas, "
        f"{stock_bajo} artículos con stock bajo (<10 unidades). "
        "Responde de forma concisa, amigable y práctica."
    )

    try:
        client = _client()
        messages = [{'role': 'system', 'content': system}]
        messages += [h for h in historial[-10:] if h.get('role') in ('user', 'assistant')]
        messages.append({'role': 'user', 'content': mensaje})
        resp = client.chat.completions.create(
            model='gpt-4o-mini', messages=messages, max_tokens=500, temperature=0.7
        )
        return Response({'respuesta': resp.choices[0].message.content})
    except ValueError as e:
        return Response({'error': str(e)}, status=503)
    except ImportError:
        return Response({'error': 'Instala openai: pip install openai>=1.0.0'}, status=503)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([EsAdministrador])
def sugerencias_view(request):
    stock_bajo = list(Mezcal.objects.filter(activo=True, stock__lt=10).values('nombre', 'stock'))
    top = list(
        OrdenItem.objects.filter(orden__estado='pagado')
        .values('mezcal__nombre')
        .annotate(total=Sum('cantidad'))
        .order_by('-total')[:5]
    )
    sin_ventas = list(
        Mezcal.objects.filter(activo=True).exclude(
            id__in=OrdenItem.objects.filter(orden__estado='pagado').values('mezcal_id')
        ).values('nombre')[:5]
    )
    ordenes = Orden.objects.filter(estado='pagado').count()

    prompt = (
        "Analiza los datos de la tienda de mezcales y proporciona exactamente 6 sugerencias accionables.\n"
        f"Stock bajo (<10 unidades): {json.dumps(stock_bajo, ensure_ascii=False)}\n"
        f"Top 5 más vendidos: {json.dumps(top, ensure_ascii=False)}\n"
        f"Artículos sin ventas: {json.dumps(sin_ventas, ensure_ascii=False)}\n"
        f"Órdenes completadas: {ordenes}\n\n"
        'Responde ÚNICAMENTE con JSON válido: '
        '{"sugerencias": [{"tipo": "inventario|ventas|marketing|promocion|operacion", '
        '"titulo": "titulo corto", "descripcion": "descripcion accionable y específica", '
        '"prioridad": "alta|media|baja"}]}'
    )

    try:
        client = _client()
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'Eres consultor de retail de bebidas artesanales. Responde SOLO con JSON válido.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=900, temperature=0.4,
            response_format={'type': 'json_object'}
        )
        return Response(json.loads(resp.choices[0].message.content))
    except ValueError as e:
        return Response({'error': str(e)}, status=503)
    except ImportError:
        return Response({'error': 'Instala openai: pip install openai>=1.0.0'}, status=503)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([EsAdministrador])
def personalizacion_view(request):
    usuario_id = request.query_params.get('usuario_id')

    if usuario_id:
        try:
            u = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado.'}, status=404)
        compras = list(
            OrdenItem.objects.filter(orden__usuario=u, orden__estado='pagado')
            .values('mezcal__nombre', 'mezcal__tipo', 'mezcal__region')
            .annotate(cantidad=Sum('cantidad'))
            .order_by('-cantidad')[:10]
        )
        gasto = Orden.objects.filter(usuario=u, estado='pagado').aggregate(t=Sum('total'))['t'] or 0
        prompt = (
            f"Analiza el historial del cliente '{u.username}': "
            f"compras={json.dumps(compras, ensure_ascii=False)}, "
            f"gasto total=${float(gasto):,.2f} MXN.\n"
            'Devuelve JSON: {"nombre_cliente":"...","perfil":"descripcion del perfil",'
            '"recomendaciones":[{"mezcal_sugerido":"...","razon":"..."}],'
            '"estrategia_fidelizacion":"..."}'
        )
    else:
        segmentos = list(
            Orden.objects.filter(estado='pagado')
            .values('usuario__username')
            .annotate(ordenes=Count('id'), total=Sum('total'))
            .order_by('-total')[:10]
        )
        prompt = (
            f"Analiza los segmentos de clientes: {json.dumps(segmentos, ensure_ascii=False)}.\n"
            'Devuelve JSON: {"segmentos":[{"nombre":"...","descripcion":"...","estrategia":"..."}],'
            '"recomendacion_global":"..."}'
        )

    try:
        client = _client()
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'Experto en CRM de bebidas artesanales. Responde SOLO con JSON válido.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=700, temperature=0.5,
            response_format={'type': 'json_object'}
        )
        return Response(json.loads(resp.choices[0].message.content))
    except ValueError as e:
        return Response({'error': str(e)}, status=503)
    except ImportError:
        return Response({'error': 'Instala openai: pip install openai>=1.0.0'}, status=503)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

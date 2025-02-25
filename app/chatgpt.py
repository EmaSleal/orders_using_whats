import openai
import json
from app.config import Config

client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

def verificar_pedido_con_chatgpt(productos_pedido, productos_disponibles):
    """
    Usa ChatGPT para validar productos en un pedido y sugerir correcciones si es necesario.
    Devuelve una respuesta JSON con "productos_validos" y "productos_sugeridos".
    """
    prompt = f"""
    Un cliente ha hecho un pedido con los siguientes productos:
    {productos_pedido}

    Los productos disponibles en el inventario son:
    {productos_disponibles}

    Revisa si hay productos en el pedido que no coinciden con los disponibles.
    - Si un producto coincide exactamente, agrégalo a "productos_validos".
    - Si un producto tiene un error de escritura, sugiere la versión correcta en "productos_sugeridos".
    - Si un producto no existe, ignóralo.

    Responde en formato JSON como este:
    {{
        "productos_validos": ["8 cloro 1/2 gal", "2 desinfectante ltr"],
        "productos_sugeridos": {{"papael jumbro rol": "papel jumbo roll"}}
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en validación de pedidos."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5
    )

    return response.choices[0].message.content

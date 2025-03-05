import requests
import json

def verificar_intencion_y_formato(mensaje):
    """
    Usa un modelo de IA local para analizar la intención del mensaje (Pedido, Reporte, Agregar Artículo)
    y devuelve la versión corregida si es necesario.
    - Si la intención y el formato están correctos, devuelve "true".
    - Si la intención es correcta, pero el formato es incorrecto, devuelve el mensaje corregido.
    - Si la intención es incorrecta, devuelve "false".
    """

    # 📌 Definir el prompt para la IA
    prompt = f"""
    Un usuario ha enviado el siguiente mensaje por WhatsApp:
    "{mensaje}"

    Determina cuál es la intención del mensaje:
    - Si es un **pedido**, estructura el mensaje en este formato:
      pedido:
      CLIENTE
      FECHA DE ENTREGA
      CANTIDAD ARTICULO
      CANTIDAD ARTICULO

    - Si es un **reporte**, estructura el mensaje en este formato:
      reporte:
      hoy
      reporte:
      20/02 a hoy
      reporte:
      20/02/2025 a hoy
      reporte:
      20/02/25 a hoy
      reporte:
      3 (desde hace 3 días a hoy)

    - Si es para **agregar artículos**, devuelve simplemente:
      "Agregar articulo"

    Responde SOLO con:
    - "true" si el formato y la intención son correctos.
    - El mensaje corregido si la intención es correcta pero el formato está mal.
    - "false" si la intención y el formato no tienen sentido.
    """

    # 📌 Hacer el request a la API local
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "deepseek-r1:7b",
        "prompt": prompt,
        "stream": False,
        "format": "json"  # Para asegurar que la respuesta sea JSON
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Lanza error si el request falla
        data = response.json()

        # 📌 Extraer la respuesta generada
        if "response" in data:
            resultado = data["response"].strip()
            if resultado.lower() == "true" or resultado.lower() == "false":
                return resultado
            return resultado  # Devuelve el mensaje corregido si el formato estaba mal
        
        return "false"  # Si no se entiende el mensaje, devuelve falso
    
    except requests.RequestException as e:
        return {"error": f"Fallo en la API local: {str(e)}"}

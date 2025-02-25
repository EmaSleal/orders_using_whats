from flask import jsonify
from app.database import ejecutar_sp
from app.whatsapp import enviar_mensaje_whatsapp
from datetime import datetime, timedelta
from rapidfuzz import process
from app.chatgpt import verificar_pedido_con_chatgpt
import json
import pandas as pd

def insertar_articulos_desde_excel(file_path):
    """
    Procesa un archivo Excel e inserta los artículos en la base de datos.
    """
    try:
        # Leer el archivo de Excel
        df = pd.read_excel(file_path)

        # Verificar que contiene las columnas necesarias
        required_columns = ['Descripcion', 'Presentacion', 'Codigo', 'Institucional', 'Mayorista']
        for col in required_columns:
            if col not in df.columns:
                return {"error": f"El archivo no contiene la columna requerida: {col}"}

        # Limpiar y normalizar los datos
        df = df.dropna(subset=['Descripcion', 'Presentacion', 'Codigo'])  # Eliminar filas vacías
        df['Presentacion'] = df['Presentacion'].str.strip().str.lower().str.capitalize()

        # Insertar presentaciones y productos en la base de datos
        for _, row in df.iterrows():
            descripcion = row['Descripcion'].replace("'", "''")  # Escapar comillas
            presentacion = row['Presentacion'].replace("'", "''")
            codigo = row['Codigo']
            precio_institucional = row['Institucional'] if not pd.isna(row['Institucional']) else 0
            precio_mayorista = row['Mayorista'] if not pd.isna(row['Mayorista']) else 0

            # Insertar presentación y obtener ID
            resultado = ejecutar_sp("InsertarPresentacion", (presentacion, 0))

            # 📌 Asegurar que `InsertarPresentacion` devolvió un ID válido
            if resultado and len(resultado[0]) > 0:
                id_presentacion = resultado[0][0][0]  # Extraer el ID de la presentación
            else:
                return {"error": f"No se pudo obtener un ID para la presentación '{presentacion}'"}

            # Insertar producto
            ejecutar_sp("InsertarProducto", (descripcion, codigo, id_presentacion, precio_institucional, precio_mayorista,0))

        return {"message": "Artículos agregados correctamente"}

    except Exception as e:
        return {"error": str(e)}


def procesar_reporte(message_body, phone_number):
    """
    Procesa un mensaje de reporte y envía los resultados por WhatsApp.
    """
    lines = message_body.split("\n")
    if len(lines) > 1:
        fecha_str = lines[1].strip()
        fecha_inicio, fecha_fin = procesar_fechas_reporte(fecha_str)

        if fecha_inicio and fecha_fin:
            reporte = obtener_reporte_por_articulo(fecha_inicio, fecha_fin)
            enviar_mensaje_whatsapp(phone_number, reporte)
            return jsonify({"message": "Reporte enviado con éxito"}), 200
        else:
            return jsonify({"error": "Formato de fecha inválido"}), 400
    
    return jsonify({"error": "Formato inválido para el mensaje de reporte."}), 400

def procesar_pedido(message_body, phone_number):
    """
    Procesa solicitudes de pedido y almacena la factura en la base de datos.
    """
    lines = message_body.split("\n")

    if len(lines) < 3:
        return {"error": "Formato de pedido inválido"}, 400

    client_line = lines[1].strip().lower()  # Nombre del cliente
    fecha_entrega_str = lines[2].strip()  # Fecha de entrega

    fecha_entrega = extraer_fecha_entrega(fecha_entrega_str)

    if fecha_entrega is None:
        return jsonify({"error": "Formato de fecha de entrega inválido"}), 400

    # 📌 Determinar si es un cliente mayorista
    palabras_mayorista = ["mayorista", "wholesale", "distribuidor", "b2b"]
    mejor_coincidencia = process.extractOne(client_line, palabras_mayorista, score_cutoff=80)
    es_mayorista = mejor_coincidencia is not None  # ✅ Evitar error de NoneType

    # 📌 Extraer el nombre del cliente sin "mayorista"
    client_name = client_line
    for palabra in palabras_mayorista:
        client_name = client_name.replace(palabra, "").strip()

    # 📌 Buscar cliente en la base de datos con coincidencia difusa
    cliente = buscar_cliente_por_nombre(client_name)

    if cliente is None:
        return {"error": "No se encontró un cliente con suficiente coincidencia"}, 404

    id_cliente = cliente["idCliente"]
    mejor_nombre_cliente = cliente["nombreCliente"]
    similitud_cliente = cliente["similitud"]

    print(f"✅ Cliente encontrado: {mejor_nombre_cliente} (Similitud: {similitud_cliente}%)")
    print(f"📌 Tipo de cliente: {'Mayorista' if es_mayorista else 'Institucional'}")

    # 📌 Procesar productos
    id_factura = None
    for line in lines[3:]:  # Procesar productos desde la cuarta línea
        parts = line.split(" ", 1)

        # ✅ Evitar error de "list index out of range"
        if len(parts) < 2:
            print(f"❌ Error: Línea de producto inválida -> '{line}'")  # Debugging
            continue

        try:
            cantidad = int(parts[0])
        except ValueError:
            print(f"❌ Error: Cantidad inválida en línea -> '{line}'")  # Debugging
            continue

        nombre_producto = parts[1].strip()

        # 📌 Buscar el producto en la base de datos con coincidencia difusa
        producto = buscar_producto_por_nombre(nombre_producto)

        if producto is None:
            print(f"❌ Error: Producto no encontrado -> '{nombre_producto}'")  # Debugging
            continue

        id_producto = producto["idProducto"]
        mejor_nombre_producto = producto["nombreProducto"]
        similitud_producto = producto["similitud"]

        # 📌 Seleccionar el precio correcto
        precio_producto = producto["precioMayorista"] if es_mayorista else producto["precioInstitucional"]

        print(f"✅ Producto encontrado: {mejor_nombre_producto} (Similitud: {similitud_producto}%)")
        print(f"📌 Precio usado: {precio_producto} ({'Mayorista' if es_mayorista else 'Institucional'})")

        if id_factura is None:
            id_factura = crear_factura(id_cliente, fecha_entrega, es_mayorista)

        insertar_linea_factura(id_factura, id_producto, cantidad, precio_producto)

    if id_factura:
        actualizar_total_factura(id_factura, phone_number)
        return {"message": f"Pedido registrado para {mejor_nombre_cliente} (ID: {id_cliente})"}, 200
    else:
        return {"error": "No se pudo crear la factura"}, 500



def procesar_fechas_reporte(fecha_str):
    """
    Convierte diferentes formatos de fecha en un rango de fechas para la consulta.
    """
    fecha_str = fecha_str.strip().lower()
    hoy = datetime.today().strftime('%Y-%m-%d')

    if fecha_str == "hoy":
        return hoy, hoy

    if "a hoy" in fecha_str:
        fecha_inicio_str = fecha_str.split(" a hoy")[0].strip()
        fecha_inicio = extraer_fecha_entrega(fecha_inicio_str)
        return fecha_inicio, hoy

    if fecha_str.isdigit():
        dias = int(fecha_str)
        fecha_inicio = (datetime.today() - timedelta(days=dias)).strftime('%Y-%m-%d')
        return fecha_inicio, hoy

    return None, None

def obtener_reporte_por_articulo(fecha_inicio, fecha_fin):
    """
    Obtiene un resumen de productos pedidos en un rango de fechas, incluyendo su presentación.
    """
    resultados = ejecutar_sp("ObtenerReportePorArticulo", (fecha_inicio, fecha_fin))

    if resultados and len(resultados[0]) > 0:
        reporte = f"📊 Reporte de pedidos desde {fecha_inicio} hasta {fecha_fin}:\n"
        for item in resultados[0]:
            id_producto = item[0]
            nombre_producto = item[1]  # Ya viene en formato "Descripción (Presentación)"
            cantidad_total = item[2]

            reporte += f"- {cantidad_total}x {nombre_producto}\n"

        return reporte
    else:
        return f"No hay pedidos registrados entre {fecha_inicio} y {fecha_fin}."


def procesar_fechas_reporte(fecha_str):
    """
    Convierte diferentes formatos de fecha en un rango de fechas para la consulta.
    """
    fecha_str = fecha_str.strip().lower()
    hoy = datetime.today().strftime('%Y-%m-%d')

    # Caso: "hoy"
    if fecha_str == "hoy":
        return hoy, hoy

    # Caso: "20/02 a hoy"
    if "a hoy" in fecha_str:
        fecha_inicio_str = fecha_str.split(" a hoy")[0].strip()
        fecha_inicio = extraer_fecha_entrega(fecha_inicio_str)
        return fecha_inicio, hoy

    # Caso: "3" (últimos N días)
    if fecha_str.isdigit():
        dias = int(fecha_str)
        fecha_inicio = (datetime.today() - timedelta(days=dias)).strftime('%Y-%m-%d')
        return fecha_inicio, hoy

    # Si la fecha no coincide con los formatos anteriores, devolver None
    return None, None

def actualizar_total_factura(id_factura, phone_number):
    """
    Actualiza el total de una factura y envía un mensaje de WhatsApp con los detalles.
    """
    try:
        ejecutar_sp("ActualizarTotalFactura", (id_factura,))
        factura_info = obtener_factura_completa(id_factura)
        
        if factura_info:
            enviar_mensaje_whatsapp(phone_number, factura_info)
            print(f"Factura {id_factura} actualizada y mensaje enviado a {phone_number}")
        else:
            print(f"No se pudo obtener la información de la factura {id_factura}")
    except Exception as e:
        print(f"Error al actualizar el total de la factura {id_factura}: {e}")

def extraer_fecha_entrega(fecha_str):
    """
    Intenta convertir diferentes formatos de fecha a un formato estándar (YYYY-MM-DD).
    Si la fecha es "hoy", usa la fecha actual.
    """
    fecha_str = fecha_str.strip().lower()

    if fecha_str == "hoy":
        return datetime.today().strftime('%Y-%m-%d')

    formatos = ['%d/%m/%Y', '%d/%m/%y', '%d/%m']  
    for formato in formatos:
        try:
            fecha = datetime.strptime(fecha_str, formato)
            
            # Si el formato es "%d/%m" y no tiene año, asumimos el año actual.
            if formato == '%d/%m':
                fecha = fecha.replace(year=datetime.today().year)
            
            return fecha.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None

def obtener_factura_completa(id_factura):
    """
    Obtiene los detalles completos de la factura usando el SP 'ObtenerFacturaCompleta'.
    """
    resultados = ejecutar_sp("ObtenerFacturaCompleta", (id_factura,))

    if resultados and len(resultados) == 3:
        cliente_info = resultados[0][0] if resultados[0] else None
        detalle_factura = resultados[1] if resultados[1] else []
        total_factura = resultados[2][0] if resultados[2] else None

        if cliente_info and total_factura:
            mensaje = f"🧾 Factura #{id_factura}\n"
            mensaje += f"👤 Cliente: {cliente_info[1]}\n📞 Teléfono: {cliente_info[3]}\n"
            mensaje += f"📅 Fecha: {cliente_info[4]}\n🚚 Entrega: {cliente_info[5]}\n"
            mensaje += f"🛒 Tipo: {cliente_info[6]}\n"
            mensaje += "📦 Detalle:\n"
            for item in detalle_factura:
                mensaje += f"- {item[3]}x {item[2]} (₡{item[4]} c/u) = ₡{item[5]}\n"

            mensaje += f"\n💰 Total: ₡{total_factura[1]}"
            return mensaje
    return None

# def buscar_o_insertar_producto(nombre_producto):
#     """
#     Busca un producto por nombre utilizando similitud de texto con RapidFuzz.
#     Si no existe un producto con suficiente coincidencia, lo inserta y devuelve un objeto con el ID, nombre y precio.
#     """
#     producto_existente = buscar_producto_por_nombre(nombre_producto)

#     if producto_existente:
#         # Producto encontrado con coincidencia alta
#         id_producto = producto_existente["idProducto"]
#         nombre_producto = producto_existente["nombreProducto"]
#         precio_producto = producto_existente.get("precioProducto", 0)
#         print(f"Producto encontrado: {nombre_producto} (ID: {id_producto}, Precio: {precio_producto})")
#     else:
#         # Producto no encontrado, insertar
#         print(f"Producto no encontrado, insertando nuevo: {nombre_producto}")
#         resultados = ejecutar_sp("InsertarProducto", (nombre_producto, nombre_producto, 0, 0))
#         if resultados:
#             id_producto = resultados[0][0][0]  # ID del producto insertado
#             precio_producto = 0  # Precio por defecto si no se proporciona
#             print(f"Producto insertado con ID: {id_producto}")
#         else:
#             return None  # Si hay un error al insertar, retornamos None

#     # Retornar un objeto con los datos del producto
#     return {
#         "id": id_producto,
#         "nombre": nombre_producto,
#         "precio": precio_producto
#     }


from rapidfuzz import process

def buscar_producto_por_nombre(nombre_producto):
    """
    Busca el producto más parecido usando similitud de texto con RapidFuzz.
    Si la similitud es menor al 30%, lo ignora.
    """
    resultados = ejecutar_sp("ObtenerProductos", ())

    if not resultados or len(resultados[0]) == 0:
        return None  # No hay productos en la base de datos

    productos = resultados[0]  # Lista de productos [(idProducto, nombre, precioInstitucional, precioMayorista)]

    # Crear un diccionario con idProducto como clave y (nombre, precioInstitucional, precioMayorista) como valor
    productos_dict = {producto[0]: (producto[1], producto[2], producto[3]) for producto in productos}

    # Buscar coincidencias con RapidFuzz (ahora usando el nombre formateado con la presentación)
    mejor_coincidencia = process.extractOne(
        nombre_producto, [p[0] for p in productos_dict.values()], score_cutoff=90
    )

    if mejor_coincidencia:
        mejor_nombre, similitud, _ = mejor_coincidencia

        # Buscar el ID del producto con el mejor nombre
        id_producto = next(
            (id for id, (nombre, precio_inst, precio_may) in productos_dict.items() if nombre == mejor_nombre), None
        )

        if id_producto:
            return {
                "idProducto": id_producto,
                "nombreProducto": mejor_nombre,
                "precioInstitucional": productos_dict[id_producto][1],
                "precioMayorista": productos_dict[id_producto][2],
                "similitud": similitud
            }
    #print(f"No se encontró un producto similar a '{nombre_producto}'")
    return None  


def crear_factura(id_cliente, fecha_entrega, es_mayorista):
    """
    Crea una factura para un cliente con fecha de entrega y devuelve su ID.
    """
    descripcion = "Mayorista" if es_mayorista else "Institucional"
    
    resultados = ejecutar_sp("CrearFactura", (id_cliente, fecha_entrega, descripcion, 0))

    if resultados is not None:
        id_factura = resultados[0][0][0]  # ID generado por la base de datos
        print(f"Factura insertada con ID: {id_factura}, Fecha de entrega: {fecha_entrega}, Tipo: {descripcion}")
    else:
        print("Error al insertar la factura.")
        id_factura = None

    return id_factura

def insertar_linea_factura(id_factura, id_producto, cantidad,precio_producto):
    """
    Inserta una línea de factura.
    """
    ejecutar_sp("InsertarLineaFactura", (id_factura, id_producto, cantidad, precio_producto,0))


def buscar_o_insertar_cliente(nombre_cliente, telefono):
    """
    Busca un cliente por nombre. Si no existe, lo inserta.
    """
    # Buscar el cliente

    resultados = buscar_cliente_por_nombre(nombre_cliente)
    if resultados and len(resultados) > 0:
        # Cliente encontrado
        id_cliente = resultados['idCliente'] # Supongamos que el ID es la primera columna
        print(f"Cliente encontrado: {id_cliente}")
    else:
        # Cliente no encontrado, insertar
        resultados = ejecutar_sp("InsertarCliente", (nombre_cliente, telefono, 0))
        if resultados is not None:
            id_cliente = resultados[0][0][0]  # ID generado por la base de datos
            print(f"Cliente insertado con ID: {id_cliente}")
        else:
            print("Error al insertar el cliente.")
            id_cliente = None

    return id_cliente


def buscar_cliente_por_nombre(nombre_cliente):
    """
    Busca el cliente más parecido usando similitud de texto con RapidFuzz.
    """
    # Obtener la lista de clientes desde la base de datos
    resultados = ejecutar_sp("ObtenerClientes", ())

    if not resultados or len(resultados[0]) == 0:
        return None  # No hay clientes en la base de datos

    clientes = resultados[0]  # Lista de clientes [(idCliente, nombre)]

    # Crear un diccionario con idCliente como clave y nombre como valor
    clientes_dict = {cliente[0]: cliente[1] for cliente in clientes}

    # Buscar coincidencias con RapidFuzz
    mejor_coincidencia = process.extractOne(
        nombre_cliente, clientes_dict.values(), score_cutoff=70
    )

    if mejor_coincidencia:
        mejor_nombre, similitud, _ = mejor_coincidencia

        # Buscar el ID del cliente con el mejor nombre
        id_cliente = next(
            (id for id, nombre in clientes_dict.items() if nombre == mejor_nombre), None
        )

        if id_cliente:
            return {
                "idCliente": id_cliente,
                "nombreCliente": mejor_nombre,
                "similitud": similitud
            }

    return None
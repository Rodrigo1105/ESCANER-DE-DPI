from flask import Flask, request, jsonify, render_template
import pytesseract
import cv2
import numpy as np
import re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os  # <-- Importamos esto nuevo para manejar la ruta de Windows

app = Flask(__name__)

# --- RUTAS EXACTAS DE TU COMPUTADORA ---
# 1. Dónde instalaste Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 2. La solución definitiva para la carpeta del idioma (sin comillas extrañas)
os.environ['TESSDATA_PREFIX'] = r'C:\Users\DELL\Documents\dpi proyect\tessdata'
# ---------------------------------------

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
credenciales = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
cliente_gspread = gspread.authorize(credenciales)
NOMBRE_DOCUMENTO = "Base_Datos_DPI"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/escanear-dpi', methods=['POST'])
def escanear_dpi():
    if 'imagen' not in request.files:
        return jsonify({"error": "No se envió ninguna imagen"}), 400

    archivo = request.files['imagen']
    in_memory_file = archivo.read()
    npimg = np.frombuffer(in_memory_file, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # --- NUEVO PREPROCESAMIENTO (Más suave y efectivo) ---
    # 1. Ampliamos la imagen al doble para que las letras pequeñas sean legibles
    img_ampliada = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # 2. Convertimos a escala de grises
    gray = cv2.cvtColor(img_ampliada, cv2.COLOR_BGR2GRAY)
    
    # 3. Aplicamos un filtro suave para quitar ruido de la cámara sin borrar las letras
    procesada = cv2.bilateralFilter(gray, 9, 75, 75)

    # Extraer texto
    texto_extraido = pytesseract.image_to_string(procesada, lang='spa')

    print("\n--- LO QUE LEYÓ TESSERACT V2 ---")
    print(texto_extraido)
    print("--------------------------------\n")

    # --- EXTRACCIÓN CON REGEX ---
    dpi_match = re.search(r'\b\d{4}\s?\d{5}\s?\d{4}\b', texto_extraido)
    numero_dpi = dpi_match.group(0).replace(" ", "") if dpi_match else "No detectado"

    apellidos_match = re.search(r'APELLIDOS?\s*\n+([A-ZÁÉÍÓÚÑ\s]+)', texto_extraido, re.IGNORECASE)
    apellidos = apellidos_match.group(1).strip() if apellidos_match else ""

    nombres_match = re.search(r'NOMBRES?\s*\n+([A-ZÁÉÍÓÚÑ\s]+)', texto_extraido, re.IGNORECASE)
    nombres = nombres_match.group(1).strip() if nombres_match else ""
    
    nombre_completo = f"{nombres} {apellidos}".strip()
    if not nombre_completo:
        nombre_completo = "No detectado"

    # Limpieza básica para la fecha (ej. corregir la 'S' por '5' y la 'A' por '1' que le pasó a tu fecha)
    fecha_limpia = texto_extraido.replace('S', '5').replace('A', '1').replace('O', '0')
    fecha_match = re.search(r'\b\d{2}\s*[A-Z]{3}\s*\d{4}\b|\b\d{2}[/ -]\d{2}[/ -]\d{4}\b', fecha_limpia, re.IGNORECASE)
    fecha_nacimiento = fecha_match.group(0).strip() if fecha_match else "No detectada"

    # --- GUARDAR EN SHEETS (Corregido) ---
    try:
        hoja = cliente_gspread.open(NOMBRE_DOCUMENTO).sheet1
        fecha_escaneo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Agregamos value_input_option para evitar el error <Response [200]>
        hoja.append_row([numero_dpi, nombre_completo, fecha_nacimiento, fecha_escaneo], value_input_option="USER_ENTERED")
        mensaje_guardado = "Guardado en Google Sheets con éxito."
    except Exception as e:
        mensaje_guardado = f"Aviso de Sheets: {str(e)}"
        print(f"Error técnico de Sheets: {e}")

    return jsonify({
        "estado_bd": mensaje_guardado,
        "datos_procesados": {
            "dpi": numero_dpi,
            "nombre": nombre_completo,
            "fecha_nacimiento": fecha_nacimiento
        }
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
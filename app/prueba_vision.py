import re
from PIL import Image
import pytesseract

# 1. CONFIGURACIÓN
# Ajusta la ruta si tu instalación es diferente
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("--- INICIANDO SISTEMA CÓRTEX ---")

try:
    # 2. CARGAR IMAGEN
    # Asegúrate de que 'auto.jpg' esté en la carpeta
    imagen = Image.open("auto.jpg")
    
    # 3. PRE-PROCESAMIENTO DE VISIÓN
    # Convertir a escala de grises
    imagen_gris = imagen.convert('L')

    # Aumentar tamaño (2x) para ver mejor letras pequeñas
    ancho, alto = imagen_gris.size
    imagen_grande = imagen_gris.resize((ancho*2, alto*2), Image.Resampling.LANCZOS)

    # Binarización (Alto contraste blanco/negro)
    imagen_umbral = imagen_grande.point(lambda x: 0 if x < 128 else 255, '1')

    # 4. EXTRACCIÓN DE TEXTO (OCR)
    config_tesseract = "--psm 7"
    texto_sucio = pytesseract.image_to_string(imagen_umbral, config=config_tesseract)
    
    print(f"Lectura cruda del sensor: '{texto_sucio.strip()}'")

    # 5. LIMPIEZA DE DATOS
    # Usamos Regex para dejar solo letras y números
    placa_limpia = re.sub(r'[^a-zA-Z0-9]', '', texto_sucio)

    print("--- PLACA IDENTIFICADA ---")
    print(f"[{placa_limpia}]")
    print("--------------------------")

    # 6. BASE DE DATOS (Simulada) 📝
    # Lista de vehículos permitidos
    autos_autorizados = ['ABC1234', 'PCH9604', 'GHI7777']

    # 7. TOMA DE DECISIONES (Cerebro) 🧠
    print("\nVerificando permisos en base de datos...")
    
    if placa_limpia in autos_autorizados:
        # Si la placa ESTÁ en la lista:
        print(f"✅ ACCESO CONCEDIDO: El vehículo {placa_limpia} es bienvenido.")
        print("-> Portón abriéndose...")
    else:
        # Si la placa NO está en la lista:
        print(f"🚫 ACCESO DENEGADO: El vehículo {placa_limpia} no está registrado.")
        print("-> Seguridad notificada.")

except Exception as e:
    print(f"⚠️ Error crítico en el sistema: {e}")
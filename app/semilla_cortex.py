import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

# Aseguramos que las tablas existan
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- BANCOS DE DATOS (CONTEXTO SONORA) ---
COLONIAS = [
    "Centro", "Sahuaro", "San Benito", "Proyecto Rio Sonora", "Pueblitos", 
    "Altares", "Solidaridad", "Villa Bonita", "Bugambilias", "Pitic",
    "Loma Larga", "Nuevo Hermosillo", "Los Arcos", "Modelo", "Country Club"
]

CALLES = [
    "Blvd. Rodriguez", "Calle Reforma", "Blvd. Kino", "Periferico Norte", 
    "Calle Rosales", "Blvd. Vildosola", "Calle Veracruz", "Blvd. Morelos",
    "Calle Nayarit", "Calle Yanez", "Blvd. Solidaridad", "Calle 12"
]

DELITOS_ALTO_IMPACTO = ["HOMICIDIO DOLOSO", "ROBO A MANO ARMADA", "SECUESTRO", "PORTACION DE ARMAS"]
DELITOS_MEDIO_IMPACTO = ["ROBO A NEGOCIO", "ROBO DE VEHICULO", "ASALTO A TRANSEUNTE", "ALLANAMIENTO"]
DELITOS_BAJO_IMPACTO = ["CHOQUE CON FUGA", "DAÑOS A PROPIEDAD", "ALTERACION DEL ORDEN", "CONDUCCION PUNIBLE"]

MARCAS = ["NISSAN", "TOYOTA", "HONDA", "FORD", "CHEVROLET", "JEEP", "MAZDA", "ITALIKA"]
MODELOS = {
    "NISSAN": ["TSURU", "VERSA", "SENTRA", "NP300"],
    "TOYOTA": ["COROLLA", "HILUX", "TACOMA", "CAMRY"],
    "HONDA": ["CIVIC", "CR-V", "ACCORD", "HR-V"],
    "FORD": ["LOBO", "RANGER", "FIESTA", "FIGO"],
    "CHEVROLET": ["AVEO", "SILVERADO", "SPARK", "ONIX"],
    "JEEP": ["CHEROKEE", "WRANGLER", "RUBICON"],
    "MAZDA": ["MAZDA 3", "MAZDA 6", "CX-5"],
    "ITALIKA": ["FT150", "125Z", "VORT-X"]
}
COLORES = ["BLANCO", "NEGRO", "GRIS", "ROJO", "AZUL", "PLATA", "ARENA"]

NOMBRES = ["Juan", "Pedro", "Luis", "Carlos", "Jorge", "Miguel", "Jose", "Ramon", "Jesus", "Francisco"]
APELLIDOS = ["Perez", "Lopez", "Garcia", "Martinez", "Rodriguez", "Hernandez", "Gonzales", "Ramirez"]
ALIAS = ["El Cholo", "El Flaco", "El Gordo", "El Neto", "El Ruso", "El Pelon", "El Chino"]

# Coordenadas base Hermosillo
LAT_BASE = 29.07
LON_BASE = -110.95

# --- GENERADORES ---
def generar_placa():
    letras = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
    nums = "".join(random.choices("0123456789", k=4 if random.random() > 0.5 else 3))
    return f"{letras}{nums}"

def generar_ubicacion():
    # Variación aleatoria para dispersar en el mapa
    lat = LAT_BASE + random.uniform(-0.05, 0.05)
    lon = LON_BASE + random.uniform(-0.05, 0.05)
    return str(lat)[:9], str(lon)[:10]

def sembrar_datos():
    db = SessionLocal()
    print("⚡ INICIANDO GÉNESIS DE DATOS CÓRTEX...")
    
    # 1. LIMPIEZA (OPCIONAL - Descomenta si quieres borrar todo antes)
    # db.query(models.Vehiculo).delete()
    # db.query(models.Persona).delete()
    # db.query(models.Incidente).delete()
    # db.query(models.VehiculoInteres).delete()
    # db.commit()

    # --- ESCENARIO A: ALTO IMPACTO (ROJOS PARA LA APP) ---
    print("🔴 Sembrando Incidentes Críticos...")
    placas_rojas = []
    for _ in range(10):
        crear_incidente_completo(db, nivel="ALTO", lista_placas=placas_rojas)

    # --- ESCENARIO B: VINCULADOS (NARANJAS PARA LA APP) ---
    print("🟠 Sembrando Incidentes Vinculados...")
    placas_naranjas = []
    for _ in range(15):
        crear_incidente_completo(db, nivel="MEDIO", lista_placas=placas_naranjas)

    # --- ESCENARIO C: RUIDO/LIMPIOS (VERDES/HISTÓRICOS) ---
    print("🟢 Sembrando Historial Operativo...")
    for _ in range(30):
        crear_incidente_completo(db, nivel="BAJO")

    # --- ESCENARIO D: KÁRDEX (AMARILLOS - LISTA NEGRA DIRECTA) ---
    print("🟡 Llenando Kárdex de Inteligencia...")
    placas_amarillas = []
    for _ in range(10):
        placa = generar_placa()
        marca = random.choice(MARCAS)
        modelo = random.choice(MODELOS[marca])
        
        kardex = models.VehiculoInteres(
            placa=placa,
            marca=marca,
            modelo=modelo,
            color=random.choice(COLORES),
            anio=str(random.randint(2000, 2024)),
            propietario="DESCONOCIDO",
            estatus="BAJO VIGILANCIA",
            nivel_alerta="MEDIA",
            notas="Vehículo reportado merodeando zonas bancarias. Posible halconeo.",
            fecha_registro=datetime.now() - timedelta(days=random.randint(1, 60))
        )
        db.add(kardex)
        placas_amarillas.append(placa)
    
    db.commit()
    print("\n✅ PROCESO TERMINADO CON ÉXITO.")
    print("="*40)
    print("📋 GUÍA DE PRUEBA TÁCTICA")
    print("="*40)
    print(f"🔴 PLACAS CRÍTICAS (Probar en App -> ALERTA ROJA):")
    print(f"   {placas_rojas[:3]}") 
    print(f"🟠 PLACAS VINCULADAS (Probar en App -> ALERTA NARANJA):")
    print(f"   {placas_naranjas[:3]}")
    print(f"🟡 PLACAS SOSPECHOSAS (Probar en App -> ALERTA AMARILLA):")
    print(f"   {placas_amarillas[:3]}")
    print("="*40)
    db.close()

def crear_incidente_completo(db, nivel="BAJO", lista_placas=None):
    # 1. Definir datos base
    fecha = datetime.now() - timedelta(days=random.randint(0, 365))
    lat, lon = generar_ubicacion()
    colonia = random.choice(COLONIAS)
    calle = random.choice(CALLES)
    
    if nivel == "ALTO":
        tipo = random.choice(DELITOS_ALTO_IMPACTO)
        narrativa = f"Se reporta {tipo} en la colonia {colonia}. Testigos afirman detonaciones de arma de fuego. Sujetos armados a bordo del vehículo huyen hacia el poniente."
    elif nivel == "MEDIO":
        tipo = random.choice(DELITOS_MEDIO_IMPACTO)
        narrativa = f"Reporte de {tipo} en comercio local. Sustrajeron mercancía y efectivo. Se da a la fuga en vehículo con rumbo desconocido."
    else:
        tipo = random.choice(DELITOS_BAJO_IMPACTO)
        narrativa = f"Incidente menor de {tipo}. Se elabora IPH y se cita a las partes."

    # 2. Crear Incidente
    inc = models.Incidente(
        folio_interno=f"CTX-{uuid.uuid4().hex[:6].upper()}",
        folio_911=f"911-{random.randint(10000, 99999)}",
        descripcion_hechos=narrativa,
        calle=calle,
        colonia=colonia,
        latitud=lat,
        longitud=lon,
        tipo_incidente=tipo,
        creado_en=fecha
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)

    # 3. Crear Vehículo Vinculado
    marca = random.choice(MARCAS)
    modelo = random.choice(MODELOS[marca])
    placa = generar_placa()
    color = random.choice(COLORES)
    
    veh = models.Vehiculo(
        id_incidente=inc.id_incidente,
        marca=marca,
        modelo=modelo,
        anio=str(random.randint(1995, 2025)),
        color=color,
        placas=placa,
        caracteristicas="Vidrios polarizados" if nivel == "ALTO" else "Sin novedad"
    )
    db.add(veh)
    
    if lista_placas is not None:
        lista_placas.append(placa)

    # 4. Crear Persona Vinculada (Para Córtex Neuronal)
    if random.random() > 0.3: # 70% de probabilidad de tener sospechoso
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
        alias = random.choice(ALIAS) if nivel == "ALTO" else ""
        
        per = models.Persona(
            id_incidente=inc.id_incidente,
            nombre_alias=f"{nombre} ({alias})" if alias else nombre,
            descripcion_ropa="Camisa negra, pantalón mezclilla" if nivel == "ALTO" else "Ropa casual",
            sexo="H" if random.random() > 0.1 else "M"
        )
        db.add(per)

    db.commit()

if __name__ == "__main__":
    sembrar_datos()
import random
from datetime import datetime, timedelta
import uuid
from app import models, database
from sqlalchemy.orm import Session

# --- CONFIGURACIÓN ---
CANTIDAD = 50

# --- DATOS REALES DE HERMOSILLO ---
COLONIAS = [
    "Centro", "Sahuaro", "Pueblitos", "Solidaridad", "Nuevo Hermosillo", 
    "Palo Verde", "San Benito", "Balderrama", "Villa de Seris", "5 de Mayo",
    "Los Olivos", "Las Lomas", "Modelo", "Constitución", "La Cholla", "Altares"
]

CALLES = [
    "Blvd. Eusebio Kino", "Blvd. Solidaridad", "Calle Reforma", "Blvd. Luis Encinas",
    "Periférico Norte", "Calle Rosales", "Blvd. Morelos", "Calle Veracruz",
    "Blvd. Vildósola", "Calle General Piña", "Av. Tecnológico", "Blvd. Quiroga"
]

DELITOS = [
    "Robo a negocio con violencia", "Robo a negocio sin violencia", 
    "Despojo de vehiculo", "Herido con arma de fuego", "Homicidio", 
    "Privacion ilegal de la libertad", "Extorsion", 
    "Robo a transeunte con violencia", "Robo a transeunte sin violencia"
]

NARRATIVAS = [
    "Reportan sujetos sospechosos en la zona.",
    "Se recibe llamada al 911 indicando detonaciones.",
    "Robo en proceso, sujetos huyen a pie.",
    "Vehículo abandonado con las puertas abiertas.",
    "Asalto a mano armada en comercio local.",
    "Riña campal en vía pública.",
    "Sujeto sustrae mercancía sin pagar y agrede al guardia.",
    "Despojo de vehículo a conductor de plataforma."
]

VEHICULOS_MARCAS = ["Nissan", "Toyota", "Ford", "Chevrolet", "Honda", "Volkswagen"]
VEHICULOS_MODELOS = ["Tsuru", "Corolla", "Ranger", "Aveo", "Civic", "Jetta", "Sentra", "Hilux"]
COLORES = ["Blanco", "Negro", "Gris", "Rojo", "Azul", "Plata"]

NOMBRES = ["Juan Pérez", "Luis López", "Carlos García", "El Beto", "El Chuy", "Desconocido", "Marco Antonio", "Jesús Manuel"]
ROPAS = ["Camiseta negra y jeans", "Sudadera gris", "Gorra roja y short", "Vestimenta oscura", "Camisa a cuadros"]

# Coordenadas base Hermosillo (Centro aprox)
LAT_BASE = 29.072967
LON_BASE = -110.955919

def crear_datos():
    db = database.SessionLocal()
    print(f"--- INICIANDO INYECCIÓN DE {CANTIDAD} REGISTROS ---")
    
    for i in range(CANTIDAD):
        # 1. Generar Fecha Aleatoria (Últimos 30 días)
        dias_atras = random.randint(0, 30)
        hora_random = random.randint(0, 23)
        minuto_random = random.randint(0, 59)
        fecha = datetime.now() - timedelta(days=dias_atras)
        fecha = fecha.replace(hour=hora_random, minute=minuto_random)

        # 2. Generar Coordenadas (Dispersión en Hermosillo)
        # Offset aleatorio para que no caigan en el mismo punto
        lat = LAT_BASE + random.uniform(-0.05, 0.05)
        lon = LON_BASE + random.uniform(-0.05, 0.05)

        # 3. Crear Incidente
        tipo = random.choice(DELITOS)
        folio = f"CTX-{uuid.uuid4().hex[:6].upper()}"
        
        incidente = models.Incidente(
            folio_interno=folio,
            folio_911=str(random.randint(100000, 999999)),
            tipo_incidente=tipo,
            descripcion_hechos=random.choice(NARRATIVAS),
            calle=f"{random.choice(CALLES)} y {random.choice(CALLES)}", # Simular cruce
            colonia=random.choice(COLONIAS),
            latitud=str(lat),
            longitud=str(lon),
            creado_en=fecha
        )
        
        db.add(incidente)
        db.commit() # Guardamos para tener el ID
        db.refresh(incidente)

        # 4. Agregar Vehículos (Aleatorio: a veces sí, a veces no)
        if random.random() > 0.4: # 60% de probabilidad de tener vehículo
            veh = models.Vehiculo(
                id_incidente=incidente.id_incidente,
                marca=random.choice(VEHICULOS_MARCAS),
                modelo=random.choice(VEHICULOS_MODELOS),
                anio=str(random.randint(1995, 2024)),
                color=random.choice(COLORES),
                placas=f"WZZ-{random.randint(100, 999)}",
                caracteristicas="Vidrios polarizados" if random.random() > 0.5 else "Golpe en defensa"
            )
            db.add(veh)

        # 5. Agregar Personas (Aleatorio)
        if random.random() > 0.3: # 70% de probabilidad
            per = models.Persona(
                id_incidente=incidente.id_incidente,
                nombre_alias=random.choice(NOMBRES),
                sexo="H",
                descripcion_ropa=random.choice(ROPAS)
            )
            db.add(per)
        
        print(f"[{i+1}/{CANTIDAD}] Generado: {folio} - {tipo} ({fecha.strftime('%Y-%m-%d')})")

    db.commit()
    db.close()
    print("--- ¡PROCESO TERMINADO CON ÉXITO! ---")

if __name__ == "__main__":
    crear_datos()
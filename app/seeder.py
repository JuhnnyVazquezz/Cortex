# ==============================================================================
# OPERACIÓN CÉLULAS: GENERADOR DE CLUSTERS TÁCTICOS PARA CÓRTEX V17
# ==============================================================================
import random
from datetime import datetime, time
from faker import Faker
from database import SessionLocal
import models

# Configuración Regional
fake = Faker('es_MX')

# --- DEFINICIÓN DE CÉLULAS CRIMINALES (GRUPOS SEPARADOS) ---

# GRUPO 1: LOS ROBA-COCHES (Usan Tsurus y Motos)
CELULA_A = {
    "criminales": [
        {"nombre": "EL KEVIN", "sexo": "H", "edad": "22"},
        {"nombre": "EL BRAYAN", "sexo": "H", "edad": "24"}
    ],
    "vehiculos": [
        {"marca": "NISSAN", "modelo": "TSURU", "placas": "VWE-9090", "color": "BLANCO"},
        {"marca": "ITALIKA", "modelo": "FT150", "placas": "SIN PLACA", "color": "ROJA"}
    ],
    "delitos": ["ROBO DE VEHICULO", "VEHICULO SOSPECHOSO"]
}

# GRUPO 2: LOS ASALTANTES (Usan Jeep y armas)
CELULA_B = {
    "criminales": [
        {"nombre": "EL RUSO", "sexo": "H", "edad": "35"},
        {"nombre": "LA CHONA", "sexo": "M", "edad": "29"},
        {"nombre": "EL TONNY", "sexo": "H", "edad": "19"}
    ],
    "vehiculos": [
        {"marca": "JEEP", "modelo": "CHEROKEE", "placas": "WDZ-1122", "color": "GRIS"}
    ],
    "delitos": ["ROBO A NEGOCIO CON VIOLENCIA", "PERSONA CON ARMA DE FUEGO"]
}

# GRUPO 3: LOS "FINOS" (Extorsión y fraude, andan en Honda)
CELULA_C = {
    "criminales": [
        {"nombre": "EL INGENIERO", "sexo": "H", "edad": "45"},
        {"nombre": "EL LICENCIADO", "sexo": "H", "edad": "50"}
    ],
    "vehiculos": [
        {"marca": "HONDA", "modelo": "CIVIC", "placas": "SON-4421", "color": "NEGRO"}
    ],
    "delitos": ["EXTORSION", "FRAUDE"]
}

DELITOS_RANDOM = ["ROBO A CASA HABITACION", "DAÑOS DOLOSOS", "RIÑA", "ACCIDENTE DE TRANSITO", "ROBO SIMPLE"]

def generar_datos_inteligentes():
    db = SessionLocal()
    print("🚀 INICIANDO SEMBRADO DE CÉLULAS INDEPENDIENTES...")

    try:
        # Generamos 80 incidentes
        for i in range(80):
            
            # TIRAR EL DADO TÁCTICO (1-100)
            dado = random.randint(1, 100)
            
            # LÓGICA DE CLUSTERS:
            # 1-10: Célula A (10% probabilidad)
            # 11-20: Célula B (10% probabilidad)
            # 21-25: Célula C (5% probabilidad)
            # 26-100: CRIMEN RANDOM (75% probabilidad - Puntos aislados)
            
            datos_incidente = {}
            vehiculos_a_usar = []
            personas_a_usar = []

            if dado <= 10:
                # --- OPERA CÉLULA A ---
                origen = CELULA_A
                datos_incidente["tipo"] = random.choice(origen["delitos"])
                # Usan uno de sus vehículos
                v = random.choice(origen["vehiculos"])
                vehiculos_a_usar.append(v)
                # Participa 1 o 2 miembros
                for p in random.sample(origen["criminales"], k=random.randint(1, 2)):
                    p["tipo"] = "PRESUNTO"
                    personas_a_usar.append(p)

            elif dado <= 20:
                # --- OPERA CÉLULA B ---
                origen = CELULA_B
                datos_incidente["tipo"] = random.choice(origen["delitos"])
                v = random.choice(origen["vehiculos"])
                vehiculos_a_usar.append(v)
                for p in random.sample(origen["criminales"], k=random.randint(1, 3)):
                    p["tipo"] = "PRESUNTO"
                    personas_a_usar.append(p)

            elif dado <= 25:
                # --- OPERA CÉLULA C ---
                origen = CELULA_C
                datos_incidente["tipo"] = random.choice(origen["delitos"])
                v = random.choice(origen["vehiculos"])
                vehiculos_a_usar.append(v)
                p = random.choice(origen["criminales"])
                p["tipo"] = "PRESUNTO"
                personas_a_usar.append(p)

            else:
                # --- CRIMEN RANDOM (AISLADO) ---
                datos_incidente["tipo"] = random.choice(DELITOS_RANDOM)
                # Vehículo random (sin placas o placas nuevas random)
                if random.random() < 0.5:
                    vehiculos_a_usar.append({
                        "marca": random.choice(["FORD", "CHEVROLET", "VW", "TOYOTA"]),
                        "modelo": "GENERICO",
                        "placas": f"RND-{random.randint(100,999)}",
                        "color": fake.color_name().upper()
                    })
                # Presunto random
                personas_a_usar.append({
                    "nombre": fake.name().upper(),
                    "sexo": "H",
                    "edad": str(random.randint(18, 50)),
                    "tipo": "PRESUNTO"
                })

            # --- SIEMPRE AGREGAR UNA VÍCTIMA RANDOM (AFECTADO) ---
            personas_a_usar.append({
                "nombre": fake.name().upper(),
                "sexo": random.choice(["H", "M"]),
                "edad": str(random.randint(20, 70)),
                "tipo": "AFECTADO"
            })

            # --- CREAR INCIDENTE EN DB ---
            fecha_random = fake.date_between(start_date='-6m', end_date='today')
            
            nuevo_inc = models.Incidente(
                folio_interno=f"CTX-{random.randint(10000, 99999)}",
                folio_c5i=f"911-{random.randint(1000, 9999)}",
                tipo_incidente=datos_incidente["tipo"],
                descripcion_hechos=fake.text(max_nb_chars=100),
                razonamiento_autoridad="Informe Policial Homologado capturado.",
                calle=fake.street_name().upper(),
                colonia=random.choice(["CENTRO", "SAN BENITO", "SOLIDARIDAD", "NUEVO HERMOSILLO"]),
                latitud=str(29.07 + random.uniform(-0.05, 0.05)),
                longitud=str(-110.95 + random.uniform(-0.05, 0.05)),
                fecha_incidente=fecha_random,
                hora_incidente=time(random.randint(0, 23), 0),
                fecha_registro_sistema=datetime.now()
            )
            db.add(nuevo_inc)
            db.flush()

            # Insertar Vehículos
            for v in vehiculos_a_usar:
                db.add(models.Vehiculo(
                    id_incidente=nuevo_inc.id_incidente,
                    marca=v["marca"], modelo=v["modelo"],
                    placas=v["placas"], color=v["color"], anio="2015"
                ))

            # Insertar Personas
            for p in personas_a_usar:
                db.add(models.Persona(
                    id_incidente=nuevo_inc.id_incidente,
                    tipo_involucrado=p["tipo"],
                    nombre_alias=p["nombre"],
                    sexo=p["sexo"],
                    edad=p.get("edad", "Unknown"),
                    vestimenta="ROPA CASUAL"
                ))

        db.commit()
        print("✅ LISTO: Se generaron 3 CÉLULAS CRIMINALES separadas y ruido aleatorio.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generar_datos_inteligentes()
# crear_prueba.py (VERSIÓN BLINDADA FINAL)
from database import SessionLocal
import models
from datetime import datetime
import uuid # Para generar IDs únicos y que no choque

# Conectar
db = SessionLocal()

# PLACA DE PRUEBA
PLACA_TEST = "RATA666"

print(f"--- SEMBRANDO OBJETIVO: {PLACA_TEST} ---")

try:
    # 1. LIMPIEZA PREVIA (Borrar rastros anteriores de esta prueba)
    print("🧹 Limpiando datos de prueba anteriores...")
    
    # Borrar Kardex previo de RATA666
    db.query(models.VehiculoInteres).filter(models.VehiculoInteres.placa == PLACA_TEST).delete()
    
    # Borrar incidentes previos de prueba (Buscamos por la descripción para no fallar por ID)
    incidentes_test = db.query(models.Incidente).filter(models.Incidente.descripcion_hechos.contains("Sujetos armados huyen en Ford Lobo")).all()
    for inc in incidentes_test:
        # Primero borramos los vehículos y personas asociados a ese incidente para no romper reglas FK
        db.query(models.Vehiculo).filter(models.Vehiculo.id_incidente == inc.id_incidente).delete()
        db.query(models.Persona).filter(models.Persona.id_incidente == inc.id_incidente).delete()
        db.delete(inc)
    
    db.commit() # Confirmar limpieza

    # 2. CREAR NUEVOS DATOS
    print("🌱 Insertando nuevos registros...")

    # A. Crear registro en KÁRDEX
    kardex = models.VehiculoInteres(
        placa=PLACA_TEST,
        marca="FORD", modelo="LOBO", color="NEGRO", anio="2022",
        propietario="JUAN 'EL MALO' PÉREZ",
        estatus="ROBADO",
        nivel_alerta="ALTA",
        notas="Vehículo utilizado en fuga bancaria. Armados y peligrosos.",
        fecha_registro=datetime.now()
    )
    db.add(kardex)

    # B. Crear INCIDENTE 1 (Robo a Banco)
    folio1 = f"CTX-TEST-{uuid.uuid4().hex[:4].upper()}" # ID Único
    inc1 = models.Incidente(
        folio_interno=folio1, 
        folio_911="911-ALERTA-01",
        tipo_incidente="ROBO A BANCO",
        descripcion_hechos="Sujetos armados huyen en Ford Lobo Negra tras asalto a sucursal.",
        colonia="Centro", 
        calle="Av. Reforma", 
        creado_en=datetime.now()
    )
    db.add(inc1)
    db.flush() 
    
    db.add(models.Vehiculo(id_incidente=inc1.id_incidente, placas=PLACA_TEST, marca="FORD", modelo="LOBO"))

    # C. Crear INCIDENTE 2 (Atropello)
    folio2 = f"CTX-TEST-{uuid.uuid4().hex[:4].upper()}" # ID Único
    inc2 = models.Incidente(
        folio_interno=folio2, 
        folio_911="911-ALERTA-02",
        tipo_incidente="ATROPELLO Y FUGA",
        descripcion_hechos="Mismo vehículo atropelló a oficial de tránsito en la huida.",
        colonia="Vado del Rio", 
        calle="Blvd. Colosio", 
        creado_en=datetime.now()
    )
    db.add(inc2)
    db.flush()
    
    db.add(models.Vehiculo(id_incidente=inc2.id_incidente, placas=PLACA_TEST, marca="FORD", modelo="LOBO"))

    db.commit()
    print("✅ ¡ÉXITO TOTAL! DATOS SEMBRADOS.")
    print(f"👉 PRUEBA AHORA EN TU CELULAR ESCRIBIENDO: {PLACA_TEST}")

except Exception as e:
    print(f"❌ ERROR CRÍTICO: {e}")
    db.rollback()
finally:
    db.close()
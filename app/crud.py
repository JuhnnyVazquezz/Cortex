# app/crud.py
from sqlalchemy.orm import Session
from . import models
import uuid
from datetime import datetime

def crear_incidente_db(db: Session, folio_911: str, descripcion: str, lat: str, lon: str):
    # Generar Folio CORTEX profesional: CTX-AÑO-MES-UUID_CORTO
    anio_mes = datetime.now().strftime("%Y%m")
    suffix = str(uuid.uuid4())[:6].upper()
    folio_cortex = f"CTX-{anio_mes}-{suffix}"

    nuevo_incidente = models.Incidente(
        folio_interno=folio_cortex,
        folio_911=folio_911,
        descripcion_hechos=descripcion,
        latitud=lat,
        longitud=lon
    )
    db.add(nuevo_incidente)
    db.commit()
    db.refresh(nuevo_incidente)
    return nuevo_incidente

def guardar_evidencia_db(db: Session, id_incidente: uuid.UUID, ruta: str):
    nueva_evidencia = models.Evidencia(
        id_incidente=id_incidente,
        ruta_archivo_segura=ruta,
        tipo_evidencia="ADJUNTO_OPERADOR"
    )
    db.add(nueva_evidencia)
    db.commit()
    return nueva_evidencia

def obtener_todos(db: Session, skip: int = 0, limit: int = 100):
    # Trae incidentes activos ordenados por fecha reciente
    return db.query(models.Incidente)\
             .filter(models.Incidente.activo == True)\
             .order_by(models.Incidente.creado_en.desc())\
             .offset(skip).limit(limit).all()

def obtener_por_id(db: Session, id_incidente: str):
    return db.query(models.Incidente).filter(models.Incidente.id_incidente == id_incidente).first()
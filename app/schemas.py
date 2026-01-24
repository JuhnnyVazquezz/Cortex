from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- ESQUEMAS HIJOS ---

class VehiculoSchema(BaseModel):
    marca: Optional[str] = ""
    modelo: Optional[str] = ""
    anio: Optional[str] = ""
    color: Optional[str] = ""
    placas: Optional[str] = ""
    caracteristicas: Optional[str] = ""
    
    class Config:
        from_attributes = True

class PersonaSchema(BaseModel):
    nombre_alias: Optional[str] = ""
    descripcion_ropa: Optional[str] = ""
    sexo: Optional[str] = ""
    
    class Config:
        from_attributes = True

class EvidenciaOut(BaseModel):
    ruta_archivo_segura: str
    class Config:
        from_attributes = True

# --- ESQUEMA PRINCIPAL ---

class IncidenteOut(BaseModel):
    id_incidente: int  # <--- ¡AQUÍ ESTABA EL ERROR! (Antes decía UUID)
    folio_interno: Optional[str] = ""
    folio_911: Optional[str] = ""
    tipo_incidente: Optional[str] = ""
    
    calle: Optional[str] = ""
    colonia: Optional[str] = ""
    latitud: Optional[str] = ""
    longitud: Optional[str] = ""
    
    descripcion_hechos: Optional[str] = ""
    creado_en: Optional[datetime] = None
    
    # Listas
    vehiculos: List[VehiculoSchema] = []
    personas: List[PersonaSchema] = []
    evidencias: List[EvidenciaOut] = []

    class Config:
        from_attributes = True



# --- SCHEMAS PARA CARGA MASIVA (INPUT) ---
class VehiculoIn(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[str] = None
    color: Optional[str] = None
    placas: Optional[str] = None
    caracteristicas: Optional[str] = None

class PersonaIn(BaseModel):
    nombre_alias: Optional[str] = None
    descripcion_ropa: Optional[str] = None
    sexo: Optional[str] = None

class IncidenteIn(BaseModel):
    folio_911: Optional[str] = None
    tipo_incidente: Optional[str] = None
    fecha_hora: Optional[datetime] = None # O str
    descripcion_hechos: Optional[str] = None
    calle: Optional[str] = None
    colonia: Optional[str] = None
    latitud: Optional[str] = None
    longitud: Optional[str] = None
    
    vehiculos: List[VehiculoIn] = []
    personas: List[PersonaIn] = []
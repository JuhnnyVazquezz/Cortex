from sqlalchemy import Column, Integer, String, DateTime, Date, Time, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# =========================================================
# 1. USUARIOS (ACCESO AL SISTEMA)
# =========================================================
class Usuario(Base):
    __tablename__ = "usuarios"
    id_usuario = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    nombre_completo = Column(String)
    rol = Column(String) # admin, oficial, monitor

# =========================================================
# 2. INCIDENTES (EL NÚCLEO OPERATIVO)
# =========================================================
class Incidente(Base):
    __tablename__ = "incidentes"
    
    id_incidente = Column(Integer, primary_key=True, index=True)
    
    # --- FOLIOS ---
    folio_interno = Column(String, unique=True, index=True) # Ej: CTX-A1B2C3 (Automático)
    folio_c5i = Column(String, nullable=True)             # Ej: 911-2026-X (Manual)
    
    # --- TIEMPO ---
    # Separamos fecha y hora como solicitaste para precisión operativa
    fecha_incidente = Column(Date, nullable=True) 
    hora_incidente = Column(Time, nullable=True)
    # Este campo es interno para saber cuándo se guardó el registro realmente
    fecha_registro_sistema = Column(DateTime, default=datetime.now) 

    # --- UBICACIÓN Y CLASIFICACIÓN ---
    tipo_incidente = Column(String) # Catálogo A-Z (Robo, Homicidio, etc.)
    descripcion_hechos = Column(Text) # Narrativa libre
    razonamiento_autoridad = Column(Text, nullable=True) # Nuevo campo solicitado
    
    calle = Column(String, nullable=True)
    colonia = Column(String, nullable=True)
    latitud = Column(String, default="0.0")
    longitud = Column(String, default="0.0")

    # --- RELACIONES ---
    vehiculos = relationship("Vehiculo", back_populates="incidente", cascade="all, delete-orphan")
    personas = relationship("Persona", back_populates="incidente", cascade="all, delete-orphan")
    evidencias = relationship("Evidencia", back_populates="incidente", cascade="all, delete-orphan")

# =========================================================
# 3. VEHÍCULOS INVOLUCRADOS
# =========================================================
class Vehiculo(Base):
    __tablename__ = "vehiculos_incidente"
    
    id_vehiculo = Column(Integer, primary_key=True, index=True)
    id_incidente = Column(Integer, ForeignKey("incidentes.id_incidente"))
    
    marca = Column(String, default="DESCONOCIDO")
    modelo = Column(String, default="DESCONOCIDO")
    # Guardamos el año como String para permitir "SIN AÑO" o "2024"
    anio = Column(String, default="SIN AÑO") 
    color = Column(String, default="DESCONOCIDO")
    placas = Column(String, default="SIN PLACAS")
    
    # Estándar para vincularlo al incidente padre
    incidente = relationship("Incidente", back_populates="vehiculos")

# =========================================================
# 4. PERSONAS (AFECTADOS Y PRESUNTOS)
# =========================================================
class Persona(Base):
    __tablename__ = "personas_incidente"
    
    id_persona = Column(Integer, primary_key=True, index=True)
    id_incidente = Column(Integer, ForeignKey("incidentes.id_incidente"))
    
    # --- CLASIFICACIÓN ---
    # Aquí definimos si es "AFECTADO" (Víctima) o "PRESUNTO" (Imputado)
    tipo_involucrado = Column(String, default="PRESUNTO") 
    
    nombre_alias = Column(String, default="DESCONOCIDO")
    sexo = Column(String, default="SIN SEXO") # M, H, o SIN SEXO
    edad = Column(String, default="DESCONOCIDO") # String para permitir "25 aprox"
    vestimenta = Column(String, nullable=True)
    
    incidente = relationship("Incidente", back_populates="personas")

# =========================================================
# 5. EVIDENCIA MULTIMEDIA
# =========================================================
class Evidencia(Base):
    __tablename__ = "evidencias"
    
    id_evidencia = Column(Integer, primary_key=True, index=True)
    id_incidente = Column(Integer, ForeignKey("incidentes.id_incidente"))
    
    ruta_archivo_segura = Column(String) 
    tipo = Column(String, default="imagen")
    
    incidente = relationship("Incidente", back_populates="evidencias")

# =========================================================
# 6. KÁRDEX (VEHÍCULOS DE INTERÉS - LPR)
# =========================================================
# Este módulo NO lo tocamos, funciona perfecto para las alertas LPR
class VehiculoInteres(Base):
    __tablename__ = "vehiculos_interes"
    
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String, index=True, unique=True)
    marca = Column(String, nullable=True)
    modelo = Column(String, nullable=True)
    color = Column(String, nullable=True)
    anio = Column(String, nullable=True)
    propietario = Column(String, nullable=True)
    estatus = Column(String, default="SOSPECHOSO") 
    nivel_alerta = Column(String, default="MEDIA")
    notas = Column(Text, nullable=True)
    fecha_registro = Column(DateTime, default=datetime.now)
    fotos = relationship("FotoInteres", back_populates="vehiculo", cascade="all, delete-orphan")

class FotoInteres(Base):
    __tablename__ = "fotos_interes"
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos_interes.id"))
    ruta = Column(String)
    vehiculo = relationship("VehiculoInteres", back_populates="fotos")
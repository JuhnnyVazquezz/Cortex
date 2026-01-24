# =========================================================================
# CÓRTEX V17.5 - NÚCLEO CENTRAL DE OPERACIONES (GPS FIX + RED VISUAL)
# =========================================================================

import shutil
import os
import uuid
import json
import requests
import re
from datetime import datetime, timedelta, date, time
from typing import List, Optional
from io import BytesIO

# --- LIBRERIAS DE ANÁLISIS DE DATOS ---
import pandas as pd
from PIL import Image 

# --- COMUNICACIÓN REAL-TIME ---
import pusher

# --- FASTAPI & REDES ---
import uvicorn 
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles

# --- SEGURIDAD Y CIFRADO ---
from jose import JWTError, jwt
from passlib.context import CryptContext

# --- BASE DE DATOS SQLALCHEMY ---
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc
import database 
import models 

# =================================================================
# 1. CONFIGURACIÓN DEL SISTEMA
# =================================================================

UBICACIONES_CACHE = {}

pusher_client = pusher.Pusher(
  app_id='2100678',
  key='e7ac8c8ce7e5485c41c9',
  secret='a0d8ba67c17329710c3c',
  cluster='us2',
  ssl=True
)

SECRET_KEY = "cortex_v15_ultra_secure_key_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title="CÓRTEX V17 - COMMAND CENTER",
    description="Sistema de Inteligencia Táctica y Operaciones",
    version="17.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
    templates = Jinja2Templates(directory=FRONTEND_DIR)

os.makedirs("uploads/evidencias", exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

models.Base.metadata.create_all(bind=database.engine)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =================================================================
# 2. SISTEMA DE ALERTAS (WEBSOCKETS + PUSHER)
# =================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws/alertas")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- MODIFICACIÓN 1: Actualización de caché con Timestamp para detectar desconexión ---
@app.post("/api/v1/ubicacion/")
async def recibir_ubicacion(
    lat: str = Form(...), 
    lon: str = Form(...), 
    oficial_id: str = Form("Oficial"),
    codigo: str = Form("10-8")
):
    try:
        if lat != "0.0" and lon != "0.0":
            # Guardamos timestamp numérico para calcular tiempo real
            UBICACIONES_CACHE[oficial_id] = {
                "lat": lat, 
                "lon": lon, 
                "ts": datetime.now().timestamp(), 
                "hora": datetime.now().strftime("%H:%M:%S")
            }
        
        pusher_client.trigger('canal-operaciones', 'evento-gps', {
            'lat': lat, 'lon': lon, 'oficial': oficial_id, 'codigo': codigo,
            'hora': datetime.now().strftime("%H:%M:%S")
        })
        return {"status": "ok", "mensaje": "Ubicación actualizada"}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

# --- MODIFICACIÓN 2: El Endpoint que FALTABA para que el mapa lea los datos ---
@app.get("/api/v1/ubicacion/{oficial_id}")
async def obtener_ubicacion_gps(oficial_id: str):
    # 1. Buscar coincidencia exacta
    if oficial_id in UBICACIONES_CACHE:
        return UBICACIONES_CACHE[oficial_id]
    
    # 2. Fallback: Si no está el ID exacto, devolvemos el último registrado (para pruebas)
    if len(UBICACIONES_CACHE) > 0:
        ultimo_id = list(UBICACIONES_CACHE.keys())[-1]
        return UBICACIONES_CACHE[ultimo_id]

    raise HTTPException(status_code=404, detail="Sin señal GPS")

# =================================================================
# 3. MOTORES DE INTELIGENCIA (LPR & BÚSQUEDA)
# =================================================================

PLATE_RECOGNIZER_TOKEN = "164762dba606541691236b0f6855e08fe0538a76"

def consultar_plate_recognizer(img_bytes):
    try:
        response = requests.post(
            'https://api.platerecognizer.com/v1/plate-reader/',
            data=dict(regions=['mx']),
            files=dict(upload=img_bytes),
            headers={'Authorization': f'Token {PLATE_RECOGNIZER_TOKEN}'}
        )
        resultado = response.json()
        if 'results' in resultado and len(resultado['results']) > 0:
            return resultado['results'][0]['plate'].upper()
        return None
    except:
        return None

def buscar_en_db(placa, db):
    """ Busca antecedentes priorizando DELITOS GRAVES """
    resultados = [] 
    
    # A. Kardex (Vehículos de Interés)
    try:
        kardex = db.query(models.VehiculoInteres).filter(models.VehiculoInteres.placa == placa).all()
        for k in kardex:
            resultados.append({
                "origen": "KARDEX",
                "titulo": f"¡ALERTA: {k.estatus}!",
                "color": "ROJO" if k.estatus in ["ROBADO", "SECUESTRO"] else "NARANJA",
                "vehiculo": f"{k.marca} {k.modelo}",
                "narrativa": k.notas,
                "fecha": k.fecha_registro.strftime("%Y-%m-%d")
            })
    except: pass

    # B. Incidentes (Historial operativo)
    # ORDENAMOS POR FECHA DESCENDENTE (LO MAS NUEVO PRIMERO)
    vehs = db.query(models.Vehiculo).filter(models.Vehiculo.placas == placa).join(models.Incidente).order_by(models.Incidente.fecha_incidente.desc()).all()
    
    # ⚠️ LÓGICA DE PRIORIDAD VISUAL
    palabras_clave_rojas = ['ROBO', 'HOMICIDIO', 'ARMA', 'SECUESTRO', 'DETONACIONES']
    
    for v in vehs:
        inc = v.incidente
        delito = inc.tipo_incidente.upper()
        
        # Determinar color
        color = "ROJO" if any(x in delito for x in palabras_clave_rojas) else "NARANJA"
        
        item = {
            "origen": "INCIDENTE",
            "titulo": f"ANTECEDENTE: {delito}",
            "color": color,
            "vehiculo": f"{v.marca} {v.modelo}",
            "info_extra": f"Folio: {inc.folio_interno}",
            "narrativa": f"{inc.descripcion_hechos}",
            "fecha": inc.fecha_incidente.strftime("%Y-%m-%d") if inc.fecha_incidente else "S/F"
        }
        
        # Si es rojo, lo ponemos al principio de la lista, si no, al final
        if color == "ROJO":
            resultados.insert(0, item)
        else:
            resultados.append(item)

    if resultados:
        return {
            "resultado": "POSITIVO", "placa_detectada": placa, "existe_registro": True, 
            "alertas": resultados, "cantidad_alertas": len(resultados)
        }
    return { "resultado": "NEGATIVO", "placa_detectada": placa, "existe_registro": False }

def resolver_coordenadas(lat, lon, oficial_id="Oficial"):
    if lat and lon and lat != "0.0" and lat != "0" and lon != "0.0": return lat, lon
    if oficial_id in UBICACIONES_CACHE: return UBICACIONES_CACHE[oficial_id]["lat"], UBICACIONES_CACHE[oficial_id]["lon"]
    if UBICACIONES_CACHE:
        ultimo = list(UBICACIONES_CACHE.values())[-1]
        return ultimo["lat"], ultimo["lon"]
    return "29.072967", "-110.955919"

# =================================================================
# 4. FUNCIONES UTILITARIAS
# =================================================================

def comprimir_imagen(upload_file: UploadFile) -> str:
    try:
        img = Image.open(upload_file.file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((1280, 1280)) 
        
        filename = f"{uuid.uuid4()}.jpg"
        ruta_relativa = f"evidencias/{filename}"
        img.save(f"uploads/{ruta_relativa}", "JPEG", quality=70, optimize=True)
        return ruta_relativa
    except Exception as e:
        filename = f"{uuid.uuid4()}_{upload_file.filename}"
        ruta_relativa = f"evidencias/{filename}"
        with open(f"uploads/{ruta_relativa}", "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return ruta_relativa

def generar_folio_interno():
    return f"CTX-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"

# =================================================================
# 5. ENDPOINTS OPERATIVOS (IPH / LPR / MÓVIL)
# =================================================================

@app.get("/api/v1/placa/texto/{placa}")
async def manual_lpr(placa: str, lat: str="0.0", lon: str="0.0", oficial_id: str="Oficial", db: Session = Depends(get_db)):
    clean = re.sub(r'[^A-Z0-9]', '', placa.upper())
    lat_final, lon_final = resolver_coordenadas(lat, lon, oficial_id)
    res = buscar_en_db(clean, db)
    if res["resultado"] == "POSITIVO":
        await manager.broadcast(json.dumps({
            "tipo": "ALERTA_CRITICA", "placa": clean, "alertas_detalle": res["alertas"], 
            "cantidad": res["cantidad_alertas"], "lat": lat_final, "lon": lon_final
        }))
    return res

@app.get("/api/v1/movil/consulta/{placa}")
async def consulta_placa_movil(placa: str, db: Session = Depends(get_db)):
    print(f"📱 MÓVIL CONSULTANDO: {placa}") 
    
    # 1. Limpieza
    placa_input_clean = placa.replace("-", "").replace(" ", "").upper().strip()
    
    # 2. Búsqueda de TODOS los registros
    registros = db.query(models.Vehiculo).join(models.Incidente)\
        .filter(func.replace(func.replace(models.Vehiculo.placas, '-', ''), ' ', '').ilike(f"%{placa_input_clean}%"))\
        .order_by(models.Incidente.fecha_incidente.desc())\
        .all()
    
    # 3. Si no hay nada, responder limpio
    if not registros:
        return {
            "resultado": "LIMPIO",
            "color": "VERDE",
            "mensaje": f"Placa {placa_input_clean} sin reportes."
        }
    
    # 4. PREPARAR LISTA COMPLETA PARA EL C5i (ESCRITORIO) 
    alertas_para_escritorio = []
    palabras_clave_rojas = ["ROBO", "HOMICIDIO", "SECUESTRO", "ARMAS", "DETONACIONES"]
    
    vehiculo_prioritario = None 

    for v in registros:
        inc = v.incidente
        es_grave = any(k in inc.tipo_incidente.upper() for k in palabras_clave_rojas)
        color = "ROJO" if es_grave else "NARANJA"
        
        # Guardamos en la lista global
        alertas_para_escritorio.append({
            "titulo": inc.tipo_incidente,
            "narrativa": inc.descripcion_hechos,
            "vehiculo": f"{v.marca} {v.modelo}",
            "color": color,
            "fecha": str(inc.fecha_incidente)
        })

        if es_grave and vehiculo_prioritario is None:
            vehiculo_prioritario = v 
        
    if vehiculo_prioritario is None:
        vehiculo_prioritario = registros[0]

    inc_prio = vehiculo_prioritario.incidente

    # --- 🚨 DISPARAR ALERTA EN PANTALLA PC (WEBSOCKETS) ---
    lat_alerta, lon_alerta = resolver_coordenadas("0.0", "0.0", "Oficial")
    
    await manager.broadcast(json.dumps({
        "tipo": "ALERTA_CRITICA",
        "placa": vehiculo_prioritario.placas,
        "lat": lat_alerta,
        "lon": lon_alerta,
        "cantidad": len(registros),
        "alertas_detalle": alertas_para_escritorio 
    }))
    
    # 5. Responder al Celular
    return {
        "resultado": "ALERTA",
        "color": "ROJO", 
        "mensaje": f"¡{len(registros)} REPORTES ENCONTRADOS!",
        "data": {
            "placa": vehiculo_prioritario.placas,
            "vehiculo": f"{vehiculo_prioritario.marca} {vehiculo_prioritario.modelo}",
            "delito": inc_prio.tipo_incidente,
            "fecha": str(inc_prio.fecha_incidente),
            "folio": inc_prio.folio_interno,
            "narrativa": inc_prio.descripcion_hechos[:150] + "..."
        },
        "historial": alertas_para_escritorio 
    }

@app.post("/api/v1/vision/placa")
async def vision_lpr(archivo: UploadFile = File(...), lat: str=Form("0.0"), lon: str=Form("0.0"), oficial_id: str=Form("Oficial"), db: Session = Depends(get_db)):
    try:
        content = await archivo.read()
        placa = consultar_plate_recognizer(content)
        if not placa: return {"resultado": "NEGATIVO", "placa_detectada": "NO VISIBLE", "existe_registro": False}
        lat_final, lon_final = resolver_coordenadas(lat, lon, oficial_id)
        res = buscar_en_db(placa, db)
        if res["resultado"] == "POSITIVO":
            await manager.broadcast(json.dumps({
                "tipo": "ALERTA_CRITICA", "placa": placa, "alertas_detalle": res["alertas"], 
                "cantidad": res["cantidad_alertas"], "lat": lat_final, "lon": lon_final
            }))
        return res
    except Exception as e: return {"error": str(e)}

# --- GEOCODING ---
@app.get("/api/v1/geo/reverse/")
def geocodificacion_inversa(lat: str, lon: str):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        r = requests.get(url, headers={'User-Agent': 'CortexApp/1.0'}, timeout=5)
        if r.status_code == 200:
            d = r.json().get('address', {})
            return {"calle": d.get('road', 'Desc.'), "colonia": d.get('neighbourhood', d.get('suburb', 'Desc.'))}
    except: pass
    return {"calle": "", "colonia": ""}

@app.get("/api/v1/geo/search/")
def buscar_direccion(q: str):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
        r = requests.get(url, headers={'User-Agent': 'CortexApp/1.0'}, timeout=5)
        if r.status_code == 200 and len(r.json()) > 0:
            return [{"lat": r.json()[0]['lat'], "lon": r.json()[0]['lon']}]
    except: pass
    return []

# --- CRUD INCIDENTES V17 ---
@app.post("/api/v1/incidentes/")
async def upsert_incidente(
    id_incidente: str = Form(""), folio_c5i: str = Form(""), descripcion: str = Form(...), razonamiento: str = Form(""), 
    tipo_incidente: str = Form("OTROS"), calle: str = Form(""), colonia: str = Form(""), latitud: str = Form(""), longitud: str = Form(""), 
    fecha_incidente: str = Form(""), hora_incidente: str = Form(""), datos_vehiculos: str = Form("[]"), datos_personas: str = Form("[]"), 
    archivos: List[UploadFile] = File(None), db: Session = Depends(get_db)
):
    obj_fecha = None; obj_hora = None
    if fecha_incidente:
        try: obj_fecha = datetime.strptime(fecha_incidente, "%Y-%m-%d").date()
        except: pass
    else: obj_fecha = datetime.now().date()
    
    if hora_incidente:
        try: obj_hora = datetime.strptime(hora_incidente, "%H:%M").time()
        except: pass

    inc_existente = None
    if id_incidente and id_incidente not in ["null", "undefined", ""]:
        inc_existente = db.query(models.Incidente).filter(models.Incidente.id_incidente == id_incidente).first()

    if inc_existente:
        inc_existente.folio_c5i = folio_c5i
        inc_existente.descripcion_hechos = descripcion
        inc_existente.razonamiento_autoridad = razonamiento
        inc_existente.calle = calle
        inc_existente.colonia = colonia
        inc_existente.latitud = latitud
        inc_existente.longitud = longitud
        inc_existente.tipo_incidente = tipo_incidente
        inc_existente.fecha_incidente = obj_fecha
        inc_existente.hora_incidente = obj_hora
        
        db.query(models.Vehiculo).filter(models.Vehiculo.id_incidente == id_incidente).delete()
        db.query(models.Persona).filter(models.Persona.id_incidente == id_incidente).delete()
        obj_final = inc_existente
    else:
        obj_final = models.Incidente(
            folio_interno=generar_folio_interno(),
            folio_c5i=folio_c5i,
            descripcion_hechos=descripcion, 
            razonamiento_autoridad=razonamiento,
            calle=calle, colonia=colonia, latitud=latitud, longitud=longitud, 
            tipo_incidente=tipo_incidente, 
            fecha_incidente=obj_fecha, hora_incidente=obj_hora
        )
        db.add(obj_final)
        db.flush() 

    try:
        vehs = json.loads(datos_vehiculos) if datos_vehiculos.strip() else []
        for v in vehs:
            db.add(models.Vehiculo(
                id_incidente=obj_final.id_incidente, 
                marca=v.get("marca") or "DESCONOCIDO", 
                modelo=v.get("modelo") or "DESCONOCIDO", 
                anio=v.get("anio") or "SIN AÑO", 
                color=v.get("color") or "DESCONOCIDO", 
                placas=v.get("placas") or "SIN PLACAS"
            ))
    except Exception as e: print(f"Warning Vehiculos: {e}")

    try:
        pers = json.loads(datos_personas) if datos_personas.strip() else []
        for p in pers:
            db.add(models.Persona(
                id_incidente=obj_final.id_incidente, 
                tipo_involucrado=p.get("tipo") or "PRESUNTO",
                nombre_alias=p.get("nombre") or "DESCONOCIDO", 
                sexo=p.get("sexo") or "SIN SEXO",
                edad=p.get("edad") or "DESC",
                vestimenta=p.get("vestimenta") or ""
            ))
    except Exception as e: print(f"Warning Personas: {e}")

    if archivos:
        for archivo in archivos:
            if archivo.filename:
                ruta = comprimir_imagen(archivo)
                db.add(models.Evidencia(id_incidente=obj_final.id_incidente, ruta_archivo_segura=ruta))
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error DB: {str(e)}")

    return {"mensaje": "Operación Exitosa", "folio": obj_final.folio_interno}

@app.delete("/api/v1/incidentes/{id_incidente}")
async def eliminar_incidente(id_incidente: int, db: Session = Depends(get_db)):
    inc = db.query(models.Incidente).filter(models.Incidente.id_incidente == id_incidente).first()
    if not inc: raise HTTPException(status_code=404, detail="No encontrado")
    
    db.query(models.Vehiculo).filter(models.Vehiculo.id_incidente == id_incidente).delete()
    db.query(models.Persona).filter(models.Persona.id_incidente == id_incidente).delete()
    db.query(models.Evidencia).filter(models.Evidencia.id_incidente == id_incidente).delete()
    
    db.delete(inc)
    db.commit()
    return {"status": "eliminado", "id": id_incidente}

@app.get("/api/v1/buscar/")
def buscar_incidentes(q: Optional[str]=None, db: Session=Depends(get_db)):
    query = db.query(models.Incidente)
    if q:
        termino = f"%{q.strip()}%"
        query = query.outerjoin(models.Vehiculo).filter(
            or_(
                models.Incidente.folio_interno.ilike(termino), 
                models.Incidente.folio_c5i.ilike(termino),
                models.Incidente.tipo_incidente.ilike(termino), 
                models.Incidente.colonia.ilike(termino),
                models.Vehiculo.placas.ilike(termino)
            )
        )
    resultados = query.order_by(models.Incidente.fecha_registro_sistema.desc()).limit(100).all()
    
    lista_final = []
    for r in resultados:
        f_str = r.fecha_incidente.strftime("%Y-%m-%d") if r.fecha_incidente else ""
        h_str = r.hora_incidente.strftime("%H:%M") if r.hora_incidente else ""
        
        vehs = [{"marca": v.marca, "modelo": v.modelo, "anio": v.anio, "color": v.color, "placas": v.placas} for v in r.vehiculos]
        pers = [{"nombre": p.nombre_alias, "tipo": p.tipo_involucrado, "sexo": p.sexo, "vestimenta": p.vestimenta, "edad": p.edad} for p in r.personas]
        evs = [{"ruta_archivo_segura": e.ruta_archivo_segura} for e in r.evidencias]
        
        lista_final.append({
            "id_incidente": r.id_incidente,
            "folio_interno": r.folio_interno,
            "folio_c5i": r.folio_c5i,
            "tipo_incidente": r.tipo_incidente,
            "descripcion_hechos": r.descripcion_hechos,
            "razonamiento_autoridad": r.razonamiento_autoridad,
            "calle": r.calle,
            "colonia": r.colonia,
            "latitud": r.latitud,
            "longitud": r.longitud,
            "fecha": f_str,
            "hora": h_str,
            "vehiculos": vehs,
            "personas": pers,
            "evidencias": evs
        })
    return lista_final

@app.get("/api/v1/estadisticas/")
def obtener_estadisticas(db: Session = Depends(get_db)):
    total_inc = db.query(models.Incidente).count()
    total_veh = db.query(models.Vehiculo).distinct(models.Vehiculo.placas).count()
    
    top_delitos = db.query(models.Incidente.tipo_incidente, func.count(models.Incidente.tipo_incidente))\
        .group_by(models.Incidente.tipo_incidente).order_by(func.count(models.Incidente.tipo_incidente).desc()).limit(5).all()
    
    fechas = db.query(models.Incidente.fecha_registro_sistema).all()
    dias_count = [0] * 7 
    horas_count = [0, 0, 0, 0]
    
    for f in fechas:
        if f[0]:
            dias_count[int(f[0].strftime("%w"))] += 1
            h = int(f[0].strftime("%H"))
            if 0<=h<6: horas_count[0]+=1
            elif 6<=h<12: horas_count[1]+=1
            elif 12<=h<18: horas_count[2]+=1
            else: horas_count[3]+=1

    top_colonias = db.query(models.Incidente.colonia, func.count(models.Incidente.colonia))\
        .filter(models.Incidente.colonia != "").group_by(models.Incidente.colonia)\
        .order_by(func.count(models.Incidente.colonia).desc()).limit(5).all()

    heat = []
    puntos = db.query(models.Incidente.latitud, models.Incidente.longitud).all()
    for p in puntos:
        try:
            if p.latitud and p.longitud and p.latitud != "0.0":
                heat.append([float(p.latitud), float(p.longitud), 1.0])
        except: continue

    return {
        "kpis": {"total_incidentes": total_inc, "total_vehiculos": total_veh},
        "graficas": {
            "delitos_labels": [x[0] for x in top_delitos], "delitos_data": [x[1] for x in top_delitos],
            "dias_data": dias_count, "horas_data": horas_count,
            "colonias_labels": [x[0] for x in top_colonias], "colonias_data": [x[1] for x in top_colonias]
        },
        "heatmap": heat
    }

def normalizar_nombre(nombre):
    if not nombre: return "DESC"
    n = nombre.upper().strip()
    return n.replace("EL ", "").replace("LA ", "").replace("ALIAS ", "").strip()

# --- BUSCA ESTA FUNCIÓN EN TU main.py Y REEMPLÁZALA COMPLETA ---

@app.get("/api/v1/inteligencia/red/")
def obtener_red_vinculos(db: Session = Depends(get_db)):
    nodes = []; edges = []; ids_nodos_agregados = set(); personas_unicas = {}; vehiculos_unicos = {}
    
    # Traemos más incidentes para que la red se vea "poblada" (hasta que filtren)
    incidentes = db.query(models.Incidente).order_by(models.Incidente.fecha_registro_sistema.desc()).limit(1000).all()

    for inc in incidentes:
        try:
            id_inc_node = f"inc_{inc.id_incidente}"
            
            # Imagen
            img_url = None
            if inc.evidencias and len(inc.evidencias) > 0:
                img_url = f"http://localhost:8000/static/{inc.evidencias[0].ruta_archivo_segura}"
            
            # HTML Tooltip (Solo info del incidente)
            titulo_inc = f"""
            <div style='background:white; color:black; padding:8px; border:1px solid #ccc; border-radius:4px;'>
                <b style='color:#0d6efd;'>{inc.tipo_incidente}</b><br>
                <span style='font-size:10px;'>{inc.folio_interno}</span><br>
                <span style='font-size:10px;'>📅 {inc.fecha_incidente}</span><br>
                <span style='font-size:10px;'>📍 {inc.colonia}</span>
                {f"<img src='{img_url}' width='100%' style='margin-top:5px;border-radius:3px;'>" if img_url else ""}
            </div>
            """

            if id_inc_node not in ids_nodos_agregados:
                node = {
                    "id": id_inc_node, 
                    "label": inc.tipo_incidente[:15], 
                    "title": titulo_inc,
                    "group": "incidente", 
                    "colonia": inc.colonia,  # Dato para filtrar
                    "font": {"color": "white", "face": "Roboto"}
                }
                
                # Diseño del Nodo Incidente
                if img_url:
                    node.update({"shape": "circularImage", "image": img_url, "size": 30, "borderWidth":3, "color": {"border": "#0d6efd", "background":"white"}})
                else:
                    node.update({"shape": "dot", "color": "#3b82f6", "size": 20})
                
                nodes.append(node)
                ids_nodos_agregados.add(id_inc_node)

            # --- PERSONAS (CORRECCIÓN DE COLORES) ---
            for p in inc.personas:
                nombre_norm = normalizar_nombre(p.nombre_alias)
                id_per_node = personas_unicas.get(nombre_norm)
                
                # LÓGICA DE COLOR ESTRICTA
                es_victima = p.tipo_involucrado.upper() in ["AFECTADO", "VICTIMA", "VÍCTIMA", "DENUNCIANTE"]
                color_p = "#22c55e" if es_victima else "#ef4444" # Verde vs Rojo
                
                if not id_per_node:
                    id_per_node = f"per_{p.id_persona}_{uuid.uuid4().hex[:4]}"
                    personas_unicas[nombre_norm] = id_per_node
                    
                    nodes.append({
                        "id": id_per_node, 
                        "label": nombre_norm, 
                        "group": "persona",
                        "tipo_persona": "VICTIMA" if es_victima else "PRESUNTO", # Para filtrar
                        "title": f"<b>{p.nombre_alias}</b><br>{p.tipo_involucrado}<br>Edad: {p.edad}",
                        "shape": "dot", 
                        "color": color_p, 
                        "size": 15, 
                        "font": {"color": "#fca5a5" if not es_victima else "#86efac"}
                    })
                
                # La arista (línea) también hereda el color
                edges.append({"from": id_inc_node, "to": id_per_node, "color": {"color": color_p, "opacity": 0.4}})

            # --- VEHÍCULOS ---
            for v in inc.vehiculos:
                placa = v.placas.replace("-","").replace(" ","").strip().upper() if v.placas else "S/P"
                llave = placa if len(placa) > 2 else f"AUTO_{v.marca}_{v.modelo}"
                id_veh_node = vehiculos_unicos.get(llave)
                
                # Tooltip SOLO del vehículo
                tt_veh = f"""
                <div style='background:white; color:black; padding:5px; border-radius:3px;'>
                    <b>{v.marca} {v.modelo}</b><br>
                    <span style='background:#000;color:white;padding:2px 4px;border-radius:3px;'>{placa}</span>
                </div>
                """

                if not id_veh_node:
                    id_veh_node = f"veh_{v.id_vehiculo}_{uuid.uuid4().hex[:4]}"
                    vehiculos_unicos[llave] = id_veh_node
                    
                    node_v = {
                        "id": id_veh_node, 
                        "label": f"{v.marca}\n{placa}", 
                        "group": "vehiculo",
                        "title": tt_veh, 
                        "shape": "dot", 
                        "color": "#f59e0b", # Amarillo
                        "size": 15,
                        "font": {"color": "#fcd34d"}
                    }
                    # Si quieres que el vehículo tenga foto si el incidente la tiene, descomenta esto:
                    # if img_url: node_v.update({"shape": "circularImage", "image": img_url})

                    nodes.append(node_v)
                
                edges.append({"from": id_inc_node, "to": id_veh_node, "color": {"color": "#f59e0b", "opacity": 0.4}})
        except: continue
    
    return {"nodes": nodes, "edges": edges}

# =================================================================
# 7. USUARIOS & WEB
# =================================================================

@app.get("/api/v1/users/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.Usuario).all()
    return [{"id_usuario": u.id_usuario, "username": u.username, "nombre_completo": u.nombre_completo, "rol": u.rol} for u in users]

@app.post("/api/v1/users/")
def create_user(username: str=Form(...), password: str=Form(...), nombre: str=Form(...), rol: str=Form(...), db: Session=Depends(get_db)):
    if db.query(models.Usuario).filter(models.Usuario.username == username).first():
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    hashed = pwd_context.hash(password)
    db.add(models.Usuario(username=username, password_hash=hashed, nombre_completo=nombre, rol=rol))
    db.commit()
    return {"mensaje": "Usuario creado"}

@app.delete("/api/v1/users/{id_usuario}")
def delete_user(id_usuario: int, db: Session=Depends(get_db)):
    u = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if u: db.delete(u); db.commit()
    return {"status": "ok"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm=Depends(), db: Session=Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    token = jwt.encode({"sub": user.username, "exp": datetime.utcnow()+timedelta(hours=24)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "rol": user.rol}

@app.get("/frontend/login.html")
async def login_page(): return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))
@app.get("/index.html")
@app.get("/frontend/index.html")
async def index_page(): return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.post("/panel/preview")
async def preview_excel(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content)).fillna("")
        return {"datos": df.to_dict(orient="records"), "mensaje": f"{len(df)} registros."}
    except Exception as e: return {"error": str(e)}

@app.post("/panel/confirmar")
async def confirmar_carga(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    count = 0
    for row in data.get('registros', []):
        inc = models.Incidente(
            folio_interno=str(row.get('FOLIO', f"MASIVO-{uuid.uuid4().hex[:4]}")),
            tipo_incidente=str(row.get('DELITO', 'OTROS')),
            descripcion_hechos=str(row.get('DESCRIPCION', 'Carga Masiva')),
            colonia=str(row.get('COLONIA', '')),
            calle=str(row.get('CALLE', '')),
            fecha_registro_sistema=datetime.now()
        )
        db.add(inc); db.flush()
        if 'PLACA' in row and str(row['PLACA']):
            db.add(models.Vehiculo(id_incidente=inc.id_incidente, placas=str(row['PLACA']), marca=str(row.get('MARCA', '')), modelo=str(row.get('MODELO', ''))))
        count += 1
    db.commit()
    return {"status": "ok", "mensaje": f"{count} registros procesados."}

# =================================================================
# 8. ARRANQUE DEL SERVIDOR (MOTOR UVICORN)
# =================================================================
if __name__ == "__main__":
    # "main:app" -> Archivo main.py, objeto app
    # host="0.0.0.0" -> Permite conexiones desde la red (celular)
    # reload=True -> Reinicia el servidor automáticamente si editas código
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
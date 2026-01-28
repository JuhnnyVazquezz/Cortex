# =========================================================================
# CÓRTEX V17.6 - NÚCLEO CENTRAL (FIX FINAL: BÚSQUEDA + GPS + ALERTAS)
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

# MEMORIA RAM PARA GPS (Aquí viven las coordenadas en tiempo real)
UBICACIONES_CACHE = {}

SECRET_KEY = "cortex_v15_ultra_secure_key_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title="CÓRTEX V17 - COMMAND CENTER",
    description="Sistema de Inteligencia Táctica y Operaciones",
    version="17.6.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montaje de archivos estáticos
if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
    templates = Jinja2Templates(directory=FRONTEND_DIR)

os.makedirs("uploads/evidencias", exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Crear tablas si no existen
models.Base.metadata.create_all(bind=database.engine)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =================================================================
# 2. SISTEMA DE ALERTAS (WEBSOCKETS)
# =================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ PANTALLA C5i CONECTADA: {websocket.client.host}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Envia el mensaje a TODAS las pantallas (PC)
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error WS: {e}")
                pass

manager = ConnectionManager()

@app.websocket("/ws/alertas")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Mantener vivo
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# =================================================================
# 3. MÓDULO GPS (FIX COMPROBADO)
# =================================================================

@app.post("/api/v1/ubicacion/")
async def recibir_ubicacion(
    lat: str = Form(...), 
    lon: str = Form(...), 
    oficial_id: str = Form(...), 
    codigo: str = Form("10-8")
):
    try:
        # Validación básica para no guardar ceros o nulos
        if lat and lon and lat != "0.0" and lon != "0.0":
            
            # --- GUARDADO COMPATIBLE CON MAPA Y CELULAR ---
            UBICACIONES_CACHE[oficial_id] = {
                "latitud": lat,   # Clave corregida
                "longitud": lon,  # Clave corregida
                "ts": datetime.now().timestamp(), 
                "hora": datetime.now().strftime("%H:%M:%S"),
                "status": "ONLINE",
                "oficial": oficial_id
            }
        
        return {"status": "ok", "mensaje": "Coordenadas actualizadas"}
    except Exception as e:
        print(f"❌ ERROR GPS: {e}")
        return {"status": "error", "mensaje": str(e)}

@app.get("/api/v1/ubicacion/{oficial_id}")
async def obtener_ubicacion_gps(oficial_id: str):
    # 1. Buscar coincidencia exacta
    datos = UBICACIONES_CACHE.get(oficial_id)
    
    if datos:
        return datos
    
    # 2. Fallback: Evitar error 404 en el mapa
    return {
        "latitud": 0, 
        "longitud": 0, 
        "status": "WAITING_SIGNAL",
        "ts": 0
    }

def resolver_coordenadas(lat, lon, oficial_id="Oficial"):
    # Intenta usar las coordenadas que vienen en la petición
    if lat and lon and lat != "0.0" and lat != "0" and lon != "0.0": 
        return lat, lon
    
    # Si vienen vacías, buscamos la última posición GPS conocida del oficial en Cache
    if oficial_id in UBICACIONES_CACHE: 
        return UBICACIONES_CACHE[oficial_id]["latitud"], UBICACIONES_CACHE[oficial_id]["longitud"]
    
    # Fallback final (Centro de Hermosillo)
    return "29.072967", "-110.955919"

# =================================================================
# 4. MOTORES DE INTELIGENCIA (BÚSQUEDA RESTAURADA)
# =================================================================

PLATE_RECOGNIZER_TOKEN = "164762dba606541691236b0f6855e08fe0538a76"

def consultar_plate_recognizer(img_bytes):
    try:
        response = requests.post(
            'https://api.platerecognizer.com/v1/plate-reader/',
            data=dict(regions=['mx']),
            files=dict(upload=img_bytes),
            headers={'Authorization': f'Token {PLATE_RECOGNIZER_TOKEN}'},
            timeout=10 
        )
        resultado = response.json()
        if 'results' in resultado and len(resultado['results']) > 0:
            return resultado['results'][0]['plate'].upper()
        return None
    except:
        return None

# --- ENDPOINT CONSULTA MÓVIL (LÓGICA RESTAURADA) ---
@app.get("/api/v1/movil/consulta/{placa}")
async def consulta_placa_movil(placa: str, db: Session = Depends(get_db)):
    print(f"📱 MÓVIL CONSULTANDO: {placa}") 
    
    # 1. Limpieza Básica
    placa_input_clean = placa.replace("-", "").replace(" ", "").upper().strip()
    
    # 2. BÚSQUEDA ROBUSTA (RESTITUIDA)
    # Usamos ILIKE y REPLACE en SQL para ignorar guiones y espacios en la BD también
    registros = db.query(models.Vehiculo).join(models.Incidente)\
        .filter(func.replace(func.replace(models.Vehiculo.placas, '-', ''), ' ', '').ilike(f"%{placa_input_clean}%"))\
        .order_by(models.Incidente.fecha_incidente.desc())\
        .all()
    
    # 3. Si no hay registros, buscamos en KARDEX (Vehículos de Interés sin incidente)
    kardex_matches = []
    if not registros:
        kardex = db.query(models.VehiculoInteres).filter(func.replace(func.replace(models.VehiculoInteres.placa, '-', ''), ' ', '').ilike(f"%{placa_input_clean}%")).all()
        for k in kardex:
            kardex_matches.append({
                "titulo": f"¡ALERTA: {k.estatus}!",
                "narrativa": k.notas,
                "vehiculo": f"{k.marca} {k.modelo}",
                "color": "ROJO",
                "fecha": k.fecha_registro.strftime("%Y-%m-%d"),
                "info_extra": "LISTA NEGRA KARDEX"
            })

    # 4. Procesamiento de Resultados
    if not registros and not kardex_matches:
        return {
            "resultado": "LIMPIO",
            "color": "VERDE",
            "mensaje": f"Placa {placa_input_clean} sin reportes."
        }
    
    # Preparamos la lista para la alerta
    alertas_para_escritorio = []
    palabras_clave_rojas = ["ROBO", "HOMICIDIO", "SECUESTRO", "ARMAS", "DETONACIONES"]
    
    # Agregamos primero los de KARDEX si hubo
    alertas_para_escritorio.extend(kardex_matches)

    vehiculo_prioritario = None 

    for v in registros:
        inc = v.incidente
        es_grave = any(k in inc.tipo_incidente.upper() for k in palabras_clave_rojas)
        color = "ROJO" if es_grave else "NARANJA"
        
        datos_alerta = {
            "titulo": inc.tipo_incidente,
            "narrativa": inc.descripcion_hechos,
            "vehiculo": f"{v.marca} {v.modelo}",
            "color": color,
            "fecha": str(inc.fecha_incidente),
            "info_extra": f"FOLIO: {inc.folio_interno}"
        }
        
        alertas_para_escritorio.append(datos_alerta)

        if es_grave and vehiculo_prioritario is None:
            vehiculo_prioritario = v 
            
    # Datos para la tarjeta principal del celular
    dato_principal = alertas_para_escritorio[0]
    
    # --- 🚨 DISPARAR ALERTA EN PANTALLA PC (WEBSOCKETS) ---
    # Usamos la ubicación del móvil (OFICIAL_MOVIL_01)
    lat_alerta, lon_alerta = resolver_coordenadas("0.0", "0.0", "OFICIAL_MOVIL_01")
    
    await manager.broadcast(json.dumps({
        "tipo": "ALERTA_CRITICA",
        "placa": placa_input_clean,
        "lat": lat_alerta,
        "lon": lon_alerta,
        "cantidad": len(alertas_para_escritorio),
        "alertas_detalle": alertas_para_escritorio
    }))
    print(f"🚨 ALERTA ENVIADA A PC: {placa_input_clean}")

    # 5. Responder al Celular
    return {
        "resultado": "ALERTA",
        "color": "ROJO", 
        "mensaje": f"¡{len(alertas_para_escritorio)} ALERTAS!",
        "data": { # Para la tarjeta principal (Legacy support)
            "placa": placa_input_clean,
            "vehiculo": dato_principal["vehiculo"],
            "delito": dato_principal["titulo"],
            "fecha": dato_principal["fecha"],
            "folio": dato_principal.get("info_extra", ""),
            "narrativa": dato_principal["narrativa"]
        },
        "historial": alertas_para_escritorio 
    }

# --- ENDPOINT VISIÓN (LPR) ---
@app.post("/api/v1/vision/placa")
async def vision_lpr(
    archivo: UploadFile = File(...), 
    lat: str=Form("0.0"), 
    lon: str=Form("0.0"), 
    oficial_id: str=Form("Oficial"), 
    db: Session = Depends(get_db)
):
    try:
        content = await archivo.read()
        placa = consultar_plate_recognizer(content)
        
        if not placa: 
            return {"resultado": "NEGATIVO", "placa_detectada": "NO VISIBLE", "existe_registro": False}
        
        # Reutilizamos la lógica de consulta móvil para consistencia
        # NOTA: Llamamos a la lógica interna, no al endpoint HTTP para ahorrar tiempo
        res = await consulta_placa_movil(placa, db)
        
        # Inyectamos la placa detectada real
        res["placa_detectada"] = placa
        
        # Si fue positivo, la alerta ya se disparó dentro de consulta_placa_movil
        # Pero necesitamos asegurarnos que la ubicación sea la de la FOTO, no la del cache
        if res.get("resultado") == "ALERTA":
             # Re-broadcast con la ubicación exacta de la foto si está disponible
             if lat != "0.0":
                 await manager.broadcast(json.dumps({
                    "tipo": "ALERTA_CRITICA",
                    "placa": placa,
                    "lat": lat,
                    "lon": lon,
                    "cantidad": len(res.get("historial", [])),
                    "alertas_detalle": res.get("historial", [])
                }))

        return res
    except Exception as e: 
        print(f"Error Vision: {e}")
        return {"error": str(e)}

# =================================================================
# 5. ENDPOINTS DE SOPORTE (GEO, USUARIOS, ESTADISTICAS)
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

# --- MÓDULO RED NEURAL ENRIQUECIDO V33 ---
@app.get("/api/v1/inteligencia/red/")
def obtener_red_vinculos(db: Session = Depends(get_db)):
    nodes = []; edges = []; ids = set()
    
    # Traemos incidentes recientes
    incidentes = db.query(models.Incidente).order_by(models.Incidente.fecha_registro_sistema.desc()).limit(200).all()
    
    for inc in incidentes:
        nid = f"inc_{inc.id_incidente}"
        
        # Detectar primera imagen para mostrarla en el nodo
        foto = None
        if inc.evidencias and len(inc.evidencias) > 0:
            foto = f"http://192.168.248.28:8000/static/{inc.evidencias[0].ruta_archivo_segura}"

        if nid not in ids:
            nodes.append({
                "id": nid, 
                "label": inc.tipo_incidente, 
                "group": "incidente",
                "folio": inc.folio_interno,
                "colonia": inc.colonia,
                "municipio": getattr(inc, "municipio", "HERMOSILLO"),
                "narrativa": inc.descripcion_hechos, # DATA REAL COMPLETA
                "image": foto, # FOTO REAL
                "db_id": inc.id_incidente # ID PARA ABRIR EXPEDIENTE
            })
            ids.add(nid)
        
        # Vehiculos
        for v in inc.vehiculos:
            vid = f"veh_{v.id_vehiculo}"
            label_v = f"{v.marca} {v.modelo}"
            if vid not in ids:
                nodes.append({
                    "id": vid, 
                    "label": label_v, 
                    "group": "vehiculo",
                    "placa": v.placas, # PLACA REAL
                    "color_veh": v.color
                })
                ids.add(vid)
            edges.append({"from": nid, "to": vid})

        # Personas
        for p in inc.personas:
            pid = f"per_{p.id_persona}"
            if pid not in ids:
                # Normalizar Rol
                es_victima = p.tipo_involucrado.upper() in ["AFECTADO", "VICTIMA", "DENUNCIANTE"]
                tipo_norm = "VICTIMA" if es_victima else "IMPUTADO"
                
                nodes.append({
                    "id": pid, 
                    "label": p.nombre_alias, 
                    "group": "persona", 
                    "tipo_persona": tipo_norm, 
                    "edad": p.edad,
                    "vestimenta": p.vestimenta
                })
                ids.add(pid)
            edges.append({"from": nid, "to": pid})

    return {"nodes": nodes, "edges": edges}

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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
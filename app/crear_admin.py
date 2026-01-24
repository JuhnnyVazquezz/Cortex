from database import SessionLocal, engine
import models
from passlib.context import CryptContext

# Configuración de seguridad
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def crear_admin():
    db = SessionLocal()
    
    # Datos del Comandante
    usuario = "admin"
    password_plana = "cortex123"
    
    # Verificar si ya existe
    existe = db.query(models.Usuario).filter(models.Usuario.username == usuario).first()
    if existe:
        print(f"⚠️ El agente '{usuario}' ya existe. Borrándolo para reiniciar credenciales...")
        db.delete(existe)
        db.commit()

    # Crear Usuario
    hashed_password = pwd_context.hash(password_plana)
    nuevo_usuario = models.Usuario(
        username=usuario,
        password_hash=hashed_password,
        nombre_completo="COMANDANTE JUHNNY",
        rol="admin"
    )
    
    db.add(nuevo_usuario)
    db.commit()
    print(f"✅ USUARIO CREADO EXITOSAMENTE")
    print(f"👤 User: {usuario}")
    print(f"🔑 Pass: {password_plana}")
    db.close()

if __name__ == "__main__":
    crear_admin()
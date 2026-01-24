from database import SessionLocal, engine
import models
from passlib.context import CryptContext

# Configuración de seguridad (Igual que en main.py)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def crear_admin():
    db = SessionLocal()
    
    # Verificar si ya existe
    existe = db.query(models.Usuario).filter(models.Usuario.username == "admin").first()
    if existe:
        print("--- EL ADMIN YA EXISTE ---")
        return

    print("Creando usuario Administrador...")
    
    # Encriptar password
    password_hash = pwd_context.hash("cortex123")
    
    nuevo_admin = models.Usuario(
        username="admin",
        password_hash=password_hash,
        nombre_completo="Comandante Juhnny",
        rol="admin"
    )
    
    db.add(nuevo_admin)
    db.commit()
    print("✅ USUARIO 'admin' CREADO EXITOSAMENTE")
    db.close()

if __name__ == "__main__":
    crear_admin()
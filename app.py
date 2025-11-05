from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from typing import Annotated
import httpx # Para hacer peticiones HTTP externas
from pydantic import BaseModel # Para definir el modelo de datos del request
import os
#from db.database import get_connection
# from starlette.middleware.base import BaseHTTPMiddleware


# from dotenv import load_dotenv # 👈 Importar dotenv
# load_dotenv() # 👈 Cargar variables de entorno al inicio


# app = FastAPI(
#     docs_url=None,
#     redoc_url=None,
#     openapi_url=None
# )

app = FastAPI()


# --- Configuración de rutas para archivos estáticos ---

# 1. Calcula la ruta base del directorio donde está app.py
#    Esto es: /var/www/html/Detenidos/back/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Construye la ruta al directorio 'Front'
#    Vamos un nivel arriba de BASE_DIR (a /var/www/html/Detenidos/)
#    y luego entramos en la carpeta 'Front'.
FRONT_END_DIR = os.path.join(BASE_DIR, ".", "static")

# 3. VERIFICA que el directorio 'Front' exista
#    Esto es crucial. Si no existe, verás el error de nuevo.
if not os.path.isdir(FRONT_END_DIR):
    raise RuntimeError(f"El directorio de frontend no se encuentra: {FRONT_END_DIR}")

# 4. Monta la carpeta 'Front' para servir archivos estáticos.
#    Ahora StaticFiles sabe dónde buscar realmente.
app.mount("/static", StaticFiles(directory=FRONT_END_DIR), name="static")

# --- Rutas de la aplicación ---

#


@app.get("/")
async def root():
    # Sirve el index.html desde la carpeta Front.
    # Necesitamos la ruta completa al archivo index.html.
    file_path = os.path.join(FRONT_END_DIR, "reCaptcha.html")

    # Verifica si el archivo existe antes de intentar servirlo
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="reCaptcha.html no encontrado en el frontend.")

    return FileResponse(file_path)



# import os
# from pathlib import Path
# from fastapi import FastAPI, Form, HTTPException, Depends
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# import httpx # Para hacer peticiones HTTP externas
# from pydantic import BaseModel # Para definir el modelo de datos del request

# app = FastAPI()

# --- Configuración de reCAPTCHA Enterprise ---
# ¡IMPORTANTE! NUNCA expongas estas claves directamente en el código de producción.
# Usa variables de entorno (por ejemplo, con python-dotenv o la configuración de tu orquestador).
# Para este ejemplo, las pondremos aquí, pero cámbialo en producción.
# Puedes obtenerlas de tu consola de Google Cloud.
# clave de sitio web
# 6LfgxQIsAAAAAIhBYViY8onMMC6RcxsFloNbewQf
# clave secreta
# 6LfgxQIsAAAAAPToIkHuZ_oxFyvDITlU5AjU8neh
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "recaptch-adetenidos")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "6Le1vgMsAAAAAMk2D_4PdAxWNFAQVfh6o5yji_er") # Esta es la clave para la verificación del backend


# --- Configuración de archivos estáticos (igual que antes) ---
# static_dir = Path(__file__).parent / "static"
# app.mount("/static", StaticFiles(directory=static_dir), name="static")

# @app.get("/", response_class=HTMLResponse)
# async def read_root():
    # index_html_path = static_dir / "reCaptcha.html"
    # if not index_html_path.exists():
        # return HTMLResponse("<h1>Error: reCaptcha.html no encontrado en la carpeta 'static'.</h1>", status_code=404)
    # with open(index_html_path, "r", encoding="utf-8") as f:
        # html_content = f.read()
    # return HTMLResponse(content=html_content)

# --- Endpoint para el inicio de sesión con verificación reCAPTCHA ---

# Modelo para la respuesta de Google reCAPTCHA Enterprise
class RecaptchaAssessment(BaseModel):
    name: str
    event: dict # Contiene info como token, siteKey, userAgent
    riskAnalysis: dict # Contiene score, reasons
    tokenProperties: dict # Contiene valid, hostname, action, createTime, expireTime

async def verify_recaptcha_enterprise(recaptcha_token: str, action: str):
    """
    Verifica un token de reCAPTCHA Enterprise con la API de Google.
    """
    if not GOOGLE_CLOUD_PROJECT_ID or not GOOGLE_API_KEY:
        print("Saltando verificación reCAPTCHA: Credenciales no configuradas.")
        # En un entorno de desarrollo, podrías devolver True para probar.
        # En producción, esto debería ser un error o False.
        return True # Permite el paso si las credenciales no están configuradas (SOLO PARA DESARROLLO)

    url = f"https://recaptchaenterprise.googleapis.com/v1/projects/{GOOGLE_CLOUD_PROJECT_ID}/assessments?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "event": {
            "token": recaptcha_token,
            "siteKey": "6Le1vgMsAAAAAIAtnT0vy4hsKUZc8CTox966bdPL", # Tu site key del frontend
            "expectedAction": action, # La acción que esperas (ej. 'LOGIN')
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status() # Lanza una excepción para errores HTTP (4xx o 5xx)
            assessment_data = response.json()
            assessment = RecaptchaAssessment(**assessment_data)

            # --- Lógica de decisión basada en la puntuación de riesgo ---
            # Un score cercano a 1.0 es probablemente un usuario real.
            # Un score cercano a 0.0 es probablemente un bot.
            # Los "reasons" pueden dar más detalles.

            # Ejemplo: Considerar "válido" si el token es válido y la puntuación es alta
            is_valid_token = assessment.tokenProperties.get("valid", False)
            score = assessment.riskAnalysis.get("score", 0.0)
            
            # Puedes ajustar este umbral según tus necesidades y las de tu aplicación
            min_score = 0.5 # Ejemplo: requerir una puntuación mínima de 0.5
            
            if is_valid_token and score >= min_score and assessment.tokenProperties.get("action") == action:
                print(f"reCAPTCHA Verified: Score={score}, Reasons={assessment.riskAnalysis.get('reasons')}")
                return True
            else:
                print(f"reCAPTCHA Failed: Valid token={is_valid_token}, Score={score}, Expected Action={action}, Actual Action={assessment.tokenProperties.get('action')}, Reasons={assessment.riskAnalysis.get('reasons')}")
                return False

        except httpx.HTTPStatusError as e:
            print(f"Error HTTP al verificar reCAPTCHA: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=500, detail="Error interno al verificar reCAPTCHA.")
        except httpx.RequestError as e:
            print(f"Error de red al verificar reCAPTCHA: {e}")
            raise HTTPException(status_code=500, detail="Error de conexión al verificar reCAPTCHA.")
        except Exception as e:
            print(f"Error inesperado al procesar reCAPTCHA: {e}")
            raise HTTPException(status_code=500, detail="Error interno al procesar reCAPTCHA.")


@app.post("/login")
async def login(
    usuario: str = Form(...),
    clave: str = Form(...),
    g_recaptcha_token: str = Form(..., alias="g_recaptcha_token") # Obtiene el token de reCAPTCHA
):
    print(f"Intento de login para usuario: {usuario}")
    print(f"Token reCAPTCHA recibido: {g_recaptcha_token[:10]}...") # Imprimir solo un fragmento

    # 1. Verificar el token de reCAPTCHA Enterprise
    is_recaptcha_valid = await verify_recaptcha_enterprise(g_recaptcha_token, action="LOGIN")

    if not is_recaptcha_valid:
        raise HTTPException(status_code=400, detail="Verificación reCAPTCHA fallida o puntuación baja.")

    # 2. Si reCAPTCHA es válido, procede con la lógica de autenticación real
    #    (¡Aquí iría tu código para verificar usuario y contraseña en una BD!)
    if usuario == "test" and clave == "password":
        return {"message": f"Inicio de sesión exitoso para {usuario}!"}
    else:

        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")






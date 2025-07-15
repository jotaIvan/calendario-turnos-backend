# main.py
import pandas as pd
from datetime import datetime, date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import moment

# --- Mapeo de Horarios por Tipo de Turno y Día de la Semana ---
HORARIOS_POR_TURNO = {
    "Lunes a Viernes": {
        "T1A": "05:45 - 13:45",
        "T1B": "07:00 - 15:00",
        "T2A": "13:45 - 21:45",
        "T2B": "15:30 - 23:30",
        "R": "Descanso",
        "HN": "Horas Nocturnas",
        "": "Día Libre / No Definido"
    },
    "Sábado": {
        "T1A": "06:15 - 14:15",
        "T1B": "07:00 - 15:00",
        "T2A": "15:30 - 23:30",
        "T2B": "15:00 - 23:00",
        "R": "Descanso",
        "HN": "Horas Nocturnas",
        "": "Día Libre / No Definido"
    },
    "Domingos y Festivos": {
        "T1A": "07:30 - 15:30",
        "HN": "09:00 - 17:00",
        "T2A": "15:30 - 23:30",
        "R": "Descanso",
        "T1B": "No aplica",
        "T2B": "No aplica",
        "": "Día Libre / No Definido"
    }
}

# Cargar variables de entorno del archivo .env
load_dotenv()

# --- Configuración ---
EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "turnoRaiz.xlsx")

app = FastAPI(
    title="API de Turnos",
    description="Una API para gestionar y consultar turnos de trabajo desde un archivo Excel.",
    version="1.0.0"
)

# --- Lista de Nombres de Personas ---
# ¡AJUSTA ESTA LISTA! Asegúrate de que estos nombres coincidan EXACTAMENTE
# con los encabezados de tus columnas en el Excel.
NOMBRES_PERSONAS = ['J. VIDAL', 'M. PAEZ', 'L.DOMINGUEZ', 'J.VASQUEZ', 'J.CANALES', 'L. FERNANDEZ', 'N. SANTANDER', 'P. PEÑA', 'L. MOLINA', 'N. CARREÑO']

# --- Configuración CORS ---
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:19000",
    "http://localhost:19001",
    # Asegúrate de que esta IP sea la de tu máquina donde corres el backend
    # Por ejemplo, "http://192.168.1.XX:8000" o "http://192.168.91.252:8000"
    "http://192.168.91.252:8000", # <-- AJUSTA ESTA IP SI ES NECESARIO
    "http://192.168.150.252:8000", # <-- AJUSTA ESTA IP SI ES NECESARIO
    "https://calendario-turnos-backend.onrender.com" # Tu URL de Render.com
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Para desarrollo, "*" es conveniente. En producción, usa 'origins'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Función auxiliar para determinar el tipo de día
def get_tipo_dia(fecha: date):
    if fecha.weekday() == 5: # Sábado es 5
        return "Sábado"
    elif fecha.weekday() == 6: # Domingo es 6
        return "Domingos y Festivos"
    else: # Lunes a Viernes (0 a 4)
        return "Lunes a Viernes"

# --- Función para cargar turnos desde el archivo Excel (MODIFICADA) ---
def cargar_turnos_desde_excel_full(archivo_path: str) -> dict:
    try:
        print(f"Intentando cargar Excel desde: {archivo_path}")
        df = pd.read_excel(archivo_path)
    except FileNotFoundError:
        print(f"Error: Archivo Excel no encontrado en {archivo_path}")
        raise HTTPException(status_code=404, detail="Archivo Excel de turnos no encontrado.")
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo Excel: {e}")

    turnos_data_completa = {}
    
    if 'FECHA' not in df.columns:
        raise HTTPException(status_code=500, detail="Columna 'FECHA' no encontrada en el Excel.")
    
    # Si 'AÑO' no está o está vacía, intentamos inferirla del año actual o de la columna 'FECHA'
    if 'AÑO' not in df.columns or df['AÑO'].isnull().all():
        print("Advertencia: Columna 'AÑO' no encontrada o vacía. Intentando inferir el año del mes actual.")
        anio_defecto = datetime.now().year # Usamos el año actual como fallback
        df['AÑO'] = df['AÑO'].fillna(anio_defecto)

    for index, row in df.iterrows():
        try:
            fecha_bruta = str(row['FECHA']).strip() # Asegúrate de que siempre sea un string y quita espacios
            anio = int(row['AÑO'])

            fecha_obj = None

            # 1. Intentar parsear como fecha de Pandas/Python nativa (si ya viene bien del Excel)
            if isinstance(row['FECHA'], (pd.Timestamp, datetime, date)):
                fecha_obj = row['FECHA'].date()

            # 2. Intentar parsear el formato "DD/MM, dia_semana_abreviado"
            elif ',' in fecha_bruta and '/' in fecha_bruta:
                try:
                    # Extraer "DD/MM" y el "dia_semana_abreviado"
                    partes_fecha = fecha_bruta.split(',')[0].strip() # "18/12"
                    dia_str, mes_str = partes_fecha.split('/')
                    dia = int(dia_str)
                    mes = int(mes_str)
                    fecha_obj = date(anio, mes, dia)
                except ValueError:
                    print(f"Advertencia: No se pudo parsear 'DD/MM' de '{fecha_bruta}'.")
            
            # 3. Intentar parsear el formato "DD/MM/YYYY" si es posible
            elif '/' in fecha_bruta and len(fecha_bruta.split('/')) == 3:
                try:
                    fecha_obj = datetime.strptime(fecha_bruta, "%d/%m/%Y").date()
                except ValueError:
                    print(f"Advertencia: No se pudo parsear como 'DD/MM/YYYY': '{fecha_bruta}'.")

            # 4. Intentar parsear como solo día si 'MES_NUMERO' está disponible
            elif isinstance(fecha_bruta, (int, float)): # Si el valor es solo el día numérico
                dia = int(fecha_bruta)
                mes = datetime.now().month # Valor por defecto, si no hay 'MES_NUMERO'
                if "MES_NUMERO" in df.columns and pd.notna(row["MES_NUMERO"]):
                    mes = int(row["MES_NUMERO"])
                fecha_obj = date(anio, mes, dia)

            if fecha_obj is None:
                print(f"Error: No se pudo parsear la fecha '{fecha_bruta}' en la fila {index}. Saltando.")
                continue # Saltar esta fila si la fecha no pudo ser parseada

            fecha_str = fecha_obj.strftime("%Y-%m-%d")
            
            turnos_del_dia = {}
            for persona in NOMBRES_PERSONAS:
                tipo_turno_raw = row.get(persona, '')
                tipo_turno = str(tipo_turno_raw).strip() if pd.notna(tipo_turno_raw) else ''
                
                tipo_dia = get_tipo_dia(fecha_obj)
                horario = HORARIOS_POR_TURNO.get(tipo_dia, {}).get(tipo_turno, "Horario no disponible")

                turnos_del_dia[persona] = {
                    "tipo_turno": tipo_turno,
                    "horario": horario
                }
            turnos_data_completa[fecha_str] = turnos_del_dia

        except Exception as e:
            print(f"Error general procesando fila {index} (Fecha: {row.get('FECHA', 'N/A')}): {e}")
            continue

    print(f"Cargados {len(turnos_data_completa)} días de turnos para {len(NOMBRES_PERSONAS)} personas.")
    return turnos_data_completa

# Cargar los turnos al iniciar la aplicación FastAPI
# Se hace una carga inicial global para que los endpoints puedan acceder a ella
turnos_completos = cargar_turnos_desde_excel_full(EXCEL_FILE_PATH)

# --- Rutas de la API ---

@app.get("/")
async def read_root():
    return {"message": "Bienvenido a la API de Turnos!"}

@app.get("/turnos")
async def get_all_turnos():
    global turnos_completos
         
    if not turnos_completos:
        # Intenta recargar si está vacío (útil si el archivo aparece después del inicio)       
        turnos_completos = cargar_turnos_desde_excel_full(EXCEL_FILE_PATH)
        if not turnos_completos:
             raise HTTPException(status_code=404, detail="Turnos no cargados o archivo no encontrado")
    return turnos_completos

@app.post("/register_device")
async def register_device(request: dict): # <-- Cambiado a dict para recibir JSON
    device_token = request.get("device_token")
    if device_token:
        print(f"Dispositivo registrado con token: {device_token}")
        # Aquí es donde REALMENTE guardarías el token en una base de datos.
        # Por ahora, solo lo imprimimos.
        return {"message": "Token de dispositivo registrado exitosamente"}
    raise HTTPException(status_code=400, detail="Falta el token del dispositivo")
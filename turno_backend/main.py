# main.py
import pandas as pd
from datetime import datetime, date # <-- Añade 'date' aquí
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Para permitir que React Native se conecte
from dotenv import load_dotenv # Para cargar variables de entorno
import os


# --- Mapeo de Horarios por Tipo de Turno y Día de la Semana ---
# Usaremos una estructura para facilitar la consulta
HORARIOS_POR_TURNO = {
    "Lunes a Viernes": {
        "T1A": "05:45 - 13:45",
        "T1B": "07:00 - 15:00",
        "T2A": "13:45 - 21:45",
        "T2B": "15:30 - 23:30",
        "R": "Descanso", # Añade el horario para Descanso si no está en Excel
        "HN": "Horas Nocturnas", # Añade para Horas Nocturnas si no está en Excel
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
        "HN": "09:00 - 17:00", # Asumo que es el horario de HN para domingos/festivos
        "T2A": "15:30 - 23:30",
        "R": "Descanso",
        "T1B": "No aplica", # Puedes poner "No aplica" o el horario si existe
        "T2B": "No aplica", # Puedes poner "No aplica" o el horario si existe
        "": "Día Libre / No Definido"
    }
}

# Cargar variables de entorno del archivo .env
load_dotenv()

# --- Configuración ---
# Usamos una variable de entorno para la ruta del archivo Excel
# Esto es útil para cuando despliegues la aplicación,
# ya que la ruta podría cambiar.
EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "turnoRaiz.xlsx") # Reemplaza "Turnos.xlsx" con el nombre real de tu archivo

# Inicializa la aplicación FastAPI
app = FastAPI(
    title="API de Turnos",
    description="Una API para gestionar y consultar turnos de trabajo desde un archivo Excel.",
    version="1.0.0"
)

# --- Configuración CORS ---
# Esto es CRÍTICO para que tu aplicación React Native (que se ejecuta en un "origen" diferente)
# pueda hacer solicitudes a tu backend.
# En desarrollo, permitimos todos los orígenes. En producción, deberías restringirlo
# a la URL de tu aplicación React Native.
origins = [
    "http://localhost",
    "http://localhost:8080", # Puerto común para desarrollo web
    "http://localhost:19000", # Puerto de Expo Go (si usas 'npm start' con Expo)
    "http://localhost:19001", # Otro puerto que a veces usa Expo Go
    "exp://192.168.1.XX:19000", # Ejemplo de URL de Expo Go en tu red local (reemplazar XX con tu IP)
    "exp://172.20.10.XX:19000", # Otro ejemplo de URL de Expo Go
    "http://192.168.1.XX:8000", # Si accedes a tu backend desde tu móvil directamente con la IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Por ahora, permitimos todos los orígenes para desarrollo. ¡Cambiar en producción!
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)


# Función auxiliar para determinar el tipo de día
def get_tipo_dia(fecha: date):
    # Asumiendo que los festivos no están en tu lógica actual.
    # Si tienes una lista de festivos, la integrarías aquí.
    if fecha.weekday() == 5: # Sábado es 5
        return "Sábado"
    elif fecha.weekday() == 6: # Domingo es 6
        # Aquí necesitarías una lógica para verificar si es festivo también.
        # Por ahora, solo distinguimos entre L-V, S, D.
        return "Domingos y Festivos"
    else: # Lunes a Viernes (0 a 4)
        return "Lunes a Viernes"

# --- Funciones de Lógica (Adaptadas de tu script original) ---

def cargar_turnos_desde_excel(archivo_path: str) -> dict:
    """
    Carga los turnos desde un archivo Excel y los retorna como un diccionario.
    Clave: 'YYYY-MM-DD', Valor: Tipo de turno.
    """
    try:
        df = pd.read_excel(archivo_path)
    except FileNotFoundError:
        print(f"Error: Archivo no encontrado en la ruta: {archivo_path}")
        raise HTTPException(status_code=404, detail="Archivo Excel de turnos no encontrado.")
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo Excel: {e}")

    df = df.dropna(subset=["AÑO", "FECHA", "J. VIDAL"]).copy()

    def extraer_fecha(row):
        try:
            dia_mes = str(row["FECHA"]).split(',')[0].strip() # Asegurarse de que FECHA sea string
            # Manejar formatos como '1/1' o '01/01'
            if '/' in dia_mes:
                partes_fecha = dia_mes.split('/')
                dia = int(partes_fecha[0])
                mes = int(partes_fecha[1])
            else:
                # Si no hay '/', intentar asumir que es solo el día si es numérico
                # Esto es una suposición, si tus fechas tienen otro formato, ajusta aquí.
                dia = int(dia_mes)
                # El mes lo tomaremos del año si no está presente, esto puede ser problemático.
                # Es mejor que tu columna "FECHA" tenga siempre un formato consistente (ej. "dia/mes")
                mes = int(row["MES_NUMERO"]) if "MES_NUMERO" in df.columns else datetime.now().month # Fallback, idealmente tu Excel tiene columna de mes si no está en 'FECHA'
                print(f"Advertencia: Formato de fecha inusual '{dia_mes}'. Asumiendo día {dia} y mes {mes}.")
                
            año = int(row["AÑO"])
            return datetime(año, mes, dia)
        except ValueError as ve:
            print(f"Error de formato de fecha en la fila: {row['FECHA']} - {ve}")
            return None
        except Exception as e:
            print(f"Error inesperado extrayendo fecha: {row['FECHA']} - {e}")
            return None

    df["Fecha"] = df.apply(extraer_fecha, axis=1)

    # Filtrar las filas donde la fecha no pudo ser extraída
    df_validos = df.dropna(subset=["Fecha"])

    return {
        row["Fecha"].strftime('%Y-%m-%d'): row["J. VIDAL"]
        for _, row in df_validos.iterrows()
    }

# --- Rutas de la API ---

@app.get("/")
async def read_root():
    """Endpoint de prueba para verificar que la API está funcionando."""
    return {"message": "API de Turnos funcionando. Visita /docs para la documentación."}

@app.get("/turnos")
async def get_all_turnos():
    try:
        df_turnos = cargar_turnos_desde_excel(EXCEL_FILE_PATH)
        
        turnos_data = {}
        for index, row in df_turnos.iterrows():
            fecha_str = row["FECHA"]
            tipo_turno = row["J. VIDAL"] # Asumiendo que esta es la columna del turno

            # Obtener el tipo de día (L-V, S, D/F) para la fecha
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            tipo_dia = get_tipo_dia(fecha_obj)

            # Obtener el horario basado en el tipo de día y el tipo de turno
            horario = HORARIOS_POR_TURNO.get(tipo_dia, {}).get(tipo_turno, "Horario no disponible")

            # Guardar tanto el tipo de turno como el horario
            # Podemos devolver un objeto para cada fecha
            turnos_data[fecha_str] = {
                "tipo_turno": tipo_turno,
                "horario": horario
            }
        return turnos_data
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Archivo Excel de turnos no encontrado: {e}")
    except Exception as e:
        # Puedes loguear el error 'e' para depuración
        raise HTTPException(status_code=500, detail=f"Error al cargar turnos: {e}")

# --- Endpoint de prueba para notificaciones (futuro) ---
# Este endpoint no envía notificaciones reales aún, solo simula un registro.
# La lógica real de envío de notificaciones Firebase se añadiría aquí o en un servicio aparte.

@app.post("/register_device")
async def register_device(device_token: str):
    """
    Endpoint para que la aplicación móvil registre su token de dispositivo para notificaciones.
    En un entorno real, guardarías este token en una base de datos asociada a un usuario.
    """
    print(f"Dispositivo registrado con token: {device_token}")
    # Aquí iría la lógica para guardar el device_token en una base de datos
    # Por ahora, solo lo imprimimos.
    return {"message": "Token de dispositivo registrado exitosamente."}


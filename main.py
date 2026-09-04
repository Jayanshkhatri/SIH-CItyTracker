from fastapi import FastAPI, Header, HTTPException, Depends
from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()
app = FastAPI()

API_KEY = os.getenv("API_SECRET_KEY")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

@app.get("/")
def home():
    return {"message": "ANPR API is running"}

@app.get("/search")
def search_plate(plate: str, auth: None = Depends(verify_api_key)):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT id, plate_number, camera_id, event_time, confidence FROM plate_events WHERE plate_number = %s ORDER BY event_time DESC;",
        (plate,)
    )
    rows = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not rows:
        return {"plate": plate, "status": "not found", "events": []}
    
    events = [
        {
            "id": row[0],
            "plate_number": row[1],
            "camera_id": row[2],
            "event_time": str(row[3]),
            "confidence": row[4]
        }
        for row in rows
    ]
    
    return {"plate": plate, "status": "found", "events": events} 
@app.get("/trajectory")
def get_trajectory(plate: str, auth: None = Depends(verify_api_key)):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT pe.plate_number, pe.event_time, pe.confidence,
               c.name, ST_Y(c.location::geometry) as lat, ST_X(c.location::geometry) as lng
        FROM plate_events pe
        JOIN cameras c ON pe.camera_id = c.id
        WHERE pe.plate_number = %s
        ORDER BY pe.event_time ASC;
    """, (plate,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        return {"plate": plate, "status": "not found", "trajectory": []}
    
    trajectory = [
        {
            "plate_number": row[0],
            "event_time": str(row[1]),
            "confidence": row[2],
            "camera_name": row[3],
            "latitude": row[4],
            "longitude": row[5]
        }
        for row in rows
    ]
    
    return {"plate": plate, "status": "found", "trajectory": trajectory} 

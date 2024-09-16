import sqlite3
from flask import Flask, render_template, request, redirect, url_for
import subprocess as sp
import requests

app = Flask(__name__)

# Function to get database connection
def get_db():
    conn = sqlite3.connect('servers.db')
    conn.row_factory = sqlite3.Row  # This allows us to access columns by name
    return conn

def update_database_schema():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys=off;")
    
    # Check if the schema needs to be updated
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='servers';")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE servers (
                id INTEGER PRIMARY KEY,
                ip_address TEXT,
                server_name TEXT,
                latitude REAL,
                longitude REAL
            )
        """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servers_new (
            id INTEGER PRIMARY KEY,
            ip_address TEXT,
            server_name TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    cursor.execute("""
        INSERT INTO servers_new (id, ip_address, server_name)
        SELECT id, ip_address, server_name
        FROM servers
    """)
    cursor.execute("DROP TABLE IF EXISTS servers;")
    cursor.execute("ALTER TABLE servers_new RENAME TO servers;")
    
    cursor.execute("PRAGMA foreign_keys=on;")
    conn.commit()
    conn.close()

# Function to check if IP is up or down
def ipcheck(ip):
    try:
        status, _ = sp.getstatusoutput(f"ping -c1 -w2 {ip}")
        return status == 0
    except Exception as e:
        print(f"Error checking IP {ip}: {e}")
        return False

# Function to get latitude and longitude for an IP using ipinfo.io
def get_lat_long(ip):
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json")
        response.raise_for_status()
        data = response.json()
        loc = data.get('loc')
        if loc:
            lat, lon = loc.split(',')
            return float(lat), float(lon)
        return None, None
    except requests.RequestException as e:
        print(f"Error fetching lat/long for {ip}: {e}")
        return None, None

@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()
    cursor = db.cursor()
    
    # Fetch all servers from the database
    cursor.execute("SELECT * FROM servers")
    servers = cursor.fetchall()
    
    servers_with_status = []
    for server in servers:
        server_id = server['id']
        ip = server['ip_address']
        server_name = server['server_name']
        latitude = server['latitude']
        longitude = server['longitude']

        is_up = ipcheck(ip)
        status = "Up" if is_up else "Down"
        
        # If latitude and longitude are not present, fetch them
        if latitude is None or longitude is None:
            lat, lon = get_lat_long(ip)
            
            # Update the database with fetched latitude and longitude
            cursor.execute(
                "UPDATE servers SET latitude = ?, longitude = ? WHERE id = ?",
                (lat, lon, server_id)
            )
            db.commit()
            latitude, longitude = lat, lon
        
        servers_with_status.append((server_id, ip, server_name, status, latitude, longitude))

    return render_template("index.html", servers=servers_with_status)

@app.route("/add", methods=["GET", "POST"])
def add_server():
    if request.method == "POST":
        ip_address = request.form["ip_address"]
        server_name = request.form["server_name"]
        db = get_db()
        cursor = db.cursor()
        
        # Check if IP address already exists
        cursor.execute("SELECT * FROM servers WHERE ip_address = ?", (ip_address,))
        existing_server = cursor.fetchone()
        
        if not existing_server:
            # Get latitude and longitude if not present
            lat, lon = get_lat_long(ip_address)
            cursor.execute(
                "INSERT INTO servers (ip_address, server_name, latitude, longitude) VALUES (?, ?, ?, ?)",
                (ip_address, server_name, lat, lon)
            )
            db.commit()
        
        return redirect(url_for("index"))
    return render_template("add_server.html")

@app.route("/update/<int:id>", methods=["POST"])
def update_server(id):
    db = get_db()
    cursor = db.cursor()
    
    if request.method == "POST":
        ip_address = request.form.get("ip_address")
        server_name = request.form.get("server_name")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        if ip_address and server_name:  # Check if required fields are not empty
            cursor.execute(
                "UPDATE servers SET ip_address = ?, server_name = ?, latitude = ?, longitude = ? WHERE id = ?",
                (ip_address, server_name, latitude, longitude, id)
            )
            db.commit()
        return redirect(url_for("index"))

@app.route("/delete/<int:id>")
def delete_server(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM servers WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    update_database_schema()
    app.run(debug=True)

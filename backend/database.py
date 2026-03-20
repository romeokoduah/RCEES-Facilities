"""RCEES Facilities - Database Layer"""
import sqlite3, uuid, hashlib, json
from .config import DB_PATH, ADMIN_EMAIL, ADMIN_PASSWORD

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, role TEXT DEFAULT 'user',
    phone TEXT DEFAULT '', department TEXT DEFAULT '', organization TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')), last_login TEXT);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, icon TEXT DEFAULT '🏢',
    description TEXT DEFAULT '', color TEXT DEFAULT '#1a4731', sort_order INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS facilities (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    category_id TEXT REFERENCES categories(id), capacity INTEGER NOT NULL DEFAULT 10,
    description TEXT DEFAULT '', short_desc TEXT DEFAULT '', amenities TEXT DEFAULT '[]',
    hourly_rate REAL DEFAULT 0, half_day_rate REAL DEFAULT 0, full_day_rate REAL DEFAULT 0,
    weekend_multiplier REAL DEFAULT 1.5,
    location TEXT DEFAULT '', building TEXT DEFAULT '', floor TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1, requires_approval INTEGER DEFAULT 0,
    min_hours INTEGER DEFAULT 1, max_hours INTEGER DEFAULT 14,
    rules TEXT DEFAULT '', contact_person TEXT DEFAULT '', contact_phone TEXT DEFAULT '',
    media TEXT DEFAULT '[]', op_hours TEXT DEFAULT '{"start":7,"end":21}',
    blocked_days TEXT DEFAULT '[]', total_bookings INTEGER DEFAULT 0, avg_rating REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, ref TEXT UNIQUE NOT NULL,
    facility_id TEXT NOT NULL REFERENCES facilities(id), user_id TEXT,
    guest_name TEXT, guest_email TEXT, guest_phone TEXT, guest_org TEXT,
    title TEXT NOT NULL, description TEXT DEFAULT '', event_type TEXT DEFAULT 'general',
    booking_date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
    attendees INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    pay_status TEXT DEFAULT 'unpaid', pay_method TEXT DEFAULT '', pay_ref TEXT DEFAULT '',
    total REAL DEFAULT 0, discount_amt REAL DEFAULT 0, discount_code TEXT DEFAULT '',
    tax_amount REAL DEFAULT 0, final_amount REAL DEFAULT 0,
    special_req TEXT DEFAULT '', equipment TEXT DEFAULT '[]',
    layout TEXT DEFAULT 'default', catering INTEGER DEFAULT 0,
    is_walkin INTEGER DEFAULT 0, walkin_by TEXT DEFAULT '',
    approved_by TEXT DEFAULT '', approved_at TEXT,
    rejected_reason TEXT DEFAULT '',
    cancelled_at TEXT, cancelled_reason TEXT DEFAULT '',
    payment_token TEXT DEFAULT '',
    rating INTEGER, feedback TEXT DEFAULT '', notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY, invoice_no TEXT UNIQUE NOT NULL,
    booking_id TEXT NOT NULL REFERENCES bookings(id),
    invoice_type TEXT DEFAULT 'invoice',
    issued_to_name TEXT NOT NULL, issued_to_email TEXT DEFAULT '',
    issued_to_phone TEXT DEFAULT '', issued_to_org TEXT DEFAULT '',
    subtotal REAL DEFAULT 0, discount REAL DEFAULT 0, tax REAL DEFAULT 0,
    total REAL DEFAULT 0, currency TEXT DEFAULT 'GHS',
    line_items TEXT DEFAULT '[]',
    notes TEXT DEFAULT '', terms TEXT DEFAULT '',
    status TEXT DEFAULT 'issued',
    issued_at TEXT DEFAULT (datetime('now')), paid_at TEXT,
    created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS email_log (
    id TEXT PRIMARY KEY, to_email TEXT NOT NULL, subject TEXT NOT NULL,
    body_preview TEXT DEFAULT '', status TEXT DEFAULT 'sent',
    related_booking TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS maintenance (
    id TEXT PRIMARY KEY, facility_id TEXT NOT NULL REFERENCES facilities(id),
    title TEXT NOT NULL, description TEXT DEFAULT '',
    mtype TEXT DEFAULT 'routine', priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'scheduled',
    start_date TEXT NOT NULL, end_date TEXT NOT NULL,
    start_time TEXT DEFAULT '00:00', end_time TEXT DEFAULT '23:59',
    assigned_to TEXT DEFAULT '', vendor TEXT DEFAULT '',
    cost_est REAL DEFAULT 0, actual_cost REAL DEFAULT 0,
    blocks_bookings INTEGER DEFAULT 1, notes TEXT DEFAULT '',
    completed_at TEXT, created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS discounts (
    id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    description TEXT DEFAULT '', dtype TEXT DEFAULT 'percentage',
    value REAL NOT NULL, min_hours INTEGER DEFAULT 0, max_discount REAL DEFAULT 0,
    max_uses INTEGER DEFAULT 0, times_used INTEGER DEFAULT 0,
    valid_from TEXT, valid_until TEXT, is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS equipment (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT DEFAULT 'general',
    qty INTEGER DEFAULT 1, hourly_rate REAL DEFAULT 0, daily_rate REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY, booking_id TEXT UNIQUE, facility_id TEXT NOT NULL,
    user_id TEXT, guest_name TEXT, rating INTEGER NOT NULL,
    comment TEXT DEFAULT '', is_visible INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')));

CREATE INDEX IF NOT EXISTS ix_bk_date ON bookings(booking_date);
CREATE INDEX IF NOT EXISTS ix_bk_fac ON bookings(facility_id);
CREATE INDEX IF NOT EXISTS ix_bk_status ON bookings(status);
CREATE INDEX IF NOT EXISTS ix_bk_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS ix_bk_ref ON bookings(ref);
CREATE INDEX IF NOT EXISTS ix_bk_token ON bookings(payment_token);
CREATE INDEX IF NOT EXISTS ix_inv_bk ON invoices(booking_id);
CREATE INDEX IF NOT EXISTS ix_mt_fac ON maintenance(facility_id);

CREATE TABLE IF NOT EXISTS availability_rules (
    id TEXT PRIMARY KEY,
    facility_id TEXT REFERENCES facilities(id),
    rule_type TEXT NOT NULL,
    date TEXT,
    day_of_week INTEGER,
    start_time TEXT DEFAULT '00:00',
    end_time TEXT DEFAULT '23:59',
    is_available INTEGER DEFAULT 0,
    reason TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_avail_fac ON availability_rules(facility_id);
CREATE INDEX IF NOT EXISTS ix_avail_date ON availability_rules(date);

CREATE TABLE IF NOT EXISTS activity_log (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    details TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CATEGORIES = [
    ("cat-meet","Meeting Space","\U0001f4bc","#1e40af",1),
    ("cat-event","Event Space","\U0001f3db\ufe0f","#7c2d12",2),
    ("cat-creative","Creative Space","\U0001f3ac","#6b21a8",3),
    ("cat-lab","Laboratory","\U0001f52c","#065f46",4),
    ("cat-dining","Dining & Social","\u2615","#b45309",5),
    ("cat-outdoor","Outdoor Space","\U0001f333","#3f6212",6),
    ("cat-seminar","Seminar Room","\U0001f393","#0e7490",7),
    ("cat-lecture","Lecture Hall","\U0001f4da","#be123c",8),
]

FACILITIES = [
    {"name":"Executive Conference Room","slug":"exec-conf-room","cat":"cat-meet","cap":25,"desc":"Premium conference room with 4K AV, soundproofing, and executive furnishings.","short":"25-seat premium conference","am":["4K Projector","Surround Sound","Video Conferencing","Smart Whiteboard","AC","Wi-Fi 6"],"hr":80,"hd":280,"fd":480,"loc":"Admin Building, 2nd Floor, Rm 201","bld":"Admin Block","fl":"2","ap":0},
    {"name":"RCEES Auditorium","slug":"rcees-auditorium","cat":"cat-event","cap":350,"desc":"Flagship 350-seat auditorium with professional stage, lighting, surround sound, and green room.","short":"350-seat flagship auditorium","am":["Full Stage","Pro Lighting","Surround Sound","Wireless Mics","Green Room","Dual 4K Projectors"],"hr":300,"hd":1050,"fd":1800,"loc":"Block A, Ground Floor","bld":"Block A","fl":"G","ap":1},
    {"name":"Multimedia Studio","slug":"multimedia-studio","cat":"cat-creative","cap":15,"desc":"Professional studio with green screen, LED lighting, sound isolation, and editing workstations.","short":"Professional recording studio","am":["Green Screen","3-Point LED","Sound Booth","Camera Kit","Teleprompter","iMac Editing"],"hr":120,"hd":420,"fd":720,"loc":"Media Block, 1st Floor, Rm 103","bld":"Media Block","fl":"1","ap":1},
    {"name":"Renewable Energy Lab","slug":"renewable-energy-lab","cat":"cat-lab","cap":30,"desc":"Advanced lab for solar PV, wind energy, battery storage, and power electronics research.","short":"Solar, wind & battery lab","am":["Solar Test Bench","Wind Tunnel","Battery Analyzers","Oscilloscopes","Data Acquisition","Fume Hood"],"hr":150,"hd":520,"fd":900,"loc":"Science Block, Ground, Lab 001","bld":"Science Block","fl":"G","ap":1},
    {"name":"Environmental Monitoring Lab","slug":"env-monitoring-lab","cat":"cat-lab","cap":25,"desc":"Specialized for air quality, water analysis, soil testing, and GIS analysis.","short":"Air, water & soil analysis","am":["Air Quality Monitors","Water Analyzers","Spectrophotometer","GIS Workstations","Microscopes"],"hr":140,"hd":490,"fd":850,"loc":"Science Block, Ground, Lab 002","bld":"Science Block","fl":"G","ap":1},
    {"name":"Bioenergy Research Lab","slug":"bioenergy-lab","cat":"cat-lab","cap":25,"desc":"Biomass characterization, biogas production, and biofuel analysis.","short":"Biomass & biogas research","am":["Bomb Calorimeter","Fermentation Units","Biomass Grinder","FTIR Spectrometer","Oven & Furnace"],"hr":140,"hd":490,"fd":850,"loc":"Science Block, 1st Floor, Lab 101","bld":"Science Block","fl":"1","ap":1},
    {"name":"Energy Systems Lab","slug":"energy-systems-lab","cat":"cat-lab","cap":25,"desc":"Energy system modeling, smart grid prototyping, and real-time simulation.","short":"Smart grid & power systems","am":["OPAL-RT Simulator","Power Electronics","Smart Meters","PLC Trainers","Network Analyzer"],"hr":160,"hd":560,"fd":960,"loc":"Science Block, 1st Floor, Lab 102","bld":"Science Block","fl":"1","ap":1},
    {"name":"RCEES Cafeteria","slug":"rcees-cafeteria","cat":"cat-dining","cap":120,"desc":"Spacious cafeteria convertible for banquets, networking, and exhibitions.","short":"120-seat dining & events","am":["Commercial Kitchen","Sound System","Projector","Serving Area","Portable Stage"],"hr":200,"hd":700,"fd":1200,"loc":"Central Block, Ground","bld":"Central Block","fl":"G","ap":0},
    {"name":"Outdoor Grounds","slug":"outdoor-grounds","cat":"cat-outdoor","cap":300,"desc":"Expansive open-air grounds for ceremonies and large gatherings.","short":"300-capacity open-air venue","am":["Power Points","Water Connection","Tent Setup","Flood Lights","Parking (100+)"],"hr":180,"hd":630,"fd":1080,"loc":"RCEES Grounds, South Wing","bld":"Outdoor","fl":"G","ap":0},
    {"name":"Inner Courtyard","slug":"inner-courtyard","cat":"cat-outdoor","cap":100,"desc":"Landscaped courtyard with garden views, natural light, and water feature.","short":"Elegant 100-seat courtyard","am":["Natural Light","Covered Walkway","Garden View","Power Outlets","Water Feature"],"hr":150,"hd":520,"fd":900,"loc":"Central Building, Inner Wing","bld":"Central Block","fl":"G","ap":0},
    {"name":"Video Conference Suite","slug":"video-conf-suite","cat":"cat-meet","cap":12,"desc":"Dedicated VC suite with 85-inch display and Zoom Rooms hardware.","short":"12-seat premium VC room","am":["85in 4K Display","Multi-Camera","Directional Mics","Soundproofing","Zoom Rooms"],"hr":100,"hd":350,"fd":600,"loc":"Admin Block, 2nd Floor, Rm 205","bld":"Admin Block","fl":"2","ap":0},
    {"name":"Seminar Room A","slug":"seminar-room-a","cat":"cat-seminar","cap":50,"desc":"Flexible seminar room with movable furniture.","short":"50-seat flexible seminar","am":["Projector","Smart Whiteboard","AC","Wi-Fi","Movable Furniture","Podium"],"hr":70,"hd":245,"fd":420,"loc":"Block B, 1st Floor, B101","bld":"Block B","fl":"1","ap":0},
    {"name":"Seminar Room B","slug":"seminar-room-b","cat":"cat-seminar","cap":50,"desc":"Modern seminar room for workshops and interactive sessions.","short":"50-seat workshop room","am":["Projector","Whiteboard","AC","Wi-Fi","Breakout Zone","Charging Points"],"hr":70,"hd":245,"fd":420,"loc":"Block B, 1st Floor, B102","bld":"Block B","fl":"1","ap":0},
    {"name":"Seminar Room C","slug":"seminar-room-c","cat":"cat-seminar","cap":40,"desc":"Compact room for thesis defenses and small workshops.","short":"40-seat compact seminar","am":["Projector","Whiteboard","AC","Wi-Fi","Round-Table Option"],"hr":60,"hd":210,"fd":360,"loc":"Block B, 2nd Floor, B201","bld":"Block B","fl":"2","ap":0},
    {"name":"Lecture Hall 1","slug":"lecture-hall-1","cat":"cat-lecture","cap":80,"desc":"Tiered lecture hall with dual projection and lecture capture.","short":"80-seat tiered hall","am":["Tiered Seating","Dual Projectors","Lecture Capture","Microphones","AC"],"hr":90,"hd":315,"fd":540,"loc":"Academic Block, Ground, LH-001","bld":"Academic Block","fl":"G","ap":0},
    {"name":"Lecture Hall 2","slug":"lecture-hall-2","cat":"cat-lecture","cap":80,"desc":"Well-equipped hall with excellent acoustics.","short":"80-seat hall","am":["Tiered Seating","Projector","Microphone","AC","Whiteboard"],"hr":90,"hd":315,"fd":540,"loc":"Academic Block, Ground, LH-002","bld":"Academic Block","fl":"G","ap":0},
    {"name":"Lecture Hall 3 (Grand)","slug":"lecture-hall-3-grand","cat":"cat-lecture","cap":120,"desc":"Largest lecture hall with smart board and surround audio.","short":"120-seat grand theatre","am":["120 Tiered Seats","Smart Board","Dual Projectors","Surround Sound","Priority AC"],"hr":120,"hd":420,"fd":720,"loc":"Academic Block, 1st Floor, LH-101","bld":"Academic Block","fl":"1","ap":0},
    {"name":"Lecture Room 4 (Flexible)","slug":"lecture-room-4-flex","cat":"cat-lecture","cap":80,"desc":"Flat-floor room with movable tables for multiple configurations.","short":"80-seat flexible room","am":["Flat Floor","Movable Tables","Interactive Display","Projector","AC"],"hr":90,"hd":315,"fd":540,"loc":"Academic Block, 1st Floor, LR-102","bld":"Academic Block","fl":"1","ap":0},
]

EQUIPMENT = [
    ("Portable Projector","AV",5,20,80),("Wireless Mic Set","Audio",8,15,60),
    ("Portable PA System","Audio",4,30,120),("Mobile Whiteboard","Presentation",6,5,20),
    ("Laptop + Presenter","Computing",10,10,40),("Extension Cable 20m","Power",15,3,12),
    ("LED Light Kit","Production",3,40,160),("4K Webcam + Tripod","Recording",5,12,48),
    ("Portable Screen 100in","Presentation",4,15,60),("Flip Chart + Pads","Stationery",10,5,20),
]

DISCOUNTS = [
    ("RCEES10","RCEES Staff 10%","percentage",10,1,0,0),
    ("UENR15","UENR Community 15%","percentage",15,2,0,0),
    ("EARLYBIRD20","Early Bird 20%","percentage",20,1,0,0),
    ("FULLDAY25","Full Day 25%","percentage",25,6,0,0),
    ("WELCOME50","Welcome GH\u20b550","fixed",50,1,50,1),
    ("RESEARCH30","Research Grant 30%","percentage",30,2,0,0),
    ("WEEKEND15","Weekend 15%","percentage",15,0,0,0),
]

def init_db():
    conn = get_db(); c = conn.cursor()
    c.executescript(SCHEMA)
    try: c.execute("INSERT INTO users (id,email,name,password_hash,role,department,organization) VALUES (?,?,?,?,'admin','RCEES Administration','UENR')", (str(uuid.uuid4()), ADMIN_EMAIL, "RCEES Administrator", hash_pw(ADMIN_PASSWORD)))
    except: pass
    for cat in CATEGORIES:
        try: c.execute("INSERT INTO categories (id,name,icon,color,sort_order) VALUES (?,?,?,?,?)", cat)
        except: pass
    for f in FACILITIES:
        fid = str(uuid.uuid4())
        try: c.execute("INSERT INTO facilities (id,name,slug,category_id,capacity,description,short_desc,amenities,hourly_rate,half_day_rate,full_day_rate,location,building,floor,requires_approval) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(fid,f["name"],f["slug"],f["cat"],f["cap"],f["desc"],f["short"],json.dumps(f["am"]),f["hr"],f["hd"],f["fd"],f["loc"],f["bld"],f["fl"],f["ap"]))
        except: pass
    for eq in EQUIPMENT:
        try: c.execute("INSERT INTO equipment (id,name,category,qty,hourly_rate,daily_rate) VALUES (?,?,?,?,?,?)",(str(uuid.uuid4()),*eq))
        except: pass
    for d in DISCOUNTS:
        try: c.execute("INSERT INTO discounts (id,code,name,dtype,value,min_hours,max_discount,max_uses,is_active) VALUES (?,?,?,?,?,?,?,?,1)",(str(uuid.uuid4()),*d))
        except: pass
    # Migrate existing tables
    for col in [("is_walkin","INTEGER DEFAULT 0"),("walkin_by","TEXT DEFAULT ''"),("approved_by","TEXT DEFAULT ''"),("approved_at","TEXT"),("rejected_reason","TEXT DEFAULT ''"),("cancelled_at","TEXT"),("cancelled_reason","TEXT DEFAULT ''"),("payment_token","TEXT DEFAULT ''"),("tax_amount","REAL DEFAULT 0")]:
        try: c.execute(f"ALTER TABLE bookings ADD COLUMN {col[0]} {col[1]}")
        except: pass
    conn.commit(); conn.close()
    print("  \u2705 Database ready (18 facilities, invoices table, email log)")

"""
HealthAI - Intelligent Healthcare Assistant
Flask backend: authentication, chatbot, health tools, emergency info.
"""

import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, g, send_file, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "healthai-dev-secret-key-change-in-production"
DB_PATH = "database.db"
UPLOAD_FOLDER = os.path.join("static", "uploads", "profile_photos")
ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            profile_photo TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            time_label TEXT,
            is_done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Safe migration for databases created before these columns existed
    existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(users)")}
    if "is_admin" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if "profile_photo" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT")

    # Seed a demo admin account for the admin panel (only if it doesn't exist yet)
    admin = cur.execute("SELECT id FROM users WHERE email = ?", ("admin@healthai.com",)).fetchone()
    if admin is None:
        cur.execute(
            """INSERT INTO users (full_name, email, mobile, age, gender, password_hash, created_at, is_admin)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            ("System Admin", "admin@healthai.com", "9999999999", 30, "Other",
             generate_password_hash("admin123"), datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            flash("Access denied. Admin privileges are required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def add_no_cache_headers(response):
    # Prevent browser-back access to protected pages after logout
    if "user_id" not in session:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_RE = re.compile(r"^[0-9]{10}$")


# ---------------------------------------------------------------------------
# Static data: health tips, quotes, diseases, emergency, hospitals
# ---------------------------------------------------------------------------

HEALTH_TIPS = [
    "Drink at least 8 glasses of water every day to stay hydrated.",
    "Aim for 7-8 hours of quality sleep each night.",
    "Include fresh fruits and vegetables in every meal.",
    "Take a 10-minute walk after meals to aid digestion.",
    "Wash your hands regularly to prevent infections.",
    "Practice deep breathing for 5 minutes to reduce stress.",
    "Limit screen time before bed for better sleep quality.",
    "Get regular health check-ups even when you feel fine.",
]

HEALTH_QUOTES = [
    "Health is not valued until sickness comes. — Thomas Fuller",
    "Take care of your body. It's the only place you have to live. — Jim Rohn",
    "A healthy outside starts from the inside. — Robert Urich",
    "The greatest wealth is health. — Virgil",
    "Prevention is better than cure.",
]

DISEASES = [
    {
        "name": "Fever",
        "symptoms": ["High body temperature", "Chills", "Sweating", "Headache", "Weakness"],
        "causes": ["Viral or bacterial infection", "Inflammation", "Heat exhaustion"],
        "prevention": ["Stay hydrated", "Rest adequately", "Maintain good hygiene"],
        "medicines": ["Paracetamol (for awareness only)"],
        "food": ["Warm soups", "Coconut water", "Light, easily digestible meals"],
        "consult": "See a doctor if fever exceeds 103°F or lasts more than 3 days.",
        "icon": "thermometer",
    },
    {
        "name": "Cold",
        "symptoms": ["Runny nose", "Sneezing", "Sore throat", "Mild cough"],
        "causes": ["Viral infection (rhinovirus)", "Weather change", "Weak immunity"],
        "prevention": ["Wash hands often", "Avoid close contact with infected people", "Keep warm"],
        "medicines": ["Antihistamines (for awareness only)"],
        "food": ["Warm fluids", "Citrus fruits", "Ginger tea"],
        "consult": "See a doctor if symptoms persist beyond 10 days.",
        "icon": "cloud-drizzle",
    },
    {
        "name": "Cough",
        "symptoms": ["Persistent throat irritation", "Chest discomfort", "Phlegm"],
        "causes": ["Infection", "Allergies", "Irritants like smoke or dust"],
        "prevention": ["Avoid smoking and pollutants", "Stay hydrated", "Cover mouth when coughing"],
        "medicines": ["Cough syrups (for awareness only)"],
        "food": ["Honey with warm water", "Herbal tea", "Steamed vegetables"],
        "consult": "See a doctor if cough lasts more than 2-3 weeks or has blood.",
        "icon": "wind",
    },
    {
        "name": "Diabetes",
        "symptoms": ["Frequent urination", "Excess thirst", "Fatigue", "Blurred vision"],
        "causes": ["Insulin resistance", "Genetics", "Poor lifestyle habits"],
        "prevention": ["Regular exercise", "Balanced diet", "Routine blood sugar monitoring"],
        "medicines": ["Metformin and other prescribed medication (for awareness only)"],
        "food": ["Whole grains", "Leafy greens", "Low-sugar fruits"],
        "consult": "Regular consultation with an endocrinologist is recommended.",
        "icon": "activity",
    },
    {
        "name": "Hypertension",
        "symptoms": ["Headache", "Dizziness", "Shortness of breath", "Often no symptoms"],
        "causes": ["High salt intake", "Stress", "Obesity", "Genetics"],
        "prevention": ["Reduce salt intake", "Exercise regularly", "Manage stress", "Limit alcohol"],
        "medicines": ["Antihypertensives (for awareness only)"],
        "food": ["Low-sodium diet", "Bananas", "Leafy vegetables"],
        "consult": "Regular blood pressure monitoring with a doctor is advised.",
        "icon": "heart-pulse",
    },
    {
        "name": "Dengue",
        "symptoms": ["High fever", "Severe joint/muscle pain", "Rash", "Low platelet count"],
        "causes": ["Aedes mosquito bite (viral infection)"],
        "prevention": ["Eliminate standing water", "Use mosquito repellents", "Wear full sleeves"],
        "medicines": ["Paracetamol only, avoid aspirin/ibuprofen (for awareness only)"],
        "food": ["Papaya leaf juice", "Fluids", "Light home-cooked meals"],
        "consult": "Seek immediate medical attention for platelet monitoring.",
        "icon": "bug",
    },
    {
        "name": "Malaria",
        "symptoms": ["Cyclic fever with chills", "Sweating", "Headache", "Nausea"],
        "causes": ["Anopheles mosquito bite (Plasmodium parasite)"],
        "prevention": ["Use mosquito nets", "Avoid stagnant water", "Use repellents"],
        "medicines": ["Antimalarial drugs as prescribed (for awareness only)"],
        "food": ["Fluids", "Light, nutritious meals", "Fruits rich in Vitamin C"],
        "consult": "Immediate medical diagnosis and treatment is essential.",
        "icon": "bug",
    },
    {
        "name": "Asthma",
        "symptoms": ["Wheezing", "Shortness of breath", "Chest tightness", "Coughing"],
        "causes": ["Allergens", "Air pollution", "Genetics", "Respiratory infections"],
        "prevention": ["Avoid known triggers", "Keep inhaler accessible", "Maintain clean air at home"],
        "medicines": ["Bronchodilator inhalers (for awareness only)"],
        "food": ["Anti-inflammatory foods", "Omega-3 rich foods", "Warm fluids"],
        "consult": "Regular pulmonologist visits are recommended.",
        "icon": "wind",
    },
    {
        "name": "Migraine",
        "symptoms": ["Severe throbbing headache", "Sensitivity to light/sound", "Nausea"],
        "causes": ["Stress", "Hormonal changes", "Certain foods", "Lack of sleep"],
        "prevention": ["Maintain regular sleep schedule", "Avoid triggers", "Manage stress"],
        "medicines": ["Pain relievers as prescribed (for awareness only)"],
        "food": ["Magnesium-rich foods", "Stay hydrated", "Avoid caffeine excess"],
        "consult": "See a neurologist for frequent or severe migraines.",
        "icon": "brain",
    },
    {
        "name": "COVID-19",
        "symptoms": ["Fever", "Dry cough", "Loss of taste/smell", "Fatigue"],
        "causes": ["SARS-CoV-2 viral infection"],
        "prevention": ["Vaccination", "Wear masks in crowded areas", "Maintain hygiene"],
        "medicines": ["Symptomatic treatment as prescribed (for awareness only)"],
        "food": ["Warm fluids", "Vitamin C rich foods", "Nutritious home-cooked meals"],
        "consult": "Isolate and consult a doctor promptly if symptoms appear.",
        "icon": "shield-alert",
    },
    {
        "name": "Typhoid",
        "symptoms": ["Prolonged fever", "Weakness", "Stomach pain", "Loss of appetite"],
        "causes": ["Salmonella typhi bacteria via contaminated food/water"],
        "prevention": ["Drink clean water", "Eat hygienically prepared food", "Vaccination"],
        "medicines": ["Antibiotics as prescribed (for awareness only)"],
        "food": ["Soft, bland diet", "Boiled water", "Bananas and rice"],
        "consult": "Medical diagnosis via blood test and treatment is necessary.",
        "icon": "flask-conical",
    },
    {
        "name": "Food Poisoning",
        "symptoms": ["Nausea", "Vomiting", "Diarrhea", "Stomach cramps"],
        "causes": ["Contaminated food or water", "Bacterial toxins"],
        "prevention": ["Eat fresh food", "Store food properly", "Wash hands before eating"],
        "medicines": ["Oral rehydration salts (for awareness only)"],
        "food": ["Bland foods (rice, toast, banana)", "Plenty of fluids"],
        "consult": "See a doctor if symptoms persist beyond 2 days or show blood.",
        "icon": "utensils",
    },
]

EMERGENCIES = [
    {
        "name": "Heart Attack",
        "steps": [
            "Call emergency services immediately.",
            "Help the person sit down and stay calm.",
            "Loosen tight clothing.",
            "If prescribed, help them take their heart medication.",
            "Begin CPR if the person becomes unresponsive and stops breathing.",
        ],
        "precautions": ["Do not let the person exert themselves.", "Do not give food or water."],
        "icon": "heart-pulse",
    },
    {
        "name": "Burns",
        "steps": [
            "Cool the burn under running water for 10-20 minutes.",
            "Remove tight clothing/jewellery near the area.",
            "Cover loosely with a clean, non-stick cloth.",
            "Do not apply ice directly.",
        ],
        "precautions": ["Do not apply butter, oil, or toothpaste.", "Do not pop blisters."],
        "icon": "flame",
    },
    {
        "name": "Snake Bite",
        "steps": [
            "Keep the person calm and still.",
            "Keep the bitten limb below heart level.",
            "Remove tight clothing/jewellery near the bite.",
            "Get to a hospital immediately for anti-venom.",
        ],
        "precautions": ["Do not cut the wound or try to suck out venom.", "Do not apply a tight tourniquet."],
        "icon": "shield-alert",
    },
    {
        "name": "Fracture",
        "steps": [
            "Keep the injured area still and supported.",
            "Apply a splint if trained to do so.",
            "Apply ice wrapped in cloth to reduce swelling.",
            "Seek medical attention promptly.",
        ],
        "precautions": ["Do not try to realign the bone.", "Avoid unnecessary movement."],
        "icon": "bone",
    },
    {
        "name": "Bleeding",
        "steps": [
            "Apply firm, direct pressure with a clean cloth.",
            "Elevate the injured area if possible.",
            "Keep applying pressure until bleeding slows.",
            "Seek medical attention for deep or heavy bleeding.",
        ],
        "precautions": ["Do not remove an embedded object.", "Avoid repeatedly checking under the cloth."],
        "icon": "droplet",
    },
    {
        "name": "CPR",
        "steps": [
            "Check responsiveness and call for emergency help.",
            "Place hands at the center of the chest.",
            "Push hard and fast, about 100-120 compressions per minute.",
            "Continue until help arrives or the person responds.",
        ],
        "precautions": ["Only perform CPR if trained or guided by emergency services.", "Do not stop unless necessary."],
        "icon": "activity",
    },
]

NEARBY_HOSPITALS = [
    {
        "name": "City General Hospital",
        "phone": "+91 98765 43210",
        "address": "MG Road, Vellore, Tamil Nadu",
        "maps_query": "City General Hospital Vellore",
    },
    {
        "name": "CMC Hospital",
        "phone": "+91 91234 56789",
        "address": "Ida Scudder Road, Vellore, Tamil Nadu",
        "maps_query": "CMC Hospital Vellore",
    },
    {
        "name": "Apollo Speciality Hospital",
        "phone": "+91 90000 12345",
        "address": "Bagayam, Vellore, Tamil Nadu",
        "maps_query": "Apollo Speciality Hospital Vellore",
    },
]

SUGGESTED_QUESTIONS = [
    "What are common symptoms of dehydration?",
    "How can I improve my sleep quality?",
    "What foods boost immunity?",
    "How much water should I drink daily?",
    "What are signs I should see a doctor for a headache?",
]

SUGGESTED_QUESTIONS_TA = [
    "நீரிழப்பின் அறிகுறிகள் என்ன?",
    "தூக்கத்தை எப்படி மேம்படுத்துவது?",
    "நோய் எதிர்ப்பு சக்திக்கு என்ன உணவுகள் நல்லது?",
    "நாள் ஒன்றுக்கு எவ்வளவு தண்ணீர் குடிக்க வேண்டும்?",
    "தலைவலிக்கு எப்போது டாக்டரை பார்க்க வேண்டும்?",
]


# ---------------------------------------------------------------------------
# Simple rule-based health-education chatbot
# ---------------------------------------------------------------------------

def get_ai_response(message, lang="en"):
    text = message.lower()

    knowledge = [
        (["water", "hydrat"], "Staying hydrated is important for overall health. Most adults should aim for about 8 glasses (roughly 2 litres) of water a day, more if you're active or it's hot. Let your thirst and urine colour guide you too."),
        (["sleep", "insomnia", "tired"], "Good sleep hygiene helps a lot: keep a consistent sleep schedule, avoid screens before bed, keep your room cool and dark, and limit caffeine in the evening. Adults generally need 7-8 hours a night."),
        (["diet", "food", "nutrition", "eat"], "A balanced diet includes plenty of vegetables, fruits, whole grains, lean protein, and healthy fats, while limiting processed foods, added sugar, and excess salt."),
        (["exercise", "workout", "fitness"], "Aim for at least 150 minutes of moderate exercise a week, like brisk walking, along with some strength training. Always start gradually and listen to your body."),
        (["stress", "anxiety", "mental health"], "Managing stress can include deep breathing exercises, regular physical activity, adequate sleep, and talking to someone you trust. If stress feels overwhelming, consider speaking with a mental health professional."),
        (["fever"], "A fever is usually the body's response to infection. Rest, stay hydrated, and monitor your temperature. Seek medical care if it's very high, persistent, or accompanied by severe symptoms."),
        (["headache", "migraine"], "Common causes of headaches include dehydration, stress, and lack of sleep. Rest in a quiet, dark room and stay hydrated. See a doctor if headaches are severe, sudden, or frequent."),
        (["cold", "cough", "flu"], "For cold and cough symptoms, rest, fluids, and warm liquids like herbal tea can help. See a doctor if symptoms are severe or last more than 10 days."),
        (["diabetes", "sugar"], "Managing blood sugar involves a balanced diet, regular exercise, monitoring levels, and following your doctor's treatment plan closely."),
        (["blood pressure", "hypertension"], "Managing blood pressure involves reducing salt intake, regular exercise, stress management, and monitoring levels with your doctor."),
        (["hello", "hi", "hey"], "Hello! I'm here to share general health education information. What would you like to know about today?"),
        (["thank"], "You're welcome! Stay healthy, and don't hesitate to ask if you have more questions."),
    ]

    knowledge_ta = [
        (["water", "hydrat", "தண்ணீர்"], "உடல் நலத்திற்கு தண்ணீர் மிகவும் முக்கியம். பெரியவர்கள் தினமும் சுமார் 8 கிளாஸ் (2 லிட்டர்) தண்ணீர் குடிக்க வேண்டும், வெயில் காலத்தில் இன்னும் அதிகமாக குடிக்கவும்."),
        (["sleep", "insomnia", "tired", "தூக்க"], "நல்ல தூக்கத்திற்கு: தினமும் ஒரே நேரத்தில் தூங்கவும், தூங்குவதற்கு முன் மொபைல் பயன்பாட்டை தவிர்க்கவும், அறையை குளிர்ச்சியாகவும் இருட்டாகவும் வைக்கவும். பெரியவர்களுக்கு 7-8 மணி நேர தூக்கம் தேவை."),
        (["diet", "food", "nutrition", "eat", "உணவு"], "சரிவிகித உணவில் காய்கறிகள், பழங்கள், தானியங்கள், புரதம் மற்றும் நல்ல கொழுப்புகள் இருக்க வேண்டும். செயலாக்கப்பட்ட உணவு, அதிக சர்க்கரை, உப்பு ஆகியவற்றை குறைக்கவும்."),
        (["exercise", "workout", "fitness", "உடற்பயிற்சி"], "வாரத்திற்கு குறைந்தது 150 நிமிடங்கள் மிதமான உடற்பயிற்சி (வேகமாக நடப்பது போன்றவை) செய்யவும். எடையை தூக்கும் பயிற்சியும் நல்லது. மெதுவாக ஆரம்பிக்கவும்."),
        (["stress", "anxiety", "mental health", "மன அழுத்தம்"], "மன அழுத்தத்தை சமாளிக்க: ஆழ்ந்த மூச்சு பயிற்சி, தொடர்ந்த உடற்பயிற்சி, போதுமான தூக்கம் மற்றும் நம்பிக்கையான ஒருவரிடம் பேசுதல் உதவும். தேவைப்பட்டால் மனநல நிபுணரை அணுகவும்."),
        (["fever", "காய்ச்சல்"], "காய்ச்சல் என்பது தொற்றுக்கு உடலின் பதில். ஓய்வெடுக்கவும், தண்ணீர் அதிகம் குடிக்கவும், வெப்பநிலையை கண்காணிக்கவும். அதிகமாக இருந்தால் அல்லது தொடர்ந்தால் மருத்துவரை அணுகவும்."),
        (["headache", "migraine", "தலைவலி"], "தலைவலிக்கு பொதுவான காரணங்கள்: நீரிழப்பு, மன அழுத்தம், தூக்கமின்மை. அமைதியான, இருட்டான அறையில் ஓய்வெடுக்கவும். கடுமையாக இருந்தால் மருத்துவரை பார்க்கவும்."),
        (["cold", "cough", "flu", "சளி", "இருமல்"], "சளி மற்றும் இருமலுக்கு ஓய்வு, திரவங்கள், சூடான தேநீர் உதவும். 10 நாட்களுக்கு மேல் தொடர்ந்தால் மருத்துவரை அணுகவும்."),
        (["diabetes", "sugar", "சர்க்கரை"], "சர்க்கரை அளவை கட்டுப்படுத்த: சரிவிகித உணவு, தொடர்ந்த உடற்பயிற்சி, அளவை கண்காணித்தல் மற்றும் மருத்துவர் ஆலோசனையை பின்பற்றுதல் அவசியம்."),
        (["blood pressure", "hypertension", "இரத்த அழுத்தம்"], "இரத்த அழுத்தத்தை கட்டுப்படுத்த: உப்பு உணவை குறைக்கவும், தொடர்ந்து உடற்பயிற்சி செய்யவும், மன அழுத்தத்தை குறைக்கவும், மருத்துவரிடம் அளவை சரிபார்க்கவும்."),
        (["hello", "hi", "hey", "வணக்கம்"], "வணக்கம்! நான் பொது சுகாதார தகவல்களை பகிர இங்கே இருக்கிறேன். இன்று என்ன தெரிந்துகொள்ள விரும்புகிறீர்கள்?"),
        (["thank", "நன்றி"], "வரவேற்கிறேன்! ஆரோக்கியமாக இருங்கள், மேலும் கேள்விகள் இருந்தால் கேளுங்கள்."),
    ]

    active_knowledge = knowledge_ta if lang == "ta" else knowledge
    for keywords, response in active_knowledge:
        if any(k in text for k in keywords):
            return response

    if lang == "ta":
        return (
            "இது ஒரு நல்ல கேள்வி. நான் பொது சுகாதார கல்வி தகவல்களை மட்டுமே பகிர முடியும். "
            "உங்கள் நிலைமைக்கு ஏற்ற ஆலோசனைக்கு தகுதியான மருத்துவரை அணுகவும். "
            "உணவு, தூக்கம் அல்லது உடற்பயிற்சி போன்ற பொதுவான தலைப்பு பற்றி கேட்க விரும்புகிறீர்களா?"
        )

    return (
        "That's a great question. While I can share general health education information, "
        "I'd recommend consulting a qualified healthcare professional for advice specific to your situation. "
        "Is there a general health topic I can help explain, like nutrition, sleep, or exercise?"
    )


# ---------------------------------------------------------------------------
# Routes: Auth
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    remember = request.form.get("remember")

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return render_template("login.html")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password. Please try again.", "error")
        return render_template("login.html")

    session["user_id"] = user["id"]
    session["full_name"] = user["full_name"]
    session["is_admin"] = bool(user["is_admin"])
    session["profile_photo"] = user["profile_photo"]
    session.permanent = bool(remember)
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    mobile = request.form.get("mobile", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = []

    if not full_name or len(full_name) < 2:
        errors.append("Please enter a valid full name.")
    if not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if not MOBILE_RE.match(mobile):
        errors.append("Please enter a valid 10-digit mobile number.")
    if not age.isdigit() or not (0 < int(age) < 120):
        errors.append("Please enter a valid age.")
    if gender not in ("Male", "Female", "Other"):
        errors.append("Please select a gender.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    db = get_db()
    if not errors:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            errors.append("An account with this email already exists.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("login.html", show_register=True, form_data=request.form)

    password_hash = generate_password_hash(password)
    db.execute(
        """INSERT INTO users (full_name, email, mobile, age, gender, password_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (full_name, email, mobile, int(age), gender, password_hash, datetime.now().isoformat()),
    )
    db.commit()

    flash("Registration successful! Please log in.", "success")
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    mobile = request.form.get("mobile", "").strip()
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = []
    if not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")
    if not MOBILE_RE.match(mobile):
        errors.append("Please enter the 10-digit mobile number linked to your account.")
    if len(new_password) < 6:
        errors.append("New password must be at least 6 characters long.")
    if new_password != confirm_password:
        errors.append("Passwords do not match.")

    if not errors:
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND mobile = ?", (email, mobile)
        ).fetchone()
        if user is None:
            errors.append("No account matches that email and mobile number combination.")
        else:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), user["id"]),
            )
            db.commit()
            flash("Password reset successful! Please log in with your new password.", "success")
            return redirect(url_for("login"))

    for e in errors:
        flash(e, "error")
    return render_template("forgot_password.html", form_data=request.form)


@app.route("/logout", methods=["GET"])
@login_required
def logout_page():
    return render_template("logout.html")


@app.route("/logout/confirm", methods=["POST"])
def logout_confirm():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes: Main app pages
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    day_index = datetime.now().timetuple().tm_yday
    tip = HEALTH_TIPS[day_index % len(HEALTH_TIPS)]
    quote = HEALTH_QUOTES[day_index % len(HEALTH_QUOTES)]

    previous_tips = [HEALTH_TIPS[(day_index - offset) % len(HEALTH_TIPS)] for offset in range(1, 4)]

    db = get_db()
    reminders = db.execute(
        "SELECT * FROM reminders WHERE user_id = ? ORDER BY is_done ASC, created_at ASC",
        (session["user_id"],),
    ).fetchall()

    return render_template(
        "dashboard.html",
        full_name=session.get("full_name"),
        tip=tip,
        quote=quote,
        previous_tips=previous_tips,
        reminders=reminders,
        now=datetime.now(),
    )


@app.route("/api/reminders", methods=["GET", "POST"])
@login_required
def api_reminders():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        time_label = (data.get("time_label") or "").strip()
        if not text:
            return jsonify({"error": "Reminder text cannot be empty."}), 400
        db.execute(
            "INSERT INTO reminders (user_id, text, time_label, created_at) VALUES (?, ?, ?, ?)",
            (session["user_id"], text, time_label, datetime.now().isoformat()),
        )
        db.commit()

    rows = db.execute(
        "SELECT * FROM reminders WHERE user_id = ? ORDER BY is_done ASC, created_at ASC",
        (session["user_id"],),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/reminders/<int:reminder_id>/toggle", methods=["POST"])
@login_required
def api_reminder_toggle(reminder_id):
    db = get_db()
    reminder = db.execute(
        "SELECT * FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, session["user_id"])
    ).fetchone()
    if reminder is None:
        return jsonify({"error": "Reminder not found."}), 404
    db.execute(
        "UPDATE reminders SET is_done = ? WHERE id = ?",
        (0 if reminder["is_done"] else 1, reminder_id),
    )
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/api/reminders/<int:reminder_id>/delete", methods=["POST"])
@login_required
def api_reminder_delete(reminder_id):
    db = get_db()
    db.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, session["user_id"]))
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/chatbot")
@login_required
def chatbot():
    db = get_db()
    history = db.execute(
        "SELECT * FROM chat_history WHERE user_id = ? ORDER BY created_at ASC",
        (session["user_id"],),
    ).fetchall()
    return render_template(
        "chatbot.html",
        full_name=session.get("full_name"),
        history=history,
        suggested_questions=SUGGESTED_QUESTIONS,
        suggested_questions_ta=SUGGESTED_QUESTIONS_TA,
    )


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    lang = data.get("lang") or "en"
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    db = get_db()
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO chat_history (user_id, sender, message, created_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], "user", message, now),
    )

    reply = get_ai_response(message, lang=lang)
    db.execute(
        "INSERT INTO chat_history (user_id, sender, message, created_at) VALUES (?, ?, ?, ?)",
        (session["user_id"], "ai", reply, now),
    )
    db.commit()

    return jsonify({"reply": reply})


@app.route("/api/chat/clear", methods=["POST"])
@login_required
def api_chat_clear():
    db = get_db()
    db.execute("DELETE FROM chat_history WHERE user_id = ?", (session["user_id"],))
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/api/chat/history")
@login_required
def api_chat_history():
    query = request.args.get("q", "").strip().lower()
    db = get_db()
    if query:
        rows = db.execute(
            "SELECT * FROM chat_history WHERE user_id = ? AND lower(message) LIKE ? ORDER BY created_at ASC",
            (session["user_id"], f"%{query}%"),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM chat_history WHERE user_id = ? ORDER BY created_at ASC",
            (session["user_id"],),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/chat/export")
@login_required
def api_chat_export():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM chat_history WHERE user_id = ? ORDER BY created_at ASC",
        (session["user_id"],),
    ).fetchall()

    lines = [
        f"HealthAI Chat Export — {session.get('full_name')}",
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        "=" * 50,
        "",
    ]
    for row in rows:
        speaker = "You" if row["sender"] == "user" else "HealthAI"
        timestamp = row["created_at"][:19].replace("T", " ")
        lines.append(f"[{timestamp}] {speaker}: {row['message']}")

    content = "\n".join(lines) if rows else "No conversation history yet."
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=healthai_chat_history.txt"},
    )


@app.route("/health-tools")
@login_required
def health_tools():
    return render_template("health_tools.html", full_name=session.get("full_name"), diseases=DISEASES)


@app.route("/emergency")
@login_required
def emergency():
    return render_template(
        "emergency.html",
        full_name=session.get("full_name"),
        emergencies=EMERGENCIES,
        hospitals=NEARBY_HOSPITALS,
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "GET":
        return render_template("profile.html", full_name=session.get("full_name"), user=user)

    full_name = request.form.get("full_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "").strip()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = []
    if not full_name or len(full_name) < 2:
        errors.append("Please enter a valid full name.")
    if not MOBILE_RE.match(mobile):
        errors.append("Please enter a valid 10-digit mobile number.")
    if not age.isdigit() or not (0 < int(age) < 120):
        errors.append("Please enter a valid age.")
    if gender not in ("Male", "Female", "Other"):
        errors.append("Please select a gender.")

    wants_password_change = bool(current_password or new_password or confirm_password)
    if wants_password_change:
        if not check_password_hash(user["password_hash"], current_password):
            errors.append("Current password is incorrect.")
        elif len(new_password) < 6:
            errors.append("New password must be at least 6 characters long.")
        elif new_password != confirm_password:
            errors.append("New passwords do not match.")

    photo_filename = user["profile_photo"]
    photo_file = request.files.get("profile_photo")
    if photo_file and photo_file.filename:
        ext = photo_file.filename.rsplit(".", 1)[-1].lower() if "." in photo_file.filename else ""
        if ext not in ALLOWED_PHOTO_EXT:
            errors.append("Profile photo must be a PNG, JPG, JPEG, GIF, or WEBP image.")
        else:
            photo_filename = secure_filename(f"user_{session['user_id']}.{ext}")
            photo_file.save(os.path.join(UPLOAD_FOLDER, photo_filename))

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("profile.html", full_name=session.get("full_name"), user=user)

    if wants_password_change:
        db.execute(
            """UPDATE users SET full_name = ?, mobile = ?, age = ?, gender = ?,
               password_hash = ?, profile_photo = ? WHERE id = ?""",
            (full_name, mobile, int(age), gender, generate_password_hash(new_password),
             photo_filename, session["user_id"]),
        )
    else:
        db.execute(
            "UPDATE users SET full_name = ?, mobile = ?, age = ?, gender = ?, profile_photo = ? WHERE id = ?",
            (full_name, mobile, int(age), gender, photo_filename, session["user_id"]),
        )
    db.commit()

    session["full_name"] = full_name
    session["profile_photo"] = photo_filename
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/admin")
@admin_required
def admin_panel():
    db = get_db()
    users = db.execute(
        "SELECT id, full_name, email, mobile, age, gender, created_at, is_admin FROM users ORDER BY created_at DESC"
    ).fetchall()
    total_chats = db.execute("SELECT COUNT(*) AS c FROM chat_history").fetchone()["c"]
    return render_template(
        "admin.html",
        full_name=session.get("full_name"),
        users=users,
        total_users=len(users),
        total_chats=total_chats,
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

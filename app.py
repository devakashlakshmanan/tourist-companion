from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import os, hashlib, uuid, re
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production-" + str(uuid.uuid4()))

# ─── Configuration ───────────────────────────────────────────────────────────
GOOGLE_MAPS_API_KEY    = os.environ.get("GOOGLE_MAPS_API_KEY",    "YOUR_GOOGLE_MAPS_API_KEY")
ANTHROPIC_API_KEY      = os.environ.get("ANTHROPIC_API_KEY",      "YOUR_ANTHROPIC_API_KEY")
GOOGLE_CLIENT_ID       = os.environ.get("GOOGLE_CLIENT_ID",       "YOUR_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET   = os.environ.get("GOOGLE_CLIENT_SECRET",   "YOUR_GOOGLE_CLIENT_SECRET")

# ─── Google OAuth Setup ───────────────────────────────────────────────────────
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ─── In-Memory User Store (replace with DB in production) ────────────────────
# Format: { email: { name, email, avatar, provider, password_hash, joined } }
USERS = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user():
    email = session.get("user_email")
    if email and email in USERS:
        return USERS[email]
    return None

# ─── Auth Routes ──────────────────────────────────────────────────────────────

# ── Google OAuth Flow ──
@app.route("/auth/google/login")
def google_login():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo") or google.parse_id_token(token, nonce=None)
    email  = userinfo["email"]
    name   = userinfo.get("name", email.split("@")[0])
    avatar = userinfo.get("picture", "")
    if email not in USERS:
        USERS[email] = {
            "name": name, "email": email,
            "avatar": avatar, "provider": "google",
            "password_hash": None,
            "joined": datetime.utcnow().strftime("%B %Y")
        }
    else:
        USERS[email]["avatar"] = avatar   # refresh avatar
    session["user_email"] = email
    return redirect("/?loggedin=1")

# ── Email/Password Register ──
@app.route("/auth/register", methods=["POST"])
def register():
    data     = request.get_json()
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if email in USERS:
        return jsonify({"error": "Email already registered"}), 409
    USERS[email] = {
        "name": name, "email": email,
        "avatar": f"https://ui-avatars.com/api/?name={name.replace(' ','+')}&background=6C2BD9&color=fff&size=128",
        "provider": "email",
        "password_hash": hash_password(password),
        "joined": datetime.utcnow().strftime("%B %Y")
    }
    session["user_email"] = email
    return jsonify({"success": True, "user": safe_user(USERS[email])})

# ── Email/Password Login ──
@app.route("/auth/login", methods=["POST"])
def login():
    data     = request.get_json()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user     = USERS.get(email)
    if not user:
        return jsonify({"error": "No account found with this email"}), 404
    if user["provider"] == "google":
        return jsonify({"error": "This account uses Google Sign-In. Use the Google button."}), 400
    if user["password_hash"] != hash_password(password):
        return jsonify({"error": "Incorrect password"}), 401
    session["user_email"] = email
    return jsonify({"success": True, "user": safe_user(user)})

# ── Logout ──
@app.route("/auth/logout", methods=["POST"])
def logout():
    session.pop("user_email", None)
    return jsonify({"success": True})

# ── Get Current User ──
@app.route("/auth/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": safe_user(user)})

def safe_user(u):
    return {"name": u["name"], "email": u["email"],
            "avatar": u["avatar"], "provider": u["provider"], "joined": u["joined"]}

# ─── Destinations Data ────────────────────────────────────────────────────────
DESTINATIONS = [
    # ── NORTH INDIA ──────────────────────────────────────────────────────────
    {
        "id": 1, "name": "Delhi", "region": "North India",
        "tagline": "Where Ancient Empires Meet Modern India",
        "description": "India's sprawling capital is a living museum, where Mughal domes and British boulevards jostle with gleaming malls and street-food lanes. From the Red Fort to Humayun's Tomb, every corner tells a story spanning three millennia.",
        "best_time": "Oct – Mar",
        "budget": "₹3,000 – 8,000/day",
        "lat": 28.6139, "lng": 77.2090,
        "image": "https://images.unsplash.com/photo-1587474260584-136574528ed5?w=800&q=80",
        "highlights": ["Red Fort", "Qutub Minar", "India Gate", "Chandni Chowk", "Humayun's Tomb"],
        "cuisine": ["Butter Chicken", "Chaat", "Paranthas", "Kebabs"],
        "transport": "Metro · Auto · Cab",
        "language": "Hindi, English",
        "stay": ["The Imperial", "ITC Maurya", "Zostel Delhi"],
        "tips": "Avoid summers (Apr–Jun). Use Delhi Metro to beat traffic. Carry water."
    },
    {
        "id": 2, "name": "Agra", "region": "North India",
        "tagline": "Home of the Timeless Taj Mahal",
        "description": "Agra is synonymous with the Taj Mahal, the world's greatest monument to love. But the city also hides the massive Agra Fort and the ghost city of Fatehpur Sikri, making it essential on any India itinerary.",
        "best_time": "Oct – Mar",
        "budget": "₹2,500 – 6,000/day",
        "lat": 27.1767, "lng": 78.0081,
        "image": "https://images.unsplash.com/photo-1548013146-72479768bada?w=800&q=80",
        "highlights": ["Taj Mahal", "Agra Fort", "Fatehpur Sikri", "Mehtab Bagh", "Itmad-ud-Daulah"],
        "cuisine": ["Petha", "Mughlai Biryani", "Bedai", "Jalebi"],
        "transport": "Auto · Tonga · Cab",
        "language": "Hindi",
        "stay": ["The Oberoi Amarvilas", "ITC Mughal", "Zostel Agra"],
        "tips": "Sunrise visit to Taj is magical. Book tickets online to skip queues."
    },
    {
        "id": 3, "name": "Manali", "region": "North India",
        "tagline": "Adventure Capital of the Himalayas",
        "description": "Cradled in the Kullu Valley at 2,050 m, Manali is a paradise for trekkers, skiers, and river-rafters. Snow-capped Rohtang Pass, cedar forests, and the hippie haven of Old Manali create an irresistible blend.",
        "best_time": "Oct – Jun",
        "budget": "₹2,000 – 5,000/day",
        "lat": 32.2396, "lng": 77.1887,
        "image": "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=800&q=80",
        "highlights": ["Rohtang Pass", "Solang Valley", "Hadimba Temple", "Old Manali", "Beas River"],
        "cuisine": ["Siddu", "Dham", "Trout Fish", "Tibetan Momos"],
        "transport": "Cab · Bike Rental",
        "language": "Hindi, Kulvi",
        "stay": ["Snow Valley Resorts", "The Himalayan", "Zostel Manali"],
        "tips": "Book Rohtang Pass permit in advance. Carry warm clothes even in summer."
    },
    {
        "id": 4, "name": "Shimla", "region": "North India",
        "tagline": "Queen of Hill Stations",
        "description": "The former summer capital of British India perches on forested ridges at 2,200 m. The colonial Mall Road, Christ Church, and toy-train rides through the Shivalik foothills make Shimla eternally charming.",
        "best_time": "Mar – Jun, Dec – Jan",
        "budget": "₹2,500 – 5,500/day",
        "lat": 31.1048, "lng": 77.1734,
        "image": "https://images.unsplash.com/photo-1597074866923-dc0589150358?w=800&q=80",
        "highlights": ["Mall Road", "Christ Church", "Jakhu Temple", "Toy Train", "Kufri"],
        "cuisine": ["Chha Gosht", "Babru", "Siddu", "Aktori"],
        "transport": "Toy Train · Cab · Walk",
        "language": "Hindi, Pahari",
        "stay": ["Wildflower Hall", "Hotel Combermere", "Snow Flake Guest House"],
        "tips": "Toy train from Kalka is a UNESCO heritage experience. Visit Jakhu at dawn."
    },
    {
        "id": 5, "name": "Leh-Ladakh", "region": "North India",
        "tagline": "Land of High Passes & Moonscapes",
        "description": "At 3,500 m, Leh is India's highest accessible city. Pangong Lake's shifting blues, monasteries clinging to cliffs, and Nubra Valley's camels amid sand dunes create an otherworldly experience unlike anywhere on Earth.",
        "best_time": "Jun – Sep",
        "budget": "₹3,000 – 8,000/day",
        "lat": 34.1526, "lng": 77.5771,
        "image": "https://images.unsplash.com/photo-1509515837298-2c67a3933321?w=800&q=80",
        "highlights": ["Pangong Lake", "Nubra Valley", "Khardung La", "Thiksey Monastery", "Magnetic Hill"],
        "cuisine": ["Thukpa", "Skyu", "Butter Tea", "Momos"],
        "transport": "4WD · Bike · Shared Cab",
        "language": "Ladakhi, Hindi",
        "stay": ["The Grand Dragon", "Stok Palace Heritage", "Zostel Leh"],
        "tips": "Acclimatize for 2 days before trekking. Carry cash — ATMs are scarce beyond Leh."
    },
    {
        "id": 6, "name": "Varanasi", "region": "North India",
        "tagline": "The Eternal City on the Ganges",
        "description": "One of the world's oldest living cities, Varanasi's ghats pulse with life, death, and devotion. Sunrise boat rides past flaming funeral pyres and the Ganga Aarti ceremony at dusk are among India's most profound experiences.",
        "best_time": "Oct – Mar",
        "budget": "₹1,500 – 4,000/day",
        "lat": 25.3176, "lng": 82.9739,
        "image": "https://images.unsplash.com/photo-1561361058-c24cecae35ca?w=800&q=80",
        "highlights": ["Dashashwamedh Ghat", "Kashi Vishwanath Temple", "Sarnath", "Manikarnika Ghat", "Ganga Aarti"],
        "cuisine": ["Kachori Sabzi", "Baati Chokha", "Lassi", "Malaiyyo"],
        "transport": "Boat · Rickshaw · Walk",
        "language": "Hindi, Bhojpuri",
        "stay": ["BrijRama Palace", "Hotel Ganges View", "Stops Hostel"],
        "tips": "Sunrise boat ride is unmissable. Respect rituals at ghats. Avoid monsoon visits."
    },
    {
        "id": 7, "name": "Amritsar", "region": "North India",
        "tagline": "City of the Golden Temple",
        "description": "The holiest city in Sikhism radiates warmth and spirituality. The Golden Temple's reflection on the sacred Amrit Sarovar, the Wagah Border flag-lowering ceremony, and Punjabi hospitality make it an unforgettable destination.",
        "best_time": "Oct – Mar",
        "budget": "₹1,500 – 4,000/day",
        "lat": 31.6340, "lng": 74.8723,
        "image": "https://images.unsplash.com/photo-1588416936097-41850ab3d86d?w=800&q=80",
        "highlights": ["Golden Temple", "Wagah Border", "Jallianwala Bagh", "Durgiana Temple", "Gobindgarh Fort"],
        "cuisine": ["Amritsari Kulcha", "Dal Makhani", "Lassi", "Pinni"],
        "transport": "Auto · Rickshaw · Cab",
        "language": "Punjabi, Hindi",
        "stay": ["Taj Swarna", "Hotel Ritz Plaza", "Jugaadus Hostel"],
        "tips": "Langar at Golden Temple is free for all. Wagah ceremony needs early arrival."
    },
    {
        "id": 8, "name": "Rishikesh", "region": "North India",
        "tagline": "Yoga Capital of the World",
        "description": "Where the Ganges tumbles out of the Himalayas, Rishikesh blends spirituality with adrenaline. Ashrams, Beatles history, world-class white-water rafting, and bungee jumping coexist harmoniously in this sacred town.",
        "best_time": "Sep – Nov, Feb – May",
        "budget": "₹1,000 – 4,000/day",
        "lat": 30.0869, "lng": 78.2676,
        "image": "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=800&q=80",
        "highlights": ["Laxman Jhula", "Ram Jhula", "Triveni Ghat", "Rajaji National Park", "Beatles Ashram"],
        "cuisine": ["Aloo Puri", "Thali", "Lassi", "Herbal Teas"],
        "transport": "Walk · Auto · Cab",
        "language": "Hindi, Garhwali",
        "stay": ["Ananda in the Himalayas", "Zostel Rishikesh", "Parmarth Niketan"],
        "tips": "Alcohol-free zone. Book rafting and bungee in advance during peak season."
    },

    # ── SOUTH INDIA ──────────────────────────────────────────────────────────
    {
        "id": 9, "name": "Kerala Backwaters", "region": "South India",
        "tagline": "God's Own Country",
        "description": "A network of 900 km of serene waterways, lagoons, and lakes fringed by coconut palms. Houseboat (kettuvallam) cruises through Alleppey's canals, Kumarakom's bird sanctuary, and Vembanad Lake are bucket-list experiences.",
        "best_time": "Oct – Feb",
        "budget": "₹4,000 – 12,000/day",
        "lat": 9.4981, "lng": 76.3388,
        "image": "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800&q=80",
        "highlights": ["Alleppey Houseboats", "Kumarakom", "Vembanad Lake", "Punnamada Lake", "Kuttanad"],
        "cuisine": ["Karimeen Pollichathu", "Appam & Stew", "Prawn Curry", "Kerala Sadya"],
        "transport": "Houseboat · Ferry · Cab",
        "language": "Malayalam",
        "stay": ["CGH Earth Coconut Lagoon", "Raheem Residency", "Zostel Alleppey"],
        "tips": "Book houseboats 3–6 months ahead for peak season. Negotiate prices at jetties."
    },
    {
        "id": 10, "name": "Munnar", "region": "South India",
        "tagline": "Rolling Tea Carpets of the Western Ghats",
        "description": "Perched at 1,600 m in Kerala's Western Ghats, Munnar's endless emerald tea gardens, spice plantations, and mist-draped peaks provide India's most romantic hill-station escape.",
        "best_time": "Sep – May",
        "budget": "₹2,000 – 6,000/day",
        "lat": 10.0889, "lng": 77.0595,
        "image": "https://images.unsplash.com/photo-1580502304784-8985b7eb7260?w=800&q=80",
        "highlights": ["Eravikulam National Park", "Top Station", "Tea Museum", "Attukad Falls", "Chinnakanal"],
        "cuisine": ["Tea-smoked dishes", "Bamboo Biryani", "Puttu & Kadala", "Kerala Fish Curry"],
        "transport": "Cab · Jeep Safari",
        "language": "Malayalam, Tamil",
        "stay": ["Windermere Estate", "Fragrant Nature", "Tea County"],
        "tips": "Neelakurinji blooms only once in 12 years (next: 2030). Visit Eravikulam for Nilgiri Tahr."
    },
    {
        "id": 11, "name": "Mysuru", "region": "South India",
        "tagline": "City of Palaces & Sandalwood",
        "description": "The cultural capital of Karnataka dazzles with its illuminated Mysore Palace, vibrant Dasara festival, and fragrant sandalwood products. Chamundi Hills and nearby Srirangapatna add historical depth.",
        "best_time": "Oct – Mar",
        "budget": "₹2,000 – 5,000/day",
        "lat": 12.2958, "lng": 76.6394,
        "image": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?w=800&q=80",
        "highlights": ["Mysore Palace", "Chamundi Hills", "Brindavan Gardens", "Devaraja Market", "Srirangapatna"],
        "cuisine": ["Mysore Pak", "Masala Dosa", "Obbattu", "Filter Coffee"],
        "transport": "Auto · KSRTC Bus · Cab",
        "language": "Kannada",
        "stay": ["Lalitha Mahal Palace Hotel", "Royal Orchid Metropole", "Zostel Mysuru"],
        "tips": "Palace lights up on Sundays and holidays. Dasara (Oct) is spectacular but crowded."
    },
    {
        "id": 12, "name": "Ooty", "region": "South India",
        "tagline": "The Nilgiri Blue Mountain Queen",
        "description": "Surrounded by the fragrant Nilgiri Hills and endless tea estates, Ooty's Botanical Gardens, Ooty Lake, and the UNESCO Nilgiri Mountain Railway toy train make it Tamil Nadu's most beloved hill station.",
        "best_time": "Apr – Jun, Sep – Nov",
        "budget": "₹2,000 – 5,000/day",
        "lat": 11.4102, "lng": 76.6950,
        "image": "https://images.unsplash.com/photo-1623776787756-41ab6feaa625?w=800&q=80",
        "highlights": ["Botanical Gardens", "Ooty Lake", "Doddabetta Peak", "Nilgiri Mountain Railway", "Pykara Falls"],
        "cuisine": ["Varkey", "Avalose Unda", "Fresh Nilgiri Tea", "Chocolate"],
        "transport": "Toy Train · Cab · Auto",
        "language": "Tamil, Toda",
        "stay": ["Savoy Hotel", "The Monarch", "YWCA Anandagiri"],
        "tips": "Take the toy train at least one way. Avoid May–June peak: book months ahead."
    },
    {
        "id": 13, "name": "Hampi", "region": "South India",
        "tagline": "Ruins of the Vijayanagara Empire",
        "description": "A UNESCO World Heritage Site, Hampi's boulder-strewn landscape conceals the magnificent ruins of the Vijayanagara Empire. The Virupaksha Temple, Stone Chariot, and Vittala Temple complex are architectural masterpieces.",
        "best_time": "Oct – Feb",
        "budget": "₹1,000 – 3,000/day",
        "lat": 15.3350, "lng": 76.4600,
        "image": "https://images.unsplash.com/photo-1590050752117-238cb0fb12b1?w=800&q=80",
        "highlights": ["Virupaksha Temple", "Stone Chariot", "Vittala Temple", "Elephant Stables", "Lotus Mahal"],
        "cuisine": ["Jolada Rotti", "Bisi Bele Bath", "Mango Juice", "Sugarcane Juice"],
        "transport": "Cycle · Auto · Coracle",
        "language": "Kannada",
        "stay": ["Evolve Back Kamalapura", "Mowgli Guest House", "Zostel Hampi"],
        "tips": "Rent a bicycle to explore. Cross the Tungabhadra by coracle for the hippie island."
    },
    {
        "id": 14, "name": "Pondicherry", "region": "South India",
        "tagline": "The French Riviera of the East",
        "description": "A former French colony with tree-lined boulevards, yellow-painted villas, and a promenade along the Bay of Bengal. Auroville's Golden Dome, excellent cafés, and scuba diving make it India's most cosmopolitan escape.",
        "best_time": "Oct – Mar",
        "budget": "₹2,000 – 6,000/day",
        "lat": 11.9416, "lng": 79.8083,
        "image": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?w=800&q=80",
        "highlights": ["Promenade Beach", "Auroville", "French Quarter", "Basilica of Sacred Heart", "Paradise Beach"],
        "cuisine": ["Crepes", "Bouillabaisse", "Coconut Prawn Curry", "Baguette"],
        "transport": "Cycle · Auto · Walk",
        "language": "Tamil, French, English",
        "stay": ["Palais de Mahe", "Gratitude Heritage", "International Guest House"],
        "tips": "White Town is car-free: walk or cycle. Auroville requires pre-booking meditation sessions."
    },

    # ── WEST INDIA ───────────────────────────────────────────────────────────
    {
        "id": 15, "name": "Goa", "region": "West India",
        "tagline": "Sun, Sand & Soulful Sunsets",
        "description": "India's smallest state packs beaches, Portuguese churches, spice farms, and vibrant nightlife into a tiny coastal gem. From the white sands of Palolem to the heritage streets of Fontainhas, Goa has something for everyone.",
        "best_time": "Nov – Feb",
        "budget": "₹2,500 – 8,000/day",
        "lat": 15.2993, "lng": 74.1240,
        "image": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=800&q=80",
        "highlights": ["Palolem Beach", "Basilica of Bom Jesus", "Dudhsagar Falls", "Fontainhas", "Anjuna Flea Market"],
        "cuisine": ["Goan Fish Curry", "Vindaloo", "Xacuti", "Bebinca", "Feni"],
        "transport": "Bike Rental · Cab · Ferry",
        "language": "Konkani, English, Hindi",
        "stay": ["Taj Exotica", "Pousada Tauma", "Zostel Palolem"],
        "tips": "North Goa for parties; South Goa for peace. Rent a scooter for freedom. Nov–Feb is ideal."
    },
    {
        "id": 16, "name": "Mumbai", "region": "West India",
        "tagline": "The City That Never Sleeps",
        "description": "India's financial capital is a city of dreams where Bollywood glam meets Dharavi grit. The Gateway of India, Marine Drive at night, Elephanta Caves, and the best street food in India make Mumbai endlessly captivating.",
        "best_time": "Nov – Feb",
        "budget": "₹3,000 – 10,000/day",
        "lat": 19.0760, "lng": 72.8777,
        "image": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=800&q=80",
        "highlights": ["Gateway of India", "Marine Drive", "Elephanta Caves", "Dharavi", "Chhatrapati Shivaji Terminus"],
        "cuisine": ["Vada Pav", "Pav Bhaji", "Bhel Puri", "Bombay Duck", "Cutting Chai"],
        "transport": "Local Train · Metro · Bus · Cab",
        "language": "Marathi, Hindi, English",
        "stay": ["The Taj Mahal Palace", "ITC Grand Central", "Zostel Mumbai"],
        "tips": "Local trains are fastest but crowded. Buy 1-day tourist pass. Avoid monsoon travel."
    },
    {
        "id": 17, "name": "Udaipur", "region": "West India",
        "tagline": "The City of Lakes & Palaces",
        "description": "Floating palaces reflected in shimmering lakes, havelis, and mewar art make Udaipur arguably India's most romantic city. The City Palace complex, Lake Pichola sunset boat rides, and Sajjangarh fort are unmissable.",
        "best_time": "Sep – Mar",
        "budget": "₹2,500 – 8,000/day",
        "lat": 24.5854, "lng": 73.7125,
        "image": "https://images.unsplash.com/photo-1568640347023-a616a30bc3bd?w=800&q=80",
        "highlights": ["City Palace", "Lake Pichola", "Jag Mandir", "Sajjangarh Fort", "Jagdish Temple"],
        "cuisine": ["Dal Baati Churma", "Gatte ki Sabzi", "Laal Maas", "Ghevar"],
        "transport": "Auto · Boat · Cycle",
        "language": "Rajasthani, Hindi",
        "stay": ["Taj Lake Palace", "RAAS Devigarh", "Zostel Udaipur"],
        "tips": "Sunset boat ride on Lake Pichola is magical. Book heritage hotels early for festivals."
    },
    {
        "id": 18, "name": "Jaipur", "region": "West India",
        "tagline": "The Pink City of Rajasthan",
        "description": "The capital of Rajasthan earns its 'Pink City' nickname from terracotta-washed buildings. Amber Fort's mirror-inlaid halls, the five-storey Hawa Mahal facade, and Jantar Mantar astronomical observatory are extraordinary.",
        "best_time": "Oct – Mar",
        "budget": "₹2,000 – 7,000/day",
        "lat": 26.9124, "lng": 75.7873,
        "image": "https://images.unsplash.com/photo-1477587458883-47145ed31245?w=800&q=80",
        "highlights": ["Amber Fort", "Hawa Mahal", "City Palace", "Jantar Mantar", "Nahargarh Fort"],
        "cuisine": ["Dal Baati Churma", "Pyaaz Kachori", "Ghevar", "Laal Maas"],
        "transport": "Auto · Rickshaw · Cab",
        "language": "Rajasthani, Hindi",
        "stay": ["Rambagh Palace", "Samode Haveli", "Zostel Jaipur"],
        "tips": "Composite ticket covers 5 major forts/palaces. Elephant rides banned — opt for jeep at Amber."
    },
    {
        "id": 19, "name": "Jodhpur", "region": "West India",
        "tagline": "The Blue City of the Thar",
        "description": "The mighty Mehrangarh Fort looms over a sea of indigo blue houses in India's 'Sun City'. The Jaswant Thada cenotaph, the narrow lanes of the old city, and the Bishnoi village safaris are uniquely Jodhpur experiences.",
        "best_time": "Oct – Mar",
        "budget": "₹1,500 – 5,000/day",
        "lat": 26.2389, "lng": 73.0243,
        "image": "https://images.unsplash.com/photo-1557939574-a8b2a7b62a5e?w=800&q=80",
        "highlights": ["Mehrangarh Fort", "Jaswant Thada", "Umaid Bhawan Palace", "Clock Tower Market", "Osian Desert"],
        "cuisine": ["Makhaniya Lassi", "Mirchi Bada", "Mawa Kachori", "Ker Sangri"],
        "transport": "Auto · Cab",
        "language": "Rajasthani, Hindi",
        "stay": ["RAAS Jodhpur", "Umaid Bhawan Palace", "Cosy Hostel"],
        "tips": "Climb to Mehrangarh at sunrise for stunning fort and blue-city views."
    },

    # ── EAST INDIA ───────────────────────────────────────────────────────────
    {
        "id": 20, "name": "Kolkata", "region": "East India",
        "tagline": "City of Joy & Intellectual Grandeur",
        "description": "The cultural heartbeat of India, Kolkata's Victorian architecture, trams, Durga Puja grandeur, Rabindranath Tagore's heritage, and addictive street food make it the most intellectually stimulating city in the subcontinent.",
        "best_time": "Oct – Feb",
        "budget": "₹1,500 – 5,000/day",
        "lat": 22.5726, "lng": 88.3639,
        "image": "https://images.unsplash.com/photo-1558431382-27e303142255?w=800&q=80",
        "highlights": ["Victoria Memorial", "Howrah Bridge", "Dakshineswar Temple", "Park Street", "Kumartuli"],
        "cuisine": ["Rosogolla", "Macher Jhol", "Kati Roll", "Doi Maach", "Puchka"],
        "transport": "Tram · Metro · Yellow Taxi",
        "language": "Bengali",
        "stay": ["The Oberoi Grand", "Taj Bengal", "Zostel Kolkata"],
        "tips": "Durga Puja (Oct) is world-class art. Explore Kumartuli for clay idol sculptors."
    },
    {
        "id": 21, "name": "Darjeeling", "region": "East India",
        "tagline": "Tea, Trains & the Himalayas",
        "description": "The 'Queen of the Hills' offers the most spectacular Himalayan panorama in India — Kangchenjunga (world's 3rd highest peak) visible from Tiger Hill at dawn. The UNESCO Darjeeling Himalayan Railway and tea gardens complete the magic.",
        "best_time": "Mar – May, Sep – Nov",
        "budget": "₹2,000 – 5,000/day",
        "lat": 27.0360, "lng": 88.2627,
        "image": "https://images.unsplash.com/photo-1544461772-722b489b7d41?w=800&q=80",
        "highlights": ["Tiger Hill Sunrise", "Darjeeling Himalayan Railway", "Happy Valley Tea Estate", "Batasia Loop", "Peace Pagoda"],
        "cuisine": ["Darjeeling Tea", "Momos", "Thukpa", "Churpi Soup"],
        "transport": "Toy Train · Jeep · Walk",
        "language": "Nepali, Bengali",
        "stay": ["The Elgin", "Glenburn Tea Estate", "Youth Hostel Darjeeling"],
        "tips": "Tiger Hill jeep leaves at 4 AM — book previous evening. Clear days are Oct–Nov."
    },
    {
        "id": 22, "name": "Puri", "region": "East India",
        "tagline": "Sacred Shores of Lord Jagannath",
        "description": "One of India's four sacred dhams, Puri combines the magnificent 12th-century Jagannath Temple with a beautiful beach and the world-famous Rath Yatra chariot festival that draws millions of devotees.",
        "best_time": "Nov – Feb",
        "budget": "₹1,000 – 3,000/day",
        "lat": 19.8135, "lng": 85.8312,
        "image": "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=800&q=80",
        "highlights": ["Jagannath Temple", "Puri Beach", "Rath Yatra", "Konark Sun Temple", "Chilika Lake"],
        "cuisine": ["Mahaprasad", "Chenna Poda", "Dahi Bara Aloo Dum", "Rasabali"],
        "transport": "Auto · Rickshaw · Walk",
        "language": "Odia",
        "stay": ["Toshali Sands", "Hotel Hans Coco Palms", "Lemon Tree Puri"],
        "tips": "Non-Hindus cannot enter Jagannath Temple. Konark is 35 km away — ideal day trip."
    },
    {
        "id": 23, "name": "Kaziranga", "region": "East India",
        "tagline": "The Rhino Kingdom of Assam",
        "description": "A UNESCO World Heritage Site, Kaziranga harbours two-thirds of the world's one-horned rhinoceros population, along with wild elephants, tigers, and migratory birds across its elephant-grass floodplains.",
        "best_time": "Nov – Apr",
        "budget": "₹3,000 – 7,000/day",
        "lat": 26.5775, "lng": 93.1711,
        "image": "https://images.unsplash.com/photo-1600689436014-48c2e72c5f8f?w=800&q=80",
        "highlights": ["One-Horned Rhino Safari", "Elephant Safari", "Bird Watching", "Kohora Range", "Bagori Range"],
        "cuisine": ["Assamese Thali", "Bamboo Shoot Curry", "Masor Tenga", "Pitha"],
        "transport": "Jeep Safari · Elephant Safari",
        "language": "Assamese",
        "stay": ["Iora-The Retreat", "Wild Grass Lodge", "Kaziranga National Orchid"],
        "tips": "Book safaris through Assam Tourism. Morning safaris offer best wildlife sightings."
    },
    {
        "id": 24, "name": "Andaman Islands", "region": "East India",
        "tagline": "Tropical Paradise of the Bay of Bengal",
        "description": "Emerald forests plunge into gin-clear turquoise waters at these remote islands. Radhanagar Beach (Asia's best), Havelock Island's diving, Ross Island's colonial ruins, and bioluminescent plankton at night are extraordinary.",
        "best_time": "Oct – May",
        "budget": "₹4,000 – 10,000/day",
        "lat": 11.7401, "lng": 92.6586,
        "image": "https://images.unsplash.com/photo-1559128010-7c1ad6e1b6a5?w=800&q=80",
        "highlights": ["Radhanagar Beach", "Cellular Jail", "Havelock Island", "Neil Island", "Barren Island Volcano"],
        "cuisine": ["Grilled Lobster", "Fish Curry", "Coconut Prawn", "Andamanese Crab"],
        "transport": "Ferry · Speed Boat · Cab",
        "language": "Hindi, Bengali, Tamil",
        "stay": ["Havelock Island Beach Resort", "Symphony Palms", "Zostel Havelock"],
        "tips": "Inner Line Permit required for some islands. Book ferries well in advance. Carry cash."
    }
]

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           google_maps_key=GOOGLE_MAPS_API_KEY,
                           anthropic_key=ANTHROPIC_API_KEY,
                           google_client_id=GOOGLE_CLIENT_ID)

@app.route("/api/destinations")
def get_destinations():
    region = request.args.get("region", "All India")
    q      = request.args.get("q", "").lower()
    data   = DESTINATIONS
    if region != "All India":
        data = [d for d in data if d["region"] == region]
    if q:
        data = [d for d in data if q in d["name"].lower()
                or q in d["description"].lower()
                or q in d["region"].lower()]
    return jsonify(data)

@app.route("/api/destination/<int:dest_id>")
def get_destination(dest_id):
    dest = next((d for d in DESTINATIONS if d["id"] == dest_id), None)
    if not dest:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dest)

@app.route("/api/regions")
def get_regions():
    regions = ["All India"] + sorted(set(d["region"] for d in DESTINATIONS))
    return jsonify(regions)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

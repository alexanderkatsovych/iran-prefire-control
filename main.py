import requests
import os
import json
import hashlib
from datetime import datetime, timezone

# --- КОНФИГУРАЦИЯ ---
REGIONS = {
    'Iran': {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.0},
    'Israel': {'lamin': 29.5, 'lomin': 34.2, 'lamax': 33.3, 'lomax': 35.9},
    'Iraq': {'lamin': 29.0, 'lomin': 38.0, 'lamax': 37.5, 'lomax': 48.5},
    'Jordan': {'lamin': 29.0, 'lomin': 35.0, 'lamax': 33.0, 'lomax': 39.0},
    'Qatar': {'lamin': 24.2, 'lomin': 50.4, 'lamax': 26.6, 'lomax': 51.7},
    'Gulf of Aden': {'lamin': 10.0, 'lomin': 43.0, 'lamax': 15.0, 'lomax': 51.0},
    'Diego Garcia': {'lamin': -8.0, 'lomin': 71.0, 'lamax': -6.0, 'lomax': 73.0}
}

STRATEGIC_BOUNDS = {'lamin': -10.0, 'lomin': 33.0, 'lamax': 45.0, 'lomax': 75.0}

MIL_GROUPS = {
    'Tankers (Hidden +6)': ['LAGR', 'QUID', 'GOLD', 'K35R', 'TKRR', 'NACHO'],
    'Strategic Bombers': ['DEATH', 'MYSTIC', 'REAPER', 'FURY', 'BONE', 'DARK', 'MYTEE', 'DOOM', 'SKULL'],
    'Intelligence/UAV': ['FORTE', 'MQ9', 'GHAWK', 'VEXL', 'HAWK', 'JAKE'],
    'Helicopters/SOF': ['STALK', 'DUST', 'EVAC', 'MOJO', 'COWBOY', 'HUEY', 'KNIFE'],
    'Transport/Cargo': ['RCH', 'C130', 'C17', 'C5', 'CN235', 'CNTRL'],
    'Fighters/Strike': ['VIPER', 'DUKE', 'BOLT', 'F15', 'F16', 'F35', 'NIGHT', 'SHUCK', 'TABOR']
}

NEWS_SOURCES = {
    'Emirates': 'https://www.emirates.com/english/help/travel-updates/',
    'flydubai': 'https://www.flydubai.com/en/contact/operational-updates',
    'Jazeera': 'https://www.jazeeraairways.com/en-kw/media-centre'
}

STATE_FILE = "state.json"

def get_region(lat, lon):
    for name, b in REGIONS.items():
        if b['lamin'] <= lat <= b['lamax'] and b['lomin'] <= lon <= b['lomax']:
            return name
    return "Other/Intl"

def get_news_updates(old_hashes):
    updates, new_hashes = {}, {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    for name, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=15)
            h = hashlib.md5(res.text.encode()).hexdigest()
            new_hashes[name] = h
            status_text = "🆕 NEW UPDATE" if old_hashes.get(name) != h else "no updates"
            updates[name] = {"status": status_text, "url": url}
        except:
            updates[name] = {"status": "error", "url": url}
            new_hashes[name] = old_hashes.get(name)
    return updates, new_hashes

def send_tg(message, level="INFO"):
    token, chat_id = os.environ.get('TG_TOKEN'), os.environ.get('TG_CHAT_ID')
    icons = {"RED": "🔴 RED ALERT", "BLUE": "🔵 BLUE STATUS", "GREEN": "🟢 GREEN STATUS"}
    msg = f"{icons.get(level, '🔍')}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: state = json.load(f)
    else: state = {"civ_iran": 0, "mil_reg": 0, "news_hashes": {}}

    news_status, updated_hashes = get_news_updates(state.get('news_hashes', {}))
    
    try:
        r = requests.get("https://opensky-network.org/api/states/all", params=STRATEGIC_BOUNDS, timeout=25)
        states = r.json().get('states', []) or []
    except: states = []

    civ_count, mil_total, tankers_count = 0, 0, 0
    mil_data = {group: {} for group in MIL_GROUPS}

    for s in states:
        callsign, lon, lat = (s[1] or "").strip().upper(), s[5], s[6]
        region = get_region(lat, lon)
        is_mil = False
        for

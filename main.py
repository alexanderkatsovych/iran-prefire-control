import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta

# --- КОНФИГУРАЦИЯ ---
AIRLINES = {'UAE': 'Emirates', 'FDB': 'flydubai', 'JZR': 'Jazeera'}
NEWS_SOURCES = {
    'Emirates': 'https://www.emirates.com/english/help/travel-updates/',
    'flydubai': 'https://www.flydubai.com/en/contact/operational-updates',
    'Jazeera': 'https://www.jazeeraairways.com/en-kw/media-centre'
}
KEYWORDS_SUSPENSION = ['suspended', 'until', 'avoid', 'temporary stop', 'interrupted', 'canceled']
MIL_CALLSIGNS = ['FORTE', 'LAGR', 'NCHO', 'GOLD', 'QUID', 'RCH', 'VIPER', 'DUKE', 'BOLT']

# Зоны (Стратегическая и Иран)
STRATEGIC_BOUNDS = {'lamin': 12.0, 'lomin': 34.0, 'lamax': 42.0, 'lomax': 65.0}
IRAN_BOUNDS = {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.0}
STATE_FILE = "state.json"

def send_tg(message, level="INFO"):
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    if level == "RED":
        emoji = "🔴 **CRITICAL ALERT**"
    elif level == "YELLOW":
        emoji = "⚠️ **WARNING**"
    else:
        emoji = "🔍 **SYSTEM CHECK**"
    
    msg = f"{emoji}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'})

def update_airline_news():
    suspended = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    print("--- Проверка новостей авиакомпаний ---")
    for comp, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=15)
            content = res.text.lower()
            found = 'iran' in content and any(w in content for w in KEYWORDS_SUSPENSION)
            print(f"[{comp}]: {'Найдена приостановка' if found else 'Новостей нет'}")
            if found: suspended.append(comp)
        except Exception as e:
            print(f"[{comp}]: Ошибка доступа: {e}")
    return suspended

if __name__ == "__main__":
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: history = json.load(f)
    else: history = {"counts": [], "suspended": [], "last_alert": 0}

    # 1. Сбор новостей
    current_suspended = update_airline_news()
    active_monitored = {k: v for k, v in AIRLINES.items() if v not in current_suspended}

    # 2. Сбор данных OpenSky
    print("\n--- Запрос данных из OpenSky ---")
    try:
        r = requests.get("https://opensky-network.org/api/states/all", params=STRATEGIC_BOUNDS, timeout=25)
        states = r.json().get('states', []) or []
    except Exception as e:
        print(f"Ошибка OpenSky: {e}")
        states = []

    civ_in_iran = []
    mil_active = []
    squawks = []

    for s in states:
        callsign = (s[1] or "").strip()
        lon, lat, squawk = s[5], s[6], s[14]

        if squawk in ['7700', '7500', '7600']:
            squawks.append(f"{callsign} ({squawk})")

        if any(m in callsign for m in MIL_CALLSIGNS):
            mil_active.append(callsign)
        
        if callsign[:3] in active_monitored:
            if IRAN_BOUNDS['lamin'] <= lat <= IRAN_BOUNDS['lamax'] and IRAN_BOUNDS['lomin'] <= lon <= IRAN_BOUNDS['lomax']:
                civ_in_iran.append(callsign)

    print(f"Гражданских в Иране: {len(civ_in_iran)}")
    print(f"Военных в зоне: {len(mil_active)}")

    # 3. Система баллов
    score = 0
    reasons = []

    if squawks:
        score += 10
        reasons.append(f"🚨 SOS: Сигналы бедствия {', '.join(squawks)}")

    civ_count = len(civ_in_iran)
    if active_monitored and civ_count == 0:
        score += 10
        reasons.append("🚨 Небо Ирана пусто для активных компаний.")
    
    if len(mil_active) >= 4:
        score += 6
        reasons.append(f"🛡 Активность ВВС: {len(mil_active)} бортов в зоне.")

    # 4. ЛОГИКА ОТЧЕТА (Для проверки)
    if score >= 9:
        send_tg("\n".join(reasons), level="RED")

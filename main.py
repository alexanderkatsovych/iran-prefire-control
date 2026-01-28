import requests
import os
import json
import hashlib
from bs4 import BeautifulSoup
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
    # Расширенные заголовки для обхода простых блокировок (как у flydubai) 
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    }
    for name, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                # Используем BeautifulSoup для извлечения только видимого текста 
                soup = BeautifulSoup(res.text, 'html.parser')
                # Удаляем скрипты и стили, которые создают "шум" 
                for script in soup(["script", "style"]):
                    script.decompose()
                clean_text = soup.get_text()
                
                h = hashlib.md5(clean_text.encode()).hexdigest()
                new_hashes[name] = h
                status_text = "🆕 NEW UPDATE / НОВОЕ ОБНОВЛЕНИЕ" if old_hashes.get(name) != h else "no updates / нет новостей"
                updates[name] = {"status": status_text, "url": url}
            elif res.status_code == 403:
                updates[name] = {"status": "protected/no access", "url": url}
                new_hashes[name] = old_hashes.get(name)
            else:
                updates[name] = {"status": f"code {res.status_code}", "url": url}
                new_hashes[name] = old_hashes.get(name)
        except Exception as e:
            updates[name] = {"status": "connection issue", "url": url}
            new_hashes[name] = old_hashes.get(name)
    return updates, new_hashes

def send_tg(message, level="INFO"):
    token, chat_id = os.environ.get('TG_TOKEN'), os.environ.get('TG_CHAT_ID')
    icons = {"RED": "🔴 RED ALERT / КРИТИЧЕСКИЙ УРОВЕНЬ", "BLUE": "🔵 BLUE STATUS / ВНИМАНИЕ", "GREEN": "🟢 GREEN STATUS / НОРМА"}
    msg = f"{icons.get(level, '🔍')}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': False})

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
        for group, tags in MIL_GROUPS.items():
            if any(t in callsign for t in tags):
                mil_data[group][region] = mil_data[group].get(region, 0) + 1
                mil_total += 1
                is_mil = True
                if group == 'Tankers (Hidden +6)': tankers_count += 1
                break
        if not is_mil and region == 'Iran': civ_count += 1

    prev_civ, prev_mil = state.get('civ_iran', 0), state.get('mil_reg', 0)
    civ_diff = ((civ_count - prev_civ) / prev_civ * 100) if prev_civ > 0 else 0
    mil_total_real = sum(sum(r.values()) for r in mil_data.values())
    mil_diff = ((mil_total_real - prev_mil) / prev_mil * 100) if prev_mil > 0 else 0
    hidden_fighters = tankers_count * 6

    # ЛОГИКА ОЦЕНКИ
    level = "GREEN"
    reasons = []
    if civ_count <= 2: 
        level = "RED"
        reasons.append("🚨 EMPTY SKY / НЕБО ПУСТО (0-2)")
    elif civ_diff <= -30: 
        level = "RED"
        reasons.append(f"🚨 TRAFFIC COLLAPSE / ОБВАЛ ТРАФИКА ({abs(civ_diff):.1f}%)")
    elif mil_diff >= 15 or tankers_count >= 3: 
        level = "BLUE"
        reasons.append("⚠️ HIGH MIL ACTIVITY / АКТИВНОСТЬ ВВС")

    # СБОРКА ОТЧЕТА (Bilingual) 
    report = "🇮🇷 **REGULAR AVIATION / ГРАЖДАНСКИЕ:**\n"
    report += f"• Iran/Иран: {civ_count} ({civ_diff:+.1f}%)\n\n"
    
    report += f"🌍 **MILITARY / ВОЕННЫЕ ({mil_diff:+.1f}%):**\n"
    for group, regions in mil_data.items():
        loc_str = ", ".join([f"{count} in {reg}" for reg, count in regions.items()]) if regions else "none"
        report += f"• {group}: {loc_str}\n"
    
    if hidden_fighters > 0:
        report += f"• **Est. hidden fighters / Скрытые истребители: +{hidden_fighters}**\n\n"

    report += f"📰 **NEWS / НОВОСТИ:**\n"
    for comp, data in news_status.items():
        if "NEW UPDATE" in data['status']:
            report += f"• [{comp}]({data['url']}): {data['status']}\n"
        else:
            report += f"• {comp}: {data['status']}\n"

    if reasons:
        report += f"\n📋 **ANALYSIS / АНАЛИЗ:**\n" + "\n".join([f"• {r}" for r in reasons])

    # Сохранение и отправка
    state.update({"civ_iran": civ_count, "mil_reg": mil_total_real, "news_hashes": updated_hashes})
    with open(STATE_FILE, "w") as f: json.dump(state, f)
    send_tg(report, level=level)

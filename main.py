
import json
from datetime import datetime, timezone

# --- CONFIGURATION (BILINGUAL) ---
REGIONS = {
    'Iran / Иран': {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.0},
    'Israel / Израиль': {'lamin': 29.5, 'lomin': 34.2, 'lamax': 33.3, 'lomax': 35.9},'Diego Garcia / Диего-Гарсия': {'lamin': -8.0, 'lomin': 71.0, 'lamax': -6.0, 'lomax': 73.0}
}

STRATEGIC_BOUNDS = {'lamin': -10.0, 'lomin': 33.0, 'lamax': 45.0, 'lomax': 75.0}

# Расширенные группы: добавили иранские военные префиксы
MIL_GROUPS = {
    'Tankers / Заправщики': ['LAGR', 'QUID', 'GOLD', 'K35R', 'TKRR', 'NACHO', 'IRAF'],
    'Strategic Bombers / Бомбардировщики': ['DEATH', 'MYSTIC', 'REAPER', 'FURY', 'BONE', 'DARK', 'MYTEE', 'DOOM', 'SKULL'],
    'Intelligence/UAV / Разведка/БПЛА': ['FORTE', 'MQ9', 'GHAWK', 'VEXL', 'HAWK', 'JAKE'],
    'Helicopters/SOF / Вертолеты/Спецназ': ['STALK', 'DUST', 'EVAC', 'MOJO', 'COWBOY', 'HUEY', 'KNIFE'],
    'Transport/Cargo / Транспорт/Грузовые': ['RCH', 'C130', 'C17', 'C5', 'CN235', 'SAHA', 'POUYA', 'FARS', 'IRGC'],
    'Fighters/Strike / Истребители/Штурмовики': ['VIPER', 'DUKE', 'BOLT', 'F15', 'F16', 'F35', 'NIGHT', 'SHUCK', 'TABOR', 'IRAF', 'MERAJ']
}

STATE_FILE = "state.json"

def get_region(lat, lon):
    for name, b in REGIONS.items():
        if b['lamin'] <= lat <= b['lamax'] and b['lomin'] <= lon <= b['lomax']:
            return name
    return "Other/Intl / Другие"

def send_tg(message, level="INFO"):
    token, chat_id = os.environ.get('TG_TOKEN'), os.environ.get('TG_CHAT_ID')
    icons = {"RED": "🔴 RED ALERT / КРИТИЧЕСКИЙ", "BLUE": "🔵 BLUE STATUS / ВНИМАНИЕ", "GREEN": "🟢 GREEN STATUS / НОРМА"}
    msg = f"{icons.get(level, '🔍')}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: state = json.load(f)
    else: state = {"civ_iran": 0, "mil_reg": 0}

    try:
        r = requests.get("https://opensky-network.org/api/states/all", params=STRATEGIC_BOUNDS, timeout=25)
        states = r.json().get('states', []) or []
    except: states = []

    civ_count, tankers_count = 0, 0
    mil_by_region = {reg: {group: [] for group in MIL_GROUPS} for reg in REGIONS}

    for s in states:
        callsign, lon, lat = (s[1] or "").strip().upper(), s[5], s[6]
        region = get_region(lat, lon)
        
        if region in mil_by_region:
            is_mil = False
            for group, tags in MIL_GROUPS.items():
                if any(callsign.startswith(t) for t in tags):
                    mil_by_region[region][group].append(callsign)
                    is_mil = True
                    if group == 'Tankers / Заправщики': tankers_count += 1
                    break
            
            if not is_mil and region == 'Iran / Иран': civ_count += 1

    # Динамика
    prev_civ, prev_mil = state.get('civ_iran', 0), state.get('mil_reg', 0)
    civ_diff = ((civ_count - prev_civ) / prev_civ * 100) if prev_civ > 0 else 0
    mil_total_now = sum(len(calls) for reg in mil_by_region.values() for calls in reg.values())
    mil_diff = ((mil_total_now - prev_mil) / prev_mil * 100) if prev_mil > 0 else 0
    
    level = "GREEN"
    reasons = []
    if civ_count <= 2 or (civ_diff <= -30 and prev_civ > 10):
        level = "RED"
        reasons.append("🚨 TRAFFIC ANOMALY / АНОМАЛИЯ ТРАФИКА")
    elif mil_diff >= 15 or tankers_count >= 3:
        level = "BLUE"
        reasons.append("⚠️ MIL ACTIVITY / АКТИВНОСТЬ ВВС")

    report = f"🇮🇷 **REGULAR / ГРАЖДАНСКИЕ:**\n• Iran / Иран: {civ_count} ({civ_diff:+.1f}%)\n\n"
    report += f"⚔️ **MILITARY / ВОЕННЫЕ ({mil_diff:+.1f}%):**\n"
    
    # Все регионы и группы всегда видны (чек-лист)
    for reg in REGIONS.keys():
        groups = mil_by_region[reg]
        report += f"📍 **{reg}**\n"
        for group, calls in groups.items():
            status = f"{len(calls)} ✈️ ({', '.join(calls)})" if calls else "0"
            report += f"  └ {group}: {status}\n"
        report += "\n"
    
    if tankers_count > 0: report += f"• **Est. stealth fighters / Скрытые истребители: +{tankers_count * 6}**\n"
    if reasons: report += f"\n📋 **ANALYSIS / АНАЛИЗ:**\n" + "\n".join([f"• {r}" for r in reasons])

    state.update({"civ_iran": civ_count, "mil_reg": mil_total_now})
    with open(STATE_FILE, "w") as f: json.dump(state, f)
    send_tg(report, level=level)

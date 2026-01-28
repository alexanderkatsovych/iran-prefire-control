import requests
import os
import json
from datetime import datetime, timezone

# --- КОНФИГУРАЦИЯ ЗОН / REGIONS CONFIG ---
REGIONS = {
    'Iran / Иран': {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.0},
    'Israel / Израиль': {'lamin': 29.5, 'lomin': 34.2, 'lamax': 33.3, 'lomax': 35.9},
    'Iraq / Ирак': {'lamin': 29.0, 'lomin': 38.0, 'lamax': 37.5, 'lomax': 48.5},
    'Jordan / Иордания': {'lamin': 29.0, 'lomin': 35.0, 'lamax': 33.0, 'lomax': 39.0},
    'Qatar / Катар': {'lamin': 24.2, 'lomin': 50.4, 'lamax': 26.6, 'lomax': 51.7},
    'Gulf of Aden / Аденский залив': {'lamin': 10.0, 'lomin': 43.0, 'lamax': 15.0, 'lomax': 51.0},
    'Diego Garcia / Диего-Гарсия': {'lamin': -8.0, 'lomin': 71.0, 'lamax': -6.0, 'lomax': 73.0}
}

STRATEGIC_BOUNDS = {'lamin': -10.0, 'lomin': 33.0, 'lamax': 45.0, 'lomax': 75.0}

# --- ВОЕННЫЕ ГРУППЫ / MILITARY GROUPS ---
MIL_GROUPS = {
    'Tankers / Заправщики': ['LAGR', 'QUID', 'GOLD', 'K35R', 'TKRR', 'NACHO'],
    'Strategic Bombers / Бомбардировщики': ['DEATH', 'MYSTIC', 'REAPER', 'FURY', 'BONE', 'DARK', 'MYTEE', 'DOOM', 'SKULL'],
    'Intelligence/UAV / Разведка/БПЛА': ['FORTE', 'MQ9', 'GHAWK', 'VEXL', 'HAWK', 'JAKE'],
    'Helicopters/SOF / Вертолеты/Спецназ': ['STALK', 'DUST', 'EVAC', 'MOJO', 'COWBOY', 'HUEY', 'KNIFE'],
    'Transport/Cargo / Транспорт/Грузовые': ['RCH', 'C130', 'C17', 'C5', 'CN235', 'CNTRL'],
    'Fighters/Strike / Истребители/Штурмовики': ['VIPER', 'DUKE', 'BOLT', 'F15', 'F16', 'F35', 'NIGHT', 'SHUCK', 'TABOR']
}

STATE_FILE = "state.json"

def get_region(lat, lon):
    for name, b in REGIONS.items():
        if b['lamin'] <= lat <= b['lamax'] and b['lomin'] <= lon <= b['lomax']:
            return name
    return "Other/Intl / Другие"

def send_tg(message, level="INFO"):
    token, chat_id = os.environ.get('TG_TOKEN'), os.environ.get('TG_CHAT_ID')
    icons = {
        "RED": "🔴 RED ALERT / КРИТИЧЕСКИЙ УРОВЕНЬ",
        "BLUE": "🔵 BLUE STATUS / ВНИМАНИЕ",
        "GREEN": "🟢 GREEN STATUS / НОРМА"
    }
    msg = f"{icons.get(level, '🔍')}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: state = json.load(f)
    else: state = {"civ_iran": 0, "mil_reg": 0}

    try:
        r = requests.get("https://opensky-network.org/api/states/all", params=STRATEGIC_BOUNDS, timeout=25)
        states = r.json().get('states', []) or []
    except: states = []

    civ_count, tankers_count = 0, 0
    # mil_structure: { Group: { Region: [Callsigns] } }
    mil_structure = {group: {} for group in MIL_GROUPS}

    for s in states:
        callsign, lon, lat = (s[1] or "").strip().upper(), s[5], s[6]
        region = get_region(lat, lon)
        is_mil = False
        
        for group, tags in MIL_GROUPS.items():
            if any(t in callsign for t in tags):
                if region not in mil_structure[group]:
                    mil_structure[group][region] = []
                mil_structure[group][region].append(callsign)
                is_mil = True
                if group == 'Tankers / Заправщики': tankers_count += 1
                break
        
        if not is_mil and region == 'Iran / Иран':
            civ_count += 1

    # Анализ динамики
    prev_civ = state.get('civ_iran', 0)
    civ_diff = ((civ_count - prev_civ) / prev_civ * 100) if prev_civ > 0 else 0
    mil_total_now = sum(len(calls) for g in mil_structure.values() for calls in g.values())
    prev_mil = state.get('mil_reg', 0)
    mil_diff = ((mil_total_now - prev_mil) / prev_mil * 100) if prev_mil > 0 else 0
    hidden_fighters = tankers_count * 6

    # Уровни угрозы
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

    # Сборка отчета
    report = "🇮🇷 **REGULAR / ГРАЖДАНСКИЕ:**\n"
    report += f"• Iran / Иран: {civ_count} ({civ_diff:+.1f}%)\n\n"
    
    report += f"⚔️ **MILITARY / ВОЕННЫЕ ({mil_diff:+.1f}%):**\n"
    found_mil = False
    for group, regions in mil_structure.items():
        if not regions: continue
        found_mil = True
        report += f"• **{group}**\n"
        for reg, calls in regions.items():
            calls_str = ", ".join(calls)
            report += f"  └ 📍 {reg}: {len(calls)} ✈️ ({calls_str})\n"
    
    if not found_mil:
        report += "• No military aircraft detected / Военных бортов не обнаружено\n"
    
    if hidden_fighters > 0:
        report += f"\n• **Est. hidden fighters / Скрытые истребители: +{hidden_fighters}**\n"

    if reasons:
        report += f"\n📋 **ANALYSIS / АНАЛИЗ:**\n" + "\n".join([f"• {r}" for r in reasons])

    # Сохранение и отправка
    state.update({"civ_iran": civ_count, "mil_reg": mil_total_now})
    with open(STATE_FILE, "w") as f: json.dump(state, f)
    send_tg(report, level=level)

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
MIL_CALLSIGNS = ['FORTE', 'LAGR', 'NCHO', 'GOLD', 'QUID', 'RCH', 'VIPER', 'DUKE']

# Зоны мониторинга (LaTeX формат для точности)
# Стратегическая зона: $12.0^\circ N - 42.0^\circ N, 34.0^\circ E - 65.0^\circ E$
STRATEGIC_BOUNDS = {'lamin': 12.0, 'lomin': 34.0, 'lamax': 42.0, 'lomax': 65.0}
# Границы Ирана: $24.0^\circ N - 40.0^\circ N, 44.0^\circ E - 63.0^\circ E$
IRAN_BOUNDS = {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.0}

STATE_FILE = "state.json"

def send_tg(message, level="GREEN"):
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    emoji = "🔴 **STRATEGIC RED ALERT**" if level == "RED" else "🟢 **REGIONAL STATUS**"
    msg = f"{emoji}\n\n{message}\n\n🕒 _UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}_"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'})

def update_airline_news():
    suspended = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for comp, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=15)
            content = res.text.lower()
            if 'iran' in content and any(w in content for w in KEYWORDS_SUSPENSION):
                suspended.append(comp)
        except: continue
    return suspended

if __name__ == "__main__":
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: history = json.load(f)
    else: history = {"counts": [], "suspended": [], "last_alert": 0}

    # 1. Адаптивный фильтр компаний
    current_suspended = update_airline_news()
    active_monitored = {k: v for k, v in AIRLINES.items() if v not in current_suspended}

    # 2. Сбор данных из расширенной зоны
    try:
        r = requests.get("https://opensky-network.org/api/states/all", params=STRATEGIC_BOUNDS, timeout=25)
        states = r.json().get('states', []) or []
    except: states = []

    # Разделение трафика
    civ_in_iran = [s[1].strip() for s in states if s[1] and s[1].strip()[:3] in active_monitored 
                   and IRAN_BOUNDS['lamin'] <= s[6] <= IRAN_BOUNDS['lamax'] 
                   and IRAN_BOUNDS['lomin'] <= s[5] <= IRAN_BOUNDS['lomax']]
    
    mil_active = [s[1].strip() for s in states if s[1] and any(m in s[1].strip() for m in MIL_CALLSIGNS)]
    
    # 3. Аналитика
    score = 0
    reasons = []
    
    # Новое официальное закрытие
    for comp in current_suspended:
        if comp not in history.get("suspended", []):
            send_tg(f"ℹ️ **ОФИЦИАЛЬНО**: {comp} подтвердили приостановку полетов над Ираном.")

    # Детектор пустого неба (только если компании "активны")
    civ_count = len(civ_in_iran)
    if active_monitored and civ_count == 0:
        score += 8
        reasons.append("🚨 **ОПУСТЕВШИЙ ТРАНЗИТ**: Активные компании не входят в небо Ирана.")
    
    # Анализ 3-часового тренда (проверка каждые 15 мин * 12 = 3 часа)
    tehran_hour = (datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)).hour
    if 6 <= tehran_hour <= 23 and len(history["counts"]) >= 12:
        avg_3h = sum(history["counts"][-12:]) / 12
        if civ_count < avg_3h / 3 and avg_3h > 3:
            score += 6
            reasons.append(f"📉 Резкий спад трафика: сейчас {civ_count} (3ч среднее ~{int(avg_3h)}).")

    # Военная активность
    if len(mil_active) >= 3:
        score += 5
        reasons.append(f"🛡 **OSINT**: В стратегической зоне {len(mil_active)} бортов (заправщики/разведка).")

    # 4. Финальный вывод
    if score >= 8:
        send_tg("\n".join(reasons), level="RED")
    elif score >= 5 and (time.time() - history.get('last_alert', 0) > 3600):
        send_tg("⚠️ Подозрительная активность:\n" + "\n".join(reasons), level="GREEN")
        history['last_alert'] = time.time()
    elif datetime.now(timezone.utc).hour % 3 == 0 and datetime.now(timezone.utc).minute < 15:
        send_tg(f"Регион стабилен.\nРейсов в Иране: {civ_count}\nАктивных ВВС: {len(mil_active)}", level="GREEN")

    # Сохранение состояния
    history["suspended"] = current_suspended
    history["counts"].append(civ_count)
    if len(history["counts"]) > 24: history["counts"].pop(0)
    with open(STATE_FILE, "w") as f: json.dump(history, f)

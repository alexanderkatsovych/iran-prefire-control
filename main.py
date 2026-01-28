import requests
from bs4 import BeautifulSoup
import os

# --- НАСТРОЙКИ ---
AIRLINES = {'UAE': 'Emirates', 'FDB': 'flydubai', 'JZR': 'Jazeera'}
IRAN_BOUNDS = {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.5}
NEWS_SOURCES = {
    'Emirates': 'https://www.emirates.com/english/help/travel-updates/',
    'flydubai': 'https://www.flydubai.com/en/plan/travel-updates',
    'Jazeera': 'https://www.jazeeraairways.com/en-kw/media-centre'
}
KEYWORDS = ['Iran', 'airspace', 'reroute', 'suspension', 'Tehran', 'closed']

def send_tg(message):
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    if not token or not chat_id:
        print("Ошибка: Токены не найдены!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    requests.post(url, data=payload)

def get_live_flights():
    url = "https://opensky-network.org/api/states/all"
    try:
        r = requests.get(url, params=IRAN_BOUNDS, timeout=20)
        states = r.json().get('states', [])
        if not states: return []
        return [f"{AIRLINES[s[1].strip()[:3]]} ({s[1].strip()})" for s in states if s[1].strip()[:3] in AIRLINES]
    except: return None

def check_news():
    headers = {'User-Agent': 'Mozilla/5.0'}
    alerts = []
    for comp, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if any(w.lower() in res.text.lower() for w in KEYWORDS):
                alerts.append(f"🔔 *{comp}*: Есть новости по Ирану!")
        except: continue
    return alerts

if __name__ == "__main__":
    # Проверка рейсов
    flights = get_live_flights()
    if flights is not None:
        if len(flights) == 0:
            send_tg("⚠️ *В небе Ирана пусто.* Выбранные компании сейчас там не летят.")
        else:
            send_tg("✈️ *Рейсы в небе Ирана:*\n" + "\n".join(set(flights)))

    # Проверка новостей
    for n in check_news():
        send_tg(n)

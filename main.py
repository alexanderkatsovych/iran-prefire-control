import requests
from bs4 import BeautifulSoup
import os

# --- НАСТРОЙКИ ---
AIRLINES = {'UAE': 'Emirates', 'FDB': 'flydubai', 'JZR': 'Jazeera'}
# Координаты Ирана (Bounding Box)
IRAN_BOUNDS = {'lamin': 24.0, 'lomin': 44.0, 'lamax': 40.0, 'lomax': 63.5}
# Источники новостей
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
        print("Ошибка: Токены Telegram не найдены в Secrets!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    requests.post(url, data=payload)

def get_live_flights():
    """Проверка живых рейсов над Ираном через OpenSky"""
    url = "https://opensky-network.org/api/states/all"
    try:
        r = requests.get(url, params=IRAN_BOUNDS, timeout=20)
        data = r.json()
        states = data.get('states', [])
        if not states:
            return []
        
        found = []
        for s in states:
            callsign = s[1].strip()
            code = callsign[:3]
            if code in AIRLINES:
                found.append(f"{AIRLINES[code]} ({callsign})")
        return found
    except Exception as e:
        print(f"Ошибка OpenSky: {e}")
        return None

def check_news():
    """Скрейпинг сайтов авиакомпаний"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    found_alerts = []
    for company, url in NEWS_SOURCES.items():
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            text = soup.get_text().lower()
            
            triggered = [w for w in KEYWORDS if w.lower() in text]
            if triggered:
                found_alerts.append(f"🔔 *{company}*: Обнаружены слова {', '.join(triggered)} на странице обновлений.")
        except:
            continue
    return found_alerts

if __name__ == "__main__":
    # 1. Проверяем небо
    flights = get_live_flights()
    
    # Логика: если рейсов 0, а обычно они есть - это повод проверить вручную
    if flights is not None:
        if len(flights) == 0:
            # Не отправляем сообщение постоянно, только логируем в Actions
            print("В небе Ирана сейчас пусто для выбранных компаний.")
        else:
            msg = "✈️ *Рейсы над Ираном сейчас:*\n" + "\n".join(flights)
            print(msg)
            # Раскомментируйте строку ниже, если хотите получать отчет при каждом запуске
            # send_tg(msg)

    # 2. Проверяем новости
    news = check_news()
    if news:
        for n in news:
            send_tg(n)

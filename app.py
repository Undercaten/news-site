import time
import json
import re
import threading
import os
import requests
import feedparser
import schedule
from datetime import datetime
from flask import Flask, send_file, jsonify
from google import genai

app = Flask(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client(api_key=api_key.strip())

last_status = "Сервер запустился, ожидание первой загрузки..."

SOURCES = [
    # Государственные / Федеральные / Телеканалы
    {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml"},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml"},
    {"name": "RT на русском", "url": "https://russian.rt.com/rss"},
    {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml"},
    {"name": "Российская газета", "url": "https://rg.ru/xml/index.xml"},
    {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news"},
    {"name": "Взгляд", "url": "https://vz.ru/rss.xml"},
    {"name": "Царьград", "url": "https://tsargrad.tv/news/rss"},
    {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp"},
    {"name": "Вести", "url": "https://www.vesti.ru/vesti.rss"},
    {"name": "Первый канал", "url": "https://www.1tv.ru/news/rss"},
    {"name": "НТВ", "url": "https://www.ntv.ru/exp/news.rss"},
    {"name": "Комсомольская правда", "url": "https://www.kp.ru/rss/all.xml"},
    {"name": "Московский комсомолец", "url": "https://www.mk.ru/rss/news/index.xml"},
    {"name": "АиФ", "url": "https://aif.ru/rss/all.php"},
    {"name": "Regnum", "url": "https://regnum.ru/rss"},
    {"name": "Пятый канал", "url": "https://www.5-tv.ru/news/rss/"},
    {"name": "Life.ru", "url": "https://life.ru/rss"},
    
    # Деловые / Умеренные / IT
    {"name": "РБК", "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"},
    {"name": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/news.xml"},
    {"name": "Ведомости", "url": "https://www.vedomosti.ru/rss/news"},
    {"name": "Forbes Russia", "url": "https://www.forbes.ru/new_rss.xml"},
    {"name": "Независимая газета", "url": "https://www.ng.ru/rss/"},
    {"name": "Росбалт", "url": "https://www.rosbalt.ru/feed/"},
    {"name": "BFM", "url": "https://www.bfm.ru/news.rss"},
    {"name": "Газета.Ru", "url": "https://www.gazeta.ru/export/rss/lenta.xml"},
    {"name": "Сноб", "url": "https://snob.ru/rss/"},
    {"name": "Фонтанка", "url": "https://www.fontanka.ru/fontanka.rss"},
    {"name": "Эксперт", "url": "https://expert.ru/rss/"},
    {"name": "Секрет Фирмы", "url": "https://secretmag.ru/export/rss.xml"},
    {"name": "Хабр", "url": "https://habr.com/ru/rss/news/"},
    {"name": "VC.ru", "url": "https://vc.ru/rss"},
    {"name": "3DNews", "url": "https://3dnews.ru/news/rss/"},
    {"name": "N+1", "url": "https://nplus1.ru/rss"},
    {"name": "RTVI", "url": "https://rtvi.com/rss/"},
    {"name": "E1.ru", "url": "https://www.e1.ru/text/rss/"},
    
    # Независимые / Иностранные / Оппозиционные
    {"name": "Meduza", "url": "https://meduza.io/rss/all"},
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/russian/rss.xml"},
    {"name": "Радио Свобода", "url": "https://www.svoboda.org/api/z$qtiu_mqp"},
    {"name": "DW на русском", "url": "https://rss.dw.com/xml/rss-ru-all"},
    {"name": "Новая газета Европа", "url": "https://novayagazeta.eu/feed/rss"},
    {"name": "Медиазона", "url": "https://zona.media/rss"},
    {"name": "Настоящее Время", "url": "https://www.currenttime.tv/api/z-pqpiev-q"},
    {"name": "Голос Америки", "url": "https://www.golosameriki.com/api/z-pqqier-q"},
    {"name": "The Insider", "url": "https://theins.ru/feed"},
    {"name": "The Moscow Times", "url": "https://www.themoscowtimes.com/ru/rss"},
    {"name": "ОВД-Инфо", "url": "https://ovd.news/rss.xml"},
    {"name": "Холод", "url": "https://holod.media/feed/"},
    {"name": "Бумага", "url": "https://paperpaper.ru/feed/"},
]

def fetch_and_update_news():
    global last_status
    last_status = f"[{datetime.now().strftime('%H:%M:%S')}] Начат сбор новостей..."
    print(last_status, flush=True)
    
    if not client:
        last_status = "❌ Ошибка: Не задан GEMINI_API_KEY в Environment Variables"
        print(last_status, flush=True)
        return

    current_time = time.time()
    active_topics = {}
    existing_theme_names = []

    if os.path.exists('news_data.json'):
        try:
            with open('news_data.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                for topic in old_data:
                    if current_time - topic.get("added_at", current_time) < 86400:
                        active_topics[topic["theme"]] = topic
                        existing_theme_names.append(topic["theme"])
        except Exception:
            pass

    articles = []
    for source in SOURCES:
        try:
            res = requests.get(source["url"], timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
            if res.status_code == 200:
                feed = feedparser.parse(res.content)
                for entry in feed.entries[:3]:
                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": source["name"]
                    })
        except Exception:
            pass
            
    last_status = f"📥 Собрано {len(articles)} новых статей. Обработка ИИ..."
    print(last_status, flush=True)

    if not articles:
        return

    prompt = f"""
    Проанализируй список свежих новостей. Сгруппируй их по событиям.
    У нас уже есть текущие темы дня: {json.dumps(existing_theme_names, ensure_ascii=False)}
    ЕСЛИ новое событие относится к одной из этих тем, используй ТОЧНО ТАКОЕ ЖЕ название.
    Верни СТРОГО чистый JSON массив:
    [
      {{
        "theme": "Нейтральный заголовок",
        "articles": [
          {{"title": "Заголовок", "link": "URL", "source": "Издание"}}
        ]
      }}
    ]
    Свежие статьи: {json.dumps(articles, ensure_ascii=False)}
    """

    # Система повторных попыток при ошибке 503
    max_retries = 3
    response_text = None
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt
            )
            response_text = response.text
            break # Успешно получили ответ, выходим из цикла попыток
        except Exception as e:
            if '503' in str(e) or 'UNAVAILABLE' in str(e):
                if attempt < max_retries - 1:
                    print(f"⚠️ Сервер Google перегружен (503). Повтор через 10 сек... ({attempt + 1}/{max_retries})", flush=True)
                    time.sleep(10)
                else:
                    last_status = f"❌ Ошибка: Серверы Google недоступны после {max_retries} попыток."
                    print(last_status, flush=True)
                    return
            else:
                last_status = f"❌ Неизвестная ошибка ИИ: {e}"
                print(last_status, flush=True)
                return

    if not response_text:
        return

    try:
        match = re.search(r'\[.*\]', response_text, re.DOTALL)
        clean_json = match.group(0) if match else response_text
        new_clusters = json.loads(clean_json)

        for cluster in new_clusters:
            theme_name = cluster["theme"]
            if theme_name in active_topics:
                existing_links = {a["link"] for a in active_topics[theme_name]["articles"]}
                for art in cluster["articles"]:
                    if art["link"] not in existing_links:
                        active_topics[theme_name]["articles"].append(art)
            else:
                cluster["added_at"] = current_time
                active_topics[theme_name] = cluster

        final_data = []
        for t in active_topics.values():
            if len(t["articles"]) >= 3:
                final_data.append(t)
                
        final_data.sort(key=lambda x: x.get("added_at", 0), reverse=True)

        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        last_status = f"✅ Успех! Активных тем за 24ч: {len(final_data)}"
        print(last_status, flush=True)
    except Exception as e:
        last_status = f"❌ Ошибка парсинга JSON: {e}"
        print(last_status, flush=True)

def run_scheduler():
    fetch_and_update_news()
    schedule.every(15).minutes.do(fetch_and_update_news)
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/news_data.json')
def news_data():
    if not os.path.exists('news_data.json'):
        return jsonify([])
    return send_file('news_data.json')

@app.route('/status')
def status():
    return jsonify({"status": last_status})

@app.route('/run-now')
def run_now():
    threading.Thread(target=fetch_and_update_news).start()
    return "Сбор запущен. Проверьте /status через 30 секунд."

if __name__ == '__main__':
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
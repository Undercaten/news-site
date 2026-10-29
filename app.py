import socket
socket.setdefaulttimeout(5)

import time
import json
import re
import threading
import feedparser
import schedule
import os
import google.generativeai as genai
from datetime import datetime
from flask import Flask, send_file, jsonify

app = Flask(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key.strip())

SOURCES = [
    {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml"},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml"},
    {"name": "RT на русском", "url": "https://russian.rt.com/rss"},
    {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml"},
    {"name": "Российская газета", "url": "https://rg.ru/xml/index.xml"},
    {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news"},
    {"name": "Взгляд", "url": "https://vz.ru/rss.xml"},
    {"name": "Царьград", "url": "https://tsargrad.tv/news/rss"},
    {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp"},
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
]

def fetch_and_update_news():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Начинаю сбор новостей с 30 сайтов...", flush=True)
    
    if not api_key:
        print("❌ Ошибка: Переменная GEMINI_API_KEY не найдена в настройках!", flush=True)
        return

    articles = []
    for source in SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:4]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": source["name"]
                })
        except Exception:
            pass
            
    print(f"📥 Собрано {len(articles)} статей. Отправляю Gemini...", flush=True)

    prompt = f"""
    Проанализируй список новостных статей. Сгруппируй их по одинаковым событиям.
    Оставь ТОЛЬКО те темы, которые осветили как минимум 3 РАЗНЫХ источника.
    Верни СТРОГО чистый JSON массив без пояснений:
    [
      {{
        "theme": "Нейтральный безоценочный заголовок события",
        "articles": [
          {{"title": "Ориг. заголовок", "link": "URL", "source": "Издание"}}
        ]
      }}
    ]
    Статьи: {json.dumps(articles, ensure_ascii=False)}
    """

    # Список кандидатов названий моделей
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-latest']
    response_text = None

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            res = model.generate_content(prompt)
            if res and res.text:
                response_text = res.text
                print(f"Запрос успешно обработан моделью: {model_name}", flush=True)
                break
        except Exception as e:
            print(f"Модель {model_name} не подсоединилась: {e}", flush=True)

    if not response_text:
        print("❌ Ошибка: ни одна из моделей Gemini не вернула ответ.", flush=True)
        return

    try:
        # Вырезаем чисто JSON массив из ответа
        match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if match:
            clean_json = match.group(0)
            grouped_data = json.loads(clean_json)
        else:
            grouped_data = json.loads(response_text)

        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(grouped_data, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Успех! Создано {len(grouped_data)} сюжетов.", flush=True)
    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}", flush=True)

def run_scheduler():
    fetch_and_update_news()
    schedule.every(30).minutes.do(fetch_and_update_news)
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

if __name__ == '__main__':
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
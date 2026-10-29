import socket

# Защита: если какой-то новостной сайт упал, мы ждем его не более 5 секунд и идем дальше
socket.setdefaulttimeout(5)

import time
import json
import threading
import feedparser
import schedule
import os
import google.generativeai as genai
from datetime import datetime
from flask import Flask, send_file, jsonify

app = Flask(__name__)

# Ключ берется из скрытых настроек сервера (мы укажем его на Render)
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

SOURCES = [
    # Государственные и крупные федеральные
    {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml"},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml"},
    {"name": "RT на русском", "url": "https://russian.rt.com/rss"},
    {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml"},
    {"name": "Российская газета", "url": "https://rg.ru/xml/index.xml"},
    {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news"},
    {"name": "Взгляд", "url": "https://vz.ru/rss.xml"},
    {"name": "Царьград", "url": "https://tsargrad.tv/news/rss"},
    {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp"},
    # Деловые и умеренные
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
    # Независимые и международные
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
    articles = []

    for source in SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            # Берем по 4 свежие новости, чтобы ИИ было из чего выбирать совпадения
            for entry in feed.entries[:4]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": source["name"]
                })
        except Exception as e:
            print(f"Пропуск {source['name']} из-за таймаута или ошибки", flush=True)

    print(f"📥 Собрано {len(articles)} статей. Отправляю Gemini...", flush=True)

    prompt = f"""
    Проанализируй список новостных статей.
    Сгруппируй их по одинаковым событиям. 
    Оставь ТОЛЬКО те темы, которые осветили как минимум 3 РАЗНЫХ источника.

    Верни ответ СТРОГО в формате валидного JSON:
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

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        result_text = response.text.replace('```json', '').replace('```', '').strip()
        grouped_data = json.loads(result_text)

        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(grouped_data, f, ensure_ascii=False, indent=4)

        print(f"✅ Успех! Создано {len(grouped_data)} сюжетов.", flush=True)
    except Exception as e:
        print(f"❌ Ошибка ИИ: {e}", flush=True)


def run_scheduler():
    fetch_and_update_news()  # Сразу собираем при запуске
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
        # Если файл еще не создался, отдаем пустой массив
        return jsonify([])
    return send_file('news_data.json')


if __name__ == '__main__':
    # Запускаем сборщик в отдельном процессе
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    # Запускаем сайт
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
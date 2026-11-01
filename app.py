import time
import json
import os
import requests
import feedparser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, send_file, jsonify
from pymongo import MongoClient
import certifi

app = Flask(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
mongo_uri = os.environ.get("MONGO_URI")

# Подключение к облачной MongoDB (certifi предотвращает ошибки SSL на Render)
db_client = MongoClient(mongo_uri, tlsCAFile=certifi.where()) if mongo_uri else None
collection = db_client['vashinews']['articles'] if db_client else None

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
    {"name": "Вести", "url": "https://www.vesti.ru/vesti.rss"},
    {"name": "Первый канал", "url": "https://www.1tv.ru/news/rss"},
    {"name": "НТВ", "url": "https://www.ntv.ru/exp/news.rss"},
    {"name": "Комсомольская правда", "url": "https://www.kp.ru/rss/all.xml"},
    {"name": "Московский комсомолец", "url": "https://www.mk.ru/rss/news/index.xml"},
    {"name": "АиФ", "url": "https://aif.ru/rss/all.php"},
    {"name": "Regnum", "url": "https://regnum.ru/rss"},
    {"name": "Пятый канал", "url": "https://www.5-tv.ru/news/rss/"},
    {"name": "Life.ru", "url": "https://life.ru/rss"},
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
    {"name": "Михаил Смирнов", "url": "https://www.michael-smirnov.ru/feed/"}
]

def fetch_single_feed(source):
    articles = []
    try:
        # Серверы Render в США, поэтому скачиваем напрямую без прокси
        res = requests.get(source["url"], timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
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
    return articles

def fetch_and_update_news():
    if not api_key or collection is None:
        return "Ошибка: не заданы ключи API или MongoDB"

    current_time = time.time()
    active_topics = {}
    existing_theme_names = []

    # Чтение прошлых тем из облачной БД
    db_doc = collection.find_one({"_id": "news_cluster"})
    if db_doc and "data" in db_doc:
        old_data = db_doc["data"]
        for topic in old_data:
            if current_time - topic.get("added_at", current_time) < 86400:
                active_topics[topic["theme"]] = topic
                existing_theme_names.append(topic["theme"])

    articles = []
    
    # Многопоточный сбор
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_single_feed, src) for src in SOURCES]
        for future in as_completed(futures):
            result = future.result()
            if result:
                articles.extend(result)

    if not articles:
        return "Нет новых статей"

    prompt = f"""
    Ты - новостной редактор. Сгруппируй новости, описывающие СТРОГО ОДНО И ТО ЖЕ событие.
    Текущие темы: {json.dumps(existing_theme_names, ensure_ascii=False)}
    Если событие относится к существующей теме, используй ТОЧНО ТАКОЕ ЖЕ название.
    Выбери категорию: "Политика", "Технологии", "Наука", "Общество".

    Верни валидный массив JSON:
    [
      {{
        "theme": "Заголовок",
        "category": "Категория",
        "articles": [
          {{"title": "Название", "link": "URL", "source": "Издание"}}
        ]
      }}
    ]

    Статьи: {json.dumps(articles, ensure_ascii=False)}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    # Прямой запрос к Gemini без прокси
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=45)
        if res.status_code == 200:
            data = res.json()
            response_text = data['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Ошибка Gemini: {res.status_code}"
    except Exception as e:
        return f"Ошибка сети: {e}"

    if not response_text:
        return "Пустой ответ"

    try:
        new_clusters = json.loads(response_text)

        for cluster in new_clusters:
            theme_name = cluster.get("theme", "Без темы")
            category_name = cluster.get("category", "Общество")
            cluster_articles = cluster.get("articles", [])
            
            if theme_name in active_topics:
                existing_sources = {a["source"] for a in active_topics[theme_name]["articles"]}
                existing_links = {a["link"] for a in active_topics[theme_name]["articles"]}
                
                for art in cluster_articles:
                    src = art.get("source")
                    lnk = art.get("link")
                    if lnk not in existing_links and src not in existing_sources:
                        active_topics[theme_name]["articles"].append(art)
                        existing_sources.add(src)
                        existing_links.add(lnk)
            else:
                unique_articles = []
                seen_sources = set()
                for art in cluster_articles:
                    src = art.get("source")
                    if src not in seen_sources:
                        unique_articles.append(art)
                        seen_sources.add(src)
                        
                cluster["articles"] = unique_articles
                cluster["added_at"] = current_time
                cluster["category"] = category_name
                active_topics[theme_name] = cluster

        final_data = []
        for t in active_topics.values():
            if len(t["articles"]) >= 3:
                final_data.append(t)
                
        final_data.sort(key=lambda x: x.get("added_at", 0), reverse=True)

        # Сохранение в базу данных вместо файла
        collection.update_one(
            {"_id": "news_cluster"},
            {"$set": {"data": final_data, "updated_at": current_time}},
            upsert=True
        )
        return "Успешно обновлено!"
    except Exception as e:
        return f"Ошибка JSON: {e}"

@app.route('/')
def home():
    return send_file('index.html')

# Эмулируем отдачу JSON файла для фронтенда
@app.route('/news_data.json')
def news_data():
    if collection is not None:
        db_doc = collection.find_one({"_id": "news_cluster"})
        if db_doc and "data" in db_doc:
            return jsonify(db_doc["data"])
    return jsonify([])

# Маршрут для внешнего пинга cron-job
@app.route('/run-now')
def run_now():
    status = fetch_and_update_news()
    return jsonify({"status": status})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
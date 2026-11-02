import time
import json
import threading
import os
import requests
import feedparser
import schedule
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, send_file, jsonify

app = Flask(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
last_status = "Сервер запустился, ожидание первой загрузки..."

SOURCES = [
    # ==========================================
    # 1. УЖЕ ИСПОЛЬЗОВАННЫЕ ИСТОЧНИКИ (13)
    # ==========================================
    {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml"},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml"},
    {"name": "RT на русском", "url": "https://russian.rt.com/rss"},
    {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml"},
    {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news"},
    {"name": "РБК", "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"},
    {"name": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/news.xml"},
    {"name": "Ведомости", "url": "https://www.vedomosti.ru/rss/news"},
    {"name": "Газета.Ru", "url": "https://www.gazeta.ru/export/rss/lenta.xml"},
    {"name": "Сноб", "url": "https://snob.ru/rss/"},
    {"name": "Фонтанка", "url": "https://www.fontanka.ru/fontanka.rss"},
    {"name": "Хабр", "url": "https://habr.com/ru/rss/news/"},
    {"name": "VC.ru", "url": "https://vc.ru/rss"},

    # ==========================================
    # 2. ГОСУДАРСТВЕННЫЕ И ФЕДЕРАЛЬНЫЕ СМИ
    # ==========================================
    {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp"},
    {"name": "Российская газета", "url": "https://rg.ru/xml/index.xml"},
    {"name": "Московский комсомолец (МК)", "url": "https://www.mk.ru/rss/news/index.xml"},
    {"name": "Комсомольская правда (КП)", "url": "https://www.kp.ru/rss/all.xml"},
    {"name": "Аргументы и Факты (АиФ)", "url": "https://aif.ru/rss/all.php"},
    {"name": "НТВ", "url": "https://www.ntv.ru/export/rss.jsp"},
    {"name": "Вести.Ru", "url": "https://www.vesti.ru/vesti.rss"},
    {"name": "РЕН ТВ", "url": "https://ren.tv/export/rss.xml"},
    {"name": "Пятый канал", "url": "https://www.5-tv.ru/news/rss/"},
    {"name": "ТВ Центр", "url": "https://www.tvc.ru/channel/rss"},
    {"name": "Звезда", "url": "https://tvzvezda.ru/export/rss.xml"},
    {"name": "Взгляд", "url": "https://vz.ru/export/yandex.xml"},
    {"name": "Regnum", "url": "https://regnum.ru/rss"},
    {"name": "Росбалт", "url": "https://www.rosbalt.ru/feed/"},
    {"name": "Life.ru", "url": "https://life.ru/rss"},
    {"name": "Ридус", "url": "https://www.ridus.ru/rss.xml"},
    {"name": "Царьград", "url": "https://tsargrad.tv/export/yandex.xml"},
    {"name": "Свободная пресса", "url": "https://svpressa.ru/rss.xml"},
    {"name": "Парламентская газета", "url": "https://www.pnp.ru/rss/index.xml"},
    {"name": "Независимая газета", "url": "https://www.ng.ru/rss/"},
    {"name": "Профиль", "url": "https://profile.ru/feed/"},

    # ==========================================
    # 3. НЕЗАВИСИМЫЕ, ОППОЗИЦИОННЫЕ И ИНОСТРАННЫЕ (Читаются с Render без VPN)
    # ==========================================
    {"name": "Meduza", "url": "https://meduza.io/rss/all"},
    {"name": "Медиазона", "url": "https://zona.media/rss"},
    {"name": "BBC News Русская служба", "url": "https://feeds.bbci.co.uk/russian/rss.xml"},
    {"name": "Deutsche Welle (DW) на русском", "url": "https://rss.dw.com/xml/rss-ru-all"},
    {"name": "Радио Свобода", "url": "https://www.svoboda.org/api/zrqiteuhiq"},
    {"name": "The Insider", "url": "https://theins.ru/feed"},
    {"name": "Новая газета Европа", "url": "https://novayagazeta.eu/feed"},
    {"name": "Эхо", "url": "https://echofm.online/feed"},
    {"name": "Дождь (TV Rain)", "url": "https://tvrain.tv/export/rss/all.xml"},
    {"name": "Republic", "url": "https://republic.ru/export/all.xml"},
    {"name": "Бумага", "url": "https://paperpaper.ru/feed/"},
    {"name": "Холод", "url": "https://holod.media/feed/"},
    {"name": "Черта", "url": "https://cherta.media/feed/"},
    {"name": "Важные истории", "url": "https://istories.media/rss/"},
    {"name": "Настоящее Время", "url": "https://www.currenttime.tv/api/z-pqpiev-q"},
    {"name": "Голос Америки", "url": "https://www.golosameriki.com/api/z$qyimiv_q"},
    {"name": "RFI на русском", "url": "https://www.rfi.fr/ru/rss"},
    {"name": "Новости ООН", "url": "https://news.un.org/feed/view/ru/1269382/rss.xml"},
    {"name": "Amnesty International RU", "url": "https://eurasia.amnesty.org/feed/"},

    # ==========================================
    # 4. ЭКОНОМИКА, БИЗНЕС И ФИНАНСЫ
    # ==========================================
    {"name": "Forbes Россия", "url": "https://www.forbes.ru/newrss.xml"},
    {"name": "Banki.ru", "url": "https://www.banki.ru/xml/news.rss"},
    {"name": "Секрет Фирмы", "url": "https://secretmag.ru/export/rss.xml"},
    {"name": "Клерк.Ру", "url": "https://www.klerk.ru/export/news.rss"},
    {"name": "Эксперт", "url": "https://expert.ru/rss/"},
    {"name": "BFM.ru", "url": "https://www.bfm.ru/news.rss"},
    {"name": "Прайм", "url": "https://1prime.ru/export/rss2/index.xml"},
    {"name": "БКС Экспресс", "url": "https://bcs-express.ru/rss"},
    {"name": "Финам", "url": "https://www.finam.ru/analysis/newsitem/rsspoint/"},
    {"name": "Frank Media", "url": "https://frankrg.com/feed"},
    {"name": "Экономика и жизнь", "url": "https://www.eg-online.ru/news/rss/"},

    # ==========================================
    # 5. ТЕХНОЛОГИИ, IT И НАУКА
    # ==========================================
    {"name": "3DNews", "url": "https://3dnews.ru/news/rss/"},
    {"name": "iXBT.com", "url": "https://www.ixbt.com/export/news.rss"},
    {"name": "N+1", "url": "https://nplus1.ru/rss"},
    {"name": "Naked Science", "url": "https://naked-science.ru/feed"},
    {"name": "Tproger", "url": "https://tproger.ru/feed/"},
    {"name": "CNews", "url": "https://www.cnews.ru/inc/rss/news.xml"},
    {"name": "Rozetked", "url": "https://rozetked.me/events/rss"},
    {"name": "Wylsacom", "url": "https://wylsa.com/feed/"},
    {"name": "Код Дурова", "url": "https://kod.ru/rss/"},
    {"name": "Хакер (Xakep)", "url": "https://xakep.ru/feed/"},
    {"name": "Hi-Tech Mail.ru", "url": "https://hi-tech.mail.ru/rss/all/"},
    {"name": "4PDA", "url": "https://4pda.to/feed/"},
    {"name": "TAdviser", "url": "https://www.tadviser.ru/xml/tadviser.xml"},
    {"name": "Rusbase (RB.ru)", "url": "https://rb.ru/feeds/all/"},
    {"name": "Techrocks", "url": "https://techrocks.ru/feed/"},
    {"name": "Биомолекула", "url": "https://biomolecula.ru/rss"},
    {"name": "Элементы", "url": "https://elementy.ru/rss/news"},
    {"name": "TechInsider", "url": "https://www.techinsider.ru/out/rss.xml"},

    # ==========================================
    # 6. ИГРЫ, ГЕЙМДЕВ И КИБЕРСПОРТ
    # ==========================================
    {"name": "StopGame", "url": "https://stopgame.ru/rss/new"},
    {"name": "Игромания", "url": "https://www.igromania.ru/rss/rss_news.xml"},
    {"name": "DTF", "url": "https://dtf.ru/rss"},
    {"name": "GoHa.Ru", "url": "https://www.goha.ru/rss/news"},
    {"name": "PlayGround.ru", "url": "https://www.playground.ru/rss/news.xml"},
    {"name": "Cybersport.ru", "url": "https://www.cybersport.ru/rss/materials"},
    {"name": "Канобу", "url": "https://kanobu.ru/rss/news.xml"},
    {"name": "Игры Mail.ru", "url": "https://games.mail.ru/pc/rss/"},
    {"name": "VGTimes", "url": "https://vgtimes.ru/rss.xml"},
    {"name": "Gamedev.ru", "url": "https://gamedev.ru/rss.xml"},
    {"name": "Dota2.ru", "url": "https://dota2.ru/news/rss/"},

    # ==========================================
    # 7. СПОРТ
    # ==========================================
    {"name": "Sports.ru", "url": "https://www.sports.ru/rss/all_news.xml"},
    {"name": "Чемпионат", "url": "https://www.championat.com/rss/news/"},
    {"name": "Sportbox.ru", "url": "https://news.sportbox.ru/rss"},
    {"name": "Матч ТВ", "url": "https://matchtv.ru/rss"},
    {"name": "Советский спорт", "url": "https://www.sovsport.ru/rss"},
    {"name": "Спорт-Экспресс", "url": "https://www.sport-express.ru/services/rss/news/"},
    {"name": "Eurosport RU", "url": "https://www.eurosport.ru/rss.xml"},
    {"name": "F1News", "url": "https://www.f1news.ru/export/news.xml"},
    {"name": "AllBoxing", "url": "https://allboxing.ru/rss.xml"},

    # ==========================================
    # 8. ОБЩЕСТВО, КУЛЬТУРА И ЛАЙФСТАЙЛ
    # ==========================================
    {"name": "Афиша", "url": "https://www.afisha.ru/rss/"},
    {"name": "Афиша Daily", "url": "https://daily.afisha.ru/rss/"},
    {"name": "Нож", "url": "https://knife.media/feed/"},
    {"name": "Мел (Образование)", "url": "https://mel.fm/rss"},
    {"name": "Кинопоиск", "url": "https://www.kinopoisk.ru/rss/news.xml"},
    {"name": "Сеанс", "url": "https://seance.ru/feed/"},
    {"name": "Собака.ru", "url": "https://www.sobaka.ru/rss.xml"},
    {"name": "Вокруг ТВ", "url": "https://www.vokrug.tv/rss/"},
    {"name": "Культура.РФ", "url": "https://www.culture.ru/rss"},
    {"name": "Правила жизни", "url": "https://www.pravilamag.ru/out/rss.xml"},
    {"name": "Psychologies", "url": "https://www.psychologies.ru/rss/"},
    {"name": "Лайфхакер", "url": "https://lifehacker.ru/feed/"},
    {"name": "Wonderzine", "url": "https://www.wonderzine.com/rss"},
    {"name": "Горящая изба", "url": "https://burninghut.ru/feed/"},

    # ==========================================
    # 9. АВТОМОБИЛИ И ТЕХНИКА
    # ==========================================
    {"name": "Дром (Drom.ru)", "url": "https://news.drom.ru/rss/news.xml"},
    {"name": "Журнал Авто.ру", "url": "https://mag.auto.ru/rss/"},
    {"name": "За рулем", "url": "https://www.zr.ru/rss/"},
    {"name": "Авторевю", "url": "https://autoreview.ru/feed/news/rss"},
    {"name": "Motor.ru", "url": "https://motor.ru/export/rss.xml"},
    {"name": "Колеса.ru", "url": "https://www.kolesa.ru/rss"},
    {"name": "Autonews", "url": "https://www.autonews.ru/export/rss2/index.xml"},

    # ==========================================
    # 10. РЕГИОНАЛЬНЫЕ СЕТИ И ПОРТАЛЫ
    # ==========================================
    {"name": "E1.ru (Екатеринбург)", "url": "https://www.e1.ru/text/rss/"},
    {"name": "74.ru (Челябинск)", "url": "https://74.ru/text/rss/"},
    {"name": "NGS.ru (Новосибирск)", "url": "https://ngs.ru/text/rss/"},
    {"name": "116.ru (Казань)", "url": "httpss://116.ru/text/rss/"},
    {"name": "161.ru (Ростов-на-Дону)", "url": "https://161.ru/text/rss/"},
    {"name": "63.ru (Самара)", "url": "https://63.ru/text/rss/"},
    {"name": "59.ru (Пермь)", "url": "https://59.ru/text/rss/"},
    {"name": "72.ru (Тюмень)", "url": "https://72.ru/text/rss/"},
    {"name": "29.ru (Архангельск)", "url": "https://29.ru/text/rss/"},
    {"name": "76.ru (Ярославль)", "url": "https://76.ru/text/rss/"},
    {"name": "V1.ru (Волгоград)", "url": "https://v1.ru/text/rss/"},
    {"name": "ИрСити (Иркутск)", "url": "https://ircity.ru/text/rss/"},
    {"name": "Чита.ру (Забайкалье)", "url": "https://www.chita.ru/text/rss/"},
    {"name": "VL.ru (Владивосток)", "url": "https://www.newsvl.ru/rss"},
    {"name": "Кавказский Узел", "url": "https://www.kavkaz-uzel.eu/articles.rss"},
    {"name": "Татар-информ", "url": "https://www.tatar-inform.ru/rss/all"},
    {"name": "Башинформ", "url": "https://www.bashinform.ru/rss/all"}
]

def fetch_single_feed(source):
    local_articles = []
    try:
        res = requests.get(source["url"], timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            for entry in feed.entries[:3]:
                local_articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": source["name"]
                })
    except Exception:
        pass
    return local_articles

def fetch_and_update_news():
    global last_status
    last_status = f"[{datetime.now().strftime('%H:%M:%S')}] Начат сбор новостей..."
    print(last_status, flush=True)
    
    if not api_key:
        last_status = "❌ Ошибка: Не задан GEMINI_API_KEY"
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
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single_feed, src) for src in SOURCES]
        for future in as_completed(futures):
            result = future.result()
            if result:
                articles.extend(result)
            
    last_status = f"📥 Собрано {len(articles)} новых статей. Обработка ИИ..."
    print(last_status, flush=True)

    if not articles:
        return

    prompt = f"""
    Ты - точный и строгий новостной редактор. Твоя задача: сгруппировать новости, которые описывают СТРОГО ОДНО И ТО ЖЕ конкретное событие.
    НЕ объединяй разные события в одну кучу. У каждого источника бери точное название.
    Текущие темы: {json.dumps(existing_theme_names, ensure_ascii=False)}
    ЕСЛИ новое событие является развитием одной из текущих тем, используй ТОЧНО ТАКОЕ ЖЕ название.

    Для каждого события выбери ОДНУ категорию из списка: "Политика", "Технологии", "Наука", "Общество".
    Верни СТРОГО чистый JSON массив:
    [
      {{
        "theme": "Нейтральный заголовок конкретного события",
        "category": "Категория",
        "articles": [
          {{"title": "Заголовок", "link": "URL", "source": "Точное название издания"}}
        ]
      }}
    ]
    Свежие статьи: {json.dumps(articles, ensure_ascii=False)}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    max_retries = 3
    response_text = None
    
    for attempt in range(max_retries):
        try:
            res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=120)
            if res.status_code == 200:
                data = res.json()
                try:
                    response_text = data['candidates'][0]['content']['parts'][0]['text']
                    break
                except KeyError:
                    last_status = "❌ Ошибка: Ответ заблокирован фильтрами безопасности Google."
                    print(f"Сырой ответ: {data}", flush=True)
                    return
            else:
                print(f"⚠️ Ошибка Gemini ({res.status_code}): {res.text}", flush=True)
                if res.status_code in [503, 500, 429]:
                    time.sleep(10)
                else:
                    last_status = f"❌ Ошибка ИИ: {res.status_code}"
                    return
        except requests.exceptions.Timeout:
            print(f"⚠️ Таймаут запроса. Повтор... ({attempt + 1}/{max_retries})", flush=True)
            time.sleep(5)
        except Exception as e:
            last_status = f"❌ Ошибка сети: {e}"
            print(last_status, flush=True)
            return

    if not response_text:
        last_status = "❌ Ошибка: Получен пустой ответ от ИИ."
        print(last_status, flush=True)
        return

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

        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        last_status = f"✅ Успех! Активных тем за 24ч: {len(final_data)}"
        print(last_status, flush=True)
    except Exception as e:
        last_status = f"❌ Ошибка парсинга JSON: {e}"
        print(last_status, flush=True)

def run_scheduler():
    fetch_and_update_news()
    schedule.every(10).minutes.do(fetch_and_update_news)
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
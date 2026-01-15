import feedparser
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import re
import time
import random
from deep_translator import GoogleTranslator
import os

# --- 适配 Vercel 的关键修改 ---
# Vercel 运行时的路径可能和本地不一样，这样写最稳
app = Flask(__name__, static_folder='static')
CORS(app)

translator = GoogleTranslator(source='auto', target='zh-CN')

# RSS 配置 (保持不变)
RSS_FEEDS = {
    'all': 'https://news.google.com/rss/search?q=International+Film+Festival+news+OR+Cannes+OR+Venice+Film+Festival+OR+Sundance+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sundance': 'https://news.google.com/rss/search?q=Sundance+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'berlin': 'https://news.google.com/rss/search?q=Berlinale+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'cannes': 'https://news.google.com/rss/search?q=Cannes+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'venice': 'https://news.google.com/rss/search?q=Venice+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'tiff': 'https://news.google.com/rss/search?q=Toronto+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sxsw': 'https://news.google.com/rss/search?q=SXSW+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en'
}

# 缓存 (注意：Vercel 是 Serverless，缓存可能会在一段时间后重置，但短期内有效)
NEWS_CACHE = {}
CACHE_TIMEOUT = 1800 

def clean_text(text):
    if not text: return ""
    if ' - ' in text: text = text.rsplit(' - ', 1)[0]
    return re.sub(re.compile('<.*?>'), '', text)

def format_date(date_str):
    try:
        dt = datetime.strptime(date_str[:16], '%a, %d %b %Y')
        return dt.strftime('%Y-%m-%d')
    except:
        return datetime.now().strftime('%Y-%m-%d')

def fetch_all_real_data(festival_id):
    url = RSS_FEEDS.get(festival_id, RSS_FEEDS['all'])
    # 移除 print，Vercel 日志看着乱
    
    try:
        # Vercel 每次请求有时间限制（通常10秒），所以不要 sleep 太久
        # time.sleep(0.1) # 在 Vercel 上可以把这里注释掉或设很短，因为它IP池很大，不易被封
        
        feed = feedparser.parse(url)
        all_articles = []
        
        for index, entry in enumerate(feed.entries):
            raw_title = clean_text(entry.title)
            raw_desc = clean_text(entry.summary) if hasattr(entry, 'summary') else "Click to read full story."
            
            cn_title = raw_title
            cn_desc = raw_desc

            # Vercel 免费版超时时间短，我们只翻译前 5 条，保证速度
            if index < 5: 
                try:
                    cn_title = translator.translate(raw_title)
                    cn_desc = translator.translate(raw_desc[:100]) + "..."
                except:
                    pass

            all_articles.append({
                'id': entry.id,
                'title_en': raw_title,
                'title_cn': cn_title,
                'desc_en': raw_desc,
                'desc_cn': cn_desc,
                'date': format_date(entry.published) if hasattr(entry, 'published') else datetime.now().strftime('%Y-%m-%d'),
                'views': random.randint(1000, 50000),
                'link': entry.link
            })
            
        return all_articles
    except Exception:
        return []

# --- 路由 ---

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/api/news/<festival_id>')
def get_news_paginated(festival_id):
    try:
        page = int(request.args.get('page', 1))
        per_page = 16
        current_time = time.time()
        
        cache_entry = NEWS_CACHE.get(festival_id)
        
        # 简单缓存逻辑
        if not cache_entry or (current_time - cache_entry['timestamp'] > CACHE_TIMEOUT):
            real_data = fetch_all_real_data(festival_id)
            if not real_data and cache_entry:
                real_data = cache_entry['data']
            NEWS_CACHE[festival_id] = {'data': real_data, 'timestamp': current_time}
        
        all_data = NEWS_CACHE[festival_id]['data']
        
        if not all_data:
            return jsonify({'articles': [], 'meta': {'current_page': 1, 'total_pages': 0}})

        total_items = len(all_data)
        total_pages = (total_items + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        
        return jsonify({
            'articles': all_data[start:end],
            'meta': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': total_items
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Vercel 不需要 app.run()，但保留这行让你可以本地测试
if __name__ == '__main__':
    app.run(port=5000, debug=True)


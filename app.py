import feedparser
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import re
import time
import random
from deep_translator import GoogleTranslator
import os

app = Flask(__name__, static_folder='static')
CORS(app)

translator = GoogleTranslator(source='auto', target='zh-CN')

# RSS 配置
RSS_FEEDS = {
    'all': 'https://news.google.com/rss/search?q=International+Film+Festival+news+OR+Cannes+OR+Venice+Film+Festival+OR+Sundance+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sundance': 'https://news.google.com/rss/search?q=Sundance+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'berlin': 'https://news.google.com/rss/search?q=Berlinale+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'cannes': 'https://news.google.com/rss/search?q=Cannes+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'venice': 'https://news.google.com/rss/search?q=Venice+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'tiff': 'https://news.google.com/rss/search?q=Toronto+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sxsw': 'https://news.google.com/rss/search?q=SXSW+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en'
}

# 缓存
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
    try:
        feed = feedparser.parse(url)
        all_articles = []
        
        for index, entry in enumerate(feed.entries):
            raw_title = clean_text(entry.title)
            raw_desc = clean_text(entry.summary) if hasattr(entry, 'summary') else "Click to read full story."
            
            cn_title = raw_title
            cn_desc = raw_desc

            # Vercel 性能优化：只翻译前 6 条
            if index < 6: 
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
                # 给每篇文章生成一个固定的随机热度，基于标题长度哈希，确保排序稳定
                'views': int(hash(raw_title) % 40000) + 10000, 
                'link': entry.link
            })
            
        return all_articles
    except Exception:
        return []

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/api/news/<festival_id>')
def get_news_paginated(festival_id):
    try:
        page = int(request.args.get('page', 1))
        # 新增 sort 参数，默认为 latest
        sort_type = request.args.get('sort', 'latest') 
        per_page = 12 # 每次加载 12 条
        
        current_time = time.time()
        cache_entry = NEWS_CACHE.get(festival_id)
        
        # 1. 缓存处理
        if not cache_entry or (current_time - cache_entry['timestamp'] > CACHE_TIMEOUT):
            real_data = fetch_all_real_data(festival_id)
            if not real_data and cache_entry:
                real_data = cache_entry['data']
            NEWS_CACHE[festival_id] = {'data': real_data, 'timestamp': current_time}
        
        all_data = NEWS_CACHE[festival_id]['data'][:] # 复制一份，以免影响缓存原数据
        
        if not all_data:
            return jsonify({'articles': [], 'meta': {'has_more': False}})

        # 2. 全局排序 (关键步骤)
        # 必须先排序，再分页，否则"最热"只会是当前页的最热
        if sort_type == 'hottest':
            all_data.sort(key=lambda x: x['views'], reverse=True)
        else: # latest
            all_data.sort(key=lambda x: x['date'], reverse=True)

        # 3. 分页切片
        total_items = len(all_data)
        start = (page - 1) * per_page
        end = start + per_page
        
        sliced_data = all_data[start:end]
        
        return jsonify({
            'articles': sliced_data,
            'meta': {
                'current_page': page,
                'has_more': end < total_items # 告诉前端还有没有数据
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)

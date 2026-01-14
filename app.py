import feedparser
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import re
import time
import random
# 引入翻译库
from deep_translator import GoogleTranslator

app = Flask(__name__, static_folder='static')
CORS(app)

# 初始化翻译器
translator = GoogleTranslator(source='auto', target='zh-CN')

# RSS 源配置
RSS_FEEDS = {
    'all': 'https://news.google.com/rss/search?q=International+Film+Festival+news+OR+Cannes+OR+Venice+Film+Festival+OR+Sundance+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sundance': 'https://news.google.com/rss/search?q=Sundance+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'berlin': 'https://news.google.com/rss/search?q=Berlinale+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'cannes': 'https://news.google.com/rss/search?q=Cannes+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'venice': 'https://news.google.com/rss/search?q=Venice+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'tiff': 'https://news.google.com/rss/search?q=Toronto+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en',
    'sxsw': 'https://news.google.com/rss/search?q=SXSW+Film+Festival+news+when:30d&hl=en-US&gl=US&ceid=US:en'
}

# 内存缓存
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
    """【防崩溃版】抓取函数"""
    url = RSS_FEEDS.get(festival_id, RSS_FEEDS['all'])
    print(f"Server: Start fetching [{festival_id}]...")
    
    try:
        # 设置超时时间，防止网络卡死
        feed = feedparser.parse(url)
        
        if not feed.entries:
            print("Warning: Google News returned 0 items. (Network issue?)")
            return []

        all_articles = []
        
        # 遍历每一条新闻
        for index, entry in enumerate(feed.entries):
            # 获取基础信息
            raw_title = clean_text(entry.title)
            # 安全获取 summary，如果没有则给默认值
            raw_desc = clean_text(entry.summary) if hasattr(entry, 'summary') else "Click card to read full story on official site."
            
            cn_title = raw_title
            cn_desc = raw_desc

            # --- 翻译模块（带异常捕获）---
            # 只翻译前 10 条，防止请求过多被封 IP
            if index < 10:
                try:
                    cn_title = translator.translate(raw_title)
                    # 简介只翻译前100个字符
                    cn_desc = translator.translate(raw_desc[:100]) + "..."
                except Exception as e:
                    # 如果翻译失败，仅仅打印错误，不中断程序！
                    print(f"Translation skipped for item {index}: {e}")
                    # 保持英文原样
                    cn_title = raw_title
                    cn_desc = raw_desc

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
            
        print(f"Server: Successfully fetched {len(all_articles)} items.")
        return all_articles

    except Exception as e:
        # 捕获所有未知错误
        print(f"CRITICAL ERROR in fetch: {e}")
        return []

# --- 路由部分 ---

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/news/<festival_id>')
def get_news_paginated(festival_id):
    try:
        page = int(request.args.get('page', 1))
        per_page = 16
        current_time = time.time()
        
        # 缓存逻辑
        cache_entry = NEWS_CACHE.get(festival_id)
        
        if not cache_entry or (current_time - cache_entry['timestamp'] > CACHE_TIMEOUT):
            real_data = fetch_all_real_data(festival_id)
            # 如果抓取失败（空列表），且缓存里有旧数据，就暂时用旧的
            if not real_data and cache_entry:
                print("Using old cache due to fetch failure.")
                real_data = cache_entry['data']
            
            NEWS_CACHE[festival_id] = {
                'data': real_data,
                'timestamp': current_time
            }
        
        all_data = NEWS_CACHE[festival_id]['data']
        
        # 如果完全没有数据（比如断网了），返回一个空的结构，而不是报错
        if not all_data:
            return jsonify({
                'articles': [],
                'meta': {'current_page': 1, 'total_pages': 0, 'total_items': 0}
            })

        # 分页逻辑
        total_items = len(all_data)
        total_pages = (total_items + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        page_data = all_data[start:end]
        
        return jsonify({
            'articles': page_data,
            'meta': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': total_items
            }
        })

    except Exception as e:
        print(f"API Route Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("---------------------------------------")
    print(f" Server running on http://127.0.0.1:{port}")
    print("---------------------------------------")
    app.run(host='0.0.0.0', port=port)

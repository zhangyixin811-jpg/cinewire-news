import feedparser
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import re
import time
from deep_translator import GoogleTranslator
import os

# 修改这里：告诉 Flask 静态文件在哪里
app = Flask(__name__, static_folder='static')
CORS(app)

translator = GoogleTranslator(source='auto', target='zh-CN')

# ... (中间的 RSS_FEEDS, NEWS_CACHE, clean_text 等函数保持不变，照抄您之前的即可) ...
# 为了篇幅，我这里省略中间逻辑，您直接保留之前的逻辑即可
# 只需要确保 RSS_FEEDS, NEWS_CACHE, clean_text, fetch_all_real_data 等都在

# --- 关键修改 1: 增加首页路由 ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# --- 之前的 API 逻辑保持不变 ---
@app.route('/api/news/<festival_id>')
def get_news_paginated(festival_id):
    # ... (这里保留您之前的完整分页逻辑) ...
    # ... (代码太长省略，请直接使用您上一个版本的 get_news_paginated 函数内容) ...
    pass 

if __name__ == '__main__':
    # 关键修改 2: 适配云服务器端口
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
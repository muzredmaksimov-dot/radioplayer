from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Путь к файлу с новостями
NEWS_FILE = 'news.json'
ADMIN_PASSWORD = 'admin123'

# Инициализация файла новостей
def init_news_file():
    if not os.path.exists(NEWS_FILE):
        default_news = [
            {
                'id': 1,
                'title': 'Добро пожаловать в Радио Мир',
                'description': 'Новое приложение для прямой трансляции',
                'image': 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"%3E%3Crect fill="%23FF6B6B" width="400" height="300"/%3E%3Ctext x="50%25" y="50%25" font-size="32" fill="white" text-anchor="middle" dominant-baseline="middle"%3EРадио Мир%3C/text%3E%3C/svg%3E',
                'likes': 0,
                'created_at': datetime.now().isoformat()
            }
        ]
        with open(NEWS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_news, f, ensure_ascii=False, indent=2)

init_news_file()

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/news', methods=['GET'])
def get_news():
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)
    return jsonify(news)

@app.route('/api/news', methods=['POST'])
def add_news():
    data = request.json
    password = data.get('password')
    
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Неверный пароль'}), 401
    
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)
    
    new_item = {
        'id': max([n['id'] for n in news], default=0) + 1,
        'title': data.get('title'),
        'description': data.get('description'),
        'image': data.get('image', ''),
        'likes': 0,
        'created_at': datetime.now().isoformat()
    }
    
    news.append(new_item)
    
    with open(NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    
    return jsonify(new_item), 201

@app.route('/api/news/<int:news_id>', methods=['PUT'])
def update_news(news_id):
    data = request.json
    password = data.get('password')
    
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Неверный пароль'}), 401
    
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)
    
    for item in news:
        if item['id'] == news_id:
            item['title'] = data.get('title', item['title'])
            item['description'] = data.get('description', item['description'])
            item['image'] = data.get('image', item['image'])
            
            with open(NEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(news, f, ensure_ascii=False, indent=2)
            
            return jsonify(item), 200
    
    return jsonify({'error': 'Новость не найдена'}), 404

@app.route('/api/news/<int:news_id>', methods=['DELETE'])
def delete_news(news_id):
    data = request.json
    password = data.get('password')
    
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Неверный пароль'}), 401
    
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)
    
    news = [item for item in news if item['id'] != news_id]
    
    with open(NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True}), 200

@app.route('/api/news/<int:news_id>/like', methods=['POST'])
def like_news(news_id):
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)
    
    for item in news:
        if item['id'] == news_id:
            item['likes'] += 1
            with open(NEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(news, f, ensure_ascii=False, indent=2)
            return jsonify(item), 200
    
    return jsonify({'error': 'Новость не найдена'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

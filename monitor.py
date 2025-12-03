#!/usr/bin/env python3
"""
Мониторинг сайта radiomir.by
Сохраняет трек в GitHub репозиторий
"""

import requests
import re
import time
import base64
import json
import os
from datetime import datetime
from urllib.parse import quote

# ==================== КОНФИГУРАЦИЯ ====================
CONFIG = {
    # URL для парсинга
    'RADIO_URL': 'https://radiomir.by/live',
    
    # GitHub репозиторий
    'GITHUB_REPO': 'muzredmaksimov-dot/radioplayer',
    'GITHUB_FILE': 'current_track.json',
    
    # Интервал проверки (секунды)
    'CHECK_INTERVAL': 30,
    
    # Токен GitHub (из переменных окружения)
    'GITHUB_TOKEN': os.getenv('GITHUB_TOKEN'),
}

# ==================== ФУНКЦИИ ПАРСИНГА ====================
def get_current_track():
    """Получить текущий трек с сайта radiomir.by"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(CONFIG['RADIO_URL'], headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        
        # Паттерны для поиска трека
        patterns = [
            # Мета-теги
            (r'<meta property="og:title" content="([^"]+)"', 'meta_og'),
            (r'<meta name="twitter:title" content="([^"]+)"', 'meta_twitter'),
            
            # Текст на странице
            (r'Сейчас играет[^>]*>([^<]+)', 'text_playing'),
            (r'Now playing[^>]*>([^<]+)', 'text_playing_en'),
            (r'В эфире[^>]*>([^<]+)', 'text_onair'),
            
            # JavaScript переменные
            (r'currentTrack["\']?\s*[:=]\s*["\']([^"\']+)["\']', 'js_current'),
            (r'nowPlaying["\']?\s*[:=]\s*["\']([^"\']+)["\']', 'js_nowplaying'),
            (r'track["\']?\s*[:=]\s*["\']([^"\']+)["\']', 'js_track'),
            
            # Любой текст с разделителем
            (r'([^>-]{3,})\s*[-–—]\s*([^<-]{3,})', 'dash_format'),
        ]
        
        for pattern, source in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Для формата "Исполнитель - Трек"
                    if len(match) == 2:
                        artist, title = match
                        track = f"{artist.strip()} - {title.strip()}"
                        if is_valid_track(track):
                            return track, source
                else:
                    # Простой текст
                    track = str(match).strip()
                    if is_valid_track(track):
                        return track, source
        
        # Если ничего не нашли
        return "Радио МИР", "default"
        
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return "Радио МИР", "error"

def is_valid_track(track):
    """Проверяет, валиден ли трек"""
    if not track or len(track) < 3:
        return False
    
    track_lower = track.lower()
    invalid_keywords = [
        'радио', 'мир', 'radiomir', 'онлайн', 'слушать',
        'live', 'stream', 'вещание', 'эфир', 'сайт',
        'главная', 'страница', 'player', 'плеер'
    ]
    
    return not any(keyword in track_lower for keyword in invalid_keywords)

# ==================== ФУНКЦИИ GITHUB ====================
def update_github_file(track, source):
    """Обновить файл в GitHub репозитории"""
    if not CONFIG['GITHUB_TOKEN']:
        print("⚠️  GITHUB_TOKEN не установлен, пропускаю сохранение")
        return False
    
    try:
        # Данные для сохранения
        track_data = {
            "track": track,
            "artist": "Прямой эфир",
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        content = json.dumps(track_data, ensure_ascii=False, indent=2)
        encoded_content = base64.b64encode(content.encode()).decode()
        
        # URL API GitHub
        url = f"https://api.github.com/repos/{CONFIG['GITHUB_REPO']}/contents/{CONFIG['GITHUB_FILE']}"
        
        headers = {
            "Authorization": f"token {CONFIG['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # Сначала получаем текущий файл чтобы узнать SHA
        response = requests.get(url, headers=headers)
        
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        # Подготавливаем данные для обновления
        data = {
            "message": f"🤖 Обновление трека: {track[:50]}...",
            "content": encoded_content,
            "branch": "main"
        }
        
        if sha:
            data["sha"] = sha
        
        # Отправляем обновление
        if sha:
            # Обновляем существующий файл
            response = requests.put(url, headers=headers, json=data)
        else:
            # Создаем новый файл
            response = requests.put(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            print(f"✅ Трек сохранен в GitHub: {track}")
            return True
        else:
            print(f"❌ Ошибка GitHub API: {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка обновления GitHub: {e}")
        return False

# ==================== ОСНОВНОЙ ЦИКЛ ====================
def main():
    """Основной цикл мониторинга"""
    print("=" * 60)
    print("🚀 Мониторинг радио МИР запущен")
    print(f"📻 Сайт: {CONFIG['RADIO_URL']}")
    print(f"💾 Репозиторий: {CONFIG['GITHUB_REPO']}")
    print(f"📄 Файл: {CONFIG['GITHUB_FILE']}")
    print(f"⏱  Интервал: {CONFIG['CHECK_INTERVAL']} секунд")
    
    if CONFIG['GITHUB_TOKEN']:
        print("✅ GitHub токен настроен")
    else:
        print("⚠️  GitHub токен НЕ настроен (только режим мониторинга)")
    
    print("=" * 60)
    
    last_track = None
    last_source = None
    
    while True:
        try:
            # Получаем текущий трек
            current_track, source = get_current_track()
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Проверка...")
            print(f"   Найден трек: {current_track}")
            print(f"   Источник: {source}")
            
            # Проверяем, изменился ли трек
            if current_track != last_track or source != last_source:
                print(f"   ⚡ Трек изменился!")
                
                # Сохраняем в GitHub
                if CONFIG['GITHUB_TOKEN']:
                    success = update_github_file(current_track, source)
                    if success:
                        print(f"   💾 Сохранено в GitHub")
                    else:
                        print(f"   ❌ Ошибка сохранения")
                else:
                    print(f"   📝 Только мониторинг (без сохранения)")
                
                last_track = current_track
                last_source = source
            else:
                print(f"   🔄 Трек не изменился")
            
            # Ждем перед следующей проверкой
            print(f"   ⏳ Следующая проверка через {CONFIG['CHECK_INTERVAL']} секунд...")
            time.sleep(CONFIG['CHECK_INTERVAL'])
            
        except KeyboardInterrupt:
            print("\n\n👋 Остановка мониторинга")
            break
        except Exception as e:
            print(f"\n⚠️  Критическая ошибка: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

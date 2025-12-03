#!/usr/bin/env python3
"""
Мониторинг сайта radiomir.by
Обновляет current_track.txt при изменении трека
"""

import requests
import time
import re
from datetime import datetime

# URL для мониторинга
URL = "https://radiomir.by/live"
CHECK_INTERVAL = 30  # секунд
TRACK_FILE = "current_track.txt"

def get_current_track():
    """Получить текущий трек с сайта"""
    try:
        response = requests.get(URL, timeout=5)
        html = response.text
        
        # Ищем в разных местах
        patterns = [
            r'<meta property="og:title" content="([^"]+)"',
            r'Сейчас играет[^>]*>([^<]+)',
            r'currentTrack["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'nowPlaying["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                track = match.group(1).strip()
                # Фильтруем системные названия
                if len(track) > 3 and 'радио' not in track.lower():
                    return track
        
        return None
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

def save_track(track):
    """Сохранить трек в файл"""
    with open(TRACK_FILE, 'w', encoding='utf-8') as f:
        f.write(track)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Сохранен трек: {track}")

def main():
    """Основной цикл мониторинга"""
    print("🚀 Мониторинг радио МИР запущен")
    print(f"📻 Сайт: {URL}")
    print(f"⏱  Интервал проверки: {CHECK_INTERVAL} сек")
    print("-" * 50)
    
    last_track = None
    
    while True:
        try:
            # Получаем текущий трек
            current_track = get_current_track()
            
            if current_track and current_track != last_track:
                # Трек изменился - сохраняем
                save_track(current_track)
                last_track = current_track
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 Остановка мониторинга")
            break
        except Exception as e:
            print(f"⚠️  Ошибка в цикле: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

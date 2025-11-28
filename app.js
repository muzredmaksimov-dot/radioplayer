const tg = window.Telegram.WebApp;
const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const playIcon = document.getElementById('playIcon');
const visualizer = document.getElementById('visualizer');

// Поток радио МИР - УБЕДИТЕСЬ ЧТО URL РАБОЧИЙ
const STREAM_URL = 'https://media1.datacenter.by-1936/radiomir/radiomir/playlist.m3u8';

let hls = null;
let isPlaying = false;
let currentMetadata = {};
let lastMetadata = '';
let trackHistory = [];
let progressInterval;
let isHlsInitialized = false;

// Инициализация Telegram Web App
tg.expand();
tg.enableClosingConfirmation();

function initHLS() {
    console.log('Инициализация HLS...');
    
    // Если HLS уже инициализирован, уничтожаем старый экземпляр
    if (hls) {
        hls.destroy();
        hls = null;
    }
    
    if (Hls.isSupported()) {
        hls = new Hls({
            enableWorker: false,
            lowLatencyMode: true,
            backBufferLength: 90,
            debug: true, // Включаем debug для диагностики
            autoStartLoad: false,
            maxBufferLength: 30
        });
        
        hls.loadSource(STREAM_URL);
        hls.attachMedia(audio);
        
        hls.on(Hls.Events.MANIFEST_PARSED, function() {
            console.log('Манифест загружен, можно воспроизводить');
            updateStatus('Эфир подключен - нажмите Play');
            isHlsInitialized = true;
        });
        
        hls.on(Hls.Events.LEVEL_LOADED, function(event, data) {
            console.log('Уровень загружен:', data);
        });
        
        hls.on(Hls.Events.FRAG_LOADED, function(event, data) {
            console.log('Фрагмент загружен');
        });
        
        // Слушаем метаданные
        hls.on(Hls.Events.FRAG_PARSING_METADATA, function(event, data) {
            console.log('Метаданные получены:', data);
            if (data.samples) {
                parseID3Metadata(data.samples);
            }
        });
        
        hls.on(Hls.Events.ERROR, function(event, data) {
            console.error('HLS Error:', data);
            if (data.fatal) {
                switch(data.type) {
                    case Hls.ErrorTypes.NETWORK_ERROR:
                        updateStatus('❌ Ошибка сети. Проверьте URL потока');
                        console.error('Network error - проверьте URL:', STREAM_URL);
                        break;
                    case Hls.ErrorTypes.MEDIA_ERROR:
                        updateStatus('❌ Ошибка медиа формата');
                        hls.recoverMediaError();
                        break;
                    default:
                        updateStatus('❌ Критическая ошибка HLS');
                        break;
                }
            }
        });
        
    } else if (audio.canPlayType('application/vnd.apple.mpegurl')) {
        // Для Safari
        console.log('Используется встроенный HLS плеер Safari');
        audio.src = STREAM_URL;
        audio.addEventListener('loadedmetadata', function() {
            updateStatus('Safari: поток готов');
            isHlsInitialized = true;
        });
    } else {
        updateStatus('❌ Браузер не поддерживает HLS');
        console.error('HLS not supported');
    }
}

function togglePlay() {
    console.log('Toggle play, isPlaying:', isPlaying, 'isHlsInitialized:', isHlsInitialized);
    
    if (!isHlsInitialized) {
        console.log('Первая инициализация HLS');
        initHLS();
        updateStatus('Инициализация потока...');
        // Даем время на инициализацию
        setTimeout(() => {
            if (isHlsInitialized) {
                startPlayback();
            } else {
                updateStatus('❌ Ошибка инициализации. Проверьте консоль.');
            }
        }, 2000);
        return;
    }
    
    if (isPlaying) {
        pausePlayback();
    } else {
        startPlayback();
    }
}

function startPlayback() {
    console.log('Запуск воспроизведения');
    
    if (hls) {
        hls.startLoad(-1); // Начинаем загрузку с текущей позиции
    }
    
    audio.play().
        then(() => {
        console.log('Воспроизведение успешно запущено');
        showPauseIcon();
        isPlaying = true;
        updateStatus('🎵 Эфир онлайн');
        startProgressAnimation();
        visualizer.classList.add('playing');
        
        // Запускаем мониторинг метаданных
        startMetadataMonitoring();
        
    }).catch(error => {
        console.error('Ошибка воспроизведения:', error);
        updateStatus('❌ Ошибка: ' + error.message);
        showPlayIcon();
        isPlaying = false;
    });
}

function pausePlayback() {
    console.log('Пауза');
    audio.pause();
    showPlayIcon();
    isPlaying = false;
    updateStatus('⏸ Пауза');
    stopProgressAnimation();
    visualizer.classList.remove('playing');
    
    if (hls) {
        hls.stopLoad();
    }
}

// Остальные функции остаются без изменений
function parseID3Metadata(samples) {
    if (!samples || samples.length === 0) return;
    
    samples.forEach(sample => {
        try {
            if (sample.type === 'ID3') {
                parseID3Data(sample.data);
            }
        } catch (error) {
            console.warn('Error parsing ID3:', error);
        }
    });
}

function parseID3Data(data) {
    try {
        const dataView = new DataView(data);
        if (dataView.getUint16(0) !== 0x4944) return;
        
        let offset = 10;
        while (offset < dataView.byteLength - 10) {
            const frameId = String.fromCharCode(
                dataView.getUint8(offset),
                dataView.getUint8(offset + 1),
                dataView.getUint8(offset + 2),
                dataView.getUint8(offset + 3)
            );
            
            const size = dataView.getUint32(offset + 4);
            offset += 10;
            
            if (size === 0) break;
            
            try {
                const textDecoder = new TextDecoder('utf-8');
                const frameData = textDecoder.decode(
                    new DataView(dataView.buffer, offset, size)
                ).trim().replace(/\0/g, '');
                
                processID3Frame(frameId, frameData);
                
            } catch (error) {
                console.warn('Error decoding frame:', error);
            }
            
            offset += size;
        }
    } catch (error) {
        console.warn('Error parsing ID3 data:', error);
    }
}

function processID3Frame(frameId, frameData) {
    if (!frameData) return;
    
    switch(frameId) {
        case 'TIT2': // Название трека
            if (frameData && frameData !== currentMetadata.title) {
                currentMetadata.title = frameData;
                updateTrackDisplay();
            }
            break;
        case 'TPE1': // Исполнитель
            if (frameData && frameData !== currentMetadata.artist) {
                currentMetadata.artist = frameData;
                updateTrackDisplay();
            }
            break;
        case 'COMM': // Комментарий
            parseCommentMetadata(frameData);
            break;
        default:
            if (frameData.includes(' - ')) {
                parseGenericMetadata(frameData);
            }
            break;
    }
}

function parseCommentMetadata(text) {
    const patterns = [
        /(.+?)\s*-\s*(.+)/,
        /(.+?)\s*\|\s*(.+)/
    ];
    
    for (let pattern of patterns) {
        const match = text.match(pattern);
        if (match) {
            const artist = match[1].trim();
            const title = match[2].trim();
            
            if (artist && title && artist.length < 50 && title.length < 50) {
                currentMetadata.artist = artist;
                currentMetadata.title = title;
                updateTrackDisplay();
                return true;
            }
        }
    }
    return false;
}

function parseGenericMetadata(text) {
    if (text.includes(' - ')) {
        const parts = text.split(' - ');
        if (parts.length === 2) {
            const part1 = parts[0].trim();
            const part2 = parts[1].trim();
            
            if (part1.length < part2.length) {
                currentMetadata.artist = part1;
                currentMetadata.title = part2;
            } else {
                currentMetadata.artist = part2;
                currentMetadata.title = part1;
            }
            updateTrackDisplay();
            return true;
        }
    }
    return false;
}

function updateTrackDisplay() {
    if (!currentMetadata.title && !currentMetadata.artist) return;
    
    const title = currentMetadata.title || 'Радио МИР';
    const artist = currentMetadata.artist || 'Прямой эфир';
    
    const currentMetadataString = title + artist;
    if (currentMetadataString === lastMetadata) return;
    
    lastMetadata = currentMetadataString;
    
    const titleElement = document.getElementById('currentSong');
    const artistElement = document.getElementById('currentArtist');
    
    // Анимация смены трека
    titleElement.classList.add('track-change');
    artistElement.classList.add('track-change');
    
    setTimeout(() => {
        titleElement.textContent = title;
        artistElement.textContent = artist;
        
        setTimeout(() => {
            titleElement.classList.remove('track-change');
            artistElement.classList.remove('track-change');
        }, 500);
    }, 100);
    
    updateStatus('В эфире: ' + title);
    addToHistory(title, artist);
}

function addToHistory(title, artist) {
    const timestamp = new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    // Проверяем, не тот ли это же трек
    const lastTrack = trackHistory[0];
    if (lastTrack && lastTrack.title === title && lastTrack.artist === artist) {
        return;
    }
    
    trackHistory.unshift({
        title,
        artist,
        timestamp,
        id: Date.now()
    });
    
    // Ограничиваем историю 5 треками
    if (trackHistory.length > 5) {
        trackHistory = trackHistory.slice(0, 5);
    }
    
    updateHistoryDisplay();
}

function updateHistoryDisplay() {
    const historyList = document.getElementById('historyList');
    
    historyList.innerHTML = trackHistory.map(track => 
        `<div class="history-item">
            <div class="history-track">
                <strong>${track.title}</strong> - ${track.artist}
            </div>
            <div class="history-time">${track.timestamp}</div>
        </div>`
    ).join('');
}

function toggleHistory() {
    const historyElement = document.getElementById('trackHistory');
    historyElement.classList.toggle('expanded');
}

function startMetadataMonitoring() {
    setInterval(() => {
        if (isPlaying && (!currentMetadata.title || !currentMetadata.artist)) {
            updateFallbackTrackInfo();
        }
    }, 30000);
}

function updateFallbackTrackInfo() {
    const fallbackTracks = [
        { title: "Новости мира", artist: "Радио МИР" },
        { title: "Музыкальный эфир", artist: "Все включено!" },
        { title: "Информационная программа", artist: "Межгосударственная ТРК" }
    ];
    
    if (!currentMetadata.title) {
        const randomTrack = fallbackTracks[Math.floor(Math.random() * fallbackTracks.length)];
        currentMetadata.title = randomTrack.title;
        currentMetadata.artist = randomTrack.artist;
        updateTrackDisplay();
    }
}

function showPlayIcon() {
    playIcon.className = 'play-icon';
    playIcon.innerHTML = '';
}

function showPauseIcon() {
    playIcon.className = 'pause-icon';
    playIcon.innerHTML = '<div class="pause-bar"></div><div class="pause-bar"></div>';
}

function setVolume(value) {
    audio.volume = value / 100;
    document.getElementById('volumeValue').textContent = value + '%';
}

function updateStatus(message) {
    document.getElementById('status').textContent = message;
    console.log('Status:', message);
}

function startProgressAnimation() {
    let progress = 0;
    progressInterval = setInterval(() => {
        progress = (progress + 0.5) % 100;
        document.getElementById('progressFill').style.width = progress + '%';
    }, 100);
}
function stopProgressAnimation() {
    if (progressInterval) {
        clearInterval(progressInterval);
        document.getElementById('progressFill').style.width = '0%';
    }
}

function skipBack() {
    tg.showPopup({
        title: 'Перемотка',
        message: 'Функция в разработке'
    });
}

function skipForward() {
    tg.showPopup({
        title: 'Перемотка',
        message: 'Функция в разработке'
    });
}

function closeApp() {
    if (hls) {
        hls.destroy();
    }
    audio.pause();
    stopProgressAnimation();
    tg.close();
}

// Обработчики событий аудио
audio.addEventListener('play', () => {
    console.log('Audio play event');
    showPauseIcon();
    isPlaying = true;
    updateStatus('🎵 Эфир онлайн');
    visualizer.classList.add('playing');
});

audio.addEventListener('pause', () => {
    console.log('Audio pause event');
    showPlayIcon();
    isPlaying = false;
    updateStatus('⏸ Пауза');
    visualizer.classList.remove('playing');
});

audio.addEventListener('waiting', () => {
    console.log('Audio waiting event');
    updateStatus('⏳ Буферизация...');
    visualizer.classList.remove('playing');
});

audio.addEventListener('playing', () => {
    console.log('Audio playing event');
    updateStatus('🎵 Эфир онлайн');
    visualizer.classList.add('playing');
});

audio.addEventListener('error', (e) => {
    console.error('Audio error:', e);
    updateStatus('❌ Ошибка аудио');
});

// Инициализация
setVolume(60);

// Автоматическая инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing HLS...');
    initHLS();
});

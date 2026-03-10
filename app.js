// HLS Video Player
let hls;
let video = document.getElementById('videoPlayer');
const HLS_URL = 'https://media1.datacenter.by:1936/radiomir/radiomir/playlist.m3u8';

// Инициализация плеера
function initPlayer() {
    if (Hls.isSupported()) {
        hls = new Hls();
        hls.loadSource(HLS_URL);
        hls.attachMedia(video);
        
        hls.on(Hls.Events.MANIFEST_PARSED, function() {
            updateStatus('Трансляция готова к воспроизведению');
        });
        
        hls.on(Hls.Events.ERROR, function(event, data) {
            if (data.fatal) {
                updateStatus('⚠️ Ошибка подключения. Проверьте интернет.');
            }
        });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = HLS_URL;
        updateStatus('Трансляция готова');
    }
}

function togglePlay() {
    const btn = document.getElementById('playBtn');
    if (video.paused) {
        video.play();
        btn.textContent = '⏸️ Пауза';
        updateStatus('🔴 ПРЯМОЙ ЭФИР');
    } else {
        video.pause();
        btn.textContent = '▶️ Включить';
        updateStatus('⏸️ Приостановлено');
    }
}

function updateStatus(msg) {
    document.getElementById('status').textContent = msg;
}

function goFullscreen() {
    if (video.requestFullscreen) {
        video.requestFullscreen();
    }
}

// NEWS FUNCTIONS
async function loadNews() {
    try {
        const response = await fetch('/api/news');
        const news = await response.json();
        displayNews(news);
    } catch (error) {
        console.error('Ошибка загрузки новостей:', error);
        document.getElementById('newsList').innerHTML = '<p>Ошибка загрузки новостей</p>';
    }
}

function displayNews(news) {
    const newsList = document.getElementById('newsList');
    
    if (news.length === 0) {
        newsList.innerHTML = '<p>Нет новостей</p>';
        return;
    }
    
    newsList.innerHTML = news.map(item => `
        <div class="news-card">
            <img src="${item.image}" alt="${item.title}" class="news-image">
            <div class="news-content">
                <h3>${item.title}</h3>
                <p>${item.description}</p>
                <div class="news-footer">
                    <button class="like-btn" onclick="likeNews(${item.id})">👍 ${item.likes}</button>
                    <span class="news-date">${new Date(item.created_at).toLocaleDateString('ru-RU')}</span>
                </div>
            </div>
        </div>
    `).join('');
}

async function likeNews(newsId) {
    try {
        await fetch(`/api/news/${newsId}/like`, { method: 'POST' });
        loadNews();
    } catch (error) {
        console.error('Ошибка при добавлении лайка:', error);
    }
}

// ADMIN FUNCTIONS
let adminAuthed = false;

function goToAdmin() {
    document.getElementById('adminPanel').classList.remove('hidden');
    adminAuthed = false;
    document.getElementById('adminLogin').classList.remove('hidden');
    document.getElementById('adminInterface').classList.add('hidden');
    loadAdminNews();
}

function closeAdmin() {
    document.getElementById('adminPanel').classList.add('hidden');
    adminAuthed = false;
}

function adminLogin() {
    const password = document.getElementById('adminPassword').value;
    
    if (!password) {
        alert('Введите пароль');
        return;
    }
    
    if (password === 'admin123') {
        adminAuthed = true;
        document.getElementById('adminLogin').classList.add('hidden');
        document.getElementById('adminInterface').classList.remove('hidden');
        loadAdminNews();
    } else {
        alert('❌ Неверный пароль');
    }
}

async function addNews() {
    if (!adminAuthed) {
        alert('Вы не авторизованы');
        return;
    }
    
    const title = document.getElementById('newsTitle').value;
    const description = document.getElementById('newsDesc').value;
    const image = document.getElementById('newsImage').value;
    
    if (!title || !description) {
        alert('Заполните все поля');
        return;
    }
    
    try {
        const response = await fetch('/api/news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                image: image || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"%3E%3Crect fill="%23FF6B6B" width="400" height="300"/%3E%3C/svg%3E',
                password: document.getElementById('adminPassword').value
            })
        });
        
        if (response.ok) {
            alert('✅ Новость добавлена');
            document.getElementById('newsTitle').value = '';
            document.getElementById('newsDesc').value = '';
            document.getElementById('newsImage').value = '';
            loadNews();
            loadAdminNews();
        } else {
            alert('❌ Ошибка добавления');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка сервера');
    }
}

async function loadAdminNews() {
    if (!adminAuthed) return;
    
    try {
        const response = await fetch('/api/news');
        const news = await response.json();
        
        const list = document.getElementById('adminNewsList');
        list.innerHTML = news.map(item => `
            <div class="admin-news-item">
                <div>
                    <strong>${item.title}</strong>
                    <p>${item.description}</p>
                </div>
                <div class="admin-actions">
                    <button class="btn-edit" onclick="editNews(${item.id}, '${item.title.replace(/'/g, "\\'")}', '${item.description.replace(/'/g, "\\'")}', '${item.image.replace(/'/g, "\\'")}')">✏️ Редактировать</button>
                    <button class="btn-delete" onclick="deleteNews(${item.id})">🗑️ Удалить</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки новостей админа:', error);
    }
}

function editNews(id, title, description, image) {
    const newTitle = prompt('Новый заголовок:', title);
    if (newTitle === null) return;
    
    const newDesc = prompt('Новое описание:', description);
    if (newDesc === null) return;
    
    const newImage = prompt('Новое изображение (URL):', image);
    if (newImage === null) return;
    
    updateNews(id, newTitle, newDesc, newImage);
}

async function updateNews(id, title, description, image) {
    try {
        const response = await fetch(`/api/news/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                image,
                password: document.getElementById('adminPassword').value
            })
        });
        
        if (response.ok) {
            alert('✅ Новость обновлена');
            loadNews();
            loadAdminNews();
        }
    } catch (error) {
        console.error('Ошибка обновления:', error);
    }
}

async function deleteNews(id) {
    if (!confirm('Вы уверены?')) return;
    
    try {
        const response = await fetch(`/api/news/${id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: document.getElementById('adminPassword').value
            })
        });
        
        if (response.ok) {
            alert('✅ Новость удалена');
            loadNews();
            loadAdminNews();
        }
    } catch (error) {
        console.error('Ошибка удаления:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initPlayer();
    loadNews();
    setInterval(loadNews, 30000);
});

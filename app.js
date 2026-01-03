/* ===== TELEGRAM SAFE INIT ===== */
let tg = null;

if (window.Telegram && window.Telegram.WebApp) {
  tg = window.Telegram.WebApp;
  tg.ready();
}

/* ===== RADIO ===== */
const radioStream = new Audio(
  "https://media1.datacenter.by:1936/radiomir/radiomir/playlist.m3u8"
);
radioStream.crossOrigin = "anonymous";

const playBtn = document.getElementById("playBtn");

playBtn.onclick = () => {
  if (radioStream.paused) {
    radioStream.play();
    playBtn.textContent = "⏸";
  } else {
    radioStream.pause();
    playBtn.textContent = "▶️";
  }
};

/* ===== ON AIR ===== */
function getOnAir() {
  const h = new Date().getHours();
  if (h >= 7 && h < 11) return "Мировое утро";
  if (h >= 11 && h < 12) return "Музыкальный нон-стоп";
  if (h >= 12 && h < 16) return "Все просто с Катей Жаворонок";
  if (h >= 16 && h < 20) return "Вечер без суеты с Женей Задорой";
  return "Музыкальный нон-стоп";
}

document.getElementById("onAir").textContent = getOnAir();

/* ===== VOTES CACHE ===== */
let votesCache = [];

fetch("data/votes.csv")
  .then(r => r.ok ? r.text() : "")
  .then(text => {
    votesCache = text
      .split("\n")
      .slice(1)
      .map(row => {
        const [d,t,u,track] = row.split(",");
        return { user:u, track };
      });
  });

function hasVoted(userId, trackId) {
  return votesCache.some(v => v.user == userId && v.track == trackId);
}

/* ===== PREVIEW PLAYER ===== */
let preview = new Audio();

function playPreview(url) {
  preview.pause();
  preview = new Audio(url);
  preview.play();
}

/* ===== TRACKS ===== */
fetch("data/tracks.json")
  .then(r => r.json())
  .then(tracks => {
    const box = document.getElementById("tracks");
    const user = tg?.initDataUnsafe?.user || null;

    tracks.forEach(t => {
      const voted = user ? hasVoted(user.id, t.id) : false;

      const div = document.createElement("div");
      div.className = "track";
      div.innerHTML = `
        <strong>${t.artist}</strong><br>
        ${t.title}<br><br>

        <button onclick="playPreview('${t.audio}')">▶️</button>

        <button class="vote-btn ${voted ? 'disabled' : ''}"
          onclick="vote(${t.id}, 'like', this)">👍</button>

        <button class="vote-btn ${voted ? 'disabled' : ''}"
          onclick="vote(${t.id}, 'dislike', this)">👎</button>

        ${voted ? '<div class="vote-info">Вы уже голосовали</div>' : ''}
      `;
      box.appendChild(div);
    });
  });

/* ===== VOTE ===== */
function vote(trackId, type, btn) {
  if (!tg || !tg.initDataUnsafe?.user) {
    alert("Чтобы голосовать, откройте через Telegram");
    return;
  }

  const user = tg.initDataUnsafe.user;

  if (hasVoted(user.id, trackId)) return;

  btn.parentElement.querySelectorAll(".vote-btn").forEach(b => {
    b.classList.add("disabled");
  });

  btn.classList.add("selected");

  const info = document.createElement("div");
  info.className = "vote-info";
  info.textContent = "Спасибо! Голос принят";
  btn.parentElement.appendChild(info);
}

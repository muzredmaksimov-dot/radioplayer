// Безопасное подключение Telegram WebApp
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.expand();
  tg.ready();
  console.log("Запущено внутри Telegram");
} else {
  console.log("Запущено вне Telegram");
}

// Плеер
const playBtn = document.getElementById("playBtn");
const radio = document.getElementById("radio");

if (playBtn && radio) {
  playBtn.addEventListener("click", () => {
    radio.play()
      .then(() => {
        console.log("Эфир запущен");
      })
      .catch(err => {
        console.log("Ошибка воспроизведения", err);
      });
  });
}

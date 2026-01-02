let tg = null;

if (window.Telegram && window.Telegram.WebApp) {
  tg = window.Telegram.WebApp;
  tg.expand();
  tg.ready();
  console.log("Telegram WebApp OK");
} else {
  console.log("Обычный браузер");
}

document.addEventListener("DOMContentLoaded", () => {
  const playBtn = document.getElementById("playBtn");
  const radio = document.getElementById("radio");

  if (!playBtn || !radio) {
    console.error("Кнопка или плеер не найдены");
    return;
  }

  playBtn.addEventListener("click", () => {
    radio.play()
      .then(() => {
        console.log("Эфир запущен");
      })
      .catch(err => {
        console.error("Ошибка воспроизведения", err);
      });
  });
});

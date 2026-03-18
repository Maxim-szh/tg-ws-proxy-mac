# Telegram WS Proxy для macOS

[![Release](https://img.shields.io/github/v/release/Maxim-szh/tg-ws-proxy-mac)](https://github.com/Maxim-szh/tg-ws-proxy-mac/releases)
[![Issues](https://img.shields.io/github/issues/Maxim-szh/tg-ws-proxy-mac)](https://github.com/Maxim-szh/tg-ws-proxy-mac/issues)
[![License](https://img.shields.io/github/license/Maxim-szh/tg-ws-proxy-mac?cacheSeconds=1)](https://github.com/Maxim-szh/tg-ws-proxy-mac/blob/main/LICENSE)

Локальный SOCKS5-прокси для Telegram Desktop, который ускоряет загрузку файлов через WebSocket.

## ✨ Возможности

- 🚀 Ускорение загрузки фото/видео в Telegram
- 🖥️ Нативное macOS приложение с иконкой в трее
- 🔧 Простая настройка через GUI
- 📊 Статистика работы в реальном времени
- 💪 Поддержка Apple Silicon (M1/M2/M3/M4/M5)

## 📥 Установка

### Вариант 1: Готовое приложение (рекомендуется)

1. Скачайте **TG-WS-Proxy-ARM64-FINAL.dmg** из [релизов](https://github.com/Maxim-szh/tg-ws-proxy-mac/releases)
2. Откройте скачанный файл
3. Перетащите **TG WS Proxy.app** в папку **Программы**
4. Запустите приложение из **Программ**
5. При первом запуске: правый клик → **Открыть** (разрешить)

### Вариант 2: Из исходников

```bash
git clone https://github.com/Maxim-szh/tg-ws-proxy-mac.git
cd tg-ws-proxy-mac
pip install -r requirements-mac.txt
python app/macos.py
```

🚀 Использование
Запустите TG WS Proxy (иконка появится в меню-баре)

Откройте Telegram Desktop

Настройки → Продвинутые → Тип подключения → Прокси

Добавьте SOCKS5:

Сервер: 127.0.0.1

Порт: 1080

Логин/пароль: оставить пустыми

⚙️ Настройка через иконку в трее можно:

🔗 Открыть Telegram с настройками прокси

🔄 Перезапустить прокси

⚙️ Изменить порт и DC серверы

📂 Просмотреть логи

🚪 Выйти из приложения

📋 Логи
```
~/Library/Application Support/TgWsProxy/proxy.log
```
🛠 Сборка из исходников
``` bash
cd installer
./build_app.sh
```

📄 Лицензия
MIT License

🤝 Обратная связь и поддержка
Если у вас возникли проблемы или есть предложения:

🐛 Сообщить об ошибке – создайте Bug Report

💡 Предложить идею – создайте Feature Request

❓ Задать вопрос – создайте Question

Или просто откройте новый Issue

⭐ Поддержка проекта
Если проект оказался полезным, поставьте звезду на GitHub – это помогает развитию!

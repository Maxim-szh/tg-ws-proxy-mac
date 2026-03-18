# TG WS Proxy для macOS

[![Release](https://img.shields.io/github/v/release/yourusername/tg-ws-proxy-mac)](https://github.com/yourusername/tg-ws-proxy-mac/releases)
[![Downloads](https://img.shields.io/github/downloads/yourusername/tg-ws-proxy-mac/total)](https://github.com/yourusername/tg-ws-proxy-mac/releases)

Локальный SOCKS5-прокси для Telegram Desktop, который ускоряет загрузку файлов через WebSocket.

## ✨ Возможности

- 🚀 Ускорение загрузки фото/видео в Telegram
- 🖥️ Нативное macOS приложение с иконкой в трее
- 🔧 Простая настройка через GUI
- 📊 Статистика работы в реальном времени
- 💪 Поддержка Apple Silicon (M1/M2/M3) и Intel

## 📥 Установка

### Вариант 1: Готовое приложение (рекомендуется)

Скачайте установщик для вашей архитектуры:

- **🍏 Apple Silicon (M1/M2/M3)**: [TG-WS-Proxy-1.1.1-arm64.dmg](https://github.com/yourusername/tg-ws-proxy-mac/releases/latest)
- **💻 Intel**: [TG-WS-Proxy-1.1.1-x86_64.dmg](https://github.com/yourusername/tg-ws-proxy-mac/releases/latest)

1. Скачайте .dmg файл
2. Откройте его и перетащите `TG WS Proxy.app` в папку `Программы`
3. Запустите приложение из `Программ`

### Вариант 2: Из исходников

```bash
# Клонируем репозиторий
git clone https://github.com/yourusername/tg-ws-proxy-mac.git
cd tg-ws-proxy-mac

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем
python app/macos.py
Вариант 3: Через Homebrew (скоро)
bash
brew tap yourusername/tg-ws-proxy
brew install tg-ws-proxy
🚀 Использование
Запустите TG WS Proxy

В меню-баре появится иконка приложения

Откройте Telegram Desktop

Настройки → Продвинутые → Тип подключения → Прокси

Добавьте SOCKS5 прокси:

Сервер: 127.0.0.1

Порт: 1080

⚙️ Настройка
Через иконку в трее можно:

Открыть Telegram с настройками прокси

Перезапустить прокси

Изменить порт и DC серверы

Просмотреть логи

Выйти из приложения

🛠 Сборка .app из исходников
bash
cd installer
./build_universal.sh
📄 Лицензия
MIT License

⭐ Поддержка
Если проект помог, поставьте звезду на GitHub!

text

### 2. `INSTALL.md` (подробная инструкция):

```markdown
# Инструкция по установке

## Для обычных пользователей

### Шаг 1: Скачайте приложение
1. Перейдите на [страницу релизов](https://github.com/yourusername/tg-ws-proxy-mac/releases)
2. Скачайте файл для вашего Mac:
   - **Apple Silicon (M1/M2/M3)**: файл с `arm64` в названии
   - **Intel**: файл с `x86_64` в названии

### Шаг 2: Установите приложение
1. Откройте скачанный .dmg файл
2. Перетащите **TG WS Proxy.app** в папку **Программы**
3. Откройте папку **Программы** и дважды кликните на **TG WS Proxy**

### Шаг 3: Разрешите запуск (только при первом запуске)
Если macOS блокирует приложение:

**Способ 1: Через Finder**
- Нажмите правой кнопкой мыши на **TG WS Proxy.app**
- Выберите **"Открыть"**
- В диалоге нажмите **"Открыть"**

**Способ 2: Через терминал**
```bash
xattr -d com.apple.quarantine /Applications/TG\ WS\ Proxy.app
Шаг 4: Настройте Telegram
Откройте Telegram Desktop

Настройки → Продвинутые → Тип подключения → Прокси

Добавьте SOCKS5 прокси:

Сервер: 127.0.0.1

Порт: 1080

Логин/пароль: оставьте пустыми

Для разработчиков
Запуск из исходников
bash
# Клонируем репозиторий
git clone https://github.com/yourusername/tg-ws-proxy-mac.git
cd tg-ws-proxy-mac

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем
python app/macos.py
Сборка .app для распространения
bash
cd installer
./build_universal.sh
Готовое приложение появится в installer/dist/TG WS Proxy.app


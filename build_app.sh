#!/bin/bash

# Конфигурация
APP_NAME="TG WS Proxy"
VERSION="1.1.1"
BUILD_DIR="build"
DIST_DIR="dist"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}🔨 Building $APP_NAME v$VERSION for macOS (Universal)...${NC}"

# Очистка предыдущей сборки
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Создаём структуру .app
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Копируем файлы приложения - ВАЖНО: кладём всё в корень Resources, а не в proxy
echo "📦 Copying application files..."
if [ -d "../app" ]; then
    # Копируем все файлы в корень Resources (так проще для импортов)
    cp ../app/macos.py "$RESOURCES_DIR/"
    cp ../app/tg_ws_proxy.py "$RESOURCES_DIR/"
    cp ../app/__init__.py "$RESOURCES_DIR/" 2>/dev/null || true
    
    # Создаем пустой __init__.py чтобы папка стала модулем
    touch "$RESOURCES_DIR/__init__.py"
else
    echo -e "${RED}❌ Error: Cannot find application files (../app/)${NC}"
    exit 1
fi

# Копируем requirements
if [ -f "../requirements-mac.txt" ]; then
    cp ../requirements-mac.txt "$RESOURCES_DIR/"
else
    echo -e "${RED}⚠️  Warning: requirements-mac.txt not found${NC}"
fi

# Копируем README если есть
if [ -f "../README.md" ]; then
    cp ../README.md "$RESOURCES_DIR/"
fi

# Создаём универсальный установщик зависимостей
echo "📦 Creating universal dependency installer..."
cat > "$RESOURCES_DIR/install_deps.py" << 'PYTHON_EOF'
#!/usr/bin/env python3
import sys
import subprocess
import platform
import os

def main():
    arch = platform.machine()
    print(f"📦 Installing dependencies for {arch}...")
    
    # Обновляем pip
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=False)
    
    packages = [
        "psutil==5.9.8",
        "rumps==0.4.0",
        "pyperclip==1.9.0"
    ]
    
    for pkg in packages:
        print(f"Installing {pkg}...")
        cmd = [sys.executable, "-m", "pip", "install"]
        
        # Для psutil используем правильную архитектуру
        if pkg.startswith("psutil"):
            if arch == "arm64":
                # Apple Silicon
                cmd.extend(["--platform", "macosx_11_0_arm64", "--only-binary=:all:"])
            elif arch == "x86_64":
                # Intel
                cmd.extend(["--platform", "macosx_10_15_x86_64", "--only-binary=:all:"])
        
        cmd.append(pkg)
        
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Installed {pkg}")
        except subprocess.CalledProcessError:
            # Fallback to normal install
            print(f"⚠️  Falling back to standard install for {pkg}")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    
    # Отмечаем, что зависимости установлены
    with open(os.path.join(os.path.dirname(__file__), ".deps_installed"), "w") as f:
        f.write(arch)
    
    print("✅ All dependencies installed successfully!")

if __name__ == "__main__":
    main()
PYTHON_EOF

chmod +x "$RESOURCES_DIR/install_deps.py"

# Создаём простую иконку (синий круг с буквой T)
echo "🎨 Creating icon..."
mkdir -p icon.iconset
# Создаём базовое изображение с помощью Python
python3 -c "
from PIL import Image, ImageDraw
import os

size = 1024
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
margin = size // 8
draw.ellipse([margin, margin, size - margin, size - margin], 
             fill=(51, 144, 236, 255))  # Telegram blue

# Пытаемся добавить букву T
try:
    from PIL import ImageFont
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size // 2)
        bbox = draw.textbbox((0, 0), 'T', font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1]
        draw.text((tx, ty), 'T', fill=(255, 255, 255, 255), font=font)
    except:
        pass
except:
    pass

img.save('icon.iconset/icon_512x512.png')
"

# Создаём все размеры иконок
sips -z 16 16 icon.iconset/icon_512x512.png --out icon.iconset/icon_16x16.png 2>/dev/null
sips -z 32 32 icon.iconset/icon_512x512.png --out icon.iconset/icon_32x32.png 2>/dev/null
sips -z 64 64 icon.iconset/icon_512x512.png --out icon.iconset/icon_64x64.png 2>/dev/null
sips -z 128 128 icon.iconset/icon_512x512.png --out icon.iconset/icon_128x128.png 2>/dev/null
sips -z 256 256 icon.iconset/icon_512x512.png --out icon.iconset/icon_256x256.png 2>/dev/null
sips -z 512 512 icon.iconset/icon_512x512.png --out icon.iconset/icon_512x512.png 2>/dev/null

# Конвертируем в icns
iconutil -c icns icon.iconset -o icon.icns
cp icon.icns "$RESOURCES_DIR/"

# Создаём Info.plist
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>org.telegram.tgwsproxy</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Создаём универсальный лаунчер
echo "🚀 Creating universal launcher..."
cat > "$MACOS_DIR/launcher" << 'EOF'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/../Resources"

# Функция для показа диалога
show_info() {
    osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with icon note"
}

show_error() {
    osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with icon stop"
}

# Определяем архитектуру
ARCH=$(uname -m)
echo "🔧 Architecture: $ARCH"

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    show_error "Python 3 не установлен!\n\nУстановите Python с python.org"
    exit 1
fi

# Создаём виртуальное окружение если нужно
if [ ! -d "venv" ]; then
    echo "📦 First run: creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    
    # Устанавливаем зависимости через универсальный установщик
    python3 install_deps.py
    
    if [ $? -ne 0 ]; then
        show_error "Не удалось установить зависимости. Проверьте соединение с интернетом."
        exit 1
    fi
else
    source venv/bin/activate
    
    # Проверяем, установлены ли зависимости для этой архитектуры
    if [ ! -f ".deps_installed" ] || [ "$(cat .deps_installed)" != "$ARCH" ]; then
        echo "🔄 Updating dependencies for $ARCH..."
        python3 install_deps.py
    fi
fi

# Исправляем импорт в macos.py если нужно (запускается один раз)
if [ -f "macos.py" ]; then
    if grep -q "import proxy.tg_ws_proxy" macos.py; then
        echo "🔧 Fixing import in macos.py..."
        cp macos.py macos.py.bak
        sed -i '' 's/import proxy.tg_ws_proxy/import tg_ws_proxy/g' macos.py
    fi
fi

# Запускаем приложение
echo "🚀 Starting TG WS Proxy..."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Пробуем разные способы запуска
if [ -f "macos.py" ]; then
    python3 macos.py
else
    show_error "Не найден файл macos.py"
    exit 1
fi

# Если приложение закрылось, показываем сообщение
show_info "TG WS Proxy остановлен.\n\nЛоги: ~/Library/Application Support/TgWsProxy/proxy.log"
EOF

chmod +x "$MACOS_DIR/launcher"

# Создаем README для пользователя
cat > "$RESOURCES_DIR/README.txt" << EOF
TG WS Proxy v$VERSION

Приложение запущено! Иконка появится в меню-баре.

Если не работает:
1. Убедитесь что установлен Python 3.8+
2. Проверьте логи: ~/Library/Application Support/TgWsProxy/proxy.log
3. Перезапустите приложение

Для настройки Telegram:
- Настройки → Продвинутые → Тип подключения → Прокси
- SOCKS5: 127.0.0.1:1080 (без логина/пароля)
EOF

echo -e "${GREEN}✅ Build complete: $APP_BUNDLE${NC}"
echo ""
echo "📦 To create DMG, run:"
echo "    brew install create-dmg"
echo "    create-dmg --volname \"$APP_NAME\" --volicon \"icon.icns\" --window-pos 200 120 --window-size 800 400 --icon-size 100 --icon \"$APP_NAME.app\" 200 190 --hide-extension \"$APP_NAME.app\" --app-drop-link 600 185 \"$DIST_DIR/$APP_NAME.dmg\" \"$DIST_DIR/$APP_NAME.app\""
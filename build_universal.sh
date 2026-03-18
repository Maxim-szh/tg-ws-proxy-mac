#!/bin/bash
echo "🔨 Building universal TG WS Proxy..."

# Запускаем основную сборку
./build_app.sh

# Проверяем результат
if [ $? -eq 0 ]; then
    echo "✅ Universal build complete!"
    echo ""
    echo "📦 App location: dist/TG WS Proxy.app"
    echo ""
    echo "🚀 To run: open \"dist/TG WS Proxy.app\""
else
    echo "❌ Build failed!"
    exit 1
fi

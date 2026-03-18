#!/bin/bash
# Launcher for TG WS Proxy macOS App

# Получаем путь к папке с приложением
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/../Resources"

# Активируем виртуальное окружение если есть, или создаём его
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    /usr/bin/python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install cryptography==41.0.7 psutil==5.9.8 rumps==0.4.0 pyperclip==1.9.0
else
    source venv/bin/activate
fi

# Запускаем приложение
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python macos.py

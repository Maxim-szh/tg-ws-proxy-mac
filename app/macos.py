#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations   # <-- ЭТО ДОЛЖНО БЫТЬ ПЕРВЫМ

# ==== СПЕЦИАЛЬНО ДЛЯ СКРЫТИЯ ИЗ ДОКА ====
import AppKit
import objc

# Принудительно устанавливаем политику активации как агент (без иконки в доке)
NSApp = AppKit.NSApplication.sharedApplication()
NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

# Дополнительно скрываем приложение из всех списков
NSApp.deactivate()

# Убеждаемся, что инфо-словарь содержит нужные ключи
bundle = AppKit.NSBundle.mainBundle()
info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
if info:
    info['LSUIElement'] = '1'
    info['NSUIElement'] = '1'
    info['Application is agent (UIElement)'] = '1'
    info['LSBackgroundOnly'] = '1'
# ==================================================

import os
import sys
import json
import time
import psutil
import threading
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
import webbrowser
from logging.handlers import RotatingFileHandler

# Для GUI на macOS используем PyObjC или стандартный tkinter с доработкой
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

# Для иконки в трее на macOS
try:
    import rumps
    RUMP_AVAILABLE = True
except ImportError:
    RUMP_AVAILABLE = False

import asyncio
# Импортируем tg_ws_proxy из той же папки
try:
    import tg_ws_proxy
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    import tg_ws_proxy

# Определяем пути для macOS
APP_NAME = "TgWsProxy"
APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "proxy.log"
FIRST_RUN_MARKER = APP_DIR / ".first_run_done"
IPV6_WARN_MARKER = APP_DIR / ".ipv6_warned"

# Обновленный DEFAULT_CONFIG с набором DC (2,4)
DEFAULT_CONFIG = {
    "port": 1080,
    "host": "127.0.0.1",
    "dc_ip": [
        "2:149.154.167.220",   # DC2 - основной трафик
        "4:149.154.167.220"    # DC4 - медиа
    ],
    "verbose": False,
}

RECOMMENDED_DC_IP = [
    "1:149.154.175.50",
    "2:149.154.167.220",
    "4:149.154.167.220",
    "5:91.108.56.100",
]

_proxy_thread: Optional[threading.Thread] = None
_async_stop: Optional[object] = None
_config: dict = {}
_exiting: bool = False
_lock_file_path: Optional[Path] = None
_logging_initialized = False

log = logging.getLogger("tg-ws-mac")


def _ensure_dirs():
    """Создание директорий для macOS"""
    APP_DIR.mkdir(parents=True, exist_ok=True)


def _acquire_lock() -> bool:
    """Проверка единственного экземпляра для macOS"""
    global _lock_file_path
    _ensure_dirs()
    
    lock_files = list(APP_DIR.glob("*.lock"))
    
    for f in lock_files:
        try:
            pid = int(f.stem)
            # Проверяем, существует ли процесс с таким PID
            try:
                os.kill(pid, 0)
            except OSError:
                # Процесс не существует, удаляем старый lock-файл
                f.unlink(missing_ok=True)
                continue
            
            # Проверяем, является ли процесс нашим приложением
            try:
                proc = psutil.Process(pid)
                if "python" in proc.name().lower() or APP_NAME.lower() in proc.name().lower():
                    # Приложение уже запущено
                    return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                f.unlink(missing_ok=True)
        except ValueError:
            f.unlink(missing_ok=True)
    
    # Создаем новый lock-файл
    lock_file = APP_DIR / f"{os.getpid()}.lock"
    try:
        lock_file.touch()
    except Exception:
        pass
    
    _lock_file_path = lock_file
    return True


def _release_lock():
    """Удаление lock-файла"""
    global _lock_file_path
    if _lock_file_path and _lock_file_path.exists():
        try:
            _lock_file_path.unlink()
        except Exception:
            pass
    _lock_file_path = None


def load_config() -> dict:
    """Загрузка конфигурации"""
    _ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception as exc:
            log.warning(f"Failed to load config: {exc}")
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    """Сохранение конфигурации"""
    _ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def setup_logging(verbose: bool = False):
    """Настройка логирования для macOS"""
    global _logging_initialized
    _ensure_dirs()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Prevent duplicate handlers on restart/reconfigure.
    if _logging_initialized:
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        return

    fh = RotatingFileHandler(
        str(LOG_FILE), maxBytes=3 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)

    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG if verbose else logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-5s  %(message)s",
            datefmt="%H:%M:%S"))
        root.addHandler(ch)

    _logging_initialized = True


def start_proxy():
    """Запуск прокси в отдельном потоке"""
    global _proxy_thread, _config
    if _proxy_thread and _proxy_thread.is_alive():
        log.info("Proxy already running")
        return
    
    cfg = _config
    port = cfg.get("port", DEFAULT_CONFIG["port"])
    host = cfg.get("host", DEFAULT_CONFIG["host"])
    dc_ip_list = cfg.get("dc_ip", DEFAULT_CONFIG["dc_ip"])
    verbose = cfg.get("verbose", False)
    
    try:
        dc_opt = tg_ws_proxy.parse_dc_ip_list(dc_ip_list)
    except ValueError as e:
        log.error(f"Bad config dc_ip: {e}")
        _show_error_dialog(f"Ошибка конфигурации:\n{e}")
        return
    
    log.info(f"Starting proxy on {host}:{port} ...")
    _proxy_thread = threading.Thread(
        target=_run_proxy_thread,
        args=(port, dc_opt, verbose, host),
        daemon=True, name="proxy")
    _proxy_thread.start()


def _run_proxy_thread(port: int, dc_opt: Dict[int, List[str]], verbose: bool,
                      host: str = '127.0.0.1'):
    """Запуск прокси в asyncio"""
    global _async_stop
    
    # Настраиваем логирование для потока
    setup_logging(verbose)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_ev = asyncio.Event()
    _async_stop = (loop, stop_ev)
    
    try:
        loop.run_until_complete(
            tg_ws_proxy._run(port, dc_opt, stop_event=stop_ev, host=host))
    except Exception as exc:
        log.error(f"Proxy thread crashed: {exc}")
        if "Address already in use" in str(exc):
            _show_error_dialog(
                "Не удалось запустить прокси:\nПорт уже используется другим приложением.\n\n"
                "Закройте приложение, использующее этот порт, или измените порт в настройках прокси и перезапустите.")
    finally:
        loop.close()
        _async_stop = None


def stop_proxy():
    """Остановка прокси"""
    global _proxy_thread, _async_stop
    if _async_stop:
        loop, stop_ev = _async_stop
        loop.call_soon_threadsafe(stop_ev.set)
        if _proxy_thread:
            _proxy_thread.join(timeout=5)
            if _proxy_thread.is_alive():
                log.warning("Proxy thread is still alive after stop timeout")
    _proxy_thread = None
    log.info("Proxy stopped")


def restart_proxy():
    """Перезапуск прокси"""
    log.info("Restarting proxy...")
    stop_proxy()
    time.sleep(0.3)
    start_proxy()


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _show_error_dialog(text: str, title: str = "TG WS Proxy — Ошибка"):
    """Показ диалога ошибки на macOS"""
    if TK_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, text)
        root.destroy()
    else:
        script = (
            f'display dialog "{_escape_applescript(text)}" '
            f'with title "{_escape_applescript(title)}" '
            f'buttons {{"OK"}} default button "OK" with icon stop'
        )
        subprocess.run(['osascript', '-e', script], capture_output=True)


def _show_info_dialog(text: str, title: str = "TG WS Proxy"):
    """Показ информационного диалога на macOS"""
    if TK_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, text)
        root.destroy()
    else:
        script = (
            f'display dialog "{_escape_applescript(text)}" '
            f'with title "{_escape_applescript(title)}" '
            f'buttons {{"OK"}} default button "OK" with icon note'
        )
        subprocess.run(['osascript', '-e', script], capture_output=True)


def _show_yesno_dialog(text: str, title: str = "TG WS Proxy") -> bool:
    """Диалог Да/Нет на macOS"""
    if TK_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        result = messagebox.askyesno(title, text)
        root.destroy()
        return result
    else:
        script = (
            f'display dialog "{_escape_applescript(text)}" '
            f'with title "{_escape_applescript(title)}" '
            f'buttons {{"Нет", "Да"}} default button "Да"'
        )
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        return "button returned:Да" in result.stdout


def _prompt_text_dialog(text: str, default: str = "", title: str = "TG WS Proxy") -> Optional[str]:
    """Native macOS prompt with text input. Returns None on cancel."""
    script = (
        f'display dialog "{_escape_applescript(text)}" '
        f'with title "{_escape_applescript(title)}" '
        f'default answer "{_escape_applescript(default)}" '
        f'buttons {{"Отмена", "OK"}} default button "OK"'
    )
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    marker = "text returned:"
    if marker not in out:
        return None
    return out.split(marker, 1)[1].strip()


def _prompt_yesno_native(text: str, title: str = "TG WS Proxy") -> Optional[bool]:
    """Native macOS yes/no prompt. Returns None on cancel/error."""
    script = (
        f'display dialog "{_escape_applescript(text)}" '
        f'with title "{_escape_applescript(title)}" '
        f'buttons {{"Отмена", "Нет", "Да"}} default button "Да"'
    )
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if "button returned:Да" in out:
        return True
    if "button returned:Нет" in out:
        return False
    return None


def _has_ipv6_enabled() -> bool:
    """Проверка включен ли IPv6 на macOS"""
    try:
        result = subprocess.run(['sysctl', '-n', 'net.inet6.ip6.use_tempaddr'], 
                               capture_output=True, text=True)
        return result.stdout.strip() == '1'
    except Exception:
        return False


class TgWsProxyApp:
    """Основной класс приложения для macOS"""
    
    def __init__(self):
        # ==== ДОПОЛНИТЕЛЬНОЕ СКРЫТИЕ ИЗ ДОКА ====
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApp = NSApplication.sharedApplication()
            NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            NSApp.deactivate()
        except:
            pass
        # ========================================
        
        self.config = load_config()
        self.proxy_running = False
        self.status_var = None
        self.stats_text = None
        self.root = None
        self.log_window = None
        self.log_text = None
        self.log_tail_lines = 250
        self._tray_mode = False
        
        # Настройка базового логирования
        setup_logging(self.config.get("verbose", False))
        
        # On macOS Tahoe tkinter may crash in tray context.
        # Prefer tray startup and avoid first-run tkinter wizard.
        if RUMP_AVAILABLE:
            FIRST_RUN_MARKER.touch(exist_ok=True)
            self.start_in_tray()
            return

        if not FIRST_RUN_MARKER.exists():
            self.show_first_run()
        else:
            self.start_in_tray()
    
    def start_in_tray(self):
        """Запуск в системном трее"""
        if RUMP_AVAILABLE:
            self._tray_mode = True
            self.run_rumps_app()
        else:
            self._tray_mode = False
            # Fallback на стандартное окно
            self.show_main_window()
    
    def run_rumps_app(self):
        """Запуск через rumps (macOS native tray)"""
        class TgWsProxyRumps(rumps.App):
            def __init__(self, app_instance):
                super().__init__("TG WS Proxy", icon=None, quit_button="Выход")
                self.app = app_instance
                self.menu = [
                    rumps.MenuItem(f"Открыть в Telegram (127.0.0.1:{app_instance.config['port']})", 
                                  callback=self.open_in_telegram),
                    None,  # Separator
                    rumps.MenuItem("Перезапустить прокси", callback=self.restart_proxy),
                    rumps.MenuItem("Настройки", callback=self.show_settings),
                    rumps.MenuItem("Открыть логи", callback=self.open_logs),
                ]
            
            def open_in_telegram(self, sender):
                self.app.open_in_telegram()
            
            def restart_proxy(self, sender):
                self.app.restart_proxy_action()
            
            def show_settings(self, sender):
                self.app.show_settings_window()
            
            def open_logs(self, sender):
                self.app.open_logs()
            
        # Запуск прокси
        start_proxy()
        
        # Запуск rumps app
        TgWsProxyRumps(self).run()
    
    def show_main_window(self):
        """Показ основного окна (если нет трея)"""
        if not TK_AVAILABLE:
            print("Tkinter not available, running in console mode")
            start_proxy()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                stop_proxy()
            return
        
        self.root = tk.Tk()
        self.root.title("TG WS Proxy")
        self.root.geometry("500x400")
        
        # Центрирование окна
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Статус
        status_frame = ttk.LabelFrame(main_frame, text="Статус", padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.status_var = tk.StringVar(value="Прокси запущен")
        ttk.Label(status_frame, textvariable=self.status_var, font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
        
        # Статистика
        self.stats_text = scrolledtext.ScrolledText(main_frame, height=10, width=60)
        self.stats_text.grid(row=1, column=0, columnspan=2, pady=10)
        self.update_stats()
        
        # Кнопки
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Открыть в Telegram", 
                  command=self.open_in_telegram).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Настройки", 
                  command=self.show_settings_window).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Перезапустить", 
                  command=self.restart_proxy_action).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Логи", 
                  command=self.open_logs).grid(row=0, column=3, padx=5)
        
        # Запуск прокси
        start_proxy()
        
        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.root.mainloop()
    
    def update_stats(self):
        """Обновление статистики"""
        if self.stats_text and self.stats_text.winfo_exists():
            stats = tg_ws_proxy._stats.summary() if hasattr(tg_ws_proxy, '_stats') else "Статистика недоступна"
            best_ip = (
                tg_ws_proxy._best_ip_snapshot()
                if hasattr(tg_ws_proxy, '_best_ip_snapshot')
                else "недоступно"
            )
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, f"Статистика работы:\n{stats}\n\n")
            self.stats_text.insert(tk.END, f"Лучшие IP по DC:\n{best_ip}\n\n")
            self.stats_text.insert(tk.END, f"Лог-файл: {LOG_FILE}\n")
            self.root.after(2000, self.update_stats)
    
    def show_first_run(self):
        """Показ окна первого запуска"""
        # Скрываем это окно из Дока
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except:
            pass
        
        if not TK_AVAILABLE:
            FIRST_RUN_MARKER.touch()
            return
        
        root = tk.Tk()
        root.title("TG WS Proxy — Первый запуск")
        root.geometry("500x400")
        
        # Центрирование
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="TG WS Proxy", 
                 font=('Helvetica', 16, 'bold')).pack(pady=(0, 20))
        
        ttk.Label(main_frame, text="Прокси успешно запущен!\n\n"
                  "Для подключения Telegram Desktop:\n"
                  "1. Откройте Telegram → Настройки → Продвинутые → Тип подключения → Прокси\n"
                  "2. Выберите SOCKS5\n"
                  f"3. Сервер: {self.config['host']}\n"
                  f"4. Порт: {self.config['port']}\n"
                  "5. Логин/пароль оставьте пустыми\n\n"
                  "Приложение будет работать в системном трее.",
                 justify=tk.LEFT).pack(pady=10)
        
        auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Открыть прокси в Telegram сейчас",
                       variable=auto_var).pack(pady=10)
        
        def on_ok():
            FIRST_RUN_MARKER.touch()
            open_tg = auto_var.get()
            root.destroy()
            if open_tg:
                self.open_in_telegram()
            self.start_in_tray()
        
        ttk.Button(main_frame, text="Начать", command=on_ok).pack(pady=20)
        
        root.mainloop()
    
    def show_settings_window(self):
        """Окно настроек"""
        # Скрываем окно настроек из Дока
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except:
            pass

        # Native simple settings for tray mode (no tkinter on Tahoe).
        if self._tray_mode:
            try:
                current_port = str(self.config.get("port", DEFAULT_CONFIG["port"]))
                current_dc = ', '.join(self.config.get("dc_ip", DEFAULT_CONFIG["dc_ip"]))

                port_s = _prompt_text_dialog(
                    "Порт прокси (1..65535):", default=current_port,
                    title="TG WS Proxy - Настройки"
                )
                if port_s is None:
                    return
                try:
                    port = int(port_s.strip())
                    if not (1 <= port <= 65535):
                        raise ValueError
                except ValueError:
                    _show_error_dialog("Некорректный порт. Допустимо: 1..65535")
                    return

                dc_raw = _prompt_text_dialog(
                    "DC маппинги через запятую (формат DC:IP).\n"
                    "Рекомендуется: 1,2,4,5",
                    default=current_dc,
                    title="TG WS Proxy - Настройки"
                )
                if dc_raw is None:
                    return
                lines = [x.strip() for x in dc_raw.split(',') if x.strip()]
                if not lines:
                    lines = list(RECOMMENDED_DC_IP)
                tg_ws_proxy.parse_dc_ip_list(lines)

                new_config = {
                    "host": "127.0.0.1",
                    "port": port,
                    "dc_ip": lines,
                    "verbose": bool(self.config.get("verbose", DEFAULT_CONFIG["verbose"])),
                }
                save_config(new_config)
                self.config.update(new_config)
                subprocess.run([
                    'osascript', '-e',
                    'display notification "Настройки сохранены" with title "TG WS Proxy"'
                ], capture_output=True)

                restart_now = _prompt_yesno_native(
                    "Перезапустить прокси сейчас?", title="TG WS Proxy - Настройки"
                )
                if restart_now:
                    restart_proxy()
            except Exception as exc:
                log.error(f"Native settings dialog failed: {exc}")
                subprocess.run(['open', str(CONFIG_FILE)])
            return

        if not TK_AVAILABLE:
            return

        if self.root and self.root.winfo_exists():
            settings_window = tk.Toplevel(self.root)
        else:
            settings_window = tk.Tk()
        settings_window.title("Настройки TG WS Proxy")
        settings_window.geometry("500x500")
        settings_window.resizable(False, False)
        
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Host
        ttk.Label(main_frame, text="IP-адрес прокси:").grid(row=0, column=0, sticky=tk.W, pady=5)
        host_var = tk.StringVar(value=self.config.get("host", "127.0.0.1"))
        host_entry = ttk.Entry(main_frame, textvariable=host_var, width=30)
        host_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        
        # Port
        ttk.Label(main_frame, text="Порт прокси:").grid(row=1, column=0, sticky=tk.W, pady=5)
        port_var = tk.StringVar(value=str(self.config.get("port", 1080)))
        port_entry = ttk.Entry(main_frame, textvariable=port_var, width=30)
        port_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        
        # DC mappings
        ttk.Label(main_frame, text="DC → IP маппинги (формат DC:IP):").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        dc_frame = ttk.Frame(main_frame)
        dc_frame.grid(row=3, column=0, columnspan=2, pady=5)
        
        dc_text = tk.Text(dc_frame, width=50, height=8)
        dc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(dc_frame, orient=tk.VERTICAL, command=dc_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        dc_text.config(yscrollcommand=scrollbar.set)
        
        # Заполняем текущими значениями
        current_dc = self.config.get("dc_ip", DEFAULT_CONFIG["dc_ip"])
        dc_text.insert("1.0", "\n".join(current_dc))
        
        # Verbose
        verbose_var = tk.BooleanVar(value=self.config.get("verbose", False))
        ttk.Checkbutton(main_frame, text="Подробное логирование (verbose)",
                       variable=verbose_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        ttk.Label(main_frame, text="Изменения вступят в силу после перезапуска прокси.",
                 foreground="gray").grid(row=5, column=0, columnspan=2, pady=5)
        
        def save_settings():
            # Валидация
            try:
                host = host_var.get().strip()
                if not host:
                    raise ValueError("host")
                port = int(port_var.get().strip())
                if not (1 <= port <= 65535):
                    raise ValueError("port")
                
                lines = [l.strip() for l in dc_text.get("1.0", "end").strip().splitlines() if l.strip()]
                if not lines:
                    raise ValueError("dc")
                tg_ws_proxy.parse_dc_ip_list(lines)
                
                # Сохраняем
                new_config = {
                    "host": host,
                    "port": port,
                    "dc_ip": lines,
                    "verbose": verbose_var.get()
                }
                save_config(new_config)
                self.config.update(new_config)
                
                settings_window.destroy()
                
                if _show_yesno_dialog("Настройки сохранены. Перезапустить прокси сейчас?"):
                    restart_proxy()
                
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    "Некорректные значения.\n"
                    "- Host не должен быть пустым\n"
                    "- Port: 1..65535\n"
                    "- DC строки в формате DC:IP"
                )

        def load_defaults():
            host_var.set(DEFAULT_CONFIG["host"])
            port_var.set(str(DEFAULT_CONFIG["port"]))
            dc_text.delete("1.0", "end")
            dc_text.insert("1.0", "\n".join(DEFAULT_CONFIG["dc_ip"]))
            verbose_var.set(DEFAULT_CONFIG["verbose"])

        def test_config():
            try:
                host = host_var.get().strip()
                if not host:
                    raise ValueError("host")
                port = int(port_var.get().strip())
                if not (1 <= port <= 65535):
                    raise ValueError("port")
                lines = [l.strip() for l in dc_text.get("1.0", "end").strip().splitlines() if l.strip()]
                if not lines:
                    raise ValueError("dc")
                tg_ws_proxy.parse_dc_ip_list(lines)
                _show_info_dialog("Проверка прошла успешно. Конфигурация выглядит корректной.")
            except ValueError:
                messagebox.showerror("Ошибка", "Проверка не пройдена. Исправьте значения и повторите.")
        
        ttk.Button(main_frame, text="Проверить", command=test_config).grid(row=6, column=0, pady=20, sticky=tk.W)
        ttk.Button(main_frame, text="По умолчанию", command=load_defaults).grid(row=6, column=0, pady=20)
        ttk.Button(main_frame, text="Сохранить", command=save_settings).grid(row=6, column=1, pady=20, sticky=tk.W)
        ttk.Button(main_frame, text="Отмена", command=settings_window.destroy).grid(row=6, column=1, pady=20, sticky=tk.E)

        settings_window.lift()
        settings_window.focus_force()
    
    def open_in_telegram(self):
        """Открыть прокси в Telegram"""
        port = self.config.get("port", DEFAULT_CONFIG["port"])
        url = f"tg://socks?server=127.0.0.1&port={port}"
        log.info(f"Opening {url}")
        
        try:
            webbrowser.open(url)
        except Exception as e:
            log.error(f"Failed to open URL: {e}")
            # Копируем в буфер обмена на macOS
            try:
                subprocess.run(
                    ['osascript', '-e', f'set the clipboard to "{_escape_applescript(url)}"']
                )
                _show_info_dialog(
                    f"Не удалось открыть Telegram автоматически.\n\n"
                    f"Ссылка скопирована в буфер обмена: {url}")
            except Exception as exc:
                log.error(f"Clipboard copy failed: {exc}")
    
    def restart_proxy_action(self):
        """Действие при перезапуске"""
        restart_proxy()
        if self.status_var:
            self.status_var.set("Прокси перезапущен")
    
    def _read_log_tail(self, max_lines: int) -> str:
        if not LOG_FILE.exists():
            return "Лог-файл еще не создан.\n"
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return ''.join(lines[-max_lines:])
        except Exception as exc:
            return f"Не удалось прочитать лог: {exc}\n"

    def _refresh_log_view(self):
        if not self.log_window or not self.log_text:
            return
        if not self.log_window.winfo_exists() or not self.log_text.winfo_exists():
            self.log_window = None
            self.log_text = None
            return
        content = self._read_log_tail(self.log_tail_lines)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", content)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.log_window.after(1200, self._refresh_log_view)

    def open_logs(self):
        """Удобный просмотр логов внутри GUI с автообновлением."""
        if self._tray_mode:
            try:
                _ensure_dirs()
                if not LOG_FILE.exists():
                    LOG_FILE.touch()
                subprocess.run(['open', str(LOG_FILE)])
            except Exception as exc:
                log.error(f"Failed to open logs: {exc}")
            return

        if not TK_AVAILABLE:
            if LOG_FILE.exists():
                subprocess.run(['open', str(LOG_FILE)])
            else:
                _show_info_dialog("Файл логов еще не создан.")
            return

        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.focus_force()
            return

        if self.root and self.root.winfo_exists():
            self.log_window = tk.Toplevel(self.root)
        else:
            self.log_window = tk.Tk()
        self.log_window.title("TG WS Proxy - Логи")
        self.log_window.geometry("900x560")

        main = ttk.Frame(self.log_window, padding="10")
        main.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(toolbar, text="Показать строк:").pack(side=tk.LEFT)
        tail_var = tk.StringVar(value=str(self.log_tail_lines))
        tail_combo = ttk.Combobox(
            toolbar,
            textvariable=tail_var,
            width=8,
            state="readonly",
            values=("100", "250", "500", "1000", "2000"),
        )
        tail_combo.pack(side=tk.LEFT, padx=(6, 10))

        def apply_tail(*_args):
            try:
                self.log_tail_lines = int(tail_var.get())
            except ValueError:
                self.log_tail_lines = 250
            self._refresh_log_view()

        tail_combo.bind("<<ComboboxSelected>>", apply_tail)

        ttk.Button(
            toolbar, text="Открыть файл", command=lambda: subprocess.run(['open', str(LOG_FILE)])
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(toolbar, text="Обновить", command=self._refresh_log_view).pack(side=tk.LEFT)

        self.log_text = scrolledtext.ScrolledText(main, wrap=tk.WORD, font=("Menlo", 11))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

        self._refresh_log_view()
        self.log_window.lift()
        self.log_window.focus_force()
    
    def on_closing(self):
        """Обработка закрытия окна"""
        if _show_yesno_dialog("Прокси продолжит работу в фоне. Свернуть в трей?"):
            if self.root:
                self.root.withdraw()
            # TODO: Показать иконку в трее
        else:
            self.quit_app()
    
    def quit_app(self):
        """Завершение приложения"""
        global _exiting
        _exiting = True
        log.info("User requested exit")
        stop_proxy()
        _release_lock()
        
        # Завершаем процесс
        if self.root:
            self.root.quit()
        sys.exit(0)


def check_dependencies():
    """Проверка зависимостей для macOS"""
    missing = []
    
    if not TK_AVAILABLE:
        missing.append("tkinter (обычно встроен в Python)")
    
    if not RUMP_AVAILABLE:
        missing.append("rumps (установите: pip install rumps)")
    
    # Проверяем наличие tg_ws_proxy в текущей папке (не в proxy/)
    try:
        # tg_ws_proxy уже импортирован в начале файла
        tg_ws_proxy.__name__
        print("✅ tg_ws_proxy найден")
    except NameError:
        try:
            # Пробуем импортировать ещё раз
            import tg_ws_proxy
            print("✅ tg_ws_proxy импортирован")
        except ImportError:
            missing.append("tg_ws_proxy.py (должен быть в той же папке)")
    
    if missing:
        print("Отсутствуют зависимости:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nУстановите недостающие компоненты и запустите снова.")
        return False
    
    print("✅ Все зависимости найдены")
    return True


def main():
    """Основная функция"""
    # ==== ДОПОЛНИТЕЛЬНОЕ СКРЫТИЕ ПРИ ЗАПУСКЕ ====
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except:
        pass
    # ============================================
    
    # Проверяем наличие зависимостей
    if not check_dependencies():
        input("\nНажмите Enter для выхода...")
        return
    
    # Проверяем единственный экземпляр
    if not _acquire_lock():
        _show_info_dialog("Приложение уже запущено.", "TG WS Proxy")
        return
    
    try:
        # Создаем и запускаем приложение
        app = TgWsProxyApp()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        stop_proxy()
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
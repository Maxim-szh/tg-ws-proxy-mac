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
            else:
                # Другая архитектура
                pass
        
        cmd.append(pkg)
        
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Installed {pkg}")
        except subprocess.CalledProcessError:
            # Fallback to normal install
            print(f"⚠️  Falling back to standard install for {pkg}")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    
    # Отмечаем, что зависимости установлены
    deps_file = os.path.join(os.path.dirname(__file__), ".deps_installed")
    with open(deps_file, "w") as f:
        f.write(arch)
    
    print("✅ All dependencies installed successfully!")

if __name__ == "__main__":
    main()

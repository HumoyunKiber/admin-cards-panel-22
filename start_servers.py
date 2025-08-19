#!/usr/bin/env python3
"""
SimCard Management System - Server Starter
Barcha serverlarni birga ishga tushirish uchun
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def check_python_version():
    """Python versiyasini tekshirish"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 yoki yuqori versiya kerak!")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} topildi")

def install_requirements():
    """Kerakli kutubxonalarni o'rnatish"""
    print("📦 Python kutubxonalarini o'rnatish...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        print("✅ Kutubxonalar muvaffaqiyatli o'rnatildi")
    except subprocess.CalledProcessError as e:
        print(f"❌ Kutubxonalarni o'rnatishda xato: {e}")
        print("🔧 Manual o'rnatish: pip install -r requirements.txt")
        
def start_servers():
    """Serverlarni ishga tushirish"""
    print("🚀 Serverlarni ishga tushirish...")
    
    # Status API serverni ishga tushirish (9020 port)
    print("🔵 SimCard Status API ishga tushirilmoqda (port 9020)...")
    status_process = subprocess.Popen([sys.executable, "simcard_status_api.py"])
    
    # Biroz kutish
    time.sleep(2)
    
    # Asosiy API serverni ishga tushirish (9022 port)  
    print("🔵 Main SimCard API ishga tushirilmoqda (port 9022)...")
    main_process = subprocess.Popen([sys.executable, "malin.py"])
    
    print("\n" + "="*60)
    print("🎉 SERVERLAR MUVAFFAQIYATLI ISHGA TUSHIRILDI!")
    print("="*60)
    print("📍 SimCard Status API: http://localhost:9020")
    print("📍 Main SimCard API: http://localhost:9022")
    print("📍 API Docs: http://localhost:9022/docs")
    print("📍 Health Check: http://localhost:9022/health")
    print("\n💡 Web ilovani ishga tushirish uchun alohida terminalde:")
    print("   npm run dev")
    print("\n⚠️  Serverlarni to'xtatish uchun: Ctrl+C")
    print("="*60)
    
    try:
        # Serverlar ishlaydi
        status_process.wait()
        main_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Serverlar to'xtatilmoqda...")
        status_process.terminate()
        main_process.terminate()
        print("✅ Serverlar to'xtatildi")

def main():
    """Asosiy funksiya"""
    print("🔧 SimCard Management System - Server Starter")
    print("="*50)
    
    # Fayl mavjudligini tekshirish
    required_files = ["malin.py", "simcard_status_api.py", "requirements.txt"]
    missing_files = [f for f in required_files if not Path(f).exists()]
    
    if missing_files:
        print(f"❌ Quyidagi fayllar topilmadi: {', '.join(missing_files)}")
        sys.exit(1)
    
    check_python_version()
    install_requirements()
    start_servers()

if __name__ == "__main__":
    main()
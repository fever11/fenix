# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""FENIX Nöbet modu başlatıcısı (v5.10.0). Arayüzü yüklemeden yalnızca hafif izleme işlemini çalıştırır.

  python nobet_main.py                        nöbet (tepsi simgesi + izleme)
  python nobet_main.py --soyle "metin" [ses]  metni bir kez sesli okur (nöbet bunu uyarı için kullanır)
  python nobet_main.py --baslangic-kontrol    açılışta başlayan programlardaki değişiklikleri JSON yazar
  python nobet_main.py --sohbet               küçük yazılı yan sohbet penceresi (v5.10.1)
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())


def main(argv):
    from modules import nobet
    if len(argv) >= 2 and argv[1] == "--soyle":
        nobet.speak_once(argv[2] if len(argv) > 2 else "", argv[3] if len(argv) > 3 else None)
    elif len(argv) >= 2 and argv[1] == "--baslangic-kontrol":
        nobet.startup_check_json()
    elif len(argv) >= 2 and argv[1] == "--sohbet":
        from modules import mini_chat
        mini_chat.main()
    else:
        nobet.run()


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:
        try:
            from modules.killswitch import log_exit
            log_exit(f"nöbet başlatıcı hatası: {type(e).__name__}: {e}")
        except Exception:
            pass
        raise

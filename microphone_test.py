# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
FENIX Mikrofon Testi
---------------------
Uygulamayı açmadan mikrofonu dener: bulunan mikrofonları listeler, 4 saniye kayıt alır,
ses seviyesini gösterir ve konuşmayı yazıya çevirmeyi dener. Sorunun nerede olduğunu söyler.
Çalıştırma: Microphone_Test.bat (çift tıkla)
"""
import sys
import time
import yaml

sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None

from modules.audio_io import PushToTalkRecorder, list_input_devices
from modules import stt

cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
a = cfg.get("audio", {})
print("=" * 60)
print(" FENIX MİKROFON TESTİ")
print("=" * 60)
devs = list_input_devices()
if not devs:
    print("\n✗ Hiç mikrofon bulunamadı. Mikrofonu takıp Windows'un tanıdığından emin ol.")
else:
    print("\nBulunan mikrofonlar:")
    for idx, name, is_default in devs:
        print(f"  [{idx}] {name}{'   <- Windows varsayılanı' if is_default else ''}")
print(f"\nconfig.yaml -> audio.input_device: {a.get('input_device') or '(boş = varsayılan)'}")

rec = PushToTalkRecorder(sample_rate=a.get("sample_rate", 16000), device=a.get("input_device"))
input("\nEnter'a bas, sonra 4 saniye boyunca normal sesle bir şey söyle (ör. 'Opera'dan YouTube'u aç')...")
try:
    rec.record_until_released_async()
except Exception as e:
    print(f"\n✗ Mikrofon açılamadı: {e}")
    input("\nKapatmak için Enter...")
    sys.exit(1)
print(f"Kayıt: {rec.device_name}  ({rec.rate_used} Hz)")
end = time.time() + 4
while time.time() < end:
    lv = min(1.0, rec.level * 4)
    print(f"\r  seviye: {'#' * int(lv * 30):<30}  ", end="", flush=True)
    time.sleep(0.1)
wav = rec.stop_async()
print(f"\n\nEn yüksek seviye: %{rec.peak * 100:.1f}")
if rec.peak < 0.02:
    print("✗ Mikrofondan neredeyse hiç ses gelmedi.")
    print("  -> Windows: Ayarlar > Sistem > Ses > Giriş: doğru mikrofonu seç, seviyesini artır.")
    print("  -> Gizlilik > Mikrofon: 'Masaüstü uygulamalarının mikrofona erişmesine izin ver' AÇIK olmalı.")
    print("  -> Ya da yukarıdaki listeden numarayı config.yaml'da audio.input_device'a yaz.")
else:
    print("✓ Mikrofon ses alıyor. Yazıya çevriliyor...")
    groq = (cfg.get("api_keys", {}).get("groq") or "").strip() if a.get("stt", "groq") == "groq" else ""
    text, why = stt.transcribe(wav, groq_key=groq, model=a.get("stt_model", "whisper-large-v3-turbo"),
                               device_name=rec.device_name,
                               on_error=lambda where, d: print(f"  ! {where}: {d[:200]}"))
    print(f"\n{'✓ Duyduğum: ' + text if text else '✗ ' + why}")
input("\nKapatmak için Enter...")

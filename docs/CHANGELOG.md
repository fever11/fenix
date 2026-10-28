# Changelog / Değişiklik günlüğü

## 1.0.0 — 2026-10-28
İlk herkese açık sürüm / first public release.

- **TR:** JARVIS v6 tabanından çıkarıldı ve adı FENIX oldu. Deneysel "öğrenme modu" (Oyun alanı, lab) kaldırıldı;
  FENIX kişisel asistan olarak çalışır. Arayüz, sesli cevap ve ses tanıma 6 dilde: Türkçe, English, Deutsch,
  Русский, Français, Español. Yeni simge, tek tıkla kurulum (`Setup.bat`) ve sade kurulum rehberleri eklendi.
- **EN:** Derived from the JARVIS v6 code base and renamed FENIX. The experimental "learning mode" (playground/lab)
  was removed; FENIX works as a personal assistant. UI, spoken replies and speech recognition in 6 languages.
  New icon, one-click setup (`Setup.bat`) and simple setup guides.
- **TR:** Kurulum 6 dilde çalışır ve gerekirse Python'u kurar; API anahtarı ilk açılışta küçük bir pencereden girilir
  (YAML düzenlemek gerekmez). Kaynak dosyalar, raporlar ve dışa aktarılan belgeler "Core: MK-Agentic-System ·
  Powered by FENIX Engine" imzasını taşır.
- **EN:** Setup runs in 6 languages and can install Python; the API key is entered in a small first-run window
  (no YAML editing). Source files, reports and exported documents carry the "Core: MK-Agentic-System · Powered by
  FENIX Engine" signature.
- **TR:** Sohbet sırası Groq → NVIDIA → Gemini (anahtarı olmayan atlanır). Kurulum ve yardımcı dosyaların adları
  İngilizce: `Setup.bat`, `Start_FENIX.vbs`, `Connection_Test.bat`, `Microphone_Test.bat`.
- **EN:** Chat order Groq → NVIDIA → Gemini (providers without a key are skipped). Setup and helper files have English
  names: `Setup.bat`, `Start_FENIX.vbs`, `Connection_Test.bat`, `Microphone_Test.bat`.
- **TR:** Lisans: "Tüm hakları saklıdır / Kişisel Kullanım Lisansı"; AUTHORS.md eklendi.
- **EN:** License: "All rights reserved / Personal Use License"; AUTHORS.md added.
- **TR:** Yayına hazırlık: PRIVACY.md (hangi veri nerede/nereye gider), SECURITY.md, THIRD_PARTY_NOTICES.md
  (kütüphane lisansları, markalar), CONTRIBUTING.md (dış katkılar ve hak devri) eklendi.
- **EN:** Release preparation: PRIVACY.md, SECURITY.md, THIRD_PARTY_NOTICES.md (library licenses, trademarks) and
  CONTRIBUTING.md added.

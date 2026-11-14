<p align="center">
  <img src="assets/fenix.png" width="140" alt="FENIX">
</p>

<h1 align="center">FENIX</h1>
<p align="center"><b>Sesli, çok dilli kişisel masaüstü asistanı · Voice-enabled, multilingual desktop assistant</b><br>
Windows · Python 3.12 · Gemini / Groq / NVIDIA</p>

> [!IMPORTANT]
> **Şu an yalnızca Windows 10 ve 11'de çalışır.** macOS ve Linux desteği henüz yok.
> **Currently runs on Windows 10 and 11 only.** macOS and Linux are not supported yet.

<p align="center">
🇹🇷 <a href="docs/INSTALL_TR.md">Kurulum</a> ·
🇬🇧 <a href="docs/INSTALL_EN.md">Setup</a> ·
🇩🇪 <a href="docs/INSTALL_DE.md">Installation</a> ·
🇷🇺 <a href="docs/INSTALL_RU.md">Установка</a> ·
🇫🇷 <a href="docs/INSTALL_FR.md">Installation</a> ·
🇪🇸 <a href="docs/INSTALL_ES.md">Instalación</a>
</p>

---

## 🇬🇧 English

FENIX is a personal assistant for Windows that you can talk to or type to. It answers in your language, sees your
screen when you ask, reads the files you attach, researches the web in depth, and can carry out everyday tasks on your
computer — always asking for approval before anything risky.

**Languages:** Türkçe · English · Deutsch · Русский · Français · Español (interface, spoken replies and speech recognition)

**Features**
- 💬 Text and push-to-talk voice chat (F9), with spoken replies
- 👁 Screen vision: "what's this error on my screen?"
- 📎 Attachments: PDF, Word, Excel, code, images
- 🔎 Devil mode: multi-step web research with sourced reports (export to PDF/Word)
- 🖥 System actions: open apps/sites/folders, volume, close windows… (with an approval box)
- ⏰ Reminders, notes, daily summary, persistent memory
- 🌙 Watch mode: a light tray process that warns about risky downloads, suspicious links, clipboard wallet swaps and startup changes
- 📒 Action log with undo: every file FENIX creates, overwrites or deletes can be undone (deleted files go to FENIX's own trash for 30 days)
- 🖱 Right-click menu (summarize, translate, "is this safe?", make PDF, ask FENIX) and a long-press hotkey (Numpad + by default, changeable) to send selected text
- 📊 System panel: CPU/RAM/disk/GPU/network gauges, top processes, battery health, health report, security events
- ☀ Daily briefing, once on the first start of the day: weather for your cities, reminders, exchange rates, headlines, your own topics
- 📚 Long, source-based study notes: written section by section, length grows with the sources you attach
- 🔁 Backup AI providers (Cloudflare, OpenRouter, Cohere…) when the free Groq quota runs out
- 🛑 Kill switch: Ctrl+Alt+Q or mouse in the top-left corner

**Quick start:** get free Gemini and Groq keys (backup keys are optional) → double-click `Setup.bat` (pick your language; it can install Python for you) →
start FENIX from the desktop icon → paste the keys into the window. No file editing. Step-by-step guide: [docs/INSTALL_EN.md](docs/INSTALL_EN.md).

## 🇹🇷 Türkçe

FENIX, yazarak ya da konuşarak kullanabildiğin bir Windows kişisel asistanıdır. Senin dilinde cevap verir, istersen
ekranını görür, eklediğin dosyaları okur, internette derin araştırma yapıp kaynaklı rapor yazar ve bilgisayarında
günlük işleri yapar — riskli her işlemden önce onay ister.

**Özellikler:** sesli/yazılı sohbet (F9 Bas-Konuş) · ekran görme · PDF/Word/Excel/kod/görsel ekleme · Devil modunda
derin araştırma ve rapor · onaylı sistem işlemleri · hatırlatma, not, gün özeti, kalıcı hafıza · nöbet modu (indirilen
dosya, şüpheli link, cüzdan adresi değişimi, açılış programı uyarıları) · geri alınabilen işlem defteri · sağ tık menüsü
ve seçili metin kısayolu (Numpad +, değiştirilebilir) · sistem paneli (CPU/RAM/disk/GPU göstergeleri, pil sağlığı, sağlık raporu) · günün ilk açılışında brifing · kaynağa
göre uzayan ders notları · Groq kotası dolunca yedek yapay zekâ servisleri · acil kapatma (Ctrl+Alt+Q).

**Hızlı başlangıç:** ücretsiz Gemini ve Groq anahtarlarını al (yedek anahtarlar isteğe bağlı) → `Setup.bat`'a çift tıkla (dilini seç; Python yoksa kendisi kurar) →
masaüstündeki FENIX simgesiyle aç → anahtarları pencereye yapıştır. Dosya düzenlemek yok. Adım adım rehber: [docs/INSTALL_TR.md](docs/INSTALL_TR.md).

---

## Modes / Modlar

| Mode | What it does |
|---|---|
| **Safe / Güvenli** | Chat only — never touches the system |
| **Normal** | Everyday assistant — safe actions, asks before risky ones |
| **Devil** | Deep analysis & agent — web research, multi-step tasks, still asks for critical actions |

## Privacy / Gizlilik

FENIX has no server and no telemetry; your keys, chats and memory stay on your computer. Messages are sent only to the
AI and web services you configure. Details: [PRIVACY.md](PRIVACY.md).
FENIX'in sunucusu ve kullanım takibi yoktur; anahtarların, sohbetlerin ve hafızan bilgisayarında kalır. Ayrıntılar: [PRIVACY.md](PRIVACY.md).

Security: [SECURITY.md](SECURITY.md) · Third-party licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) ·
Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

## Project layout

```
app.py                 main window
modules/               assistant logic (agent, memory, audio, i18n, watch mode…)
locales/               translations (en, de, ru, fr, es — Turkish is the source language)
docs/                  setup guides in 6 languages, changelog
config.example.yaml    settings template → copy to config.yaml
Setup.bat            one-click multilingual setup (scripts/setup.ps1: Python, packages, desktop shortcut)
Start_FENIX.vbs       start without a console window
```

Adding a language (for your own copy): copy `locales/en.json`, translate the values, then add the language code to `LANGS`, `LANG_NAMES_EN`,
`TTS_VOICES`, `STT_WHISPER` and `STT_GOOGLE` in `modules/i18n.py`.

## License / Lisans

© 2026 Mustafa Koç · Core: MK-Agentic-System · Powered by FENIX Engine

FENIX is free software under the **GNU GPL v3** (GPL-3.0-only) with a few additional terms (GPL section 7):
use it, study it, change it and share it — but share your changes under the same license, keep the credit
(*"Based on FENIX by Mustafa Koç"*), don't present FENIX as your own work, and give modified versions a different name.
No warranty. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
Google, Gemini, Groq, NVIDIA and Windows are trademarks of their owners; FENIX is not affiliated with them.

FENIX, **GNU GPL v3** (GPL-3.0-only) lisansı ve birkaç ek şartla (GPL 7. bölüm) özgür bir yazılımdır: kullan, incele,
değiştir, paylaş; ama değişikliklerini aynı lisansla paylaş, emeğin sahibini belirt (*"Mustafa Koç'un FENIX projesine
dayanır"*), FENIX'i kendi eserin gibi sunma ve değiştirdiğin sürüme başka bir ad ver. Garanti yoktur. Bkz.
[LICENSE](LICENSE) ve [NOTICE.md](NOTICE.md).

> The only official source of FENIX is this repository. / FENIX'in tek resmi kaynağı bu depodur.

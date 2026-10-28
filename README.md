<p align="center">
  <img src="assets/fenix.png" width="140" alt="FENIX">
</p>

<h1 align="center">FENIX</h1>
<p align="center"><b>Sesli, çok dilli kişisel masaüstü asistanı · Voice-enabled, multilingual desktop assistant</b><br>
Windows · Python 3.12 · Gemini / Groq / NVIDIA</p>

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
- 🛑 Kill switch: Ctrl+Alt+Q or mouse in the top-left corner

**Quick start:** get a free Gemini key → double-click `Setup.bat` (pick your language; it can install Python for you) →
start FENIX from the desktop icon → paste the key into the window. No file editing. Step-by-step guide: [docs/INSTALL_EN.md](docs/INSTALL_EN.md).

## 🇹🇷 Türkçe

FENIX, yazarak ya da konuşarak kullanabildiğin bir Windows kişisel asistanıdır. Senin dilinde cevap verir, istersen
ekranını görür, eklediğin dosyaları okur, internette derin araştırma yapıp kaynaklı rapor yazar ve bilgisayarında
günlük işleri yapar — riskli her işlemden önce onay ister.

**Özellikler:** sesli/yazılı sohbet (F9 Bas-Konuş) · ekran görme · PDF/Word/Excel/kod/görsel ekleme · Devil modunda
derin araştırma ve rapor · onaylı sistem işlemleri · hatırlatma, not, gün özeti, kalıcı hafıza · nöbet modu (indirilen
dosya, şüpheli link, cüzdan adresi değişimi, açılış programı uyarıları) · acil kapatma (Ctrl+Alt+Q).

**Hızlı başlangıç:** ücretsiz Gemini anahtarı al → `Setup.bat`'a çift tıkla (dilini seç; Python yoksa kendisi kurar) →
masaüstündeki FENIX simgesiyle aç → anahtarı pencereye yapıştır. Dosya düzenlemek yok. Adım adım rehber: [docs/INSTALL_TR.md](docs/INSTALL_TR.md).

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

© 2026 Mustafa Koç — **All rights reserved / Tüm hakları saklıdır.** Core: MK-Agentic-System · Powered by FENIX Engine

Personal, non-commercial use is free. Redistribution, commercial use, or presenting FENIX (or parts of it) as your own
work — including coursework, academic projects and competitions — requires the author's written permission.
See [LICENSE](LICENSE) and [AUTHORS.md](AUTHORS.md).
Google, Gemini, Groq, NVIDIA and Windows are trademarks of their owners; FENIX is not affiliated with them.

Kişisel ve ticari olmayan kullanım serbesttir. Yeniden dağıtmak, ticari kullanmak ya da FENIX'i (veya bir parçasını)
ödev, akademik proje ve yarışmalar dahil kendi eseri gibi sunmak yazarın yazılı iznine bağlıdır.

> The only official source of FENIX is this repository. / FENIX'in tek resmi kaynağı bu depodur.

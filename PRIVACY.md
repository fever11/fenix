# Privacy / Gizlilik

FENIX runs on your own computer. It has **no server of its own and no telemetry**: the author receives nothing.
FENIX kendi bilgisayarında çalışır. **Kendine ait bir sunucusu ve kullanım takibi yoktur**: yazara hiçbir veri gelmez.

## Stored only on your computer / Yalnızca bilgisayarında saklananlar

| Data / Veri | Where / Nerede |
|---|---|
| API keys / API anahtarları | `config.yaml` |
| Chats, notes, memory, reminders, statistics / Sohbetler, notlar, hafıza, hatırlatmalar, istatistik | `data/` |
| Reports / Raporlar | `data/raporlar/` |
| Error log / Hata kaydı | `data/hatalar.log` |

Deleting the FENIX folder deletes all of this. / FENIX klasörünü silmek bunların hepsini siler.

## Sent to third-party services / Üçüncü taraf servislere gidenler

FENIX only works by sending some data to AI and web services **using your own accounts and keys**. Their own
privacy policies apply. / FENIX, bazı verileri **senin hesapların ve anahtarlarınla** yapay zekâ ve web servislerine
göndererek çalışır; bu servislerin kendi gizlilik politikaları geçerlidir.

| Service / Servis | What is sent / Ne gönderilir | When / Ne zaman |
|---|---|---|
| Google Gemini | Messages, attached files, screenshots, text for memory search (embeddings) / Mesajlar, eklenen dosyalar, ekran görüntüleri, hafıza araması için metin | Chat, "look at my screen", attachments, memory / Sohbet, ekran görme, ekler, hafıza |
| Groq | Messages; voice recordings for speech recognition / Mesajlar; ses tanıma için ses kaydı | If a Groq key is set / Groq anahtarı varsa |
| NVIDIA | Messages (backup chat), screenshots (last-resort vision) / Mesajlar (yedek sohbet), ekran görüntüsü (son yedek) | If an NVIDIA key is set / NVIDIA anahtarı varsa |
| Google speech recognition | Voice recordings / Ses kaydı | If Groq is not used / Groq kullanılmıyorsa |
| Microsoft Edge read-aloud (edge-tts) | Text that FENIX speaks / FENIX'in sesli okuduğu metin | Voice replies on / Sesli cevap açıksa |
| GitHub (api.github.com) | Nothing personal: an anonymous request for the latest FENIX release number / Kişisel hiçbir şey: en son FENIX sürüm numarası için kimliksiz bir istek | At most every 6 hours; can be turned off in Settings / En fazla 6 saatte bir; Ayarlar'dan kapatılabilir |
| DuckDuckGo, Bing, Tavily, Brave, visited websites | Search queries, page requests / Arama sorguları, sayfa istekleri | Web search and research / Web araması ve araştırma |

Screenshots are taken **only when you ask** (e.g. "what's on my screen"); the screen is never recorded continuously.
Ekran görüntüsü **yalnızca sen istediğinde** alınır; ekran sürekli kaydedilmez.

## Watch mode / Nöbet modu

Watch mode checks file names and types in Downloads, links copied to the clipboard and startup programs, **on your
computer only**. It does not read document or image contents, does not store or send clipboard text, and does not
watch the screen or microphone.
Nöbet modu İndirilenler'deki dosya adlarını ve türlerini, panoya kopyalanan linkleri ve açılış programlarını **yalnızca
bilgisayarında** kontrol eder. Belge/resim içeriğini okumaz, pano metnini saklamaz ya da göndermez, ekranı ve mikrofonu
izlemez.

## Private chat / Gizli sohbet

In 🕶 private chat, messages, actions and the title are not saved. / 🕶 Gizli sohbette mesajlar, yapılanlar ve başlık kaydedilmez.

## Tips / Öneriler

- Don't share `config.yaml` or `data/`. / `config.yaml` ve `data/` klasörünü paylaşma.
- Don't send passwords or ID numbers to FENIX; they would be sent to the AI service. / FENIX'e şifre ya da kimlik numarası
  yazma; yapay zekâ servisine gider.

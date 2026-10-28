# FENIX Kurulum Rehberi (Türkçe)

Toplam süre yaklaşık **15 dakika**. Bilgisayar bilgisi gerekmez; adımları sırayla yap.

## Neye ihtiyacın var?

| | |
|---|---|
| Bilgisayar | Windows 10 veya 11 |
| Program | Python 3.12 (ücretsiz) |
| Anahtar | Gemini API anahtarı (ücretsiz, zorunlu) |
| İsteğe bağlı | Groq API anahtarı (ücretsiz; daha hızlı sohbet ve daha iyi ses tanıma) |
| İsteğe bağlı | NVIDIA API anahtarı (ücretsiz; Groq dolunca yedek sohbet) — https://build.nvidia.com |

## 1. FENIX'i indir

1. GitHub sayfasında yeşil **Code** düğmesine bas → **Download ZIP**.
2. ZIP'e sağ tıkla → **Tümünü ayıkla**. Klasörü kolay bir yere koy, örneğin `Belgeler\fenix`.

## 2. Python'u kur

1. https://www.python.org/downloads/ adresinden **Python 3.12**'yi indir.
2. Kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu **mutlaka işaretle**, sonra **Install Now**.

## 3. Gemini anahtarını al

1. https://aistudio.google.com/apikey adresine Google hesabınla gir.
2. **Create API key** → çıkan anahtarı kopyala. Bu anahtarı **kimseyle paylaşma**.
3. (İsteğe bağlı) https://console.groq.com/keys adresinden bir Groq anahtarı da alabilirsin.

## 4. Kurulumu çalıştır

1. FENIX klasöründeki **`Setup.bat`** dosyasına çift tıkla.
   - "Windows bilgisayarınızı korudu" uyarısı çıkarsa: **Ek bilgi → Yine de çalıştır**.
2. Açılan pencerede dilini seç (1-6).
3. Python yoksa kurulum bunu söyler ve otomatik kurmayı önerir.
4. Paketler kurulurken bekle (5-10 dakika). Sonunda masaüstüne **FENIX** kısayolu eklenir.

## 5. FENIX'i başlat ve anahtarı yapıştır

- Masaüstündeki **FENIX** simgesine çift tıkla.
- İlk açılışta küçük bir **API anahtarı** penceresi çıkar: Gemini anahtarını yapıştır (Groq varsa onu da), **Kaydet ve başlat**'a bas. Dosya düzenlemen gerekmez.
- Dili sonra **⚙️ Ayarlar**'dan değiştirebilirsin.

## Kısa kullanım

| Ne | Nasıl |
|---|---|
| Yazarak sohbet | Alta yaz, **Enter** |
| Sesli sohbet | **🎤 Bas-Konuş** düğmesi ya da **F9** |
| Dosya / görsel ekleme | **📎**, sürükle-bırak ya da **Ctrl+V** |
| Mod | **Güvenli** (sadece sohbet) · **Normal** (günlük işler, riskliyse sorar) · **Devil** (derin araştırma, rapor) |
| Acil durdurma | **Ctrl+Alt+Q** ya da fareyi sol üst köşede 1,5 sn tut |

FENIX riskli bir işlem (silme, kapatma, indirme vb.) yapmadan önce **her modda onay sorar**.

## Sorun mu var?

| Belirti | Çözüm |
|---|---|
| "Python bulunamadı" | Python'u tekrar kur ve **Add python.exe to PATH** kutusunu işaretle. |
| Anahtar hatası / cevap gelmiyor | **`Connection_Test.bat`** dosyasını çalıştır; hangi anahtarın çalışmadığını söyler. |
| Mikrofon duymuyor | **`Microphone_Test.bat`** dosyasını çalıştır. Windows ses ayarlarında doğru mikrofonu seç. |
| Pencere açılmıyor | **`Start_FENIX_Debug.bat`** ile başlat; hata mesajı ekranda kalır. |
| Nöbet modu çalışmıyor | Sadece Windows'ta çalışır; `Setup.bat`'ı yeniden çalıştır. |

## Güvenlik

- `config.yaml` dosyasında anahtarların var: **kimseye gönderme, GitHub'a yükleme.**
- `data` klasöründe sohbetlerin ve hafızan durur; o da kişiseldir.
- Anahtarın bir yerde göründüyse sitesinden **sil ve yenisini oluştur**.

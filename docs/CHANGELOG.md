# Changelog / Değişiklik günlüğü

## 1.4.0 — 2026-11-14
- **TR:** İlk açılış penceresi: Gemini ve Groq anahtarları zorunlu (ikisi de ücretsiz); altında kaydırılabilir
  "isteğe bağlı" bölümde yedek anahtarlar (Cloudflare token + Account ID, OpenRouter, Cohere, NVIDIA, Tavily), her
  satırda "Anahtar al" düğmesi. Boş bırakılanlar config.yaml'a yazılmaz. Kurulum rehberleri (6 dil) ve Setup.bat
  mesajı buna göre güncellendi. Brifingin sadece günün ilk açılışında geldiği rehberde belirtildi.
- **TR:** Kaynağa göre uzayan ders notları (Mustafa'nın isteği: "çok kaynak verirsek çok uzun bir ders notu çıkmalı,
  hiç eksik hissettirmemeli"). "Ders notu çıkar / kapsamlı not hazırla" istekleri bölüm bölüm yazılır: ekli kaynaklar
  parçalara ayrılır, bölüm sayısı kaynak miktarına göre belirlenir (6-30), her kaynak parçası mutlaka bir bölüme
  atanır (plan bir parçayı atlarsa kod ekler), her bölüm ayrı istekle sadece kendi kaynağıyla yazılır; sonda "Kendini
  Dene" soruları, özet ve hangi kaynağın hangi bölümde kullanıldığı. İlerleme soldaki günlükte ("bölüm 3/12
  yazılıyor"); süre bölüm başına verilir, sadece bir bölüm takılırsa durulur. Güvenli modda kapalı.
- **TR:** Güzel belgeler (Mustafa'nın isteği; sabit şablon değil): model içeriğe göre yapıyı kendisi kurar, kod her
  yapı taşını aynı kalitede çizer. Yapı taşları: tanım, örnek, ipucu, dikkat, özet, formül, soru–cevap, adım adım, not,
  alıntı, doğrulanmamış bilgi kutuları (`::: tür başlık … :::`); konuya göre renk teması (`<!-- tema: yesil -->`);
  renkli kapak, uzun belgede içindekiler, renkli tablo başlıkları, sayfa numarası. PDF'te Türkçe harfler, alt simgeler
  (CO₂) ve oklar (→) doğru basılır (Windows'ta Segoe UI / Consolas).
- **TR:** Uydurma yerine tahmin: model emin olmadığı sayı, tarih ve isimleri "tahminim / yaklaşık / doğrulamadım" diye
  belirtir, okumadığı kaynağı göstermez. Kaynak bölümü olmayan Word/PDF belgelerinin sonuna "kaynak gösterilmeyen
  bilgileri kontrol et" notu eklenir.
- **TR:** Günlük brifing (Mustafa'nın fikri): günün ilk açılışında sohbete tek mesaj; selamlama saate göre (akşam
  açılınca "Günaydın" denmez). İçeriği kullanıcı ilk açılışta seçer, Ayarlar > "Günlük brifing ayarları"ndan değiştirir:
  hava (yazılan şehir, Open-Meteo), bugünkü ve kaçırılan hatırlatmalar, döviz kurları (Frankfurter), haber başlıkları
  (Google Haberler RSS). Yapay zekâ kullanılmaz, kota harcamaz; sohbette "brifing" ya da "günün özeti" yazınca da
  gösterilir. Konum otomatik bulunmaz. Birden fazla şehir virgülle yazılabilir (Bartın, Bilecik). Ayrıca serbest
  metinle istenen konular ("Galatasaray'ın son maçı, Bitcoin fiyatı") brifingden sonra yapay zekâ ve arama ile
  cevaplanır (yalnızca bu kısım kota kullanır; boş bırakılırsa çalışmaz).
- **TR:** 🖥️ Sistem paneli (Mustafa'nın fikri, OMEN Gaming Hub'daki "System Vitals"tan esinlendi): CPU / RAM /
  ekran kartı (NVIDIA: kullanım ve sıcaklık) halkaları, disk doluluk çubukları, ağ hızı, pil (yüzde ve pil sağlığı),
  en çok kaynak kullanan programlar (onaylı Kapat); sağlık raporu (disk, bellek, pil, açılış programları, son
  güvenlik olayları, en büyük dosyalar); işlem defteri (her satırda Geri al, FENIX çöp kutusu); güvenlik olayları
  listesi. Hepsi yerel okuma, yapay zekâ ve kota kullanmaz. Geçmiş, Raporlar, İstatistik, Ayarlar, Eklentiler,
  Yetenekler ve Öğrendiklerim panelin üstündeki kısayollara taşındı; sol menü 4 düğmeye indi (Sistem, Hatırlatma,
  Geçmiş, Nöbete geç). Sol altta küçük CPU / RAM / Disk doluluk çubukları (tıklayınca panel açılır). Panel ve
  çubuklar seçili modun rengini alır (Güvenli / Normal / Devil); %75 üstü turuncu, %90 üstü kırmızı uyarı rengidir.
- **TR:** Sağ tık menüsü (Mustafa'nın fikri): Ayarlar'dan açılınca dosyaya/klasöre sağ tıklayınca "FENIX" alt menüsü
  çıkar: Özetle, Çevir, Bu dosya güvenli mi?, PDF'e dönüştür, FENIX'e sor. İstek yan sohbet (Nöbet) penceresine gider,
  pencere kapalıysa açılır; ana pencereyi beklemek gerekmez. "Bu dosya güvenli mi?" yapay zekâ kullanmadan Nöbet'in
  dosya denetimiyle (ad, tür, imza, Windows Defender) cevaplanır. Menü sadece bu kullanıcı için eklenir (yönetici izni
  gerekmez), Ayarlar'dan tek tıkla kaldırılır. Windows 11'de "Daha fazla seçenek göster" altındadır.
- **TR:** Seçili metin kısayolu: herhangi bir uygulamada metni seçip sayı tuş takımındaki "+" tuşunu basılı tutunca
  (~0,5 sn) metin yan sohbete gelir ve "bununla ne yapayım?" diye sorulur (boş Enter = açıkla). Kısa basış eskisi gibi
  "+" yazar. Ana pencere ve Nöbet aynı anda açıksa kısayolu yalnızca biri dinler. Ayarlar'dan kapatılabilir ve tuş
  değiştirilebilir (Mustafa'nın isteği): Numpad +, Numpad -, F8, F10, F12, Pause (kısa basış tuşun normal işini yapar).
- **TR:** İşlem defteri ve geri alma (Mustafa'nın fikri): FENIX'in bilgisayarda yaptığı her değişiklik (dosya
  oluşturma, üzerine yazma, düzenleme, silme, komut, açılıştan kaldırma) `data/islem_defteri.jsonl` dosyasına tek
  satır olarak yazılır. "Bugün ne yaptın?" listeyi, "son yaptığını geri al" ya da "<numara> geri al" geri almayı
  yapay zekâya sormadan yapar (kota harcamaz); geri alma onay ister ve var olan bir dosyanın üzerine asla yazmaz.
- **TR:** FENIX çöp kutusu: FENIX'in sildiği dosyalar Geri Dönüşüm Kutusu yerine `data/cop` klasörüne taşınır, 30 gün
  sonra FENIX açılışında kalıcı silinir (sadece FENIX'in sildikleri). Üzerine yazılan dosyanın eski hâli de buraya
  kopyalanır. Dosya başka bir sürücüdeyse Geri Dönüşüm Kutusu kullanılır. PowerShell ile dosya silme komutları
  `delete_file` aracına yönlendirilir ki her silme geri alınabilsin.
- **TR:** Hızlı ek yedekler: Groq'un kotası dolunca yavaş NVIDIA'dan önce Mistral, SambaNova ve OpenRouter denenir
  (OpenAI uyumlu, tek kod). Sadece `config.yaml`'a anahtarı yazılan sağlayıcı kullanılır; hata/kota veren sağlayıcı bir
  süre dinlendirilir. Hızlı bir yedek varsa Groq'un dakika sınırı uzun beklenmez (en fazla 8 sn). Mistral için araç
  kimlikleri ve ara sistem notları otomatik uyarlanır. Gemini'ye dokunulmaz (ekran okumaya ayrılmış). Not: 14.11.2026
  itibarıyla Mistral'ın ücretsiz planında API anahtarları etkin değil (ücretli plan gerekiyor); kart istemeyen
  seçenekler SambaNova ve OpenRouter.
- **TR:** Hızlı bir yedek varsa Groq'un dakika sınırında en fazla bir Groq modeline geçilir, sonra yedeğe gidilir
  (14.11 testinde 120b, 20b ve qwen sırayla denendi; her biri aramayı baştan yaptı, 2 dk'yı geçti).
- **TR:** Bir işlem (dosya yazma vb.) yapıldıktan sonra sağlayıcı hata verirse iş başka bir sağlayıcıyla baştan
  başlatılmaz; yapılanlar söylenir (14.11: dosya yazıldıktan sonra Groq sınıra takıldı, aynı dosya ikinci kez
  yazılacaktı). Yedek denemeleri ve başarısızlık sebepleri (anahtar geçersiz, ödeme gerekiyor, model yok, kota)
  soldaki günlüğe yazılır. OpenRouter varsayılan modeli `openrouter/free` (araç destekleyen ücretsiz modeli kendisi
  seçer). Not: 14.11'de SambaNova ücretsiz hesapta 402 "Payment Required" döndürdü.
- **TR:** Kart istemeyen iki yedek daha: **Cloudflare Workers AI** (Groq'taki aynı `gpt-oss-120b`, günde ~50 soru;
  token + Account ID) ve **Cohere** deneme anahtarı (ayda 1.000 istek, ticari değil). Varsayılan sıra: Cloudflare →
  OpenRouter → Cohere → Mistral → SambaNova (ücretli olanlar sonda) → NVIDIA.
- **TR:** Bozuk yedek cevabı ayıklanır: tek karakterin onlarca kez tekrarı (14.11'de Cloudflare'daki gpt-oss
  "!!!!…" döndürdü) kullanıcıya gösterilmez, sıradaki model/sağlayıcı denenir; günlüğe yazılır.
- **TR:** Cloudflare isteklerinde cevap uzunluğu (4096 token) belirtilir; belirtilmeyince Workers AI cevabı yarıda
  kesiyordu ("…Öğle saat"). Kesilen cevaplar günlüğe yazılır.

## 1.3.0 — 2026-11-13
- **TR:** Hafif yol: basit sohbet ve hesap sorularında ("selam", "%25 indirim kaç TL", "bir şiir yaz") modele kısa bir
  talimat gider ve araç tanımları gönderilmez (~10.400 yerine ~2.000 karakter). Groq'un ücretsiz katmanında dakikada
  8.000 token sınırı var; tam talimatla ardı ardına iki basit soru bile "dakikalık sınır"a takılıyordu (13.11 testi).
  Dosya, uygulama, hatırlatma, ekran, güncel bilgi ve FENIX'in kendisiyle ilgili sorular eskisi gibi tam yoldan
  gider; FENIX'in bir önceki cevabı bir teklifse ("…açayım mı?") ya da cevap "evet" ise de tam yol seçilir.
  Güvenlik ağı: kısa talimat bir soruya yetmezse model cevap yazmak yerine bunu bildirir ve soru otomatik olarak tam
  talimat ve araçlarla yeniden sorulur. Hangi yolun kullanıldığı soldaki işlem günlüğünde görünür ("hafif yol" /
  "hafif yol yetmedi → tam talimat…").
- **TR:** İş türü yükselmesi: "sohbet" sanılan bir iş aramaya ya da dosya işine dönerse süre sınırı o türe göre uzar
  ve günlükte "iş türü değişti" yazar; ölçüm de doğru türe kaydedilir. 13.11 testinde "Bu akşam Ankara'da yağmur var
  mı?" sohbet sayıldı, 90 sn'de kesildi. Hafif yolun yetmediği bir soru yedek modelde yeniden hafif yoldan denenmez.
  "Yağmur/kar/yağış var mı" gibi sorular baştan güncel bilgi sayılır.
- **TR:** Süre ayarları (13.11 ikinci deneme): öğrenilen ortalama sınırı yalnızca uzatır, varsayılanın altına indirmez
  (hızlı aramalardan sonra 'güncel bilgi' sınırı 90 sn'ye inmiş, kotaya takılan arama kesilmişti). Groq dakika
  sınırı beklemeleri ve yavaş yedek modele geçiş süreye eklenir (görev başına en fazla 2 dk). Tam yola geçiş iş türü
  etiketini değiştirmez (çeviri "Güncel bilgi" görünüyordu); "aynısını İspanyolcaya çevir" gibi takip istekleri hafif
  yolda kalır.
- **TR:** Süre dolduğunda o ana kadar yapılan işlemler söylenir ("Şunları yaptım: Dosya yazıldı: …\siir.txt"); 13.11'de
  şiir kaydedilmişti ama cevap sadece "durdum" diyordu ve kullanıcı işin yapılmadığını sanıyordu.
- **TR:** Dakikalık sınır: art arda sorularda gpt-oss-120b Groq'un dakikalık sınırına takılınca 40 sn beklenip yavaş
  NVIDIA modeline geçiliyordu; oysa gpt-oss-20b'nin kendi dakika kotası boştu. Artık hemen sıradaki Groq modeline
  geçilir (soru sırasında bilgisayarda bir işlem yapılmadıysa; yapıldıysa iş baştan tekrarlanmasın diye geçilmez).
  Dakika kotası dolan model bir dakika boyunca sona alınır. Günlükte "sıradaki Groq modeline geçiliyor" görünür.
- **TR:** "Bu akşam Ankara'da yağmur var mı?" sohbet sanılıp 90 sn süre almış, aramayla birlikte süre yetmemişti
  (13.11). Yağmur/kar/yağış/fırtına/hava durumu soruları artık güncel bilgi sayılır; hafif yoldan tam yola geçilen
  işlerde süre en az 150 sn'ye uzatılır.
- **EN:** Simple chat and calculation questions use a short, tool-less prompt to stay under Groq's per-minute token
  limit.

## 1.2.3 — 2026-11-13
- **TR:** Önceki cevap gelmeden yazılan mesaj artık sıraya alınır ve sırayla cevaplanır; bu bilgi sohbete değil,
  soldaki işlem günlüğüne yazılır. Önceden aynı anda ikinci bir görev başlıyordu: cevaplar yanlış soruların altına
  düşüyor, iki görev aynı kotayı tüketip ikisi de yavaşlıyordu (13.11 testi). "Durdur" sıradakileri de iptal eder.
- **TR:** İş türüne göre süre (Mustafa'nın fikri): FENIX isteğin türünü bulur (sohbet, hesap, güncel bilgi,
  bilgisayar işi, dosya, kod, belge, araştırma) ve o tür işlerin bu bilgisayarda gerçekte ne kadar sürdüğünü öğrenir
  (son 30 işin ortancası, `data/is_sureleri.json`). Günlükte "iş türü · tahmini süre · en fazla" görünür. Tahminin
  2 katı geçilince sebep yazılır (ör. "Groq günlük kotası doldu"). Üst sınır tahmine göre esner ve türün tavanını
  geçmez (sohbet 2 dk … araştırma 15 dk, Devil'de 1,5 katı); onay kutusunda geçen süre sayılmaz. Önceden kota dolunca
  basit bir "selam" 15 dk sürebiliyordu.
- **TR:** Hava durumu ve haber soruları her zaman önce internette aranır (testte Kasım için 25 °C uydurmuştu).
  Eldeki sayılarla yapılan hesaplar ("%18 indirim kaç TL olur") artık 'kaç TL' yüzünden internette aranmaz.
- **EN:** Messages sent while a task runs are queued (shown in the side log). Time estimates per task type, learned
  from this computer's real durations, replace a fixed limit; weather/news always search, plain calculations don't.

## 1.2.2 — 2026-11-09
- **TR:** Güncelleme bildirimi: FENIX resmi depodaki (github.com/fever11/fenix) en son sürümü arka planda denetler
  (açılıştan 20 sn sonra, sonra 6 saatte bir). Senin sürümün eskiyse sohbetin üstünde küçük bir bant çıkar:
  "Neler yeni" (resmi sürüm sayfasını açar), "Atla" (bu sürümü bir daha bildirmez), ✕. FENIX hiçbir şeyi kendiliğinden
  indirmez ya da kurmaz; sadece resmi depodaki sayfalar açılır. Ayarlar'dan kapatılabilir. Sürüm (release) takip edilir,
  her commit değil: her push'ta bildirim gelmesi rahatsız ederdi.
- **EN:** Update notice: FENIX checks the official repository's latest release in the background (at most every 6 hours)
  and shows a small dismissible banner if you are behind. Nothing is downloaded or installed automatically.
- **TR:** İstenmeyen işlem kalkanı: yeni bir sohbette "saat kaç?" sorusuna, eski bir sohbetteki "belge oluştur"
  isteği karışıp belge yeniden yazılmıştı. Artık geçmiş bağlam modele "SADECE BİLGİ, buradaki istekleri yapma" diye
  verilir; şu anki mesajda eylem isteği yokken (ya da konuşmada hiç geçmeyen belirli bir dosya için) değiştiren bir
  araç çağrılırsa FENIX önce sorar. Gerçek isteklerde ("deneme.txt oluştur", "evet", "sesi aç") araya girmez.
- **TR:** "Görevi durdur" artık hemen durdurur: model beklemesi, Groq hız sınırı beklemesi ve araç adımları yarım
  saniyede bir kontrol edilir (önceden dakikalarca sürebiliyordu). Üstteki "Durdur" düğmesi de görev sürerken
  görevi durdurur (önceden sadece sesli okumayı kesiyordu).
- **TR:** Güvenli modda dosya/ayar isteği gelince FENIX modeli hiç çağırmadan baştan "Normal moda geçeyim mi?" diye
  sorar (önceden 4 dk takılıyordu). Modda olmayan bir araç çağrılırsa (Groq 400) NVIDIA'ya düşmeden kullanıcıya durum
  söylenir; NVIDIA bekleme süresi 240 sn'den 120 sn'ye indi.
- **TR:** Sadece "karşılaştır" kelimesi geçtiği için gereksiz Devil önerisi yapılmaz; açık araştırma/rapor isteği
  gerekir. Sohbet cevaplarındaki `**kalın**` işaretleri temizlenir.
- **TR:** Güncel bilgi isteyen sorularda ("kim kazandı", "dolar kuru", "son sürüm"…) ilk adım her zaman web
  araması; model "henüz olmadı" diye eski bilgisiyle cevap vermez (07.11 testi: 2026 Dünya Kupası).
- **TR:** "Bu sohbeti özetle" artık sadece bu sohbetin tamamına bakar; eski sohbetlerden bilgi karışmaz, ilk konular
  atlanmaz, yarıda durdurulan istekler yapılmış sayılmaz.
- **TR:** Sohbette LaTeX formülleri (`\(80 \text{km} \times 2\)`) düz yazıya çevrilir; dosya içeriği gösterirken çıkan
  ``` çitleri kalkar (dil etiketli kod blokları kalır). Her cevabın başında süresi görünür ("FENIX · 2.3 sn").
- **TR:** Ses ayarı yeni pycaw sürümüyle çalışır ("'AudioDevice' object has no attribute 'Activate'" hatası).
- **TR:** "Şunu kapat" gibi belirsiz kapatma isteklerinde FENIX pencerenin adını söyleyip önce sorar (testte arkadaki
  Opera kapanmıştı).
- **TR:** "Hangi modelleri kullanıyorsun, mesajlarım nereye gidiyor?" gibi sorularda gerçek bilgi verilir.
- **TR:** Güvenli modda bir işleme "Normal'e geçeyim mi?" sorusuna "hayır" denince işlem denenmez, net söylenir.
- **TR:** Mod değişiminden sonra iş yeniden çalışınca FENIX "bu modda mı yapayım?" diye tekrar sormaz; Normal →
  Güvenli → Normal dönüşünde önceki mesajlar (ör. sınav tarihi) kaybolmaz.
- **TR:** "Bunu kapat" FENIX'in az önce açtığı uygulamayı hedefler (testte Hesap Makinesi yerine Opera soruluyordu).
- **TR:** Normal modda araştırma/rapor isteğinde başlamadan Devil önerilir; "hayır" denirse kısa cevap verilir ve
  Normal/Güvenli modda en fazla 5 arama yapılır (testte 17 arama, 4 dk, boş sonuç).
- **TR:** "Az önce … tekrar söyle" gibi isteklerde ilk adımda araç verilmez (testte alakasız web araştırması yaptı).
  Hatırlatma isteklerinde komut çalıştırma (schtasks) kapalı; sadece hatırlatma araçları kullanılır.
- **TR:** "Seni kim geliştirdi, hangi lisans?" sorusunda gerçek bilgi (GPL-3.0) verilir. Model, "…değil mi?" diye
  yanlış bir şey onaylatılmaya çalışılınca uymaz. Sohbette kod blokları düzgün gösterilir (# yorumlar başlık olmaz).
- **TR:** Yapmadan "yaptım" kontrolü: istekte bir işlem (sil, oluştur, kapat…) varken cevap "tamamlandı/silindi"
  diyor ama o turda bilgisayarda hiçbir değişiklik yapılmadıysa cevabın altına açık bir uyarı eklenir (testte
  "[İşlem tamamlandı]" denmiş, dosya silinmemişti).
- **EN:** Unwanted-action shield: requests from old chats in the memory context are marked as information only, and a
  changing tool called without an action request in the current message now asks for confirmation first.

## 1.2.1 — 2026-11-04
- **TR:** Lisans GNU GPL v3'e (GPL-3.0-only) geçti, ek şartlar `NOTICE.md`'de: FENIX'i herkes kullanabilir,
  değiştirebilir ve paylaşabilir; değişiklikler aynı lisansla açık kalır, "Mustafa Koç'un FENIX projesine dayanır" atfı
  korunur, FENIX kimsenin kendi eseri gibi sunulamaz ve değiştirilmiş sürümler başka bir ad kullanır.
- **EN:** License changed to GNU GPL v3 (GPL-3.0-only) with additional terms in `NOTICE.md` (attribution, no
  misrepresentation of origin, modified versions use a different name).
- **TR:** Sohbet artık kopmuyor: hangi yoldan (Groq, ekran/Gemini, derin araştırma, komut hafızası) ve hangi modda
  cevap verilirse verilsin, bir sonraki mesaj önceki konuşmayı görür. Önceden "ekranıma bak" cevabı Groq'un
  geçmişine girmiyordu ve mod değiştirince bütün konuşma siliniyordu.
- **EN:** The conversation no longer breaks: whichever path (Groq, screen/Gemini, deep research, command memory) or
  mode answered, the next message sees it. Previously screen answers were missing from Groq's history and switching
  modes wiped the conversation.
- **TR:** Mod önerisi: açıkça büyük işlerde (uzun, çok parçalı istek) FENIX başlamadan sorar: "Devil modunda
  yapayım mı?" — "evet" → Devil'a geçip başlar, "hayır" → seçili modda yapar. Çalışırken büyüdüğü anlaşılan işlerde
  (adım sınırına takılma, Güvenli modda değişiklik isteme, araştırma isteğine kısa cevap) cevabın sonunda önerir ve
  nedenini söyler. Mod hiçbir zaman sormadan değişmez; "hayır" denen öneri yarım saat tekrarlanmaz.
- **EN:** Mode suggestions: when a task is too big for the current mode FENIX suggests a better one and says why;
  replying "yes" switches and reruns the request there.
- **TR:** Kendini tanı: yeni `fenix_hakkinda` aracı FENIX'in kendisi hakkındaki bilgileri o anki gerçek durumdan
  okur (sürüm, config'teki modlar ve modeller, sağlayıcılar, araçlar, hafıza, açık eklentiler, arayüz, gizlilik, sınırlar).
  Kendisi sorulunca ya da kendini anlatan belge istenince model önce bunu çağırır; orada olmayan için "emin değilim"
  der. (04.11 testinde modları dosya adlarıyla karıştırıyor, "OpenAI/Claude ile çalışırım", "veriler dışarı çıkmaz"
  diyordu.) Uzun belgelerde "önce bilgiyi topla, sonra tek seferde yaz" kuralı eklendi.
- **TR:** Kendisi sorulunca bu bilgiler modele doğrudan verilir (aracı çağırmasına güvenilmez); görev panelinde
  "🪪 Kendi bilgilerime baktım" görünür.
- **TR:** Uzun, çok bölümlü isteklerde araçlar yalnızca asıl görev cümlesine göre seçilir: 11 bölümlü belge isteğinde
  33 yerine 13 araç gider, istek boyutu ~%25 küçülür (Groq dakika sınırında daha az bekleme).
- **EN:** Self-knowledge: new `fenix_hakkinda` tool reports FENIX's real current state (version, modes, models,
  tools, memory, plugins, UI, privacy, limits); the model must use it instead of guessing.
- **TR:** Word/PDF: `write_file` .docx/.pdf'i artık gerçek belge olarak yazar (önceden düz metin yazıp "dosya bozuk"
  hatası veriyordu). Modelin çöküp ürettiği "… ** …" dizileri ekrana basılmaz.
- **TR:** Uzun işler: 7+ araç turundan sonra kullanıcının sorusu geçmişten düşüyordu, düzeltildi. Son iki turda arama
  araçları kapanır ve model işi bitirmeye yönlendirilir; adım sınırında "burada durdum" yerine ne yapıldığı söylenir.
- **TR:** "Kendini tanıtan bir belge oluştur" gibi istekler Devil modda derin araştırmaya değil araçlı akışa gider.
- **TR:** Yol hafızası: istekte üst klasörün yolu geçince yanlış proje öğreniliyordu; yazılan belge içeriği artık
  ipucuna girmiyor.

## 1.2.0 — 2026-11-03
- **TR:** Otomatik testler eklendi (`tests/`, 95 test): riskli komut onayı, Güvenli mod, hafıza, sohbet takibi,
  hatırlatıcı, kısayollar, çeviriler, imza, sahte site tespiti, Word/PDF. `Calistir_Testler.bat` ile ya da GitHub'da
  her yüklemede otomatik çalışır. Testlerin bulduğu açık kapatıldı: PowerShell'in kısa komut adları (`rm`, `ri`,
  `kill`, `spps`) riskli sayılmıyordu ve onay sorulmadan çalışabiliyordu.
- **EN:** Automated tests added (`tests/`, 95 tests), run with `Calistir_Testler.bat` or on every push via GitHub
  Actions. Fixed a gap they found: PowerShell aliases (`rm`, `ri`, `kill`, `spps`) were not treated as risky and could
  run without confirmation.
- **TR:** Eklentiler (MCP): config.yaml'daki `eklentiler` listesinde yazan MCP sunucuları FENIX açılınca arka planda
  başlar, araçları FENIX'e eklenir. Hazır gelenler: zaman (saat dilimi), git (proje geçmişi, commit), dosyalar
  (Masaüstü/Belgeler'de klasör ağacı, taşıma; Node.js gerekir). Salt okunur araçlar onaysız, yazan/silen her araç
  onay kutusuyla çalışır; Güvenli modda yalnızca salt okunur araçlar kullanılabilir. Kurulum: `Eklentileri_Kur.bat`.
  Durum: Yetenekler penceresi ya da "hangi eklentiler var?".
- **EN:** Plugins (MCP): servers listed under `eklentiler` in config.yaml start in the background and their tools are
  added to FENIX. Bundled: time zones, git, filesystem (needs Node.js). Read-only tools run directly, every tool that
  writes or deletes asks first; Safe mode gets read-only tools only. Install with `Eklentileri_Kur.bat`.
- **TR:** 🧩 Eklentiler penceresi: eklentiler config.yaml'ı düzenlemeden açılıp kapatılır; anahtar isteyenlerin
  (Tavily, Notion, GitHub) anahtarı pencereden girilir, "Anahtar al" düğmesi ilgili sayfayı açar; eksik paketler
  "Paketleri kur" ile kurulur; Uygula'ya basınca eklentiler FENIX kapanmadan yeniden başlar. Hazır katalog: zaman,
  git, dosyalar, tarayıcı (Playwright), Tavily, Notion, GitHub.
- **EN:** 🧩 Plugins window: switch plugins on/off without editing config.yaml, enter keys in the window, install
  missing packages with one button, and Apply restarts plugins without restarting FENIX.
- **TR:** Sesli cevap / Okuma açık-kapalı seçimi hatırlanır: kapatıp FENIX'i yeniden açınca kapalı kalır.
- **EN:** The spoken-reply on/off choice is remembered across restarts.
- **TR:** Eklentiler penceresinde "Kendi eklentini ekle": npm paket adı ve (varsa) anahtar değişkeniyle yeni eklenti
  eklenir, "Kaldır" ile silinir. Kendi eklenen eklentilerin her işlemi onay ister; paket adı sıkı denetlenir.
- **EN:** "Add your own plugin" in the Plugins window (npm package name + optional key variable); every action of a
  custom plugin asks for confirmation.
- **TR:** 🧭 Yol hafızası: FENIX çok adımlı bir işi başarıyla bitirince izlediği yolu şablon olarak saklar
  ("{proje} projesindeki commit'ler" → git_log). Benzer bir istekte, başka bir proje için bile, modele "bu yolla
  yapmıştın" ipucu verir; ayrıca bilgisayardaki proje klasörleri (.git içerenler) günde bir taranır. İpucu yalnızca
  bilgidir, hiçbir şey kendiliğinden çalışmaz. Süre ve adım sayısı ölçülür (data/yol_olcum.jsonl). Ayarlar'dan kapatılabilir.
- **EN:** 🧭 Workflow memory: successful multi-step paths are stored as templates and offered as hints for similar
  requests (even for other projects); git project folders are indexed once a day. Can be turned off in Settings.
- **TR:** 🔔 Başka bir penceredeyken FENIX cevap verirse sağ altta Windows bildirimi çıkar (Ayarlar'dan kapatılabilir).
- **EN:** 🔔 A Windows notification appears when FENIX replies while you're in another window (can be turned off).
- **TR:** "Paketleri kur" düğmesi kurulumu ayrı bir pencerede yapar ve FENIX'i kapatır (FENIX açıkken kurulum
  Windows'ta takılabiliyordu); Eklentileri_Kur.bat ilerlemeyi gösterir.
- **EN:** "Install packages" now runs in a separate window and closes FENIX first; the installer shows progress.


## 1.1.0 — 2026-11-01
- **TR:** Yeni holografik arayüz: koyu tema, ortada ses ve durumla hareket eden çekirdek halkası, sohbette "> SEN /
  > FENIX" etiketleri. Açılışta yükleme adımlarını gösteren başlangıç ekranı.
- **EN:** New holographic interface: dark theme, a core ring in the centre that reacts to voice and status, "> YOU /
  > FENIX" labels in chat. A splash screen shows loading steps at startup.
- **TR:** Sohbet alanı aradaki çizgiden sürüklenerek genişletilebilir (genişlik hatırlanır); Ctrl + / Ctrl - ile yazı
  büyür/küçülür; Ctrl+Backspace ve Ctrl+Delete kelime siler; uzun mesaj yazarken takılma giderildi; mod değişince
  sohbete satır eklenmez, durum çubuğunda kısa süre görünür.
- **EN:** The chat area can be widened by dragging the divider (width is remembered); Ctrl + / Ctrl - zoom the text;
  Ctrl+Backspace and Ctrl+Delete delete words; typing lag on long messages fixed; changing mode no longer adds a chat
  line, it flashes in the status bar instead.
- **TR:** İngilizce ve diğer dillerde arayüzde kalan Türkçe yazılar çevrildi.
- **EN:** Remaining Turkish texts in the English and other-language interfaces were translated.

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
- **TR:** Anahtar penceresine isteğe bağlı Tavily alanı eklendi (daha iyi web araması); Ayarlar'da maskeli görünür.
- **EN:** Optional Tavily field added to the key window (better web search); shown masked in Settings.
- **TR:** Sohbet takibi düzeltildi: hafıza bağlamı artık yalnızca o anki mesaja eklenir; önceden geçmiş kısaltılırken
  önceki sorular kesilebiliyor ve takip soruları ("maili var mı?") yanlış anlaşılıyordu. Talimata BAĞLAM (öznesiz
  takip soruları), GERÇEKÇİLİK (aşırı olumlu/onaylayıcı konuşma yerine olabilirliğe göre değerlendirme) ve yaratıcının
  kişisel iletişim bilgileri için GİZLİLİK kuralları eklendi.
- **EN:** Conversation tracking fixed: memory context is now added only to the current message; previously earlier
  questions could be cut off when history was trimmed, so follow-ups were misread. Added CONTEXT (follow-up questions),
  REALISM (judge requests by feasibility instead of over-agreeing) and PRIVACY (creator's contact details) rules.
- **TR:** NVIDIA anahtarı reddedildiğinde (401/403) oluşan iç hata düzeltildi; modeller artık doğru şekilde dinlendirilir.
- **EN:** Fixed an internal error when the NVIDIA key is rejected (401/403); models are now paused correctly.
- **TR:** Hafıza araması güçlendirildi: anlamsal arama bulamasa da sohbet başlıklarında ve eski mesajlarda kelimeyle
  aranır ("Kargocu projesi hakkında ne konuşmuştuk?" gibi sorular).
- **EN:** Memory search improved: when semantic search misses, chat titles and earlier messages are searched by keyword.
- **TR:** Daha hızlı açılış: pencere önce açılır, anlamsal hafıza arka planda yüklenir; ses kütüphaneleri ilk kullanımda
  yüklenir; kurulum Python dosyalarını önceden derler. FENIX zaten açıksa ikinci kopya açılmaz, açık pencere öne gelir.
  Hafıza kütüphanesinin (chromadb) anonim kullanım verisi gönderimi kapatıldı.
- **EN:** Faster start: the window opens first and semantic memory loads in the background; audio libraries load on
  first use; setup precompiles Python files. A second copy no longer starts if FENIX is already open. Disabled chromadb's
  anonymous telemetry.
- **TR:** Lisans: "Tüm hakları saklıdır / Kişisel Kullanım Lisansı"; AUTHORS.md eklendi.
- **EN:** License: "All rights reserved / Personal Use License"; AUTHORS.md added.
- **TR:** Yayına hazırlık: PRIVACY.md (hangi veri nerede/nereye gider), SECURITY.md, THIRD_PARTY_NOTICES.md
  (kütüphane lisansları, markalar), CONTRIBUTING.md (dış katkılar ve hak devri) eklendi.
- **EN:** Release preparation: PRIVACY.md, SECURITY.md, THIRD_PARTY_NOTICES.md (library licenses, trademarks) and
  CONTRIBUTING.md added.

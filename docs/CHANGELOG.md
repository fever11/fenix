# Changelog / Değişiklik günlüğü

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

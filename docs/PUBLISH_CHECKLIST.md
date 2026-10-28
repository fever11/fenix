# Public yapmadan önce kontrol listesi

Depo şu an **Private**. Public yapmaya karar verdiğinde bu listeyi sırayla geç.

## Hukuk ve sahiplik (hazır)
- [x] `LICENSE`: Tüm hakları saklıdır / Kişisel Kullanım Lisansı (TR + EN)
- [x] `AUTHORS.md`: yazar, ilk sürüm tarihi, JARVIS kökeni, yapay zekâ desteği beyanı
- [x] `THIRD_PARTY_NOTICES.md`: kütüphane lisansları (hepsi bu lisansla uyumlu), marka uyarısı
- [x] `PRIVACY.md`, `SECURITY.md`, `CONTRIBUTING.md`
- [x] Kaynak dosyalarda imza satırı, PDF/Word ve ikon bilgilerinde yazar adı
- [x] Pakette anahtar, e-posta, kişisel veri yok

## Senin yapacakların
- [ ] Her sürümün zip'ini ve SHA-256 parmak izini kendine e-postayla gönder (v1.0.0 gönderildi)
- [ ] Eski JARVIS sürümlerini (v1–v6) Drive/USB'ye yedekle
- [ ] Git commit e-postası: `KULLANICIADIN@users.noreply.github.com`
- [ ] Hocaya / Teknoloji Transfer Ofisi'ne sor: FENIX'i BAP başvurusunda "önceden var olan çalışmam" olarak beyan edip public yayınlamam sorun olur mu?
- [ ] İsim kontrolü: turkpatent.gov.tr'de "FENIX" araması (ABD'de yapay zekâ asistanı için başka bir firmanın "FENIX" başvurusu var)

## Public yapmadan hemen önce
- [ ] Güvenlik düzeltmeleri (sonraki sürüm): okunan sayfa/belge sonrası işlemler onaylı olsun; yalnızca okuma yapan PowerShell komutları onaysız çalışsın
- [ ] README'deki "resmi kaynak" bölümüne depo linkini yaz
- [ ] GitHub → Settings → Security: **Private vulnerability reporting** açık
- [ ] GitHub → Settings → General: Issues açık, Wiki/Projects kapalı (isteğe bağlı)
- [ ] Son sürümü Release olarak yayınla ve açıklamaya SHA-256 parmak izini yaz
- [ ] Depoda `config.yaml` ve `data/` olmadığını son kez kontrol et
- [ ] Settings → General → **Change visibility → Public**

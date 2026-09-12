# Kurulum ve bakım

## Dosya yerleşimi

Repo kökü şöyle olmalı:

```
index.html
scripts/guncelle.py
.github/workflows/guncelle.yml
```

`guncelle.yml` dosyasını **`.github/workflows/` klasörünün içine** koy, adı fark etmez
ama yolu tam bu olmalı — GitHub Actions başka yerdeki dosyayı görmez.

## İlk çalıştırma

Zamanlayıcıya güvenmeden önce elle bir kez çalıştır:

1. Repoda **Actions** sekmesine gir
2. Soldan **Fikstürü güncelle** işini seç
3. Sağdaki **Run workflow** düğmesine bas

Yeşil tik gelirse kurulum tamam. Kırmızı çarpı gelirse loga bak: betik
hata mesajlarını açık Türkçe yazıyor.

Bundan sonrası kendiliğinden yürür — 48 saatte bir çalışır (ayın tek
günlerinde, sabah 09:00'da), yeni sonuç varsa `index.html`'i günceller ve
commit'ler. Yeni sonuç yoksa hiçbir şey yapmaz, boş commit atmaz.

## Betik ne yapıyor

- Fenerbahçe 2026-27 ve Bologna 2026-27 sezon sayfalarını tarar
- Oynanmış maçların skorlarını ve maç raporu linklerini çeker
- `index.html` içindeki ilgili fikstür bloklarını yeniden yazar
- "Son güncelleme" tarihini o günün tarihi yapar

Kapanmış dönemlere (Tedesco'nun Fenerbahçe dönemi, Göle'nin vekâleti)
**hiç dokunmaz.** Onlar sabit tarihsel veri.

Rakip adlarını da korur: linki eşleşen bir maç zaten varsa, sitede yazan
Türkçe ad ("Roma", "Slavia Prag") kaynağın yazımıyla değiştirilmez.

## Yeni maçlar kendiliğinden eklenir

Betik fikstürü yamalamaz, kaynaktan **baştan kurar.** Dolayısıyla kaynakta
yeni bir maç belirdiği anda siteye de girer: Türkiye Kupası kuraları
çekildiğinde, Şampiyonlar Ligi eleme turu eşleşmeleri belli olduğunda ya da
ertelenen bir maça tarih verildiğinde elle bir şey yapmana gerek yok.
Maçlar tarih sırasına göre yerleştirilir, kulvar dökümü tablosuna yeni
satır kendiliğinden açılır.

İki küçük not:

- Yeni eklenen maçların rakip adı kaynağın yazımıyla gelir
  ("İstanbul Başakşehir" gibi). Kısaltmak istersen `index.html` içinde
  elle düzeltebilirsin; bir kez düzelttikten sonra betik o adı korur.
- Betiğin tanımadığı bir turnuva çıkarsa (örneğin Konferans Ligi) o maçlar
  atlanır ama log'a **UYARI** satırı düşer. O durumda `guncelle.py` içindeki
  `KULVAR_KODU` ve `index.html` içindeki `KULVAR` sözlüğüne yeni kodun
  eklenmesi gerekir.

## Güvenlik freni

Betik beklediğinden az maç bulursa `index.html`'e **yazmadan** hata verip
durur. Kaynak sitenin yapısı değişirse veri sessizce silinmez; iş kırmızı
yanar ve GitHub sana e-posta atar.

Eşik değerleri betiğin başındaki `DONEMLER` listesinde `en_az` alanında.
Türkiye Kupası maçları kurayla eklendikçe maç sayısı artacağı için bu
değerleri sezon içinde yükseltmene gerek yok, sadece düşmemeleri önemli.

## Elle müdahale gereken durumlar

**Teknik direktör değişirse.** Betik "fb-simdi" dönemine maç eklemeye devam
eder, ama başlıkta hâlâ eski hocanın adı yazar. O zaman `guncelle.py`
içinde ilgili dönemin `bitis` alanına ayrılış tarihini yaz:

```python
"bitis": "2026-11-15",
```

Sonra `index.html` içinde yeni hoca için yeni bir dönem bloğu açılması
gerekir — bu kısım elle ya da bana sorarak yapılır.

**Sezon biterse.** Yeni sezonun sayfa adresi değişir. `DONEMLER` içindeki
`url` ve `baslangic` alanlarını güncellemen gerekir.

## Geri doldurma (tek seferlik)

`scripts/geri_doldur.py`, 2010-11'den 2025-26'ya kadarki 16 sezonu tarar,
maçları teknik direktör dönemlerine böler ve `veriler.json` dosyasını üretir.
Site bu dosyayı yalnızca ziyaretçi eski bir dönem seçtiğinde indirir, yani
sayfa hafif kalır.

**En kolay yol: GitHub üzerinden çalıştır.** Bilgisayarına hiçbir şey
kurman gerekmez.

1. Repoda **Actions** sekmesine gir
2. Soldan **Geri doldur (tek seferlik)** işini seç
3. Sağdaki **Run workflow** düğmesine bas
4. Açılan kutucukta **"Önce deneme yap"** işaretli kalsın, çalıştır

Bu deneme hiçbir dosya yazmaz, sadece raporlar. İş bitince üstüne tıklayıp
adımları aç ve logu oku.

Çıktıda her dönem için "bulunan" ve "beklenen" maç sayısı yan yana gelir.
Hepsi "tamam" diyorsa tarihler doğrudur. O zaman işi bir kez daha çalıştır,
bu sefer **"Önce deneme yap" kutucuğunun işaretini kaldır**. Betik
`veriler.json`'u üretip repoya kendisi commit'ler.

Bir dönemde "FARK" yazıyorsa devir tarihi yanlıştır. `geri_doldur.py`
içindeki `DONEMLER` listesinde o dönemin `bas`/`bit` tarihini düzelt ve
tekrar dene. Sayılar tutmadan betik dosyayı yazmaz — bu kasıtlı.

Bu betik bir kez çalışır, sonra bir daha gerekmez. Güncel sezonu
`guncelle.py` takip ediyor.

## Elle çalıştırma (bilgisayarında)

```bash
pip install requests beautifulsoup4
python3 scripts/guncelle.py --kuru   # neyin değişeceğini gösterir, yazmaz
python3 scripts/guncelle.py          # gerçekten günceller
```

`--kuru` seçeneği bir değişiklikten emin değilsen işe yarar.

## Kaynağa saygı

Betik haftada bir çalışıyor, iki sayfa çekiyor ve istekler arasında iki
saniye bekliyor. Bu yükü artırma — cron sıklığını saatlik yaparsan hem
gereksiz hem de kaynak sitenin seni engellemesine yol açabilir. Maçlar
haftada bir oynanıyor, haftalık tarama yeterli.

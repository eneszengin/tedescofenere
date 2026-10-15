tedescofenere.com

Domenico Tedesco'nun Fenerbahçe dönemini kayıt altına alan, bugününü takip eden ve Fenerbahçe'nin güncel sonuçlarını aynı yerde tutan tek sayfalık bağımsız taraftar sitesi.

Yayında: https://tedescofenere.com

Bağımsız bir sayfadır. Fenerbahçe Spor Kulübü, Bologna FC 1909 ya da Domenico Tedesco ile resmî bir bağı, izni veya ortaklığı yoktur.

Sayfada ne var
Fikstürler — iki sekme: Tedesco'nun Fenerbahçe dönemi (45 maç, tamamı) ve Fenerbahçe'nin güncel hocası Kartal. Skora tıklayınca o maçın raporu açılır.
Karşılaştırma — 2010-11'den bugüne 16 teknik direktör dönemi arasından seçim yapıp yan yana koyma. Kulvar süzgeci: tüm maçlar, sadece lig, sadece Avrupa, sadece derbi. Derbi seçilince maç listesi de gelir.
Teknik direktörler — 2010-11'den bugüne maç başına puan tablosu.
Domenico Tedesco — kısa özgeçmiş ve kariyer tablosu.

Güncelleme
Site her gün kendini kontrol eder. scripts/gunluk.py tarihi geçmiş ama skoru boş maçları bulur, Mackolik arşivinden doldurur, teknik direktör karnesini fikstürden yeniden hesaplar ve "son güncelleme" tarihini tazeler. Maç yoksa hiçbir şey yapmaz, boş commit atmaz. Anahtar ya da hesap gerekmez. Çalışma saati gece 01:00 (TR); akşam maçları aynı gece girer.

Güvenlik frenleri: var olan bir skoru asla ezmez, kaynaktan beklenenden az maç dönerse dosyaya dokunmaz, yazmadan önce tırnaksız skor / tarih sırası / karne tutarlılığı doğrulanır. Fikstürde hiç olmayan oynanmış bir maç görürse (kupa kurası çekilmiş olabilir) işi kasten kırmızı yakar ve eklenecek satırı günlüğe yazar.

Kaynağa erişimi sınamak için: Actions > Günlük skor kontrolü > Run workflow, "Yalnızca kaynağa erişimi sına" işaretli.

Elle güncellemek için index.html içindeki veri bloğunda null yerine skoru tırnak içinde yaz ("2-1"), gerisi otomatik hesaplanır. Tırnak önemli: tırnaksız yazılan skor JavaScript'te çıkarma işlemi sayılır ve sayfanın o noktadan sonrasını çizilmez hale getirir.

Kaynak: Mackolik arşivi

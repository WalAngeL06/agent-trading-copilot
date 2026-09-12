# Bot temeli v0.1

## Kapsam

Kullanıcının 12 Eylül 2026 tarihli temel yapı talimatı kapsamında, yarışmadan
bağımsız bir uygulama çekirdeği. Master proje notundaki strateji tanımları
belirsizliğini korur. Bu belge altyapı kararlarını tanımlar, strateji onayı değildir.

Python 3.11+ standart kütüphanesi; tek süreç, ayrı sorumluluklar. Mikroservis
işletme yükü ve tek dosyada birleşen strateji/risk kodu yerine modüler paket.

## İlk çalışan akış

JSONL kapalı mumlar → kronolojik replay → sınırlı geçmiş → dedektör arayüzü
→ piyasa durum kaydı → karar → kabul → risk → yürütme durumu → JSONL günlük.

- Mum zamanları UTC ve saat dilimli; timestamp mumun kapanış zamanıdır.
- Akış kapanış zamanına göre global olarak artar veya eşittir; aynı sembol ve
  zaman diliminde zaman kesin artar. Yinelenen/eski mum hatadır.
- Geçmiş sembol ve zaman dilimi bazında tutulur. Dedektöre yalnız o ana kadar
  alınan mumlar verilir; geçmiş üst sınırı ayardır, strateji lookback'i değildir.
- Farklı zaman dilimlerinin aynı kapanıştaki mumları dosya sırasıyla işlenir.
  Bu sürüm eşzamanlı HTF/LTF snapshot birleştirme yapmaz.
- Dedektör sonucu: durum, yön, tespit zamanı, başlangıç, pencere, kanıt,
  seviyeler, geçersizleşme açıklaması, kaynak kimlikleri ve isteğe bağlı skor.
- Skor varsa yöntem adı gerekir; skor olasılık olarak yorumlanmaz.
- Varsayılan dedektörler NOT_IMPLEMENTED üretir; negatif tespit sayılmaz.
- Router her zaman NO_TRADE / STRATEGY_NOT_CONFIGURED üretir.
- Kabul ve risk politikaları yapılandırılmamıştır. İşlem adayı onaylanamaz.
- Canlı ve shadow modları başlangıçta hata verir; yalnız replay çalışır.
- Gerçek emir, dolum simülasyonu, portföy muhasebesi ve performans hesabı yoktur.
- Yapılandırma hataları başlangıçta reddedilir. Veri/modül hatası günlüğe
  yazılarak çalıştırma durur. Sessizce devam edilmez.
- Günlük her çalıştırmada yeni dosya ister, mevcut dosyanın üstüne yazmaz.

## Sonraki modüllerin sınırları

Veri adaptörü borsa şemasını mum sözleşmesine dönüştürür. Dedektörler yalnız
piyasa kanıtı üretir. Context/MTF ve pencere tarayıcısı, onaylanmış tanımlarıyla
bu sonuçları zenginleştirecek ayrı modüllerdir. Router senaryo seçer; Acceptance
işleme uygunluğu; Risk hesap ve limitler üzerinden miktarı belirler. Execution
yalnız onaylı emir sözleşmesini uygular. Position Manager dolum sonrası ayrı
durum takibi yapar. Bu son modüller bu sürümde uygulanmış sayılmaz.

## Doğrulama

Kapalı mum ve OHLC geçerliliği, gelecek mumun geçmişe sızmaması, tekrar/eski
verinin reddi, sembol ayrımı, sınırlı geçmiş, hata kaydı, deterministik replay,
strateji yokken işlem üretilmemesi ve CLI çalışması otomatik test edilir.

## Açık strateji kararları

Range sınırları, swing teyidi, deviation/reclaim, manipulation, momentum,
distribution, timeframeler, kabul koşulları, risk miktarları ve çıkış kuralları
kullanıcı kaynakları ve modül şartnameleriyle belirlenecek. Hiçbir örnek veri
veya altyapı varsayılanı bu kararları temsil etmez.

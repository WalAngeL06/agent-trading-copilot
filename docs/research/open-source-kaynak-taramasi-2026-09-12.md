# Agent Trading için açık kaynak taraması

Tarama tarihi: 12 Eylül 2026. Kapsam: mevcut Python çekirdeği, OKX Agent Trade Kit, kapalı mumlarla çoklu zaman dilimi analizi, DD kaynaklı market structure/range/deviation/manipulation fikirleri ve bunların doğrulanması.

**Öneri:** Mevcut deterministik çekirdeği koruyup açık kaynaklardan modül bazında yararlanmak. İlk öncelik SMC algoritmalarını karşılaştırmak, zaman/teyit sözleşmesini netleştirmek ve backtest doğrulamasını tasarlamak. İncelenen kaynaklar arasında DD modelinin çözülmemiş tanımlarını birebir karşılayan, doğrudan takılabilir bir uygulama belirlenmedi. Bu, bütün açık kaynak ekosisteminde böyle bir uygulama olmadığı iddiası değildir.

## Projeye göre değerlendirme

Yerel README, foundation/shadow belgeleri, veri modelleri, dedektör sözleşmesi ve tarama sırasında mevcut olan market-structure spec incelendi. Çekirdek Python 3.11+, Decimal fiyatlar, UTC kapanış zamanları ve değiştirilemez MarketSnapshot kullanıyor. Gerçek OKX SHADOW hattı mevcut; dolum simülasyonu, portföy muhasebesi ve strateji performansı henüz uygulanmış değil. Bu nedenle çalışan veri adaptörünü değiştirmekten önce strateji/doğrulama boşluklarına odaklanmak daha yararlı.

Bağlı konuşmanın son kullanıcı düzeltmesi esas alındı: **Premium/Discount giriş tetikleyicisi değil, işlem sırasında confirmation/context bilgisi. EQ'dan tepki veya reclaim otomatik zorunluluk değil.** Mevcut spec'te ayrıca ordinary setup'ları engelleyen ifadeler var. Confirmation'ın zorunlu uygunluk koşulu mu, ek destekleyici bilgi mi olduğu Acceptance tasarımında açıkça belirlenmeli; bir dış kütüphanenin varsayılanı bu kararı vermemeli.

Aşağıdaki öncelikler ve entegrasyon önerileri mühendislik değerlendirmesidir. Lisanslar ve özellikler ilgili birincil kaynaklara dayanır. Paket kurulumu, çalıştırmalı uyumluluk testi veya kârlılık doğrulaması yapılmadı. 12 proje incelendi: 11 açık kaynak aday ve ayrıca kısıtlı lisanslı vectorbt.

## Karşılaştırma

| Kaynak | Projedeki kullanım | Lisans | Öncelik / karar |
|---|---|---|---|
| [smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) | Swing, BOS/CHoCH, FVG, likidite algoritmalarını karşılaştırma | MIT | Yüksek; algoritma referansı, doğrudan canlı dedektör değil |
| [OKX Agent Trade Kit](https://github.com/okx/agent-trade-kit) | Mevcut CLI/MCP bağlantısını geliştirme | MIT | Yüksek; mevcut resmi bağlantının kaynak kodu |
| [Freqtrade](https://github.com/freqtrade/freqtrade) | Backtest, dry-run, zaman dilimi birleştirme ve bias kontrolü | GPL-3.0 | Yüksek; doğrulama referansı / ayrı deney ortamı |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | Olay tabanlı simülasyon, hesap/pozisyon ve execution mimarisi | LGPL-3.0 | Orta; uzun vadeli aday, geçiş maliyeti var |
| [Backtesting.py](https://github.com/kernc/backtesting.py) | Küçük OHLC strateji hipotezlerini hızla deneme | AGPL-3.0 | Orta; araştırma prototipi |
| [CCXT](https://github.com/ccxt/ccxt) | Borsa normalizasyonu ve alternatif veri adaptörü | MIT | Orta; ihtiyaç oluşursa |
| [Lightweight Charts](https://github.com/tradingview/lightweight-charts) | Mumlar üzerinde yapı, range ve teyit zamanlarını inceleme | Apache-2.0; attribution bildirimi | Yüksek; görsel doğrulama için |
| [QuantStats](https://github.com/ranaroussi/quantstats) | Getiri, drawdown ve performans raporları | Apache-2.0 | Orta; muhasebe/dolum çıktısı oluşunca |
| [Optuna](https://github.com/optuna/optuna) | Tanımlanmış hipotezlerin parametrelerini araştırma | MIT | Sonra; tanım belirsizliğini çözmez |
| [HftBacktest](https://github.com/nkaz001/hftbacktest) | Limit emir kuyruğu ve gecikme modelleme | MIT | Sonra; tick/order-book verisi gerektirir |
| [Cryptofeed](https://github.com/bmoscon/cryptofeed) | Order book, işlem ve türev piyasa veri akışları | AGPL-3.0-or-later; ek attribution koşulu | Sonra; Windows ve sürüm uyumu ayrıca incelenmeli |

Lisans sütunu ilgili README/LICENSE dosyalarındaki beyanı özetler. Seçilecek sürümün tam lisans ve NOTICE dosyaları entegrasyona eşlik etmeli. GPL, LGPL ve AGPL adaylarını MIT/Apache adaylarıyla aynı dağıtım koşullarına sahip kabul etmemek gerekir.

## Stratejiye en yakın kaynak: smart-money-concepts

Kütüphane OHLC/OHLCV üzerinden FVG, swing high/low, BOS/CHoCH, order block, likidite kümeleri, previous high/low ve seans bilgileri üretir. `close_break=True` seçeneği kapanışla kırılım değerlendirmeye elverişli bir karşılaştırma sağlar. Ancak sabit `swing_length` tanımı, bizim gerçek karşı hareket/teyit arayan ve her lokal pivotu structural saymayan modelimizle eşdeğer değildir. [Proje ve API tanımları](https://github.com/joshyattridge/smart-money-concepts).

Kaynak kodunda dört somut entegrasyon sorunu görüldü:

1. Swing hesaplaması negatif kaydırma ve ileri pencere kullanıyor; swing mumunda teyit zaten biliniyormuş gibi davranılamaz.
2. FVG, sonraki mumla oluşmasına rağmen orta muma etiketleniyor. Kullanılabilirlik zamanı üçüncü mum kapanışı olmalı.
3. `MitigatedIndex`, `BrokenIndex` ve sweep gibi alanlar sonradan oluşan olayları içeriyor. Gelecekteki sonuç, geçmişteki kararın girdisi olamaz.
4. Bazı fiyat seviyeleri `np.float32` dizilerine yazılıyor; bu, çekirdeğin Decimal fiyat sözleşmesiyle doğrudan uyumlu değil.

Bunlar offline grafik etiketlemesinin kendi başına hatalı olduğu anlamına gelmez. Karar motoruna aktarırken olayın oluşma ve bilinebilme zamanlarının ayrı tutulması gerekir. Ayrıca geçmişte yayımlanmış kararlar yeni veriyle yeniden yazılmamalı. [İncelenen 0.0.26 tag'inin kodu](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/0.0.26/smartmoneyconcepts/smc.py), [varsayılan dalın kodu](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/smartmoneyconcepts/smc.py).

**Kullanım kararı:** Formüller, çıktı alanları ve örnekler araştırma referansı olarak yararlı. DD swing, protected level ve external/internal kuralları kendi şartnamemizle tanımlanmalı. OHLCV kaynaklı likidite/OB etiketlerinin fiilen gözlenen order-flow veya manipülasyon niyetini kanıtladığını varsaymamak gerekir; bu, kullanılan girdilerden çıkan bir değerlendirmedir.

Sürüm ayrıntısı: erişilen GitHub Releases sayfası `0.0.26` gösterirken varsayılan dalın kodu `0.0.27` bildiriyor; `0.0.26` tag'inin iç sürüm alanı da `0.0.25`. Bu nedenle yalnız paket adını kaydetmek yerine seçilen tag/commit ve gerçek algoritma davranışı kaydedilmeli. [Sürümler](https://github.com/joshyattridge/smart-money-concepts/releases).

## Veri ve borsa bağlantısı

**OKX Agent Trade Kit:** Projenin zaten kullandığı resmi kaynağın CLI ve MCP paketleri; piyasa verisi, emir/hesap araçları ve read-only/module filtreleri var. En yararlı kullanım, mevcut adaptörün veri şeması, geçmiş mum sayfalama ve hata davranışını resmi implementasyonla karşılaştırmak. Repo README'sindeki bütün araçlar yerel adaptörümüzün desteklediği özellikler sayılmamalı. [Resmi depo](https://github.com/okx/agent-trade-kit), [OKX dokümanı](https://www.okx.com/docs-v5/agent_en/).

**CCXT:** Birleşik borsa API'si ve OKX implementasyonu nedeniyle alternatif veri kaynağı/normalizasyon referansı. Mevcut Agent Trade Kit tercihinin yanına ancak gerçek bir gereksinim oluşursa alınmalı. Borsa mumlarının açılış zamanı, son mumun eksik olabilmesi, sayfalama ve hassasiyet dönüşümleri için ayrıca adaptör gerekir. OKX desteği, OKX TR hesabındaki her ürün ve endpoint'in doğrulandığı anlamına gelmez. [CCXT deposu](https://github.com/ccxt/ccxt).

**Cryptofeed:** WebSocket üzerinden order book, trades ve diğer piyasa kanallarını toplamak için aday. Güncel kaynak metadata'sı `3.0.0`, Python `>=3.12` ve AGPL-3.0-or-later bildiriyor; LICENSE ek attribution koşulu içeriyor. Arama indeksinde eski XFree86 metadata'sı görüldü, fakat doğrudan erişilen güncel dosyalar AGPL konusunda uyumlu. Paket metadata'sındaki platform beyanı Linux/macOS; mevcut Windows projesinde kurulum/akış testi yapılmadan uyum varsayılmamalı. [README](https://raw.githubusercontent.com/bmoscon/cryptofeed/master/README.md), [güncel metadata](https://raw.githubusercontent.com/bmoscon/cryptofeed/master/pyproject.toml), [LICENSE](https://raw.githubusercontent.com/bmoscon/cryptofeed/master/LICENSE).

## Backtest ve doğrulama

**Freqtrade:** Backtest, dry-run ve strateji araçlarıyla en yararlı doğrulama referanslarından biri. Özellikle informative timeframe birleştirmesi, HTF kapanmadan HTF sonucunun LTF satırına taşınmaması gerektiğini somutlaştırıyor. `lookahead-analysis` baz ve sinyal bazında ayrıştırılmış backtest çıktılarındaki farkları araştırıyor. Bu araç doğrudan bizim bağımsız çekirdeğimize uygulanmaz; Freqtrade strateji adaptasyonu gerekir. Yöntemden yararlanıp kendi replay kontrollerimizi tasarlamak da mümkün. Negatif bias raporu tüm nedensellik sorunlarının yokluğunu garanti etmiyor. [MTF ve hata önleme dokümanı](https://www.freqtrade.io/en/stable/strategy-customization/#merge_informative_pair), [lookahead-analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/).

Erişilen release listesinde `2026.8`, 31 Ağustos tarihli sürüm ve düzenli aylık sürümler var; bakım için somut olumlu işaret. Ana framework GPL-3.0. Mevcut çekirdeği bütünüyle taşımak yerine ayrı araştırma ortamı olarak değerlendirmek önerilir. [Depo](https://github.com/freqtrade/freqtrade), [lisans](https://raw.githubusercontent.com/freqtrade/freqtrade/develop/LICENSE), [sürümler](https://github.com/freqtrade/freqtrade/releases).

**NautilusTrader:** Deterministik olay tabanlı backtest/live mimarisi ve veri/hesap/pozisyon/emir modelleri, uzun vadeli simülasyon altyapısı için güçlü aday. OKX veri ve execution adaptörü mevcut; bu, bizim TR bağlantımızın yerine takılıp doğrulandığı anlamına gelmez. Varsayılan dal Windows x86_64 ve Python 3.12–3.14 desteği bildiriyor; Python 3.11 asgari sürümümüz ve uygulama sözleşmelerimizle farkları var. [Depo](https://github.com/nautechsystems/nautilus_trader), [OKX entegrasyonu](https://nautilustrader.io/docs/latest/integrations/okx/).

Önemli bakım ayrıntısı: `1.231.0` sürüm notları v1 çekirdeğinden Rust/PyO3 v2'ye geçişi ve release candidate sürecini açıklıyor. Stable sürümün dokümanı ile develop/latest dokümanı karıştırılmamalı. Şimdiki yarışma akışında tam geçiş yerine mimari referans; sonrasında sürümü sabitlenmiş bir pilot önerilir. [Geçiş duyurusu ve sürümler](https://github.com/nautechsystems/nautilus_trader/releases).

**Backtesting.py:** Küçük OHLC hipotezlerinin komisyon/spread ve basit SL/TP davranışıyla hızlı denenmesi için uygun. `trade_on_close=False` ile market emirleri sonraki bar açılışında doluyor; `True` mevcut kapanış fiyatını kullanıyor. Bizim kapalı mumdan sonra karar veren akışımızda bu fark açıkça modellenmeli. Margin modeli initial/maintenance margin ayrımı yapmıyor; tek başına tam perpetual muhasebesi sayılmaz. AGPL lisanslı. [Depo](https://github.com/kernc/backtesting.py), [dolum ve margin API'si](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html).

**HftBacktest:** Tick/order-book replay, limit emir kuyruk konumu, gecikme ve dolum modelleri açısından yararlı. Mevcut OHLC mumları bu ayrıntıları test etmeye yetmez. Ayrıca replay emirlerin piyasayı değiştirdiği market impact'i modellemiyor; özellikle likidite tüketen dolumlar için bu sınır önemli. OKX'e hazır live bağlantı varsayılmadan veri dönüşümü ayrı değerlendirilmeli. MIT lisanslı. [Depo](https://github.com/nkaz001/hftbacktest), [dolum modeli ve sınırları](https://hftbacktest.readthedocs.io/en/latest/order_fill.html).

## Görsel inceleme ve performans araştırması

**Lightweight Charts:** Mumları ve yapı/range seviyelerini grafik üzerinde göstermek için uygun tarayıcı kütüphanesi. Bizim en değerli kullanımımız, swing'in olduğu yer ile teyit edildiği zamanı ve o anda kullanılabilir HTF bilgisini aynı replay üzerinde göstermek. Dedektör sağlamaz. Apache-2.0 yanında README'deki TradingView attribution/NOTICE ve bağlantı koşulları korunmalı. Erişilen sürüm listesinde `v5.2.1` ve 12 Ağustos tarihli yayın var. [Depo](https://github.com/tradingview/lightweight-charts), [attribution açıklaması](https://github.com/tradingview/lightweight-charts/blob/master/README.md), [sürümler](https://github.com/tradingview/lightweight-charts/releases).

**QuantStats:** Getiri serilerinden performans, drawdown ve HTML rapor üretmek için uygun. Doğru dolum ve portföy muhasebesi verisini biz üretmeliyiz; NO_TRADE/WOULD_BUY günlükleri tek başına performans kanıtı oluşturmaz. Kriptonun 365 günlük takvimi ve kullanılan bar sıklığı için yıllıklaştırma ayarları açık olmalı. Apache-2.0. [Depo ve rapor modülleri](https://github.com/ranaroussi/quantstats), [LICENSE](https://github.com/ranaroussi/quantstats/blob/main/LICENSE.txt).

**Optuna:** Python ile tanımlanan arama uzayları, örnekleme ve verimsiz denemeleri erken durdurma araçları sağlıyor. Yalnız açıkça tanımlanmış hipotezlerin parametre araştırmasında önerilir. “Gerçek retracement nedir?” gibi eksik strateji tanımlarını optimizasyon sonucuyla DD kuralı ilan etmemeliyiz. Zamana göre ayrılmış geliştirme/doğrulama/test dönemleri ve deneme kayıtları ayrı tutulmalı. MIT. [Depo](https://github.com/optuna/optuna).

## Açık kaynak kısa listesine alınmayan aday

**vectorbt:** Çok sayıda fikir/parametreyi vektörleştirerek araştırmak için ilgili, fakat erişilen LICENSE **Apache-2.0 + Commons Clause** içeriyor. Yazılımdan esaslı değer alan ürün/hizmetlerin satışını kısıtlıyor. Bu nedenle sınırsız açık kaynak adayı olarak listelenmedi; repo da kendisini fair-code olarak tanımlıyor. Bu beyan “her ticari kullanım yasak” şeklinde genellenmemeli. Araştırmada olası kullanım ve ürün entegrasyonu ayrı değerlendirilir. [Depo](https://github.com/polakowo/vectorbt), [tam lisans koşulu](https://raw.githubusercontent.com/polakowo/vectorbt/master/LICENSE.md).

## DD modülleri için neyi nereden alabiliriz?

| Bizim ihtiyaç | Yararlı referans | Bizde ayrıca tanımlanması gereken |
|---|---|---|
| Structural swing / protected high-low | smart-money-concepts karşılaştırması | Gerçek karşı hareket, responsible swing, teyit ve koruma güncellemesi |
| Body-close break | SMC close_break, kendi spec | Geçerli external level ve break olayının kullanılabilirlik zamanı |
| Premium/Discount | Kendi EQ formülü ve context modeli | Geçerli structural çift, gözlenen fiyat ve Acceptance içindeki rol |
| Range | Grafik replay + kaynakla etiketlenmiş örnekler | RH/RL seçimi, aktiflik, nested range ve invalidation |
| Deviation / manipulation | SMC liquidity/sweep alanları yardımcı karşılaştırma | Range bağlamı, reclaim, teyit ve normal breakout'tan ayrım |
| Momentum / distribution | Onaylanan hipotezlerin backtest'i | Mentorun gözlenebilir tanımı; hacim/ATR eşikleri kendiliğinden eklenmez |
| Nedensel HTF/LTF bağlamı | Freqtrade informative helper yöntemi | Snapshot kapanış/teyit sözleşmesi ve gecikmiş veri politikası |
| Dolum / pozisyon / hesap | NautilusTrader; küçük prototipte Backtesting.py | Emir, komisyon, funding, kısmi dolum ve hesap sözleşmesi |
| İnceleme / rapor | Lightweight Charts, QuantStats | Gerçek karar zamanları ve doğru equity/getiri girdileri |

Tablodaki eşleştirmeler öneridir; açık kaynakta aynı ismin kullanılması DD semantiğinin eşit olduğunu göstermez. Özellikle liquidity sweep etiketi, range deviation veya manipulation için tek başına yeterli kabul edilmemeli.

## Önerilen uygulama sırası

1. **Kaynaklı spec ve örnekler:** Swing/teyit, responsible level, range ve reclaim kararlarını tamamlamak. Yeni algoritmaları DD kaynak iddialarından ayrı hipotez olarak kaydetmek.
2. **Grafik üzerinden teyit incelemesi:** Onaylanan örneklerde olay zamanı, confirmed_at ve o anki HTF/LTF bilgilerini gösteren küçük bir replay görünümü.
3. **Causality kontrolleri:** Her T anında yalnız T'ye kadar veriyle üretilen kararları, tam veri üzerindeki T-anı kararlarıyla karşılaştırmak. Geç teyit edilen offline etiket değişebilir; T'de gerçekten yayımlanmış karar değişmemeli.
4. **Sürümü sabit bir backtest pilotu:** Küçük OHLC hipotezinde Backtesting.py veya Freqtrade; ayrıntılı event/account ihtiyacında NautilusTrader. Strateji mantığını iki ortamda ayrı ayrı yeniden yazmanın ayrışma maliyetini hesaba katmak.
5. **Muhasebe ve rapor:** Komisyon/spread ve gerekiyorsa funding/kısmi dolum sonrası equity üretmek; sonra QuantStats ile raporlamak.
6. **Daha sonra:** Parametre araştırması için Optuna; gerçek order-book hipotezi oluşursa Cryptofeed/HftBacktest.

## Entegrasyon öncesi anlamlı kontroller

- Swing uç mumu ile teyit mumu ayrılıyor mu? Sonradan bilinen break/sweep/mitigation sonucu geçmişte kullanılıyor mu?
- Örneğin 12:00–16:00 4H mumunun kapanışı 15:00 kararına girebiliyor mu? Girmemeli.
- Decimal fiyatın float'a çevrilmesi seviye karşılaştırmasını etkiliyor mu? Fiyat dönüşümünün sınırı açık mı?
- Seçilen mumda hem stop hem hedef varsa intrabar sıra bilinmiyorken hangi dolum politikası uygulanıyor?
- Karar zamanı ile uygulanabilir emir zamanı ayrılıyor mu? Sonraki bar, gecikme ve maliyet varsayımları kaydediliyor mu?
- Bootstrap uzunluğu ve geçmiş limiti değişince gerçekten yayımlanan yapı/kararlar değişiyor mu? Başlangıç koşulu açık mı?
- Araştırma dönemi dışında ve farklı piyasa dönemlerinde davranış korunuyor mu? Denenen hipotez/parametre sayısı kayıtlı mı?
- Ürünün seçilen sürümüne ait LICENSE/NOTICE, Python sürümü ve Windows desteği doğrulandı mı?

Bu kontroller önerilen gelecekteki doğrulama kapsamıdır; bu taramada çalıştırılmış testler değildir. İnceleme birincil GitHub depoları, kaynak dosyaları ve resmi proje dokümanlarına dayanır. Son commit tarihleri için GitHub REST metadata erişimi bu oturumda sağlanamadı; bakım değerlendirmesi erişilebilen sürüm notlarıyla sınırlıdır. Varsayılan dallar ve `/latest/` belgeleri hareketlidir; uygulama aşamasında tag/commit ve ona ait doküman sabitlenmelidir.

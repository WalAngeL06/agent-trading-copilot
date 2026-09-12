# Phase 1: gerçek OKX verisiyle SHADOW

12 Eylül 2026 tarihinde gerçek BTC-USDT verisiyle hat doğrulandı:
Agent Trade Kit → kapalı mum bootstrap → MTF snapshot → detektör placeholder'ları
→ NO_TRADE → kabul → risk → NO_ACTION → JSONL. Strateji kuralı eklenmedi.

## Mevcut entegrasyon incelemesi

Entegrasyon başlangıçta proje kaynaklarının dışında kuruluydu. Bu aşamada
aşağıdaki kullanıcı ayarları ve paketler değiştirilmedi; yalnız güvenli
metadata okundu. Kimlik bilgileri ve özel hesap cevapları gösterilmedi.

| Konum | Mevcut yapı |
|---|---|
| `C:/Users/Serdar Arif/.codex/config.toml` | `okx-trade-kit`: Node üzerinden yerel stdio MCP, `--site tr --modules market --read-only`; `okx-tr`: OAuth HTTP MCP |
| `C:/Users/Serdar Arif/.claude.json` | `okx-trade-kit`: aynı salt-okunur stdio; `okx-agent-trade-kit`: HTTP MCP |
| `C:/Users/Serdar Arif/AppData/Roaming/npm/node_modules/@okx_ai/okx-trade-cli/` | Resmi CLI `1.4.6`; giriş `dist/index.js` |
| `C:/Users/Serdar Arif/AppData/Roaming/npm/node_modules/@okx_ai/okx-trade-mcp/` | Resmi MCP `1.4.6`; giriş `dist/index.js` |
| `C:/Users/Serdar Arif/.codex/skills/` ve `.claude/skills/` | `okx-cex-auth`, `okx-cex-market`, `okx-cex-trade`, `okx-cex-portfolio`, `okx-cex-bot` ve referans dosyaları |

HTTP MCP adresi: `https://tr.okx.com/api/v1/mcp/tr-trading-oauth`.
Codex tarafındaki önceki OAuth girişinin tamamlanması, CLI hesap oturumunun
tamamlandığı anlamına gelmez. Bu görevde CLI hesabına giriş yapılmadı.
CLI `auth status` API anahtarı bulunmadığını bildirdi; `account config` okuması
giriş/credentials gereksinimi nedeniyle başarısız oldu. Özel hata metni bastırıldı.
Bu oturumda OAuth MCP araçları çağrılabilir araç listesinde olmadığından özel
hesap okuması MCP üzerinden ayrıca doğrulanamadı. Public piyasa hattı çalışıyor.

Kurulu registry'de 20 piyasa aracı bulundu: ticker/tickers, orderbook, candles,
index candles/ticker, instruments/category/stock tokens, funding rate,
mark price, open interest/history/change filter, price limit, trades,
market filter, pair spread ve indicator/list. Proje adaptörü bu geniş yüzeyin
yalnız ticker, candles ve orderbook kısmını açar.

Global CLI kendi başına emir komutları da içerir; HTTP OAuth MCP de ayrı
ticaret yetkileri taşıyabilir. Uygulamanın yürütücüsü bunlara bağlı değildir.
Yerel MCP salt okunur; yeni uygulama adaptörü komutları izin listesiyle
sınırlar. `live` modu ayar yüklenirken reddedilir. Emir gönderen uygulama yolu
eklenmedi. Harici CLI/MCP'nin ayrı ve bilinçli kullanımı bu motorun kapsamı dışındadır.

Uygulama API anahtarı/token istemez veya ayara yazmaz. Günlükte ortam değişkeni,
CLI stdout/stderr, hesap cevabı veya MCP kullanıcı ayarı bulunmaz. Hatalı CLI
çıktıları güvenli hata mesajına çevrilir. Kullanıcı credential depoları proje
dışındadır; `.env` dosyaları ve `runs/` mevcut `.gitignore` ile yok sayılır.
Kimlik bilgilerini kaynak dosyalarına elle kopyalamak bu korumaların dışındadır.

## Gerçek smoke sonuçları

İlk probe: 12 Eylül 2026, yaklaşık 09:23:42–09:23:44 Türkiye saati.
Aşağıdaki zamanlar UTC'dir. Mum probe'u her seri için 8 satır istedi.

| İşlem | Sonuç | Veri şekli | En son kapalı mumun kapanışı / snapshot zamanı |
|---|---|---|---|
| BTC-USDT ticker | Başarılı | 1 nesne; fiyatlar metin | `ts=1789194215866` |
| BTC-USDT orderbook | Başarılı | 1 nesne; 5 ask, 5 bid | `ts=1789194215953` |
| 4H candles | Başarılı | 8 × 9 metin alan; 7 kapalı | `2026-09-12T04:00:00Z` |
| 1H candles | Başarılı | 8 × 9 metin alan; 7 kapalı | `2026-09-12T06:00:00Z` |
| 15m candles | Başarılı | 8 × 9 metin alan; 7 kapalı | `2026-09-12T06:15:00Z` |
| 3 gün geriye 4H candles (`--after`) | Başarılı | 8 × 9 metin alan; 8 kapalı | `2026-09-09T08:00:00Z` |
| Account config read | Başarısız | CLI hesabı giriş gerektiriyor | Public bootstrap için engel değil |

OKX satır düzeni `[ts,o,h,l,c,vol,volCcy,volCcyQuote,confirm]`.
`ts` açılış zamanıdır; çekirdek kapanışı `ts + bar süresi` olarak kurar.
`confirm=0` satırları ve kapanışı snapshot sınırından sonra olan satırlar
alınmaz. Kaynak: [OKX resmi API dokümanı](https://tr.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks).

İlk uçtan uca çalışma 09:31 Türkiye saatinde her seri için **100 kapalı mum**
ile tamamlandı. Kapanışlar: 4H `04:00Z`, 1H `06:00Z`, 15m `06:30Z`.
Günlük `runs/shadow-phase1-20260912.jsonl` (Git dışında).
Ayrıca iki değerlendirmeli gerçek veri yenilemesi başarıyla tamamlandı;
günlük `runs/shadow-poll-20260912.jsonl`: bir bootstrap, iki karar, sıfır emir.
Bu kısa probe yeni bir mum kapanışını beklemedi; yeni/delayed mum birleştirme
ve veri boşluğu davranışları odaklı testlerle doğrulandı.

İlk günlükten kısaltılmış örnek:

```json
{"event":"BOOTSTRAP_COMPLETE","as_of":"2026-09-12T06:31:00.175290Z","symbol":"BTC-USDT","counts":{"4H":100,"1H":100,"15m":100},"execution_called":false}
{"event":"DECISION","mode":"shadow","decision":{"action":"NO_TRADE","reason":"STRATEGY_NOT_CONFIGURED"},"execution":{"status":"SHADOW","action":"NO_ACTION","reason":"STRATEGY_NOT_CONFIGURED","order_sent":false}}
```

## Mimari ve değişen dosyalar

`MarketSnapshot(symbol, as_of, histories)` frozen dataclass, history değerleri
tuple, eşleme kopyalanmış read-only mapping. Her seri sembol/zaman dilimi,
kapalı mum, sıkı zaman sırası ve `close_time <= as_of` koşuluyla doğrulanır.
`HistoryStore` replay/bootstrap için ortak, her seri için sınırlı geçmiş tutar.
Depo ilerlese bile verilmiş snapshot değişmez. Eski bir değerlendirme zamanı
istenirse yalnız halen bellekte tutulan nedensel altküme alınır.

Replay dosya sırasını korur. Bootstrap tüm serileri kapanışa göre birleştirir,
karar zincirini çağırmadan ortak depoyu doldurur. SHADOW yenilemesi bütün batch'i
doğrulayıp işler, sonra snapshot değerlendirir. Geciken kapalı bir HTF mumu için
global replay sırası zorlanmaz; seri içindeki sıra/süreklilik korunur.

`Detector.evaluate(snapshot)` bütün zaman dilimlerini görür; motorun private
alanlarına erişim gerekmez. `SingleTimeframeDetectorAdapter` eski detektörlere
tek tuple verir. `PatternResult.timeframe`, pencerenin hangi seriye ait olduğunu
belirtir. Detektör placeholder'ları halen `NOT_IMPLEMENTED`; router halen
`NO_TRADE / STRATEGY_NOT_CONFIGURED`. Günlük formatı `schema_version=2`.

| Değişen / eklenen dosya | Amaç |
|---|---|
| `agent_trading/data.py` | JSON sayılarını doğrudan Decimal olarak oku |
| `agent_trading/models.py` | Float girdisini reddet; immutable MarketSnapshot; sonuç timeframe alanı |
| `agent_trading/market.py` (yeni) | Ortak geçmiş deposu, sabit bar süreleri, snapshot özeti |
| `agent_trading/components.py` | Snapshot detektör API'si, eski API adaptörü, ShadowExecution |
| `agent_trading/config.py` | SHADOW modu, sembol/timeframe ve operasyon ayarlarının doğrulanması |
| `agent_trading/engine.py` | Ortak depo, işlem yapmayan bootstrap, batch güncelleme, snapshot değerlendirme, hata sonrası duruş |
| `agent_trading/okx.py` (yeni) | Resmi CLI'de salt piyasa okuma ve tam hassasiyetli kapalı mum normalizasyonu |
| `agent_trading/shadow.py` (yeni) | Bootstrap + sonlu/sürekli veri yenilemesi |
| `agent_trading/__main__.py` | Replay/SHADOW seçimi, güvenli hata kaydı, kullanıcı durdurması |
| `config.shadow.example.json` (yeni) | Yapılandırılabilir BTC-USDT / 4H / 1H / 15m örneği |
| `tests/test_foundation.py` | Eski detektör testlerini adaptörle koru; SHADOW artık destekleniyor |
| `tests/test_precision.py` (yeni) | JSON fiyat ve hacim hassasiyeti regresyonu |
| `tests/test_shadow.py` (yeni) | Causality, normalizasyon, bootstrap, intent-only execution, hata/gap ve MTF testleri |
| `README.md` | Çalıştırma yönergesi ve yeni sözleşmeler |
| `docs/superpowers/plans/2026-09-12-shadow-foundation.md` (yeni) | Onaylanmış sınırlı uygulama planı |
| `docs/shadow-phase1.md` (yeni) | Bu rapor |

## Doğrulama ve sınırlar

36 test geçti: özgün 16 replay testi, hassasiyet testi ve 19 SHADOW/MTF testi.
Testler gelecekteki/açık HTF mumlarının dışlanmasını, sembol/timeframe ayrımını,
snapshot'ın değişmemesini, bootstrap'ın işlem yapmamasını, onay verilse dahi
sadece WOULD_BUY kaydını, yinelenen poll'un etkisizliğini, gecikmiş HTF verisini
ve veri hatası sonrası motorun tekrar kullanılamamasını kapsar.

`foundation-v0.1` başlangıç commit'inde korundu:
`e4f2fdf6b4bb7dc2be1fd4912a342814c7c8f283`.
Bu aşama değişiklikleri çalışma ağacında bırakıldı; commit/tag/remote/push yapılmadı.

SHADOW örneği tek değerlendirme yapıp çıkar. Sürekli çalıştırma için kopya ayarda
`shadow_cycles=0`; her çalışma için yeni output yolu gerekir. CLI çağrıları
zaman aşımıyla sınırlı; yeniden deneme, WebSocket, gecikme SLA'sı veya otomatik
backfill yoktur. Boş gerekli seri, değişmiş kapalı mum veya atlanan bar çalışmayı
durdurur. Son mum kapanışları günlükte görünür; kapsamlı staleness/availability
politikası henüz tanımlanmadı. Sabit intraday süreleri desteklenir; gün/hafta/ay
seans semantiği, kısmi mumlar, hesap/fill takibi ve P&L simülasyonu eklenmedi.

Sıfır emir, kârlılık veya strateji doğrulaması değildir. Bu aşama veri ve SHADOW
altyapısını kanıtlar. Strateji şartnamesi gelene kadar burada durulur.

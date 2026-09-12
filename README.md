## Web App control shell (work/webapp)

This isolated branch adds a mobile-first React/Vite/TypeScript Dashboard and
Strategy Settings. From this worktree: npm install, then npm run dev.
npm run build creates dist; npm test runs 10 small checks.
No backend or Telegram account is needed for local development.

Controls and sample decisions are local/demo. LIVE selection is a confirmed
preview and remains blocked; no real execution, PAPER simulator or bot.
See [Web App handoff](docs/webapp-shell.md) for integration contracts and limits.
The backend foundation described below is preserved unchanged.

# Agent Trading

Açık kaynak, self-hosted otonom trading ajanının başlangıç altyapısı.
Python 3.11+ gerekir. Replay ve mevcut CLI SHADOW için ek Python paketi gerekmez.
Gerçek MCP adaptörü aşağıdaki isteğe bağlı kurulumu kullanır.

## Ürün yönü ve sözleşme v0.2

Nihai hedef START BOT ile gerekli piyasa durumunu sürekli tutan, onaylı strateji,
Acceptance, Trade Plan ve Risk zincirini çalıştıran bir ajandır. Kullanıcı
izin/risk/sembol kapsamını belirler; gerekli zaman dilimleri strateji profiline
aittir. Grafik/görüntüleme seçimi trading kararının girdisini değiştirmez.
Mevcut POST /api/v1/analyses manuel/debug/test, audit/demo ve inceleme yolu olarak
korunur. Otonom döngü ve Swing/strateji motoru henüz uygulanmadı.

[Analysis API v0.2](docs/specs/analysis-api-v0.2.md) raporu kullanılan zaman dilimi
haritası ve strategy_context ile genelleştirir. profile_id şu an null; strateji yok.
4H/1H/15m doğrulanmış varsayılan temeldir. [v0.1](docs/specs/analysis-api-v0.1.md)
tarihçesi ve kaydedilmiş eski raporlar değişmeden okunur. decision_as_of nedensel
bilgi kesim zamanıdır; mevcut manuel yolun en kısa gerekli aralık politikası
gelecekteki tüm stratejiler için bir kural değildir.

ANALYZE emir üretmez; PAPER simülasyon, LIVE açık yetkilendirilmiş gerçek yürütme
kavramlarıdır. PAPER/LIVE uygulanmadı; LIVE kapalıdır, kullanılabilir live anahtarı
ve borsa yazma yolu yoktur. Mevcut SHADOW yalnız niyet kaydeder, PAPER değildir.
[Otonom runtime ADR’si](docs/DECISIONS/011-autonomous-runtime-contract.md).
Sıradaki intelligence görevi: **SWING ENGINE R&D / SPEC**.

## Çalıştırma

Proje klasöründe Windows:

```powershell
py -m agent_trading --config config.example.json
```

Linux/macOS'ta `py` yerine `python3` kullanın.
Örnek dosya **sentetik** TEST-USDT mumları içerir; piyasa veya strateji kanıtı değildir.
Beklenen sonuç: `3 candles, 3 NO_TRADE, 0 orders`.

Her çalışma yeni bir günlük dosyası ister. Tekrar çalıştırırken:

```powershell
py -m agent_trading --config config.example.json --output runs/second-run.jsonl
```

Veri ve varsayılan çıktı yolu config dosyasının klasörüne göre çözülür.
`--output` yolu terminalin çalışma klasörüne göredir.

## Şu an çalışanlar

- JSONL mum okuma, fiyat/hacim ve saat dilimi doğrulama.
- Artımlı replay; sembol/zaman dilimine ayrı ve sınırlı geçmiş.
- Değiştirilebilir dedektör sözleşmesi ve yapılandırılmamış dedektör kayıtları.
- Ayrı karar, kabul, risk ve yürütme bileşenleri.
- Her mumda karar ve gerekçe günlüğü; hatada kayıt ve duruş.
- Tekrarlanabilir çıktılar ve entegrasyon testleri.
- OKX Agent Trade Kit üzerinden gerçek kapalı mumları alan SHADOW akışı.
- 4H / 1H / 15m için yapılandırılabilir bootstrap ve değiştirilemez MTF snapshot.
- Ayrı, salt okunur ürün runtime MCP adaptörü; gerçek OKX TR smoke doğrulandı.

**Bu sürüm strateji çalıştırmaz veya emir göndermez.** `NO_TRADE`, piyasanın
uygun bulunmadığı anlamına gelmez: strateji henüz yapılandırılmamıştır.
Risk ve kabul bileşenleri politika eklenene kadar onay üretmez.
Backtest, live emir yürütme, hesap takibi ve dolum simülasyonu henüz uygulanmadı.

## Gerçek OKX verisiyle SHADOW

Node ve resmi `@okx_ai/okx-trade-cli` kurulmuş olmalıdır. Bu projede doğrulanan
CLI sürümü `1.4.6`. Piyasa okuması için API anahtarı veya hesap girişi gerekmez.

```powershell
py -m agent_trading --config config.shadow.example.json --output runs/my-shadow.jsonl
```

Örnek ayar 4H, 1H, 15m için 100'er kapalı mum ister; bootstrap karar zincirini
çalıştırmaz. Ardından snapshot değerlendirilir ve `NO_TRADE / NO_ACTION` yazılır.
`shadow_cycles=1` bir değerlendirme yapıp çıkar. Ayar dosyasının bir kopyasında
`shadow_cycles=0` sürekli çalışmayı açar; Ctrl+C durdurur. Pozitif değer toplam
değerlendirme sayısıdır. `poll_interval_seconds` veri yenileme beklemesidir.

Node/CLI otomatik bulunamazsa `node_path` ve `okx_cli_path` ayarlarını girin.
İkinci yol resmi paketin `dist/index.js` dosyasıdır. Çalıştırma `shell=False`
ile yapılır; adaptör yalnız `market ticker/candles/orderbook` çağırabilir.
SHADOW yürütücüsü borsa bağlantısı taşımaz. Kabul ve risk bir gün onay verse
bile yalnız `WOULD_BUY` / `WOULD_SELL` kaydeder; belirsizlikte `NO_ACTION` üretir.

Bootstrap ve yenilemelerde boş gerekli seri, çelişkili kapalı mum veya veri
boşluğu çalışmayı durdurur. Otomatik yeniden deneme/backfill eklenmedi.
Her çalışma ayrı günlük ister; `runs/` Git tarafından yok sayılır.

Gerçek bağlantı kanıtı ve sınırlar: [Phase 1 raporu](docs/shadow-phase1.md).

## Gerçek ürün runtime MCP smoke

Resmi Node/ATK MCP `1.4.6` gerekir; mevcut CLI adaptörü korunur. Kurulu MCP
sürümü farklıysa adaptör durur, otomatik yükseltme veya CLI fallback yapmaz.
MCP yoksa ayrı olarak `npm install -g @okx_ai/okx-trade-mcp@1.4.6` kurun.
Windows'ta proje klasöründe:

```powershell
py -B -m venv .venv
.\.venv\Scripts\python.exe -B -m pip install -e '.[runtime-mcp]'
.\.venv\Scripts\python.exe -B -m agent_trading.mcp_smoke
```

Linux/macOS: ortamı `python3 -m venv .venv` ile oluşturun; sonraki iki komutta
`.venv/bin/python` kullanın. Bu platformdaki gerçek smoke henüz denenmedi.
Node/paket bulunamazsa smoke'a `--node-path` ve `--server-path` verilebilir;
ikinci yol MCP paketinin `dist/index.js` dosyasıdır. `--timeout` varsayılanı 30
saniye, her initialize/discovery/call için ayrı sınırdır.

Bu komut **gerçek internet/piyasa çağrısı** yapar: resmi Python `mcp==2.2.0`
client → ATK MCP `1.4.6` → `site=tr`, `modules=market`, read-only. API anahtarı
ve hesap girişi gerekmez; boş geçici home sayesinde hesap ayarları okunmaz.
BTC-USDT ticker, on 15m mum ve beş seviyeli book okunur. Açık/gelecek mumlar
filtrelenir; kapalı mumlar mevcut Decimal/UTC snapshot'a girer, ticker/book ayrı
gözlem zamanları taşır. Çıktı sanitize edilmiş JSON; hata nonzero çıkış üretir.
Toolkit log/update kontrolleri kapalıdır; geçici dosyalar ignored `runs/` altında
oluşup çıkışta silinir. Normal testler MCP/Node/network gerektirmez.

[Smoke kanıtı, 21 keşfedilen araç ve uyumluluk ayrıntısı](docs/runtime-atk-mcp-gate.md).
Bu dar kapı doğrulandı; mevcut CLI SHADOW komutu korunur. MCP artık aşağıdaki
ürün API/rapor akışında kullanılır. Ch.1 ve strateji tamamlanmış değildir.

## Ürün analizi API’si ve kalıcı geçmiş

Backend Hedef #2 gerçek BTC ürün akışını ekler: runtime MCP → ticker, kapalı
4H/1H/15m mumları ve orderbook → mevcut çekirdek → AnalysisReport → SQLite/API.
Strateji henüz yapılandırılmadığından başarılı veri akışının gerçek sonucu
`NO_TRADE / STRATEGY_NOT_CONFIGURED` olabilir. Eksik/eski/bozuk veri ise
`FAILED` ve null karar üretir; bu bir piyasa yönü değerlendirmesi değildir.

Windows’ta backend proje klasöründe, mevcut .venv için:

```powershell
./.venv/Scripts/python.exe -B -m pip install -e '.[product,test-product]'
./.venv/Scripts/python.exe -B -m unittest discover -s tests -v
./.venv/Scripts/python.exe -B -m uvicorn agent_trading.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Ortam yoksa önce `py -B -m venv .venv` çalıştırın. Python launcher bulunamazsa
[PROJECT_STATE](docs/PROJECT_STATE.md) içindeki doğrulanmış yorumlayıcıyı kullanın.
Linux/macOS için .venv/bin/python; bu platformun canlı smoke’u henüz doğrulanmadı.
Kurulum bir kez paket indirir; **170 testin normal çalışması internetsizdir**.
API testleri FastAPI/HTTPX kullanır; Node, ATK, hesap veya gerçek MCP oturumu gerekmez.
Replay ve CLI SHADOW komutları ek API paketleri olmadan çalışmaya devam eder.

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/analyses' -ContentType 'application/json' -Body '{"symbol":"BTC-USDT"}'
```

| Uç | Davranış |
|---|---|
| GET /health/live | Uygulama yanıt veriyor |
| GET /health/ready | SQLite ve yakın zamanda doğrulanmış MCP/MTF ön koşulları |
| POST /api/v1/analyses | Yeni tamamlanmış/başarısız rapor201; aynı idempotent istek200 |
| GET /api/v1/analyses/{analysis_id} | Orijinal kayıt; yeniden hesaplama yok |
| GET /api/v1/analyses | Geçmiş; limit1..50, offset0..10000 |

Yeni `FAILED` rapor da oluşturulmuş kaynak olarak201 döner; istemci mutlaka
`status` alanını kontrol eder. Doğrulama422, bilinmeyen kimlik404, çalışan aynı
istek/anahtar çakışması409, kapasite veya kayıt sorunu503. İsteğe bağlı
`Idempotency-Key` başlığı aynı terminal raporu MCP’yi yeniden çağırmadan döndürür;
yalnız anahtar özeti saklanır. Aynı anda bir yeni analiz çalışır.

İlk başarılı analize kadar /health/ready503 döner. POST bu durumda denenebilir.
Hazırlık önbelleği varsayılan60 saniyedir; veri hatası, süre aşımı veya yeni mum
sınırında eski kalan veri hazırlığı düşürür. GET hazır olma kontrolü ağ çağrısı
yapmaz. Yeniden başlatma geçmişi korur; yeni veri doğrulaması ayrıca gerekir.

Varsayılan SQLite yolu `runs/product/analyses.sqlite3`, her analizin ayrı çekirdek
günlüğü `runs/analyses/{analysis_id}.jsonl`. İkisi de Git dışında kalır.
SQLite DELETE rollback journal, kısa işlemler ve terminal rapor/olay atomik kaydı
kullanır. Bir süreç/worker bu veriyi sahiplenir; çoklu worker başlatmayın.
Yarım kalan RUNNING kayıtlar yeniden başlatmada FAILED/PROCESS_INTERRUPTED olur.
SQLite geçmişi, mevcut JSONL çekirdek günlüğünün yerini almaz.

Operatör ortam ayarları: ANALYSIS_DB_PATH, ANALYSIS_AUDIT_DIR,
ANALYSIS_NODE_PATH, ANALYSIS_ATK_SERVER_PATH; açık operasyon ayarları
ANALYSIS_HISTORY_LIMIT (100), ANALYSIS_PUBLICATION_GRACE_SECONDS (60),
ANALYSIS_OBSERVATION_MAX_AGE_SECONDS (60), ANALYSIS_MCP_TIMEOUT_SECONDS (20),
ANALYSIS_ANALYSIS_TIMEOUT_SECONDS (60), ANALYSIS_READY_TTL_SECONDS (60),
ANALYSIS_SQLITE_TIMEOUT_SECONDS (1) ve küçük ANALYSIS_ALLOWED_SYMBOLS listesi.
ANALYSIS_REQUIRED_TIMEFRAMES varsayılan4H,1H,15m koleksiyonunu operatör katmanında
belirler; boş/tekrarlı/desteklenmeyen aralıklar reddedilir. Mevcut runtime sabit
1m,3m,5m,15m,30m,1H,2H,4H,6H,12H aralıklarını destekler; günlük/takvim mumları
henüz desteklenmez. Onaylı profil olmadığından bu bir operasyonel inceleme
koleksiyonudur; gelecek strateji kendi gereksinimlerini sağlayacaktır.
İstemci bu alanları, chart_timeframe veya decision_timeframe değerini HTTP
isteğinde ayarlayamaz; site tr sabittir.

Ayrı **gerçek internet/piyasa** ürün doğrulaması:

```powershell
./.venv/Scripts/python.exe -B -m agent_trading.product_smoke
```

--node-path/--server-path bulunmayan kurulu runtime yollarını, --db-path/
--audit-dir saklama konumunu, --timeout/--mcp-timeout süre sınırını belirler.
Çıktı yalnız kısa kimlik/zaman/karar/spread/araç/kayıt/emir özetidir.
[Gerçek ürün kanıtı](docs/product-analysis-smoke.md): beş gerçek MCP okuması,
100’er kapalı mum, mevcut çekirdek, SQLite ve aynı raporun API’den alınması başarılı.

[Güncel v0.2 API/UX sözleşmesi](docs/specs/analysis-api-v0.2.md) fiyat/miktarları string,
tüm zamanları UTC taşır. Ticker/book gözlemleri geçmiş mum kararının girdisi olmaz.
Market Structure, Range, Deviation ve Premium/Discount NOT_IMPLEMENTED;
Acceptance/Risk NOT_EVALUATED. Açıklama yalnız rapordan üretilir, LLM yoktur.
Aynı değişmemiş gerçek smoke komutu v0.2 için de başarılı oldu:
517c6e4d-265b-4a9b-9860-cf7f8aa7e4a2;100’er kapalı mum, NO_TRADE,
order_sent=false. Gerçek v0.1/v0.2 kayıtlarının aynı içerikle HTTP/geçmişten
okunması doğrulandı; [devir kanıtı](docs/HANDOFF.md).
Tam grafik dizileri, Claude UX incelemesi, auth/CORS, sürekli veri yenileme,
Linux/container ve deployment sonraki işlerdir. Ch.1 tamamlanmış değildir.

## Configurable PAPER RiskEngine

The opt-in offline trading brain now requires a RiskEngine-approved plan before
paper execution. STRUCTURE_BE defaults to fresh validated structure support,
sweep fallback and configurable1R break-even [H]. FIXED_SL_TP preserves original
SL/TP. R:R/stop distance/size gates emit machine-readable BLOCKED with evidence;
actual next-open fills are reapproved. Swing and frozen Range semantics are preserved.

```powershell
py -B -m agent_trading.trading_brain --candles tests/data/btcusdt_15m.jsonl --stop-profile STRUCTURE_BE --break-even-r 1 --min-reward-risk 1 --risk-per-trade .01
```

Optional `--max-stop-distance` uses absolute price units; `--stop-buffer`,
`--equity`, `--quantity-step` and `--target EQ|BOUNDARY` remain configurable.
These are provisional PAPER settings [H], not trading recommendations or empirical
validation. [Risk spec](docs/specs/risk-engine-v0.1.md),
[approved/blocked evidence and gaps](docs/risk-engine.md). No LIVE is implemented.

## Modüller

| Dosya | Sorumluluk |
|---|---|
| `models.py` | Mum ve dedektör veri sözleşmeleri |
| `config.py` | Merkezi operasyon ayarları |
| `data.py` | Mum dosyasını artımlı okuma |
| `components.py` | Dedektör arayüzü ve yapılandırılmamış karar zinciri |
| `engine.py` | Geçmiş yönetimi ve akış koordinasyonu |
| `market.py` | Replay/bootstrap için ortak geçmiş deposu ve snapshot özeti |
| `okx.py` | Yalnız piyasa okuyan Agent Trade Kit CLI adaptörü ve normalizasyon |
| `okx_mcp.py` | MCP keşfi, izinli public okumalar, mevcut mum normalizer ve provenance |
| `okx_mcp_runtime.py` | Sabitlenmiş resmi SDK/ATK process yaşam döngüsü ve public izolasyonu |
| `market_observations.py` | Snapshot dışındaki immutable Decimal ticker/book gözlemleri |
| `mcp_smoke.py` | Açıkça çağrılan gerçek TR public MCP smoke |
| `analysis_config.py` | Sınırlı operatör ayarları ve gerekli zaman dilimi koleksiyonu |
| `analysis_report.py` | v0.2 bağlam/zaman dilimi raporu, freshness, exact spread ve açıklama |
| `analysis_repository.py` | SQLite kalıcı metadata/rapor/olaylar |
| `analysis_service.py` | Sınırlı gerçek MCP/MTF/çekirdek ürün akışı |
| `analysis_api_models.py` | Strict OpenAPI/string finansal veri şeması |
| `api.py` | İnce analiz/geçmiş/health HTTP arayüzü |
| `product_smoke.py` | Ayrı gerçek ürün ve SQLite smoke |
| `shadow.py` | Bootstrap ve SHADOW veri yenileme akışı |
| `journal.py` | JSONL karar/hata kaydı |
| `__main__.py` | Komut satırından çalıştırma |

`history_limit=512` bellek sınırıdır; strateji penceresi değildir. `1m` yalnız
örnek verinin zaman dilimidir. Hiçbiri önerilen trading parametresi sayılmaz.

## Veri ve zaman sözleşmesi

Her satırda `symbol`, `timeframe`, `close_time`, `open`, `high`, `low`, `close`,
`volume`, `closed` gerekir. `close_time` mumun **kapanış zamanıdır**, açılışı
değildir. Saat dilimi zorunlu; iç temsili UTC. JSON fiyat/hacim sayıları doğrudan
Decimal olarak okunur; ondalık metin de kabul edilir. Python float girdileri
hassasiyet kaybı nedeniyle reddedilir. `closed` JSON boolean `true` olmalıdır.

Dosya kapanış zamanına göre sıralanmalıdır. Aynı sembol ve zaman diliminde
tekrar/eski mum reddedilir. Farklı serilerin eşit zamandaki mumları dosya
sırasıyla işlenir. Replay dosyalarında eksik aralıklar kontrol edilmez.
OKX bootstrap/yenileme ise desteklenen sabit süreli mumlarda boşluk kontrol eder.
Gün/hafta/ay ve kısmi mum semantiği bu adaptörde desteklenmez.

Dedektör `evaluate(MarketSnapshot)` üzerinden sembol, değerlendirme zamanı ve
zaman dilimine göre ayrılmış değiştirilemez geçmişleri alır. Snapshot yalnız
`close_time <= as_of` olan kapalı mumları içerir. Eski `evaluate(history)`
detektörleri `SingleTimeframeDetectorAdapter(detector, timeframe)` ile çalışır;
adaptör eski sonuçların zamanını değiştirerek eski/gelecek sinyali gizlemez.
MTF sonuçlarında `window` belirtilirse ilgili `timeframe` de belirtilmelidir.
Günlük sözleşmesi yeni snapshot alanlarıyla `schema_version=2` olmuştur.

Dedektör sadece kendisine verilen değiştirilemez geçmişi kullanmalıdır.
Çekirdek gelecekteki mumları vermez; sonradan eklenecek dedektörün kendi
dış kaynaklarından veri sızdırmasını engelleyen bir sandbox değildir.

## Kaynaktan stratejiye

Her modül için önce kaynak iddiası → kesin koşullar → geçersizleşme → girdiler
→ çıktılar → uç durumlar → test örnekleri belirlenir. Ardından dedektör eklenir.
Skor varsa yöntem adı zorunludur; kendiliğinden başarı olasılığı anlamına gelmez.
Kaynak güvenilirliği ile ampirik doğrulama ayrı tutulur.

`foundation-v0.1` etiketi özgün replay temelini korur.
Ayrıntılı özgün kapsam: [Temel tasarım](docs/foundation.md).

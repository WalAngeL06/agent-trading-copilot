# Agent Trading Copilot

A self-hosted, open-source trading **agent runtime** with a mobile-first web
dashboard and an optional Telegram Mini App. Market data comes from the official
**OKX Agent Trade Kit (ATK) MCP** server; the deterministic strategy core runs
locally and every decision is observable.

> **Scope and safety.** Execution is **PAPER only**. LIVE trading is not
> implemented and is disabled — there is no exchange write path and no usable
> live switch. Optional OKX account access is **read-only** and limited to a
> four-tool allowlist. A working pipeline is not evidence of profitability, and
> nothing here is financial advice.

Türkçe ayrıntılı mimari, sözleşme ve kanıt bölümleri bu rehberin altında yer alır.

---

## What you get

| Surface | What it does |
|---|---|
| Web dashboard | Bot status, live OKX market connection, latest deterministic decision, account state, activity feed, Start/Stop |
| Telegram Mini App | The same dashboard inside Telegram via `/start` → **Open Dashboard** |
| HTTP API | `/health/live`, `/health/ready`, `/api/v1/bot/*`, `/api/v1/analyses` |
| Strategy core | Deterministic replay/analysis over real 15m candles, Decimal prices, UTC timestamps |

## Requirements

- **Python 3.11+**
- **Node.js 22.12+**
- **OKX ATK MCP, pinned**: `npm install -g @okx_ai/okx-trade-mcp@1.4.6`
  (the runtime refuses any other package or version)

Public market data needs **no API key**. OKX credentials are optional and only
enable read-only account/balance display.

## Quick start

```bash
git clone <your-repo-url> agent-trading && cd agent-trading
```

**1. Backend**

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -e ".[product,test-product]"
```

On Linux/macOS use `.venv/bin/python` instead of `.venv/Scripts/python.exe`.

**2. Frontend**

```bash
npm install
```

**3. Configuration**

Copy `.env.example` to `.env` and fill in only what you need. **Never commit
`.env`** — it is gitignored.

| Variable | Required | Purpose |
|---|---|---|
| `OKX_API_KEY` / `OKX_SECRET_KEY` / `OKX_PASSPHRASE` | No | Read-only OKX account/balance display |
| `TELEGRAM_BOT_TOKEN` | No | Enables the Telegram bot |
| `WEBAPP_URL` | For Telegram | Public **HTTPS** frontend URL used by the Open Dashboard button |
| `VITE_BACKEND_URL` | No | API base the browser calls (default `http://127.0.0.1:8000`) |
| `ALLOWED_ORIGINS` | For public use | Extra CORS origins; `localhost:5173` and `127.0.0.1:5173` are always allowed |

**4. Run**

Backend:

```bash
.venv/Scripts/python.exe -m uvicorn agent_trading.api:create_app --factory --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```bash
npm run dev
```

Open **http://127.0.0.1:5173**. Press **Start Bot** — within a few seconds the
market card shows `OKX ATK MCP · Connected` and the activity feed logs real
candle updates. **Stop Bot** halts the engine; the Telegram bot stays alive.

Check the backend directly:

```bash
curl http://127.0.0.1:8000/health/ready
```

`status` is `READY` once the repository is available and market data is
connected. While the engine is stopped, `NOT_READY` with
`MARKET_DATA_NOT_VALIDATED` is the correct, honest answer.

## Telegram Mini App

Telegram only loads Mini Apps over **HTTPS**, and the browser calls the backend
**directly** — so both the frontend and the backend need a public HTTPS URL. The
frontend does not proxy API requests; one tunnel is not enough.

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Start two tunnels (install: `winget install --id Cloudflare.cloudflared`):

```bash
cloudflared tunnel --url http://localhost:5173
```

```bash
cloudflared tunnel --url http://localhost:8000
```

3. Put the generated URLs in `.env`:

```
TELEGRAM_BOT_TOKEN=<your bot token>
WEBAPP_URL=https://<frontend>.trycloudflare.com
VITE_BACKEND_URL=https://<backend>.trycloudflare.com
ALLOWED_ORIGINS=https://<frontend>.trycloudflare.com
```

4. **Restart both services.** Vite reads `VITE_BACKEND_URL` at startup, and the
   backend reads `WEBAPP_URL` / `ALLOWED_ORIGINS` at startup.
5. Send `/start` to your bot and tap **Open Dashboard**. `/status` returns bot,
   execution mode, market connection, account auth and strategy state as text.

Quick-tunnel URLs change every restart — update `.env` and restart again.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "Control center could not load" | Backend not running, or `VITE_BACKEND_URL` points somewhere unreachable. Verify `/health/live`, then restart the frontend. |
| Dashboard loads but values never change | The frontend polls every 5s; a blocked or failing backend keeps the last good snapshot. Check the browser console and backend log. |
| Blocked request / invalid Host via a tunnel | Add your tunnel domain to `server.allowedHosts` in `vite.config.ts` (`.trycloudflare.com` is preconfigured). |
| CORS error on the public URL | `ALLOWED_ORIGINS` must be the bare frontend origin (scheme + host, no path), then restart the backend. |
| `ATK_NOT_INSTALLED` / `ATK_PACKAGE_MISMATCH` | Install exactly `@okx_ai/okx-trade-mcp@1.4.6` and make sure `node` is on `PATH`. |
| Telegram button does nothing | `WEBAPP_URL` must be HTTPS. Telegram rejects `http://localhost`. |
| Port already in use | Another instance or worktree holds `8000`/`5173`. Stop it, or run on different ports. |
| Account shows `AUTH_MISSING` | All three OKX variables must be set. `CONNECTED` means a successful read-only read. |

## Tests

```bash
.venv/Scripts/python.exe -B -m unittest discover -s tests
```

```bash
npm test && npm run build
```

## Reading the dashboard

- **Bot status** — `RUNNING` / `STOPPED`, always with `PAPER` mode.
- **Market data source** — `OKX ATK MCP` plus real connection state; `Connected`
  appears only after a real candle update.
- **Latest decision** — the deterministic strategy outcome. `NO_TRADE` is a real
  result, not an error or a placeholder.
- **Account** — `CONNECTED` / `AUTH_MISSING` / `ERROR` from read-only reads.
- **Activity feed** — timestamped backend events; nothing is simulated.

Strategy settings are stored in your browser and are intentionally decoupled from
the engine's approved profile; changing them does not retune the strategy core.

## Project docs

Start with [AGENTS.md](AGENTS.md) (shared constitution), then
[PROJECT_STATE](docs/PROJECT_STATE.md), [HANDOFF](docs/HANDOFF.md) and
[NEXT_TASK](docs/NEXT_TASK.md). Specifications live in [docs/specs](docs/specs/)
and design decisions in [docs/DECISIONS](docs/DECISIONS/).

---

# Agent Trading — altyapı ve sözleşmeler (detay)

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

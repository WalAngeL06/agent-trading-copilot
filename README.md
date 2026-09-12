# Agent Trading

Piyasa yapısı odaklı bir trading ajanının başlangıç altyapısı.
Python 3.11+ gerekir. Çalıştırmak için ek paket kurulumu gerekmez.

## Çalıştırma

Proje klasöründe Windows:

```powershell
py -m agent_trading --config config.example.json
py -m unittest discover -s tests -v
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

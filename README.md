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

**Bu sürüm strateji çalıştırmaz veya emir göndermez.** `NO_TRADE`, piyasanın
uygun bulunmadığı anlamına gelmez: strateji henüz yapılandırılmamıştır.
Risk ve kabul bileşenleri politika eklenene kadar onay üretmez.
Backtest, shadow, live, borsa bağlantısı, geçmiş veri indirme, hesap takibi,
MTF birleştirme ve dolum simülasyonu henüz uygulanmadı.

## Modüller

| Dosya | Sorumluluk |
|---|---|
| `models.py` | Mum ve dedektör veri sözleşmeleri |
| `config.py` | Merkezi operasyon ayarları |
| `data.py` | Mum dosyasını artımlı okuma |
| `components.py` | Dedektör arayüzü ve yapılandırılmamış karar zinciri |
| `engine.py` | Geçmiş yönetimi ve akış koordinasyonu |
| `journal.py` | JSONL karar/hata kaydı |
| `__main__.py` | Komut satırından çalıştırma |

`history_limit=512` bellek sınırıdır; strateji penceresi değildir. `1m` yalnız
örnek verinin zaman dilimidir. Hiçbiri önerilen trading parametresi sayılmaz.

## Veri ve zaman sözleşmesi

Her satırda `symbol`, `timeframe`, `close_time`, `open`, `high`, `low`, `close`,
`volume`, `closed` gerekir. `close_time` mumun **kapanış zamanıdır**, açılışı
değildir. Saat dilimi zorunlu; iç temsili UTC. Fiyat/hacmi ondalık metin olarak
gönderin. `closed` JSON boolean `true` olmalıdır.

Dosya kapanış zamanına göre sıralanmalıdır. Aynı sembol ve zaman diliminde
tekrar/eski mum reddedilir. Farklı serilerin eşit zamandaki mumları dosya
sırasıyla işlenir. Eksik mum aralıkları bu sürümde tespit edilmez; süre ve
veri sürekliliği politikası veri adaptörü şartnamesinde tanımlanacaktır.

Dedektör sadece kendisine verilen değiştirilemez geçmişi kullanmalıdır.
Çekirdek gelecekteki mumları vermez; sonradan eklenecek dedektörün kendi
dış kaynaklarından veri sızdırmasını engelleyen bir sandbox değildir.

## Kaynaktan stratejiye

Her modül için önce kaynak iddiası → kesin koşullar → geçersizleşme → girdiler
→ çıktılar → uç durumlar → test örnekleri belirlenir. Ardından dedektör eklenir.
Skor varsa yöntem adı zorunludur; kendiliğinden başarı olasılığı anlamına gelmez.
Kaynak güvenilirliği ile ampirik doğrulama ayrı tutulur.

Ayrıntılı kapsam: [Temel tasarım](docs/foundation.md).

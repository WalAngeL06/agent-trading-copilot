# Range modeli: rehber ile kod arasındaki fark (20 Eylül 2026)

Kaynak: `Desktop/öğrenme-dd finance ve odin/range_trade_learning_guide.md`
("Senior Range Trade Model - AI Implementation & Learning Guide"). Bu dosya,
`docs/PROJECT_STATE.md` ve `docs/SOURCE_REGISTRY.md` içinde "orijinal DD kaydı
repoda yok" diye geçen kaynağın kendisidir.

Ölçüm tabanı: `data/btc_deep` (BTC-USDT, giriş zaman dilimi 15m, 2025-09-02 →
2026-09-12), koşu `runs/eval-deep`, varsayılan profil.

## 1. Ölçülen huni

| Aşama | Sayı |
|---|---|
| Yön kırılımı (BIAS_BREAK) | 195 |
| Range adayı | 117 |
| İptal olan aday | 112 |
| Onaylanan range | 5 |
| Sweep | 24 (19 SHORT / 5 LONG) |
| Manipülasyon onayı | 15 (13 SHORT / 2 LONG) |
| Kurulum (setup) | 0 |
| İşlem | 0 |

İptallerin **tamamı** fitil kaynaklı: 74 `WICK_BELOW_RANGE_LOW`,
38 `WICK_ABOVE_RANGE_HIGH`. Adayların ömrü medyan **4 saat** (4 adet 1H mumu).

## 2. Kural kural karşılaştırma

| # | Rehber kuralı | Kodda durum | Kanıt |
|---|---|---|---|
| §2.1 | Pivot tespiti N-left/N-right fraktal filtresi (N=2-3) | **Farklı**: ATR eşikli salınım tespiti (`atr_multiplier=1.25`) ve gecikmeli onay | `agent_trading/swing.py` |
| §2.2 | İşlevsellik filtresi: yeni HH/LL yaptıran dip/tepe geçerli | **Var** | `trading_brain/structure.py`, `ValidLow/ValidHigh` |
| §2.3 | Kırılım teyidi gövde kapanışıyla; fitil = süpürme | **Var** (yapı katmanında) | `structure.py` başlık satırı |
| §3.1 | Ön koşul: impulse dalgası + yatay evre | **Yok** | kodda `impulse` geçmiyor |
| §3.2 | RH ve RL'ye **2'şer** geçerli temas | **Farklı**: 1 alt + 1 üst temas yeterli | `trading_brain/range.py` (`WAIT_LOW_TOUCH` → `WAIT_HIGH_TOUCH` → `RANGE_CONFIRMED`) |
| §3.2 | Temas sayılması için arada **EQ ziyareti** şart | **Yok** | aynı dosyada EQ kontrolü yok |
| §3.2 | Düşen tepeler (LH) tercihi | **Yok** | — |
| §4.1 | Sapma limiti = `(RH−EQ)`'nun %50'si; aşılır **ve** dışarıda gövde kapanırsa iptal (Breakout) | **Ters**: onaydan önce herhangi bir fitil teması iptal ediyor | `range.py`, `WICK_BELOW/ABOVE_RANGE_*` |
| §4.2 | Teyitlerde gövde kapanışı; fitil yalnız likidite alımı | **Kısmen**: onay sonrası "retire" gövde kapanışına bakıyor, onay öncesi bakmıyor | `range.py` |
| §4.3 | HTF bağlamı (4H arz/talep, FVG, ana S/R ile çakışma) zorunlu | **Yok** | girişte HTF çakışma kontrolü yok |
| §4.4 | Premium/Discount filtresi | **Yok** (yalnız eski analiz raporunda alan olarak geçiyor) | `swing.py` başlık notu |
| §5.1 | Likidite mıknatısı hedefi (karşı taraftaki birikim) | **Kısmen**: hedef sabit `range_high` | `strategy_v1/strategy.py` `_consider` |
| §5.2 | Sapma sonrası dönüş + **CHoCH gövde kırılımı** onayı | **Farklı**: "reclaim" = mumun range içinde kapanması; CHoCH yok | `trading_brain/manipulation.py` |
| §5.3 | Giriş bölgesi: CHoCH sonrası yeni FVG **veya Breaker**, retest ile | **Kısmen**: yalnız FVG/iFVG defteri; breaker/OB yok | `strategy_v1/entry.py` |
| §6 | EQL/EQH havuzları (hedef) | **Yok** | — |
| §6 | SFP etiketleme | **Kısmen**: sweep var, SFP ayrı etiket yok | `manipulation.py` |
| §6 | Giriş modelleri: FVG EQ, Breaker/S-R flip, Untested OB | **Kısmen**: sadece FVG EQ | `entry.py`, profil `entry_level` |
| §6 | Altın kural 1: girişte **LTF CHoCH teyidi** | **Yok** | doğrudan limit emir kuruluyor |
| §6 | Stop: sweep fitilinin arkası | **Var** | `TradeCandidate.sweep_extreme` |
| §7 | RBR / DBD arz-talep tabanları | **Yok** | — |
| §8 | Pazartesi aralığı (MH/ML), aylık/haftalık açılış | **Yok** | kodda `monday`, `weekly_open` geçmiyor |
| §9 | Kırılım sonrası trend takip modu | **Yok**: range "retire" edilip beklemeye geçiliyor | `range.py` |
| §10 | Acceptance katmanı 7 kuralı | **Yok**: kabul katmanı yer tutucu | `components.py` |
| — | Yön | Rehber iki yönlü; kod **LONG_ONLY** | `strategy_v1/config.py` |

## 3. Sıfır işleme katkı sıralaması

1. **§4.1 ters uygulanmış sapma/iptal kuralı.** Tek başına 112 adayın hepsini
   eliyor. Rehberde bu fitiller işlemin sinyali (manipülasyon); kodda ölüm sebebi.
2. **LONG_ONLY.** Ölçülen 15 manipülasyon onayının 13'ü SHORT. Kural düzelse bile
   fırsatların ~%87'si kullanılmıyor.
3. **§3.2 temas ve EQ kuralı eksik.** Onay ölçütü rehberden gevşek; kural 1
   düzeltilince range sayısı artacağı için bu ölçüt sıkılaştırılmalı.
4. **§5.2 CHoCH ve §6 LTF teyidi yok.** Giriş kalitesi rehberdekinden düşük.
5. **§4.3/§4.4 HTF ve premium/discount filtreleri yok.** Bağlam filtresi olmadan
   sinyal sayısı artar ama kalite düşer.

## 4. Çelişen talimat

Mevcut davranış 12 Eylül 2026 tarihli `[U-RANGE-BOUNDARIES-001]` talimatından
geliyor: "aday range'de her fitil teması onaydan önce iptal eder". Rehber §4.1/§4.2
bunun tersini söylüyor. 20 Eylül 2026'da sahip, rehberin geçerli olduğuna karar
verdi: `[U-RANGE-GUIDE-001]`. Bu belge, `[U-RANGE-BOUNDARIES-001]` kuralını
sapma limiti + gövde kapanışı kuralıyla değiştirir. Ham salınımlar, geçerli
seviyeler ve nedensellik kuralları değişmez.

## 5. Bu turda uygulanan kapsam

Yalnızca §4.1, §4.2 ve §3.2: sapma limiti, gövde kapanışlı iptal ve EQ ziyaretiyle
doğrulanan temas. Diğer maddeler (CHoCH, breaker/OB, HTF, premium/discount,
Pazartesi seviyeleri, trend modu, çift yön, acceptance) bu belgede kayıt altında
ve ayrı kararlarla ele alınacak.

## 6. Ölçülen sonuç: aynı veri, eski ve yeni kural

`data/btc_deep`, BTC-USDT, 2025-09-02 → 2026-09-12. Koşular: `runs/eval-deep`
(eski kural) ve `runs/eval-guide` (rehber kuralı).

| Metrik | Eski | Yeni |
|---|---|---|
| Range adayı | 117 | 74 |
| İptal olan aday | 112 (hepsi fitil) | 67 (hepsi gövde kapanışı) |
| Onaylanan range | 5 | 7 |
| Sweep | 24 | 41 |
| Manipülasyon onayı | 15 | 30 |
| Kurulum | 0 | 0 |
| İşlem | 0 | 0 |

Range katmanı düzeldi: onaylı range ve manipülasyon sayısı iki katına çıktı,
iptaller artık rehberin tanımladığı breakout'lar. Ama işlem hâlâ yok.

## 7. Yeni darboğaz: yön

Ölçüm (`scratchpad/entry_funnel.py` mantığı, bir yıllık koşu):

- 30 manipülasyon onayının **27'si SHORT**, 3'ü LONG.
- LONG kurulumun hazır olduğu 15m mum sayısı: **0**.
- Giriş değerlendirmesinde elenme sebepleri: 9.151 bar "4H yön izni yok",
  6.517 bar "onaylı range yok", 291 bar "manipülasyon SHORT", 157 bar
  "manipülasyon yok". Giriş FVG'si uygunluk kontrolüne hiç sıra gelmedi.

Sıradaki iki karar, önem sırasıyla:

1. **Çift yön (§5, §6).** Rehber sapmayı iki tarafta da tanımlıyor; kod yalnız
   LONG açıyor. Ölçülen fırsatların %90'ı bu yüzden kullanılamıyor.
2. **4H yön izni.** Giriş bakılan barların yarısından fazlasında LONG izni yok.
   Rehberin HTF bağlamı (§4.3) ve premium/discount (§4.4) kuralları bu kapının
   yerine geçmeli; mevcut izin kuralı rehberde tanımlı değil.

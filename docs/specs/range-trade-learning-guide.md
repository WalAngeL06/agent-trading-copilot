# Senior Range Trade Model - AI Implementation & Learning Guide

Bu rehber, Agent Trading projesindeki `Range`, `Deviation`, `Manipulation` ve `Market Structure` tespit algoritmalarının %99 doğrulukla kodlanabilmesi için hazırlanmış merkezi bir "Data Center" (Bilgi Bankası) dokümanıdır. 

Yapay zeka asistanları (Codex, Claude vb.) bu dokümanı kullanarak piyasa yapısını analiz eden deterministik kuralları ve state-machine (durum makinesi) mantıklarını inşa etmelidir.

## 1. Terminoloji ve Algoritmik Karşılıklar

*   **Range High (RH):** Üst bant.
*   **Range Low (RL):** Alt bant.
*   **Equilibrium (EQ):** Range'in orta noktası. Formül: `EQ = RL + ((RH - RL) / 2)` veya `(RH + RL) / 2`.
*   **Deviation (Sapma/Manipülasyon):** Fiyatın RH veya RL dışına çıkıp, tekrar Range içine dönmesi durumu (Tuzak).
*   **CHoCH (Change of Character):** Sapma sonrası Range içine dönüşte kırılan ilk iç tepe/dip noktası. Onay mekanizmasıdır.
*   **Breakout (Kırılım):** Fiyatın sapma limitlerini aşarak Range dışına kalıcı olarak çıkması ve yeni trend başlatması.

## 2. Market Structure (Piyasa Yapısı) Algoritması: Geçerli Tepe/Dip Tespiti

Algoritmanın **gerçek yapısal tepe/dip (External/Structural High/Low)** ile **iç yapı dalgalanmasını (Internal Structure / Gürültü)** birbirinden ayırmak için kullanacağı 3 aşamalı deterministik filtre:

### Aşama 1: Matematiksel Pivot (Fractal) Filtresi (N-Left / N-Right)
Aday tepe/dipler (local extrema) tespiti:
*   **Pivot High (Potansiyel Tepe):** Kendisinden önceki `N` mum ve sonraki `N` mumun en yüksek fiyatından (High) daha yüksek olan mumdur. `High_i = max(High_{i-N}, ..., High_{i+N})`
*   **Pivot Low (Potansiyel Dip):** Kendisinden önceki `N` mum ve sonraki `N` mumun en düşük fiyatından (Low) daha düşük olan mumdur. `Low_i = min(Low_{i-N}, ..., Low_{i+N})`
*   *Look-Ahead Bias Önlemi:* Bir pivotun tespiti `i+N` anında kesinleşir. (Genellikle N=2 veya N=3 kullanılır).

### Aşama 2: Fonksiyonel İşlevsellik Filtresi
Aşama 1'de bulunan pivotların yapısal olup olmadığının testi:
*   **Geçerli Yapısal Dip (Valid Swing Low / "High Yaptıran Low"):** Fiyatı son geçerli yapısal tepenin (ValidHigh) üzerine çıkarıp **yeni bir en yüksek (Higher High)** yaptıran dip seviyesidir.
*   **Geçerli Yapısal Tepe (Valid Swing High / "Low Yaptıran High"):** Fiyatı son geçerli yapısal dibin (ValidLow) altına düşürüp **yeni bir en düşük (Lower Low)** yaptıran tepe seviyesidir.
*   **İç Yapı (Internal Structure / Gürültü):** Son ValidHigh ve ValidLow sınırları içerisinde kalan, yeni bir majör kırılım yaptırmamış tüm lokal Pivot noktalarıdır. Ana trend yönünü değiştirmez.

### Aşama 3: Kırılım Teyit Filtresi (Body Close vs. Wick)
*   **Gerçek Kırılım (BOS / MSS) Koşulu:** `Close_current > High(ValidHigh_prev)` (Bullish) veya `Close_current < Low(ValidLow_prev)` (Bearish). Net mum gövde kapanışı şarttır.
*   **Fitil Tuzağı (Wick Break / Sweep):** Eğer `High_current > High(ValidHigh_prev)` ancak `Close_current <= High(ValidHigh_prev)` gerçekleşirse, bu bir kırılım DEĞİL, **Likidite Süpürmesi (SFP / Deviation)** olarak etiketlenir. Majör yapıyı değiştirmez.

## 3. Range Oluşum (Detection) Algoritması Kuralları

Bir Range yapısının tespit edilebilmesi için sistemin aşağıdaki adımları sırasıyla doğrulaması gerekir:

### Adım 1: Ön Koşul (Bağlam)
*   **Büyük Hareket (Impulse):** Range'den önce fiyat grafiğinde sert bir yükseliş veya düşüş dalgası yaşanmış olmalıdır. (Algoritmik olarak: Ortalama mum boyutu (ATR) veya momentum indikatörleri ile "Impulse" dalgası tanımlanmalı, ardından volatilitenin düştüğü "Sideway" (Yatay) evre tespit edilmelidir.)
*   **Likidite (Hacim):** Hacimsiz enstrümanlar filtrelenmeli, majör ve likiditesi yüksek paritelerde çalışılmalıdır.

### Adım 2: Temas (Touch) Kuralları
Geçerli bir Range çizimi için RH ve RL seviyelerine **en az 2'şer geçerli temas** şarttır. (Toplam 4 temas: 2 RH, 2 RL)

*   **EQ Ziyareti Kuralı (Çok Kritik):** Bir noktanın "geçerli temas" sayılabilmesi için, fiyatın RH veya RL'ye dokunduktan sonra yön değiştirip **kesinlikle EQ (0.5) seviyesine kadar ulaşması** (dokunması) zorunludur. EQ'ya ulaşmadan geri dönen fiyat hareketleri, temas sayısını (Touch Count) artırmaz!
*   **Referans Tavan (İlk Zirve):** RH'yi oluşturan ilk tepe noktası referans kabul edilir.
*   **Düşen Tepeler (Lower High - LH) Kuralı:** İdeal (tercih edilen) bir Range yapısında, RH'ye yapılan 2. temasın, ilk referans tepenin altında kalması (mum fitillerinin ilk tepeyi geçmemesi) beklenir. Bu durum üstte alıcıların zayıfladığını, altta satıcı baskısı biriktiğini gösterir.

## 4. Range İçi İşlem ve İptal (Invalidation) Kuralları

### Kural 1: Deviation (Sapma) Limiti ve İptal
*   Fiyat RH'nin üstüne veya RL'nin altına sarktığında bu mesafe ölçülmelidir.
*   **Limit Formülü:** Maksimum Sapma = `(RH - EQ)` mesafesinin **%50'si**. (RL için de `(EQ - RL)` mesafesinin %50'si).
*   **Breakout (Trend Kırılımı) vs Deviation:** Eğer fiyat Range sınırları dışına çıkar, sapma limitini (%50) aşar ve Range dışında **net mum gövdesi kapanışı (Body Close)** yaparsa, Range modeli *iptal (invalid)* olur. Bu artık bir tuzak değil, **Breakout (Yeni Trend Başlangıcı)** olarak etiketlenir.

### Kural 2: Kapanış Anatomisi
*   Teyit mekanizmalarında (Breakout onayı veya CHoCH onayı) sadece fitil sarkması (Wick) yeterli değildir. Karar seviyelerinin üstünde/altında net **mum gövde kapanışı (Body Close)** aranmalıdır. Fitiller sadece likidite alımı (Sweep) olarak değerlendirilir.

### Kural 3: High-Timeframe (HTF) Bağlamı
*   Düşük zaman diliminde (LTF - örn: 15m, 1H) tespit edilen Range ve Deviation hareketleri, tek başına işleme giriş sebebi değildir.
*   Bu hareketlerin, Yüksek Zaman Dilimindeki (HTF - örn: 4H, 1D) bir **Supply/Demand (Arz/Talep) bölgesine, FVG'ye (Fair Value Gap) veya Ana Destek/Direnç** seviyesine temas etmesi/denk gelmesi zorunludur.

### Kural 4: Premium / Discount (Pahalılık/Ucuzluk) Prensibi
*   Geçerli Swing High ile Swing Low arasındaki mesafenin tam %50'si (EQ).
*   **Premium Bölgesi:** HTF bağlamında fiyat %50 (EQ) seviyesinin üstündeyse (Pahalı). Burada *Long işlem aranmaz*.
*   **Discount Bölgesi:** HTF bağlamında fiyat %50 (EQ) seviyesinin altındaysa (Ucuz). Market yapısı (Market Structure) bozulmadıkça *Short işlem aranmaz*.

## 5. Manipülasyon Analizi ve İşlem Tetikleyicileri (Triggers)

AI sistemleri, Market Maker (Piyasa Yapıcı) davranışlarını şu mantıkla koda dökmelidir:

### Adım 1: Likidite Mıknatısı (Liquidity Magnet) Tespiti
*   Alt bantta (RL) bir sapma (Deviation) gerçekleştiğinde, sistem üst bantta (RH) oluşan "düşen tepelerin" (Lower Highs) arkasında biriken **Açık Likiditeleri** hedef (Target) olarak belirlemelidir.
*   Mantık: Alt taraftaki perakende stopları patlatıldı (Deviation), şimdi fiyat üst taraftaki likiditeyi temizlemek üzere hızla (mermi gibi) yukarı yönelecektir.

### Adım 2: İçeri Dönüş ve Teyit (CHoCH)
*   Sapma (Deviation) hareketi sonrasında, fiyat tekrar Range içine (RL üstüne veya RH altına) dönmelidir.
*   **Teyit (CHoCH - Change of Character):** Fiyat Range içine döndükten sonra, sapmayı başlatan en son iç tepeyi (Demand/Supply noktasını) **gövde kapanışıyla (Body Close)** kırmalıdır. Bu CHoCH kırılımı, "manipülasyon bitti, asıl yön başladı" onayıdır.

### Adım 3: İşleme Giriş (Entry) Bölgesi
*   CHoCH kırılımı oluştuktan sonra, sistem kırılımın arkasında bıraktığı **yeni FVG (Fair Value Gap)** veya **Breaker Block** bölgesini "Entry Zone" (Giriş Bölgesi) olarak işaretlemelidir. 
*   Emirler bu bölgenin retest'ine (geri çekilmesine) kurgulanır.

## 6. Likidite Konseptleri ve İşleme Giriş (Entry) Modelleri

Sistem, likidite havuzlarını ve bu havuzların temizlenmesini iki ana konsept üzerinden denetler:

### EQL/EQH (Equal Lows / Equal Highs)
*   **Rolü:** Mıknatıs / Tuzak / Hedef Bölgesi.
*   **Karakteristiği:** Aynı veya çok yakın seviyede oluşan iki veya daha fazla dip/tepe.
*   **Algoritmik Önemi:** Buralar perakende trader'ların stoplarının biriktiği havuzlardır. Fiyat henüz burayı ihlal etmemiştir, dolayısıyla sistem buraları **Açık Likidite (Hedef)** olarak etiketler.

### SFP (Swing Failure Pattern - Salınım Başarısızlığı)
*   **Rolü:** Tetikleyici / Eylem / Manipülasyon.
*   **Karakteristiği:** Fiyatın EQL/EQH veya önemli bir HTF seviyesini ihlal etmesi, ancak ötesinde gövde kapatamayıp (Body Close yok) sadece uzun bir fitil (Wick) bırakarak geri dönmesi.
*   **Algoritmik Önemi:** Piyasa yapıcının likiditeyi süpürdüğü (Sweep) andır. Sistem bunu gördüğünde **"Dönüş Onayı Aranıyor" (Waiting for Reversal)** state'ine geçer.

### Manipülasyon Sonrası En Güvenli 3 İşleme Giriş (Entry) Modeli
Deviation (SFP) gerçekleştikten sonra körü körüne işleme girilmez. Sistem, fiyat Range içine döndüğünde aşağıdaki 3 yapıdan birini arar:

1.  **FVG EQ (%50 Orta Noktası):** Hızlı dönüşte oluşan dengesizliğin (Imbalance) tam orta noktası. En yüksek R/R (Risk/Ödül) sunan giriştir.
2.  **Breaker / S/R Flip:** Fiyatı tutan ama bam diye kırılan eski destek/direnç noktasının retest edilmesi.
3.  **Untested Order Block:** Hareketi başlatan ve likiditesi henüz harcanmamış taze arz/talep mumu.

**Girişleri Optimize Eden İki Altın Kural:**
1.  **LTF CHoCH Teyidi:** Fiyat yukarıdaki giriş bölgelerine geldiğinde direkt limit emir atılmaz. LTF'ye (örn. 15m/5m) inilerek ikincil bir kırılım/CHoCH beklenir.
2.  **Risk/Hedef (Stop & TP):** 
    *   *Stop:* SFP'yi (manipülasyonu) yapan en uç fitilin arkasına veya LTF CHoCH'u başlatan son dip/tepe arkasına konur.
    *   *Target (TP):* Range EQ çizgisi veya karşı tarafta biriken EQL/EQH likidite havuzlarıdır.

## 7. Supply & Demand (Arz ve Talep) Yapıları: RBR & DBD

Piyasa yapıcının trend yönündeki birikim ve devam formasyonlarını algoritmik olarak etiketlemek için aşağıdaki yapılar denetlenir:

### RBR (Rally - Base - Rally / Yükseliş - Taban - Yükseliş)
*   **Karakteristiği:** Fiyatın güçlü bir "Rally" (Yükseliş dalgası) yapıp kısa bir süre konsolide olması ("Base") ve ardından yeni bir "Rally" yapmasıdır.
*   **Algoritmik Önemi:** Ortada oluşan "Base" (Taban) alanı sistem tarafından bir **Demand (Talep)** bölgesi olarak etiketlenir. Fiyat buraya geri çekildiğinde, alıcıların tekrar devreye girmesi beklenir.

### DBD (Drop - Base - Drop / Düşüş - Taban - Düşüş)
*   **Karakteristiği:** Fiyatın sert "Drop" (Düşüş dalgası) sonrası yataya bağlaması ("Base") ve tekrar "Drop" yapmasıdır.
*   **Algoritmik Önemi:** Ortadaki "Base" alanı sistem tarafından bir **Supply (Arz)** bölgesi olarak etiketlenir. Direnç görevi görmesi hedeflenir.

### Kurumsal Giriş (Entry) Konsepti
*   **Kör Emir Yasağı (No Blind Limit Orders):** Fiyat RBR/DBD sonucu oluşan Base alanına ilk kez döndüğünde direkt işleme girilmez.
*   **Zorunlu Teyit (Confirmation):** Fiyatın bu Base alanına temasının ardından **alt zaman diliminde (LTF) Market Yapısı Kırılımı (CHoCH / MSB)** aranması zorunludur. İşlem algoritması sadece bu onay geldikten sonra oluşan yeni alandan pozisyona dahil olur.

## 8. Kurumsal Anahtar Seviyeler (Institutional Key Levels)

Kurumsal oyuncuların (büyük fonlar/bankalar) bıraktığı izleri ve fiyat dengelerini algoritmanın deterministik olarak okuması için aşağıdaki seviyeler ve kurallar kullanılır:

### Doğal Range: Pazartesi Aralığı (Monday High/Low - MH/ML)
*   **Mantık:** CME gibi vadeli piyasaların hafta sonu boşluğunu kapatmak ve fiyatı dengelemek için Pazartesi günü oluşturduğu salınım, haftanın geri kalanı için "Doğal Range" (Yatay Bant) kabul edilir.
    *   `Monday High (MH) = Range High (RH)`
    *   `Monday Low (ML) = Range Low (RL)`
*   **Manipülasyon Takibi:** Salı gününden itibaren fiyatın MH üzerine çıkıp veya ML altına inip geri dönmesi (Range Deviation kurallarındaki gibi) bir likidite süpürmesi (SFP) olarak değerlendirilir.

### Kurumsal Zaman Seviyeleri (Monthly/Weekly Open) ve Etkileri
*   **Aylık Açılış (MO) ve Haftalık Açılış (WO):** Kurumsal maliyetlenme ve denge noktalarıdır.
*   **Destek/Direnç Rolü:** Fiyat bu seviyelerin üzerindeyse destek, altındaysa direnç görevi görür.
*   **İşlem Teyidi (Confluence):** FVG, Breaker veya OB gibi bir giriş alanı bir MO veya WO seviyesiyle kesişiyorsa (overlaps), algoritma bu setup'ın güvenilirlik puanını (setup_score) artırır.
*   **Mıknatıs (Magnet) ve Kâr Alma (TP) Etkisi:** MO, WO ve test edilmemiş MH/ML seviyeleri piyasa yapıcı için mıknatıstır. Fiyat trendine veya sapma sonrasına girdiğinde algoritmik hedefler (TP1) olarak ilk buralar aranır.

## 9. Trend Takip Modeli: `BREAKOUT_TREND_FOLLOWING`

Range %50 sapma limiti (Deviation) aşıldığında ve dışarıda gövde kapanışı (Body Close) geldiğinde, Range iptal edilir ve sistem Trend Takip Moduna geçer. Algoritma 4 adımlı bir boru hattını (pipeline) çalıştırır:

### Adım A: BREAKOUT_DETECTION (Kararlı Kırılım)
*   Range ötesinde net bir mum gövde kapanışı doğrulanır. Hacimli ve kararlı bir kırılım ("bam diye") aranır.

### Adım B: FVG_IDENTIFICATION (Dengesizlik Tespiti)
*   Kırılımı gerçekleştiren seride 1. ve 3. mumlar arası Imbalance (FVG) tespit edilir. Hedef giriş seviyesi **FVG %50 (EQ)** veya **Breaker** seviyesi olarak işaretlenir.

### Adım C: RETEST_WAITING (Geri Çekilme Beklentisi)
*   Kırılım anında en uçtan girilmez (Market emri yasağı). Fiyatın tespit edilen FVG/Breaker alanına geri çekilmesi beklenir.

### Adım D: CONFIRMATION_CHECK (LTF Teyit ve Tetikleme)
*   Fiyat bölgeye temas ettiğinde doğrudan limit emirle girilmez (Kör emir yasağı). 
*   **LTF CHoCH:** Alt zaman diliminde (15m/5m) son iç swing noktasının gövdeyle kırılması beklenir.
*   Onay alındığında emir piyasaya iletilir (Execution).

### Risk ve Kâr Alma Yönetimi (Trade Management)
*   **Stop Loss (SL):** Kırılımı başlatan ana swing noktası ötesine veya LTF CHoCH'u oluşturan dönüş fitili arkasına yerleştirilir.
*   **Scale-Out (TP1):** Trend yönündeki ilk karşıt FVG %50 (EQ) seviyesine gelindiğinde pozisyonun **%80'i kapatılır** ve **Stop Loss girişe (Breakeven) çekilir.**
*   **Target (TP2):** Kalan %20'lik pozisyon trend yönündeki açık likidite havuzlarına (EQL/EQH) kadar taşınır.
*   **Invalidation (İptal):** Fiyat retest sırasında alanı delip, kırılımı başlatan swing noktasının ötesinde gövde kapatırsa kurgu iptal edilir (Zarar kes).

```python
# BREAKOUT TREND FOLLOWING STATE MACHINE
if state == "BREAKOUT_TREND_FOLLOWING":
    
    # Adım 1: Dengesizlik ve Breaker Tespiti
    fvg_zone = detect_breakout_fvg(candles)
    fvg_eq = (fvg_zone.top + fvg_zone.bottom) / 2
    breaker_level = get_broken_range_boundary()
    
    # Adım 2: Retest Tespiti
    if price.touches(fvg_eq) or price.touches(breaker_level):
        retest_active = True
        
    # Adım 3: LTF Teyit (Confirmation)
    if retest_active and ltf_scanner.detect_choch(body_close=True):
        entry_price = price.current
        stop_loss = ltf_scanner.get_invalidation_swing()
        tp1 = find_first_opposing_fvg_eq()
        tp2 = find_major_liquidity_pool()
        
        trigger_trade_signal(
            type="TREND_CONTINUATION",
            entry=entry_price,
            sl=stop_loss,
            tp1=tp1,
            tp2=tp2
        )
```

## 10. Trade Engine - Acceptance (Kabul) Katmanı Veri Mimarisi

Yukarıdaki konseptlerden süzülen bir fırsat, işleme girmeden önce **Acceptance Engine** tarafından 7 alt kuraldan geçirilerek `Risk Engine` katmanına aktarılır. Bu yapı deterministik motorun kalbidir.

### Master Acceptance Input Payload (Girdi JSON)
```json
{
  "trade_id": "TRD-20260912-001",
  "timestamp": 1726107600,
  "symbol": "BTC-USDT",
  "setup_direction": "LONG",
  "context_dealing_range": {
    "range_high": 61200.50,
    "range_low": 59800.00,
    "equilibrium": 60500.25
  },
  "acceptance_rules": {
    "rule_1_timeframe_alignment": { "is_valid": true },
    "rule_2_smtf_gap_acceptance": { "is_valid": true },
    "rule_3_prc_pcp_patterns": { "is_valid": true },
    "rule_4_live_wick_reject": { "is_valid": true },
    "rule_5_open_closed_divergence": { "is_valid": true },
    "rule_6_true_open_and_time_window": { "is_valid": true },
    "rule_7_ssmt_triad_check": { "is_valid": true }
  }
}
```

---
**Özet Geliştirici Notu:** 
Kodlama sırasında bir "RangeState" ve "MarketStructure" modülleri oluşturulmalı. 
- Fiyat verisi (Candles) akarken MS algoritması sürekli `ValidHigh` ve `ValidLow` seviyelerini N-Left/Right filtresi ve Body Close koşuluyla güncellemeli. Fitiller `LIQUIDITY_SWEEP` olarak işaretlenmeli.
- Range algoritması sırasıyla: 1. `SEARCHING_IMPULSE` -> 2. `FORMING_RANGE` -> 3. `RANGE_VALID` -> 4. `DETECTING_DEVIATION` -> 5. `WAITING_CHOCH` veya 6. `BREAKOUT_INVALIDATED` durumları arasında geçiş yapmalıdır.
- "Institutional Levels Engine" algoritması Pazartesi günleri RH ve RL'yi MH/ML olarak set etmeli, ve MO/WO kesişimlerine göre giriş puanını artırmalıdır.

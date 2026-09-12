# Bot Foundation Implementation Plan

**Goal:** Çalıştırılabilir, strateji uydurmayan replay ve kayıt altyapısı.
**Architecture:** Tek süreçte tipli modeller, değiştirilebilir dedektörler ve
ayrı karar/kabul/risk/yürütme sınırları.
**Tech Stack:** Python 3.11+, standart kütüphane, unittest.
**Spec:** ../../foundation.md

## Global Constraints

- Gerçek emir ve strateji kuralı eklenmez.
- Fiyatlarda Decimal, zamanlarda saat dilimli UTC kullanılır.
- Yapılandırma, strateji parametreleriyle karıştırılmaz.

## Task 1 — Sözleşmeler ve veri akışı

- [x] `tests/test_foundation.py` içine kapalı/geçerli mum, zaman sırası,
  geçmiş sızıntısı ve geçmiş üst sınırı testlerini yaz.
- [x] `py -m unittest discover -s tests -v` ile eksik paket hatasını doğrula.
- [x] `agent_trading/models.py`, `data.py`, `config.py` oluştur.
  `Candle.from_dict(row)` normalize eder; `read_candles(path)` iterator döner;
  `ReplayEngine.process(candle)` yalnız o ana kadar görülen geçmişi kullanır.

## Task 2 — Karar zinciri ve günlük

- [x] Aynı test dosyasında karar yok, yapılandırılmamış politikalar,
  dedektör hatası ve deterministik tekrar testlerini ekle.
- [x] `components.py`, `engine.py`, `journal.py` oluştur.
  `Detector.evaluate(tuple[Candle, ...]) -> PatternResult` sözleşmesini kullan.
  `ReplayEngine.process(candle) -> dict` kararı döndürür ve kaydeder.
  `JsonlJournal(path)` mevcut dosyaya yazmayı reddeder.

## Task 3 — Çalıştırma ve teslim

- [x] `__main__.py`, `config.example.json`, sentetik `examples/candles.jsonl`,
  `README.md`, `.gitignore`, `pyproject.toml` ekle.
- [x] CLI testinde replay sonucunu ve live modunun reddini doğrula.
- [x] `py -m unittest discover -s tests -v` çalıştır.
- [x] `py -m agent_trading --config config.example.json` çalıştır;
  3 mum, 3 NO_TRADE, sıfır emir çıktısını doğrula.

İş bu oturumda yürütülür; boş klasörde başka çalışma veya Git dalı yoktur.


# VPS'e kurulum (Docker Compose)

> **Durum:** `compose.yaml`, `deploy/Dockerfile` ve `deploy/Caddyfile` henüz gerçek
> bir VPS'te çalıştırılmadı (geliştirme makinesinde Docker yok). Kodun dayandığı
> varsayımlar kontrol edildi; ilk kurulum sahibiyle birlikte doğrulanacak.

## Ne çalışır

| Servis | Görev | Dışarı açık mı |
|---|---|---|
| `app` | FastAPI backend, BotService ve OKX Agent Trade Kit (Node alt süreci) | Hayır, sadece `web` erişir |
| `web` | Caddy: arayüzü sunar, `/api/*` ve `/health/*` isteklerini `app`'e iletir, Let's Encrypt ile HTTPS alır | 80 ve 443 |

Kalıcı veriler Docker volume'larında durur: `agent-config` (strateji ve tercih
ayarları), `agent-runs` (PAPER oturumu, analiz geçmişi), `caddy-data`
(sertifikalar). Güncelleme ve yeniden başlatmada silinmezler.

## Gerekenler

1. Ubuntu 22.04 veya 24.04 bir VPS, 80 ve 443 portları açık.
2. VPS'in IP'sini gösteren bir alan adı (A kaydı), örneğin `bot.ornek.com`.
   Ücretsiz seçenek: DuckDNS alt alan adı. Telegram Mini App HTTPS ister, bu yüzden
   alan adı şart.
3. VPS'ten OKX TR'ye erişim. Önce bunu dene; 200 görmelisin:

   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" "https://tr.okx.com/api/v5/market/ticker?instId=BTC-USDT"
   ```

   Geliştirme bilgisayarının ağında bu bağlantı zaman zaman TLS aşamasında
   kesildi (örneğin 19 Eylül 2026); VPS'in ağında çalıştığından emin ol.

## Kurulum

1. Docker Engine ve Compose eklentisini resmi talimatla kur:
   <https://docs.docker.com/engine/install/ubuntu/>
2. Kodu VPS'e al. Repo **private** olduğu için VPS'e sadece okuma yetkili bir
   deploy key gerekir:

   ```bash
   ssh-keygen -t ed25519 -C "agent-trading-vps" -f ~/.ssh/agent_trading_deploy -N ""
   cat ~/.ssh/agent_trading_deploy.pub
   ```

   Çıkan satırı GitHub'da repo → **Settings → Deploy keys → Add deploy key**
   bölümüne yapıştır; **Allow write access** kutusunu işaretleme. Sonra:

   ```bash
   GIT_SSH_COMMAND="ssh -i ~/.ssh/agent_trading_deploy -o IdentitiesOnly=yes" \
     git clone git@github.com:WalAngeL06/agent-trading-copilot.git agent-trading
   cd agent-trading
   git config core.sshCommand "ssh -i ~/.ssh/agent_trading_deploy -o IdentitiesOnly=yes"
   ```

   Son satır, güncellemelerde `git pull` komutunun aynı anahtarı kullanmasını
   sağlar. Varsayılan dal `main`.
3. `.env` oluştur: `cp .env.example .env` ve doldur:
   - `DOMAIN=bot.ornek.com`
   - `API_ACCESS_TOKEN=` en az 24 karakterlik rastgele anahtar:
     `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Telegram: `TELEGRAM_BOT_TOKEN=` ve `TELEGRAM_ALLOWED_USER_IDS=`. Telegram
     kullanıyorsan izin listesi üretimde zorunlu: boş kalırsa bot, kendisine
     yazan herkese `/status` cevabı ve bildirim gönderir. Kendi ID'ni bota
     `/start` yazarak öğrenirsin.
   - İsteğe bağlı hesap okuması: `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE`.
     Sadece **okuma** izni ver; OKX'te anahtarı VPS'in IP'siyle sınırla.
   - `WEBAPP_URL`, `ALLOWED_ORIGINS` ve `VITE_BACKEND_URL` compose tarafından
     `DOMAIN`'den üretilir; `.env`'de boş kalabilir.
4. Başlat:

   ```bash
   docker compose up -d --build
   ```

5. Kontrol et:

   ```bash
   docker compose ps
   docker compose logs -f app
   curl https://bot.ornek.com/health/live
   ```

   Son komut `{"status":"ALIVE"}` döndürmeli. Backend açılışta hata verip
   yeniden başlıyorsa en sık sebep: `DOMAIN` herkese açık olduğu hâlde
   `API_ACCESS_TOKEN` veya `TELEGRAM_ALLOWED_USER_IDS` boş. Bu durumda backend
   korumasız başlamayı bilerek reddeder.
6. Tarayıcıda `https://bot.ornek.com` adresini aç, erişim anahtarını gir,
   **Start Agent**'a bas. Telegram'da bota `/start` yazıp **Open Dashboard**'a dokun.

## Çalışma davranışı

- OKX bağlantısı koparsa ajan durmaz: `RECONNECTING` gösterir ve 5 sn'den 5 dk'ya
  kadar artan aralıklarla yeniden bağlanır.
- PAPER oturumu her yeni mumda diske kaydedilir. Backend yeniden başlarsa,
  ajan önceden çalışıyorsa kendiliğinden başlar ve oturuma kaldığı yerden devam
  eder. Stop ile durdurulmuş ajan durmuş kalır.
- Strateji ayarları değişirse ya da kayıt OKX'in hâlâ sunduğu geçmişten eskiyse
  temiz bir oturum başlar ve etkinlik listesinde uyarı görünür.

## Çoklu parite verisi ve tarama

Strateji araştırması için OKX TR'nin 24 saatlik hacme göre en likit 30 USDT
paritesinin geçmişi VPS'te indirilir [U-MULTI-PAIR-001]; geliştirme
bilgisayarından OKX'e erişilemediği için bu adım burada yapılır. Yalnızca genel
piyasa okuması kullanılır, API anahtarı gerekmez. İlk gerçek koşu 21 Eylül
2026'da bu adımlarla yapıldı: 30 paritenin 30'u tamamlandı, boşluk çıkmadı,
indirme 18 dakika sürdü.

- `.env` içinde `DOMAIN` tanımlı olmalı: `docker compose run` bütün
  `compose.yaml`'ı okur. Uygulama henüz yayına alınmadıysa geçici bir değer
  yeterli: `printf 'DOMAIN=pending.invalid\n' > .env`.
- Komutlar konteynerin kendi Python'uyla çalışır: `/opt/venv/bin/python`
  (sistem Python'unda `mcp` paketi yok).
- Veri, proje klasörünün içindeki `data/`'ya yazılır; git bu klasörü yok sayar.
  Konteyner 10001 numaralı kullanıcıyla çalıştığı için klasör bir kez ona
  verilir. Aşağıdaki komutlar proje klasörünün içinden çalıştırılır:

  ```bash
  mkdir -p data && chown 10001:10001 data
  ```

1. Kısa gerçek deneme (ilk seferde imaj derlendiği için ~2 dakika):

   ```bash
   docker compose run --rm -v "$PWD/data:/app/data" app /opt/venv/bin/python -m agent_trading.backtest.fetch --symbols BTC-USDT --limits 4H=600,1H=600,15m=600 --out /app/data/smoke
   ```

   Beklenen: `BTC-USDT: COMPLETE 4H=600 1H=600 15m=600`.

2. Parite listesini seç ve durup gözden geçir; listeyi birlikte kontrol ederiz:

   ```bash
   docker compose run --rm -v "$PWD/data:/app/data" app /opt/venv/bin/python -m agent_trading.backtest.fetch --universe --quote USDT --top 30 --universe-only --out /app/data/okx_tr_usdt_top30
   ```

3. Tam indirme, aynı klasöre. 21 Eylül'de 18 dakika sürdü; bağlantı kopsa da
   devam etsin diye `tmux` içinde çalıştır:

   ```bash
   docker compose run --rm -v "$PWD/data:/app/data" app /opt/venv/bin/python -m agent_trading.backtest.fetch --universe --quote USDT --top 30 --limits 4H=10000,1H=10000,15m=36000 --pace 0.2 --timeout 60 --out /app/data/okx_tr_usdt_top30
   ```

   Çıkış kodu 1: bazı pariteler indirilemedi. Aynı komutu sonuna `--resume`
   ekleyerek yeniden çalıştır; tamamlananlar atlanır, liste ve bitiş anı aynı
   kalır. Çıkış kodu 2: koşu durdu (örneğin art arda üç parite başarısız oldu,
   yani OKX'e ulaşılamıyor); sebep ekranda ve `fetch_manifest.json`'da yazar.
   Kısa geçmişli pariteler (manifestte `exhausted`) OKX TR'deki listelenme
   tarihinde başlar; bu bir hata değildir.

4. Veriyi arşivle (278 MB veri, ~33 MB arşiv) ve bilgisayara al:

   ```bash
   tar czf /root/okx_tr_usdt_top30.tgz -C data okx_tr_usdt_top30
   ```

   Geliştirme bilgisayarında (PowerShell):

   ```bash
   scp root@<sunucu-ip>:/root/okx_tr_usdt_top30.tgz "C:\Users\Serdar Arif\Desktop\Agent Trading\data\okx_tr_usdt_top30.tgz"
   ```

   Arşiv gitignored `data/` altında açılır ve tarama orada çalışır
   (30 paritede ~10 dk):

   ```bash
   tar xzf data/okx_tr_usdt_top30.tgz -C data
   ```

   ```bash
   python -m agent_trading.backtest.sweep --data data/okx_tr_usdt_top30 --output runs/sweep-okx-tr
   ```

## Güncelleme

```bash
git pull
docker compose up -d --build
```

## Yedek ve sıfırlama

- Yedek: `docker run --rm -v agent-trading_agent-runs:/data -v "$PWD":/backup busybox tar czf /backup/agent-runs.tgz -C /data .`
  (volume adı proje klasörünün adıyla başlar; `docker volume ls` ile kontrol et).
- PAPER oturumunu sıfırlamak: ajanı durdur, strateji ayarlarından birini değiştirip
  kaydet (yeni ayarla temiz oturum başlar) ya da `agent-runs` içindeki
  `product/paper_session.pickle` dosyasını sil.

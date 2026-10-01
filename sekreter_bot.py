"""
Halil Utku Çiçek — Kişisel Yapay Zeka Sekreteri (Telegram Bot)
=============================================================
Bu bot, Telegram üzerinden gelen mesajları karşılar, yapay zeka ile
nazik ve profesyonel yanıtlar verir, gelen notları ve mesajları anında
Halil Utku'nun (Admin) şahsi Telegram'ına bildirim olarak iletir.

Bağımlılık: Sadece standart 'requests' kütüphanesi (ekstra kurulum gerektirmez).
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
import requests

# Windows console UTF-8 desteği
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── LOGGING AYARLARI ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("sekreter_bot")

# ── DİZİN VE KONFİGÜRASYON ──
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
MASTER_ENV_PATH = REPO_ROOT / "_knowledge" / "credentials" / "master.env"
HAFIZA_FILE = CURRENT_DIR / "hafiza.json"


def load_env():
    """master.env dosyasından anahtarları yükler."""
    env = {}
    if MASTER_ENV_PATH.exists():
        for line in MASTER_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and not v.startswith("<"):
                    env[k] = v
    # Sistem ortam değişkenleri önceliklidir
    for k, v in os.environ.items():
        if v:
            env[k] = v
    return env


ENV = load_env()
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(ENV.get("ADMIN_CHAT_ID", 8110234518))
OPENAI_API_KEY = ENV.get("OPENAI_API_KEY")

if not BOT_TOKEN:
    log.error("TELEGRAM_BOT_TOKEN bulunamadı! master.env dosyasını kontrol edin.")
    sys.exit(1)

if not OPENAI_API_KEY:
    log.error("OPENAI_API_KEY bulunamadı! master.env dosyasını kontrol edin.")
    sys.exit(1)

TG_BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── SİSTEM PROMPTU (KİŞİSEL SEKRETER PERSONASI) ──
SYSTEM_PROMPT = """Sen Halil Utku Çiçek'in yapay zeka kişisel sekreterisin.
Adın: Utku Asistan.

Kişilik ve İletişim Tarzı:
- Son derece kibar, samimi, profesyonel ve saygılı bir Türkçeyle konuşursun.
- Halil Utku Çiçek; yazılım geliştirme, yapay zeka otomasyonları ve dijital sistemler alanında çalışan bir uzmandır.
- Utku Bey şu anda yoğun bir çalışma/toplantı sürecinde olduğu için mesajları doğrudan sen karşılıyorsun.

Temel Görevlerin:
1. Gelen kişiyi sıcak bir şekilde karşıla.
2. Ne konuda iletişime geçtiğini nazikçe öğren (iş birliği, proje, teklif, danışmanlık ya da kişisel bir konu mu?).
3. Kendisinden adını, mesajını ve gerekiyorsa Utku Bey'in geri dönebilmesi için iletişim bilgisini (e-posta veya telefon) rica et.
4. "Mesajınızı ve notunuzu hemen Utku Bey'e iletiyorum, kendisi en kısa sürede sizinle iletişime geçecektir." diyerek güven ver.
5. Cevapların kısa, şık ve net olsun; gereksiz uzun paragraflar yazma.
6. Eğer mesajı atan kişi doğrudan Halil Utku ise (Admin), ona "Hoş geldiniz Utku Bey!" diyerek yardım etmeye hazır olduğunu belirt.
"""


def load_memory() -> dict:
    """Kullanıcı sohbet geçmişini dosyadan okur."""
    if HAFIZA_FILE.exists():
        try:
            return json.loads(HAFIZA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Hafıza okuma hatası: {e}")
    return {}


def save_memory(memory: dict):
    """Kullanıcı sohbet geçmişini dosyaya yazar."""
    try:
        HAFIZA_FILE.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning(f"Hafıza kaydetme hatası: {e}")


def get_ai_reply(chat_id: int, user_message: str, user_name: str, is_admin: bool) -> str:
    """OpenAI GPT-4o-mini kullanarak akıllı sekreter yanıtı üretir."""
    memory = load_memory()
    history = memory.get(str(chat_id), [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Son 6 mesajlık konuşma geçmişini ekle
    for item in history[-6:]:
        messages.append(item)

    # Yeni mesajı ekle
    context_prefix = f"[Kullanıcı: {user_name} | Admin mi: {is_admin}]: "
    messages.append({"role": "user", "content": context_prefix + user_message})

    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 300
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip()

        # Geçmişe kaydet
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        memory[str(chat_id)] = history[-10:]  # son 10 mesajı sakla
        save_memory(memory)

        return reply
    except Exception as e:
        log.error(f"OpenAI API Hatası: {e}")
        return "Merhaba! Utku Bey şu anda müsait değil. Mesajınızı aldım ve kendisine iletiyorum. En kısa sürede dönüş yapacaktır."


def send_telegram_message(chat_id: int, text: str, parse_mode: str = None) -> bool:
    """Telegram üzerinden mesaj gönderir."""
    url = f"{TG_BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        log.error(f"Telegram mesaj gönderme hatası (chat_id: {chat_id}): {e}")
        return False


def notify_admin(sender_info: dict, user_msg: str, bot_reply: str):
    """Gelen mesajı ve sekreterin yanıtını anında Halil Utku'ya (Admin) bildirir."""
    first_name = sender_info.get("first_name", "")
    last_name = sender_info.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or "Bilinmeyen"
    username = sender_info.get("username")
    user_tag = f"@{username}" if username else "Kullanıcı adı yok"
    user_id = sender_info.get("id")

    notification = (
        f"🔔 *YENİ MESAJ (Sekreter Bildirimi)*\n\n"
        f"👤 *Gönderen:* {full_name} ({user_tag})\n"
        f"🆔 *User ID:* `{user_id}`\n\n"
        f"💬 *Gelen Mesaj:*\n_{user_msg}_\n\n"
        f"🤖 *Sekreterin Yanıtı:*\n{bot_reply}"
    )
    send_telegram_message(ADMIN_CHAT_ID, notification, parse_mode="Markdown")


def run_bot():
    """Long polling döngüsü ile botu çalıştırır."""
    log.info("=" * 50)
    log.info("== Halil Utku Cicek Kisisel Sekreter Botu Baslatildi ==")
    log.info(f"[*] Admin Chat ID: {ADMIN_CHAT_ID}")
    log.info("=" * 50)

    # Başlangıçta admin'e küçük bir bilgilendirme gönder
    send_telegram_message(
        ADMIN_CHAT_ID,
        "👋 *Kişisel Sekreter Modu Aktif!*\n\n"
        "Biri bana mesaj yazdığında onu karşılayıp mesajını size anında bildireceğim.",
        parse_mode="Markdown"
    )

    offset = None

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(f"{TG_BASE_URL}/getUpdates", params=params, timeout=40)
            if resp.status_code != 200:
                log.warning(f"Telegram getUpdates hatası: {resp.status_code} {resp.text}")
                time.sleep(3)
                continue

            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1

                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue

                chat_id = msg["chat"]["id"]
                sender = msg.get("from", {})
                user_msg = msg["text"].strip()
                sender_name = sender.get("first_name", "Kullanıcı")
                is_admin = (sender.get("id") == ADMIN_CHAT_ID)

                log.info(f"==> Yeni Mesaj: [{sender_name} | {chat_id}]: {user_msg}")

                # AI Sekreter yanıtını oluştur
                bot_reply = get_ai_reply(chat_id, user_msg, sender_name, is_admin)

                # Kullanıcıya yanıt gönder
                send_telegram_message(chat_id, bot_reply)
                log.info(f"<== Sekreter Yaniti: {bot_reply[:80]}...")

                # Eğer yazan kişi admin değilse, admin'e haber ver!
                if not is_admin:
                    notify_admin(sender, user_msg, bot_reply)
                    log.info(f"[*] Admin'e bildirim iletildi (ID: {ADMIN_CHAT_ID})")

        except requests.exceptions.RequestException as e:
            log.warning(f"Ağ bağlantısı uyarısı: {e}. 3 saniye sonra tekrar deneniyor...")
            time.sleep(3)
        except Exception as e:
            log.error(f"Beklenmeyen döngü hatası: {e}", exc_info=True)
            time.sleep(3)


if __name__ == "__main__":
    run_bot()

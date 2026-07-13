import json
import os
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

CONFIG_PATH = Path(__file__).parent / "config.json"
CACHE_PATH = Path(__file__).parent / ".notified_cache"


def load_config():
    cfg_path = CONFIG_PATH
    if "GITHUB_ACTIONS" in os.environ:
        cfg_path = Path("config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)

    env_overrides = {
        ("notifications", "twilio", "enabled"): "TWILIO_ENABLED",
        ("notifications", "twilio", "account_sid"): "TWILIO_ACCOUNT_SID",
        ("notifications", "twilio", "auth_token"): "TWILIO_AUTH_TOKEN",
        ("notifications", "email", "enabled"): "EMAIL_ENABLED",
        ("notifications", "email", "sender_email"): "EMAIL_SENDER",
        ("notifications", "email", "sender_password"): "EMAIL_PASSWORD",
    }
    for keys, env_var in env_overrides.items():
        val = os.environ.get(env_var)
        if val is not None:
            d = cfg
            for k in keys[:-1]:
                d = d[k]
            if env_var.endswith("_ENABLED"):
                val = val.lower() == "true"
            elif env_var.endswith("_PORT"):
                val = int(val)
            d[keys[-1]] = val

    return cfg


def check_stock(url, headers):
    scraper = cloudscraper.create_scraper()
    resp = scraper.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True).lower()

    out_signals = ["notify me", "out of stock", "sold out", "temporarily unavailable"]
    in_signals = ["add to cart", "buy now"]

    if any(s in page_text for s in out_signals):
        return False
    if any(s in page_text for s in in_signals):
        return True
    return None


def send_sms_via_twilio(config, message):
    tw = config["notifications"].get("twilio", {})
    if not tw.get("enabled"):
        return False
    try:
        from twilio.rest import Client
        client = Client(tw["account_sid"], tw["auth_token"])
        client.messages.create(
            body=message,
            from_=tw["from_number"],
            to=tw["to_number"]
        )
        return True
    except Exception as e:
        print(f"[!] Twilio SMS failed: {e}")
        return False


def send_email(config, subject, body):
    email_cfg = config["notifications"].get("email", {})
    if not email_cfg.get("enabled") or not email_cfg.get("sender_email"):
        return False
    msg = MIMEMultipart()
    msg["From"] = email_cfg["sender_email"]
    msg["To"] = email_cfg["recipient_email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"])
        server.starttls()
        server.login(email_cfg["sender_email"], email_cfg["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[!] Email failed: {e}")
        return False


def notify(config, product_url):
    msg = f"Flipkart Stock Alert!\nPS5 is back in stock!\n{product_url}"
    print(f"[!] {msg}")
    send_sms_via_twilio(config, msg)
    send_email(config, "Flipkart Stock Alert!", msg)


def has_notified():
    if "GITHUB_ACTIONS" in os.environ:
        return Path("/tmp/ps5_notified").exists()
    return CACHE_PATH.exists()


def mark_notified():
    if "GITHUB_ACTIONS" in os.environ:
        Path("/tmp/ps5_notified").touch()
    else:
        CACHE_PATH.touch()


def clear_notified():
    if "GITHUB_ACTIONS" in os.environ:
        Path("/tmp/ps5_notified").unlink(missing_ok=True)
    else:
        CACHE_PATH.unlink(missing_ok=True)


def run_once(config):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.5",
    }
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    in_stock = check_stock(config["product_url"], headers)

    if in_stock is True:
        print(f"[{now}] IN STOCK")
        if not has_notified():
            notify(config, config["product_url"])
            mark_notified()
    elif in_stock is False:
        print(f"[{now}] Out of stock")
        clear_notified()
    else:
        print(f"[{now}] Could not determine stock status")

    return in_stock


def main():
    config = load_config()
    interval = config["check_interval_seconds"]
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Starting Flipkart stock monitor")
    print(f"[+] Checking every {interval}s\n")
    while True:
        try:
            run_once(config)
        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        config = load_config()
        run_once(config)
    else:
        main()

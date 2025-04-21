import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


def send_telegram_image(image_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as image:
        files = {"photo": image}
        payload = {"chat_id": TELEGRAM_CHAT_ID}
        requests.post(url, data=payload, files=files)


# --- CHROME SETUP ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# --- SCRAPING ---
url = "https://xrpscan.com/balances"
driver.get(url)
wait = WebDriverWait(driver, 3)

data = []
while True:
    try:
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//tr[@role='row']")))
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 6:
                try:
                    rank = cells[0].text.strip()
                    try:
                        wallet = cells[1].find_element(By.TAG_NAME, "a").text.strip()
                    except:
                        wallet = cells[1].text.strip()

                    owner = cells[3].text.strip()

                    try:
                        balance = cells[4].find_element(By.CLASS_NAME, "money").find_element(By.TAG_NAME, "span").text.strip().replace(",", "")
                    except:
                        balance = "0"

                    try:
                        xrp_locked = cells[5].find_element(By.CLASS_NAME, "money").find_element(By.TAG_NAME, "span").text.strip().replace(",", "")
                    except:
                        xrp_locked = "0"

                    data.append([rank, wallet, owner, balance, xrp_locked])
                except Exception as e:
                    print("Error extrayendo fila:", e)

        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'ml-1 mr-1 btn btn-outline-info')]")
        if next_buttons and next_buttons[-1].is_enabled():
            next_buttons[-1].click()
            time.sleep(3)
        else:
            break
    except Exception:
        break

driver.quit()

# --- CREACIÓN DE DATAFRAME ---
df = pd.DataFrame(data, columns=["Rank", "Wallet", "Owner", "Balance", "XRP Locked"])


def to_bigint(value):
    try:
        value = str(value).replace(",", "").replace(" XRP", "").strip()
        return int(value) if value.replace(".", "").isdigit() else 0
    except:
        return 0


df["Balance"] = df["Balance"].apply(to_bigint)
df["XRP Locked"] = df["XRP Locked"].apply(to_bigint)
df["Total Balance"] = df["Balance"] + df["XRP Locked"]

csv_filename = "xrp2025.csv"
df.to_csv(csv_filename, index=False)

# --- MÉTRICAS ---
total_locked = df["XRP Locked"].sum()
total_circulante = df["Balance"].sum()
total_supply = 100_000_000_000  # Fijo

pct_top10 = df.head(10)["Total Balance"].sum() / total_supply * 100
pct_top100 = df.head(100)["Total Balance"].sum() / total_supply * 100
pct_top1000 = df.head(1000)["Total Balance"].sum() / total_supply * 100
pct_top10000 = df.head(10000)["Total Balance"].sum() / total_supply * 100

# --- HISTÓRICO MÉTRICAS ---
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
metric_file = "metricas_xrp.csv"
new_metric = {
    "Timestamp": timestamp,
    "Top10Pct": round(pct_top10, 2),
    "Top100Pct": round(pct_top100, 2),
    "Top1000Pct": round(pct_top1000, 2),
    "Top10000Pct": round(pct_top10000, 2)
}

if os.path.exists(metric_file):
    metric_df = pd.read_csv(metric_file)
else:
    metric_df = pd.DataFrame(columns=new_metric.keys())

metric_df = pd.concat([metric_df, pd.DataFrame([new_metric])], ignore_index=True)
metric_df.to_csv(metric_file, index=False)

# --- GRAFICO DE MÉTRICAS ---
plt.figure(figsize=(12, 6))
plt.plot(metric_df["Timestamp"], metric_df["Top10Pct"], label="Top 10%")
plt.plot(metric_df["Timestamp"], metric_df["Top100Pct"], label="Top 100%")
plt.plot(metric_df["Timestamp"], metric_df["Top1000Pct"], label="Top 1.000%")
plt.plot(metric_df["Timestamp"], metric_df["Top10000Pct"], label="Top 10.000%")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.xlabel("Fecha")
plt.ylabel("% de Supply")
plt.title("Distribución XRP por Ballenas")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("grafico_metricas_xrp.png")
plt.close()

# --- MENSAJE TELEGRAM ---
summary_message = (
    f"🧠 *XRP Smart Report*\n"
    f"🕓 {timestamp}\n"
    f"🔒 *Bloqueado:* {total_locked:,} XRP\n"
    f"📤 *En circulación:* {total_circulante:,} XRP\n"
    f"🐋 *% en Top 10:* {pct_top10:.2f}%\n"
    f"💯 *% en Top 100:* {pct_top100:.2f}%\n"
    f"🔢 *% en Top 1.000:* {pct_top1000:.2f}%\n"
    f"🔟K *% en Top 10.000:* {pct_top10000:.2f}%"
)

send_telegram_message(summary_message)
send_telegram_image("grafico_metricas_xrp.png")

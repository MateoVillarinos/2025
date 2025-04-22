import os
import io
import time
import glob
import json
import base64
import re
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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- CONFIGURACIÓN ---
FOLDER_ID = "100_a_f6OG3h-3FfA7y3mvg3td3aMUiMn"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GDRIVE_CREDENTIALS = os.getenv("GDRIVE_CREDENTIALS")

# --- FUNCIONES DE TELEGRAM ---
def escape_md(text):
    return re.sub(r'([_\*\[\]()~`>#+=|{}.!-])', r'\\\1', str(text))

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": escape_md(message),
        "parse_mode": "MarkdownV2"
    }
    requests.post(url, json=payload)

def send_telegram_image(image_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as image:
        files = {"photo": image}
        payload = {"chat_id": TELEGRAM_CHAT_ID}
        requests.post(url, data=payload, files=files)

# --- AUTENTICACIÓN GOOGLE DRIVE ---
creds_json = json.loads(GDRIVE_CREDENTIALS)
creds = service_account.Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build("drive", "v3", credentials=creds)

def upload_to_drive(filename, mimetype):
    file_metadata = {"name": filename, "parents": [FOLDER_ID]}
    media = MediaIoBaseUpload(open(filename, "rb"), mimetype=mimetype)
    drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

def list_drive_csv_files():
    results = drive_service.files().list(q=f"'{FOLDER_ID}' in parents and name contains 'metricas_xrp_' and mimeType='text/csv'", fields="files(id, name)").execute()
    return results.get("files", [])

def download_csv_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh)

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

# --- MÉTRICAS ---
total_locked = df["XRP Locked"].sum()
total_circulante = df["Balance"].sum()
total_supply = 100_000_000_000

pct_top10 = df.head(10)["Total Balance"].sum() / total_supply * 100
pct_top100 = df.head(100)["Total Balance"].sum() / total_supply * 100
pct_top1000 = df.head(1000)["Total Balance"].sum() / total_supply * 100
pct_top10000 = df.head(10000)["Total Balance"].sum() / total_supply * 100

# --- GUARDAR Y SUBIR A DRIVE ---
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
metric_filename = f"metricas_xrp_{timestamp}.csv"
df_filename = f"xrp2025_{timestamp}.csv"
graph_filename = f"grafico_metricas_xrp_{timestamp}.png"

# Guardar local
new_metric = pd.DataFrame([{
    "Timestamp": timestamp,
    "Top10Pct": round(pct_top10, 2),
    "Top100Pct": round(pct_top100, 2),
    "Top1000Pct": round(pct_top1000, 2),
    "Top10000Pct": round(pct_top10000, 2)
}])

new_metric.to_csv(metric_filename, index=False)
df.to_csv(df_filename, index=False)

# Subir a Drive
upload_to_drive(metric_filename, "text/csv")
upload_to_drive(df_filename, "text/csv")

# --- DESCARGAR HISTÓRICO DESDE DRIVE ---
all_files = list_drive_csv_files()
all_dfs = [download_csv_from_drive(f["id"]) for f in all_files]
all_metrics = pd.concat(all_dfs, ignore_index=True).sort_values("Timestamp")

# --- GRAFICO DE LÍNEAS HISTÓRICO ---
plt.figure(figsize=(12, 6))
plt.plot(all_metrics["Timestamp"], all_metrics["Top10Pct"], label="Top 10%")
plt.plot(all_metrics["Timestamp"], all_metrics["Top100Pct"], label="Top 100%")
plt.plot(all_metrics["Timestamp"], all_metrics["Top1000Pct"], label="Top 1.000%")
plt.plot(all_metrics["Timestamp"], all_metrics["Top10000Pct"], label="Top 10.000%")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.xlabel("Fecha")
plt.ylabel("% de Supply")
plt.title("Evolución de concentración XRP")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(graph_filename)
plt.close()

upload_to_drive(graph_filename, "image/png")

# --- TELEGRAM ---
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
send_telegram_image(graph_filename)
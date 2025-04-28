import os
import io
import time
import json
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
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escape_md(message), "parse_mode": "MarkdownV2"}
    requests.post(url, json=payload)

def send_telegram_image(image_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as image:
        files = {"photo": image}
        payload = {"chat_id": TELEGRAM_CHAT_ID}
        requests.post(url, data=payload, files=files)

def send_telegram_document(file_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as file:
        files = {"document": file}
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

def get_last_metric_file():
    files = list_drive_csv_files()
    if not files:
        return None, None
    sorted_files = sorted(files, key=lambda x: x["name"], reverse=True)
    last_file = sorted_files[0]
    last_df = download_csv_from_drive(last_file["id"])
    return last_file["name"], last_df

def metrics_are_different(new_metrics, last_metrics):
    if last_metrics is None:
        return True
    last_row = last_metrics.iloc[-1]
    return not (
        new_metrics["Top10Pct"].iloc[0] == last_row["Top10Pct"] and
        new_metrics["Top100Pct"].iloc[0] == last_row["Top100Pct"] and
        new_metrics["Top1000Pct"].iloc[0] == last_row["Top1000Pct"] and
        new_metrics["Top10000Pct"].iloc[0] == last_row["Top10000Pct"]
    )

def get_last_balance_file():
    results = drive_service.files().list(q=f"'{FOLDER_ID}' in parents and name contains 'xrp2025_' and mimeType='text/csv'", fields="files(id, name)").execute()
    files = results.get("files", [])
    if not files:
        return None, None
    sorted_files = sorted(files, key=lambda x: x["name"], reverse=True)
    last_file = sorted_files[0]
    last_df = download_csv_from_drive(last_file["id"])
    return last_file["name"], last_df

def compare_wallets(df_new, df_old):
    df_old = df_old[["Wallet", "Owner", "Total Balance"]].rename(columns={"Total Balance": "Old Balance"})
    df_new = df_new[["Wallet", "Owner", "Total Balance"]].rename(columns={"Total Balance": "New Balance"})
    merged = pd.merge(df_old, df_new, on="Wallet", how="outer", suffixes=("_old", "_new"))
    merged["Balance Change"] = merged["New Balance"].fillna(0) - merged["Old Balance"].fillna(0)
    changes = merged[merged["Balance Change"] != 0].copy()
    changes["Owner"] = changes["Owner_old"].combine_first(changes["Owner_new"])
    return changes[["Wallet", "Owner", "Old Balance", "New Balance", "Balance Change"]].sort_values("Balance Change", ascending=False)

# --- SCRAPING ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

driver.get("https://xrpscan.com/balances")
wait = WebDriverWait(driver, 3)

data = []
while True:
    try:
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//tr[@role='row']")))
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 6:
                rank = cells[0].text.strip()
                wallet = cells[1].text.strip() if not cells[1].find_elements(By.TAG_NAME, "a") else cells[1].find_element(By.TAG_NAME, "a").text.strip()
                owner = cells[3].text.strip()
                balance = cells[4].text.strip().replace(",", "") if cells[4].find_elements(By.CLASS_NAME, "money") else "0"
                xrp_locked = cells[5].text.strip().replace(",", "") if cells[5].find_elements(By.CLASS_NAME, "money") else "0"
                data.append([rank, wallet, owner, balance, xrp_locked])

        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'ml-1 mr-1 btn btn-outline-info')]")
        if next_buttons and next_buttons[-1].is_enabled():
            next_buttons[-1].click()
            time.sleep(3)
        else:
            break
    except Exception:
        break

driver.quit()

# --- PROCESAMIENTO DE DATOS ---
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

total_locked = df["XRP Locked"].sum()
total_circulante = df["Balance"].sum()
total_supply = 100_000_000_000

pct_top10 = df.head(10)["Total Balance"].sum() / total_supply * 100
pct_top100 = df.head(100)["Total Balance"].sum() / total_supply * 100
pct_top1000 = df.head(1000)["Total Balance"].sum() / total_supply * 100
pct_top10000 = df.head(10000)["Total Balance"].sum() / total_supply * 100

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
metric_filename = f"metricas_xrp_{timestamp}.csv"
df_filename = f"xrp2025_{timestamp}.csv"

new_metric = pd.DataFrame([{
    "Timestamp": timestamp,
    "Top10Pct": round(pct_top10, 2),
    "Top100Pct": round(pct_top100, 2),
    "Top1000Pct": round(pct_top1000, 2),
    "Top10000Pct": round(pct_top10000, 2)
}])

last_file_name, last_metrics_df = get_last_metric_file()
if not metrics_are_different(new_metric, last_metrics_df):
    print("No hay cambios detectados en métricas. No se guarda ni envía nada.")
    exit(0)

new_metric.to_csv(metric_filename, index=False)
df.to_csv(df_filename, index=False)

upload_to_drive(metric_filename, "text/csv")
upload_to_drive(df_filename, "text/csv")

last_df_filename, last_df = get_last_balance_file()
cambios_texto = ""
if last_df is not None:
    changes_df = compare_wallets(df, last_df)
    if not changes_df.empty:
        cambios_filename = f"cambios_balances_{timestamp}.csv"
        changes_df.to_csv(cambios_filename, index=False)
        upload_to_drive(cambios_filename, "text/csv")
        send_telegram_document(cambios_filename)
        for _, row in changes_df.iterrows():
            direccion = row['Wallet']
            nombre = row['Owner'] if pd.notnull(row['Owner']) else "-"
            cambio = row['Balance Change']
            simbolo = "🔼" if cambio > 0 else "🔽"
            cambios_texto += f"{simbolo} `{direccion}` ({nombre}): {cambio:,.0f} XRP\n"

all_files = list_drive_csv_files()
all_dfs = [download_csv_from_drive(f["id"]) for f in all_files]
all_metrics = pd.concat(all_dfs, ignore_index=True).sort_values("Timestamp")

for col, title in zip(["Top10Pct", "Top100Pct", "Top1000Pct", "Top10000Pct"],
                      ["Top 10", "Top 100", "Top 1.000", "Top 10.000"]):
    plt.figure(figsize=(10, 5))
    plt.plot(all_metrics["Timestamp"], all_metrics[col], marker='o')
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.xlabel("Fecha")
    plt.ylabel("% del Supply")
    plt.title(f"Evolución del {title} XRP")
    plt.grid(True)
    plt.tight_layout()
    graph_name = f"{col}_evolucion_{timestamp}.png"
    plt.savefig(graph_name)
    plt.close()
    upload_to_drive(graph_name, "image/png")
    send_telegram_image(graph_name)

summary_message = (
    f"🧠 *XRP Smart Report (Actualización detectada)*\n"
    f"🕓 {timestamp}\n"
    f"🔒 *Bloqueado:* {total_locked:,} XRP\n"
    f"📤 *En circulación:* {total_circulante:,} XRP\n"
    f"🐋 *% en Top 10:* {pct_top10:.2f}%\n"
    f"💯 *% en Top 100:* {pct_top100:.2f}%\n"
    f"🔢 *% en Top 1.000:* {pct_top1000:.2f}%\n"
    f"🔟K *% en Top 10.000:* {pct_top10000:.2f}%\n\n"
    f"📌 *Cambios en wallets:*\n{cambios_texto}"
)

send_telegram_message(summary_message)

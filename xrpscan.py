import os
import csv
import time
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Obtener credenciales de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Crear carpeta de datos si no existe
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)

# Configuración del navegador
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Scraping de datos
url = "https://xrpscan.com/balances"
driver.get(url)
wait = WebDriverWait(driver, 3)

data = []
while True:
    try:
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//tr[@role='row']")))
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) == 7:
                rank = cells[0].text
                wallet = cells[1].text
                owner = cells[3].text
                balance = cells[4].text
                xrp_locked = cells[5].text
                percentage = cells[6].text
                data.append([rank, wallet, owner, balance, xrp_locked, percentage])

        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'ml-1 mr-1 btn btn-outline-info')]")
        if next_buttons and next_buttons[-1].is_enabled():
            next_buttons[-1].click()
            time.sleep(3)
        else:
            break
    except Exception:
        break

driver.quit()

# Guardar datos en CSV con timestamp
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
csv_filename = f"{DATA_FOLDER}/{current_time}.csv"
with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Rank", "Wallet", "Owner", "Balance", "XRP Locked", "Percentage"])
    writer.writerows(data)

# Cargar y limpiar datos
df = pd.read_csv(csv_filename, dtype=str)

def to_bigint(value):
    return int(value.replace(",", "").replace(" XRP", "")) if pd.notna(value) and value.strip() else None

def to_percentage(value):
    return round(float(value.replace("%", "").strip()), 2) if pd.notna(value) and value.strip() else None

df["Balance"] = df["Balance"].apply(to_bigint).astype("Int64")
df["XRP Locked"] = df["XRP Locked"].apply(to_bigint).astype("Int64")
df["Percentage"] = df["Percentage"].apply(to_percentage).astype(float)
df["Total Balance"] = df["Balance"].fillna(0) + df["XRP Locked"].fillna(0)

df.to_csv(csv_filename, index=False)

# Historial de balances
history_file = f"{DATA_FOLDER}/historical_data.csv"
if os.path.exists(history_file):
    history_df = pd.read_csv(history_file)
else:
    history_df = pd.DataFrame(columns=["Timestamp", "Total Balance", "Percentage"])

history_df = pd.concat([history_df, pd.DataFrame({"Timestamp": [current_time], 
                                                  "Total Balance": [df["Total Balance"].sum()], 
                                                  "Percentage": [(df["Total Balance"].sum() / 100_000_000_000) * 100]})])

history_df["Timestamp"] = pd.to_datetime(history_df["Timestamp"], format="%Y-%m-%d_%H-%M")
history_df.to_csv(history_file, index=False)

# Guardar datos en xrp2025.csv en el repositorio raíz
final_csv_filename = "xrp2025.csv"
history_df[["Timestamp", "Total Balance", "Percentage"]].to_csv(final_csv_filename, index=False)

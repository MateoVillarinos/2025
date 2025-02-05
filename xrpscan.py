import os
import time
import pandas as pd
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# Configuración del navegador
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
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
                rank, wallet, owner, balance, xrp_locked, percentage = [cells[i].text for i in [0,1,3,4,5,6]]
                data.append([rank, wallet, owner, balance, xrp_locked, percentage])
        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'ml-1 mr-1 btn btn-outline-info')]")
        if len(next_buttons) > 0 and next_buttons[-1].is_enabled():
            next_buttons[-1].click()
            time.sleep(3)
        else:
            break
    except Exception:
        break

driver.quit()

# Guardar CSV
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
if not os.path.exists("data"):
    os.makedirs("data")
output_file = f"data/{current_time}.csv"

df = pd.DataFrame(data, columns=["Rank", "Wallet", "Owner", "Balance", "XRP Locked", "Percentage"])
df.to_csv(output_file, index=False)

# Evolución histórica
csv_files = sorted([f for f in os.listdir("data") if f.endswith(".csv")])
all_data = []
for file in csv_files:
    df_temp = pd.read_csv(f"data/{file}")
    df_temp["Timestamp"] = file.split(".")[0]
    all_data.append(df_temp)

df_all = pd.concat(all_data, ignore_index=True)
df_all.to_csv("data/xrp_evolution.csv", index=False)

# Calcular métricas
total_balance = df["Balance"].str.replace(",", "").astype(float).sum()
total_percentage = (total_balance / 100_000_000_000) * 100

# Enviar mensaje a Telegram
message = f"\U0001F4C8 *XRP Tracker Update*\n\n" \
          f"Total Balance: {total_balance:,.2f}\n" \
          f"Total Percentage: {total_percentage:.6f}%"
send_telegram_message(message)

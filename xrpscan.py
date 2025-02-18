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

# Graficar evolución del balance
plt.figure(figsize=(10, 5))
plt.plot(history_df["Timestamp"], history_df["Percentage"], marker="o", linestyle="-", color="b")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.xlabel("Tiempo")
plt.ylabel("Posesion del token (%)")
plt.title("10k rich wallets XRP")
plt.grid(True)

# Guardar gráfico
plot_filename = f"{DATA_FOLDER}/evolucion_balance.png"
plt.savefig(plot_filename, bbox_inches="tight")
plt.close()

# Obtener noticias de XRP
def get_xrp_news():
    url = f"https://newsapi.org/v2/everything?q=XRP&sortBy=publishedAt&language=en&pageSize=3&apiKey={NEWSAPI_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        news_list = [f"🔹 {article['title']} - [Leer más]({article['url']})" for article in articles]
        return "\n".join(news_list)
    return "No se encontraron noticias recientes sobre XRP."

xrp_news = get_xrp_news()

# Descargar imagen del gráfico XRP/USDT en M5 desde TradingView
chart_url = "https://s3.tradingview.com/snapshots/m/M5XRPUSDT.png" 
chart_image_path = f"{DATA_FOLDER}/xrp_chart.png"
response = requests.get(chart_url, stream=True)

if response.status_code == 200:
    with open(chart_image_path, "wb") as file:
        for chunk in response.iter_content(1024):
            file.write(chunk)

# Enviar mensaje a Telegram
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

# Enviar resumen de datos y noticias
summary_message = (
    f"📊 **Total Balance actualizado:** {history_df['Total Balance'].iloc[-1]:,.0f} XRP\n"
    f"📈 **Total Porcentaje actualizado:** {history_df['Percentage'].iloc[-1]:,.7f}%\n\n"
    f"📰 **Últimas noticias sobre XRP:**\n{xrp_news}"
)

send_telegram_message(summary_message)
send_telegram_image(plot_filename)
send_telegram_image(chart_image_path)

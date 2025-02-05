import os
import csv
import time
import glob
import smtplib
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configuración de directorios y credenciales
data_dir = "data"
os.makedirs(data_dir, exist_ok=True)
from_email = "mateo.villarinos@gmail.com"
from_password = "ltvj etpn kwpb pyoz"
to_email = "shory.villarinos@gmail.com"

# Función para enviar correo
def send_email(subject, body, attachment=None):
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    if attachment:
        with open(attachment, "rb") as file:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment)}")
            msg.attach(part)
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, from_password)
        server.sendmail(from_email, to_email, msg.as_string())

# Configuración de Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Scraping de XRP Scan
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
                data.append([cells[0].text, cells[1].text, cells[3].text, cells[4].text, cells[5].text, cells[6].text])
        
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
csv_file = os.path.join(data_dir, f"xrp_data_{current_time}.csv")
df = pd.DataFrame(data, columns=["Rank", "Wallet", "Owner", "Balance", "XRP Locked", "Percentage"])
df.to_csv(csv_file, index=False)

# Consolidar todos los archivos CSV
glob_pattern = os.path.join(data_dir, "xrp_data_*.csv")
all_files = sorted(glob.glob(glob_pattern))
all_data = []

def to_bigint(value):
    if pd.isna(value) or value.strip() == "":
        return None
    return int(value.replace(",", "").replace(" XRP", ""))

for file in all_files:
    temp_df = pd.read_csv(file)
    temp_df["Balance"] = temp_df["Balance"].apply(to_bigint)
    temp_df["XRP Locked"] = temp_df["XRP Locked"].apply(to_bigint)
    temp_df["Total Balance"] = temp_df["Balance"].fillna(0) + temp_df["XRP Locked"].fillna(0)
    temp_df["Timestamp"] = file.split("_")[-1].replace(".csv", "")
    all_data.append(temp_df)

if all_data:
    consolidated_df = pd.concat(all_data, ignore_index=True)
    consolidated_df.to_csv(os.path.join(data_dir, "consolidated_xrp_data.csv"), index=False)

    # Graficar evolución del Total Balance
grouped = consolidated_df.groupby("Timestamp")["Total Balance"].sum().reset_index()
plt.figure(figsize=(10, 5))
plt.plot(grouped["Timestamp"], grouped["Total Balance"], marker="o", linestyle="-", color="b")
plt.xticks(rotation=45)
plt.xlabel("Tiempo")
plt.ylabel("Total Balance")
plt.title("Evolución del Total Balance en XRP")
plt.grid(True)
plot_filename = os.path.join(data_dir, "evolution_plot.png")
plt.savefig(plot_filename)
plt.close()

# Enviar email con resultados
subject = "Informe Evolutivo XRP"
body = "Adjunto el gráfico de la evolución del Total Balance en XRP."
send_email(subject, body, plot_filename)

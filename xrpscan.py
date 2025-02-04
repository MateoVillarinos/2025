import csv
import time
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Función para enviar correo
def send_email(subject, body, to_email):
    from_email = "mateo.villarinos@gmail.com"  # Cambia esto por tu correo
    from_password = "ltvj etpn kwpb pyoz"  # Cambia esto por tu contraseña o token de aplicación

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, from_password)
        server.sendmail(from_email, to_email, msg.as_string())

# Configuración del navegador
chrome_options = Options()
chrome_options.add_argument("--headless")  # Ejecutar en modo headless
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

# Inicializar el driver de Selenium
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# URL de la página
url = "https://xrpscan.com/balances"
driver.get(url)

# Esperar a que la tabla se cargue completamente
wait = WebDriverWait(driver, 3)

data = []

page = 1  # Página inicial
while True:  # Continuar hasta que no haya más páginas
    try:
        # Extraer las filas de la tabla
        rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//tr[@role='row']")))

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) == 7:  # Verificar que la fila tenga el número esperado de celdas
                rank = cells[0].text
                wallet = cells[1].text
                owner = cells[3].text
                balance = cells[4].text
                xrp_locked = cells[5].text
                percentage = cells[6].text

                data.append([rank, wallet, owner, balance, xrp_locked, percentage])

        # Intentar hacer clic en el botón de siguiente página
        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'ml-1 mr-1 btn btn-outline-info')]")
        
        if len(next_buttons) > 0 and next_buttons[-1].is_enabled():
            next_buttons[-1].click()
            time.sleep(3)  # Espera para asegurar que la página se actualiza
            page += 1
        else:
            break
    
    except Exception as e:
        break

# Guardar los datos en un archivo CSV
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
output_file = f"{current_time}.csv"
with open(output_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Rank", "Wallet", "Owner", "Balance", "XRP Locked", "Percentage"])
    writer.writerows(data)

# Cargar el archivo CSV
df = pd.read_csv(output_file, dtype=str)  # Cargar todo como string

# Función para limpiar y convertir a bigint
def to_bigint(value):
    if pd.isna(value) or value.strip() == "":
        return None  # Mantener valores nulos
    return int(value.replace(",", "").replace(" XRP", ""))

# Función para convertir porcentaje a decimal y escalarlo a 100 con 2 decimales
def to_percentage(value):
    if pd.isna(value) or value.strip() == "":
        return None
    return round(float(value.replace("%", "").strip()), 2)

# Aplicar transformaciones
df["Balance"] = df["Balance"].apply(to_bigint).astype("Int64")  # Convertir a bigint
df["XRP Locked"] = df["XRP Locked"].apply(to_bigint).astype("Int64")  # Convertir a bigint
df["Percentage"] = df["Percentage"].apply(to_percentage).astype(float)  # Convertir a porcentaje con 2 decimales

# Crear la columna "Total Balance" sumando "Balance" y "XRP Locked"
df["Total Balance"] = df["Balance"].fillna(0) + df["XRP Locked"].fillna(0)
df["Total Balance"] = df["Total Balance"].astype("Int64")  # Asegurar tipo bigint

# Guardar el nuevo CSV si es necesario
df.to_csv("fix_" + output_file, index=False)

# Convertir current_time a datetime
current_time_obj = datetime.strptime(current_time, "%Y-%m-%d_%H-%M")

# Restar 10 minutos a la hora actual
time_minus_10 = (current_time_obj - timedelta(minutes=9)).strftime("%Y-%m-%d_%H-%M")


# Leer el balance anterior desde el archivo correspondiente a 10 minutos atrás
previous_file = f"{time_minus_10}.csv"
try:
    df_previous = pd.read_csv(previous_file, dtype=str)
    previous_balance = df_previous["Total Balance"].sum()
except FileNotFoundError:
    previous_balance = 0

# Calcular sumas totales
total_balance = df["Total Balance"].sum()
total_percentage = (total_balance / 100_000_000_000) * 100
total_percentage = round(total_percentage, 4)  # Limitar a 4 decimales

# Calcular diferencia con el valor anterior
difference = total_balance - previous_balance
difference_str = ""

if difference > 0:
    difference_str = f"Diferencia positiva: {difference}"
elif difference < 0:
    difference_str = f"Diferencia negativa: {difference}"
else:
    difference_str = "Sin diferencia"

# Imprimir resultados
print(f"Total de Percentage: {total_percentage:.4f}")
print(f"Total de Total Balance: {total_balance}")
print(f"{difference_str}")

# Enviar correo
subject = f"Informe de Balance - {current_time}"
body = f"""
Total Balance: {total_balance}
Total Percentage: {total_percentage:.4f}
{difference_str}
"""
send_email(subject, body, "mateo.villarinos@gmail.com")

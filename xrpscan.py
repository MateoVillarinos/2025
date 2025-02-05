import os
import csv
import time
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random

# Obtener credenciales de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

# Evolución del balance
csv_files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")])
historical_data = []
porcentaje = []
timestamps = []

for file in csv_files:
    df_temp = pd.read_csv(f"{DATA_FOLDER}/{file}", dtype=str)
    if "Total Balance" in df_temp.columns:
        total_balance = df_temp["Total Balance"].astype(float).sum()
        historical_data.append(total_balance)
        porcentaje.append(round((total_balance / 100_000_000_000) * 100, 7))
        timestamps.append(file.replace(".csv", ""))

# Graficar evolución del balance
plt.figure(figsize=(10, 5))
plt.plot(timestamps, porcentaje, marker="o", linestyle="-", color="b")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.xlabel("Tiempo")
plt.ylabel("Posesion del token")
plt.title("10k rich wallets XRP")
plt.grid(True)

# Guardar gráfico
plot_filename = f"{DATA_FOLDER}/evolucion_balance.png"
plt.savefig(plot_filename, bbox_inches="tight")
plt.close()

# Enviar imagen a Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, json=payload)

#def send_telegram_image(image_path):
#    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
#    with open(image_path, "rb") as image:
#        files = {"photo": image}
#        payload = {"chat_id": TELEGRAM_CHAT_ID}
#        requests.post(url, data=payload, files=files)

# Lista de más de 1000 frases motivadoras
motivational_quotes = [
    # ÉXITO Y DINERO
    "El dinero es solo una herramienta, no un propósito. Tu propósito es lo que realmente te hará millonario.",
    "El éxito no se mide por la cantidad de dinero, sino por la cantidad de libertad que tienes.",
    "No trabajes por dinero, haz que el dinero trabaje para ti.",
    "La riqueza no es cuestión de suerte, sino de estrategia y persistencia.",
    "Si no construyes tu sueño, alguien te contratará para que ayudes a construir el suyo.",
    "Ganar dinero mientras duermes es el único camino hacia la libertad financiera.",
    "No es cuánto ganas, sino cuánto inviertes y multiplicas.",
    "Tu mentalidad define tu cuenta bancaria.",
    
    # MADUREZ Y RESPONSABILIDAD
    "Ser maduro no significa saberlo todo, sino aprender a vivir con sabiduría.",
    "La responsabilidad es la clave del respeto y la confianza.",
    "El verdadero liderazgo comienza con la responsabilidad personal.",
    "Toma decisiones con la cabeza, pero nunca olvides lo que dicta el corazón.",
    "Crecer es aprender a ser fuerte sin perder la ternura.",
    "Cada decisión que tomas hoy es un ladrillo en la construcción de tu futuro.",
    "Haz lo correcto, incluso cuando nadie te esté mirando.",
    
    # AMOR Y FAMILIA
    "La familia es la riqueza más grande que jamás poseerás.",
    "El amor no se trata de encontrar a alguien perfecto, sino de ver la perfección en alguien imperfecto.",
    "Valora a quienes siempre han estado a tu lado, no cuando los necesites, sino porque lo merecen.",
    "Ama sin miedo, porque cada momento es una oportunidad para ser feliz.",
    "No hay éxito más grande que ser amado y amar a los tuyos con todo el corazón.",
    
    # SALUD Y EJERCICIO
    "Cuida tu cuerpo, porque es el único lugar en el que tienes que vivir.",
    "La disciplina en el ejercicio se traduce en disciplina en la vida.",
    "Un cuerpo fuerte es la base para una mente fuerte.",
    "La salud es la verdadera riqueza. Sin ella, todo lo demás pierde valor.",
    "No se trata de ser el más fuerte, sino de ser la mejor versión de ti mismo.",
    "Cada gota de sudor es un paso más cerca de la mejor versión de ti mismo.",
    
    # PASIÓN Y SER ÚNICO
    "Ser diferente es tu mayor ventaja, no tu debilidad.",
    "La pasión convierte lo ordinario en extraordinario.",
    "No te conformes con ser uno más, atrévete a ser único.",
    "El mundo pertenece a quienes tienen fuego en el alma y determinación en la mirada.",
    "La pasión es el motor que transforma los sueños en realidades.",
    "Los que se atreven a ser distintos son los que cambian el mundo.",
    
    # BONDAD Y AMABILIDAD
    "La bondad es un idioma que todos pueden entender.",
    "Las personas pueden olvidar lo que dijiste, pero nunca olvidarán cómo las hiciste sentir.",
    "Ser amable no es una debilidad, sino una fortaleza poco común.",
    "Ayudar a otros no te quita nada, pero sí te enriquece el alma.",
    "Un acto de bondad, por pequeño que sea, puede cambiar un día, una vida o el mundo.",
    
    # MÁS FRASES ALEATORIAS
    "No esperes el momento perfecto, haz que el momento sea perfecto.",
    "Cada día es una nueva oportunidad para empezar de nuevo.",
    "No midas tu vida en años, sino en momentos que te dejen sin aliento.",
    "El miedo es solo una ilusión, el coraje es real.",
    "La paciencia y la persistencia convierten lo imposible en inevitable.",
    "No se trata de cuántas veces caes, sino de cuántas veces te levantas.",
    "Si quieres resultados diferentes, haz cosas diferentes.",
    "Las excusas no te acercan a tus metas, la acción sí.",
    "Tu vida cambia cuando decides que nada volverá a ser igual.",
    "El esfuerzo de hoy es el éxito de mañana.",
    "Nada grande se logra sin pasión y dedicación.",
    "La única forma de fracasar es rendirse.",
    "Rodéate de personas que te inspiren a crecer.",
    "Si crees en ti, ya tienes la mitad del camino recorrido.",
    "Sueña en grande, pero trabaja más grande aún.",
]

# Seleccionar una frase aleatoria
motivational_message = random.choice(motivational_quotes)

# Agregar la frase al mensaje de resumen
summary_message = (
    f"Total Balance actualizado: {historical_data[-1]:,.0f} XRP\n"
    f"Total Porcentaje actualizado: {porcentaje[-1]:,.7f}%\n\n"
    f"🌟 {motivational_message} 🌟"
)

send_telegram_message(summary_message)
#send_telegram_image(plot_filename)

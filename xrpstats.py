import pandas as pd
import matplotlib.pyplot as plt
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Obtener el archivo más reciente generado por xrpscan.py
csv_files = sorted(glob.glob("fix_*.csv"))

if not csv_files:
    print("No se encontraron archivos CSV.")
    exit()

latest_file = csv_files[-1]  # Último archivo generado

# Leer el archivo CSV
try:
    df = pd.read_csv(latest_file)
    df["Percentage"] = df["Total Balance"] / 100_000_000_000
except Exception as e:
    print(f"Error al leer el archivo CSV: {e}")
    exit()

# Calcular la suma total de "Percentage"
total_percentage = df["Percentage"].sum()

# Crear gráfico
plt.figure(figsize=(10, 5))
plt.plot(df["Percentage"], marker="o", linestyle="-", color="b")
plt.xlabel("Índice")
plt.ylabel("Percentage")
plt.title("Distribución del Percentage en el Último CSV")
plt.grid(True)

# Guardar el gráfico como imagen
plot_filename = "percentage_plot.png"
plt.savefig(plot_filename)
plt.close()

# Enviar correo con gráfico adjunto
from_email = "mateo.villarinos@gmail.com"
from_password = "ltvj etpn kwpb pyoz"
to_email = "mateo.villarinos@gmail.com"

subject = "Informe de Percentage"
body = f"Total Percentage en el último archivo: {total_percentage:.4f}"

msg = MIMEMultipart()
msg["From"] = from_email
msg["To"] = to_email
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))

# Adjuntar gráfico
with open(plot_filename, "rb") as attachment:
    part = MIMEBase("application", "octet-stream")
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={plot_filename}")
    msg.attach(part)

# Enviar el correo
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, from_password)
        server.sendmail(from_email, to_email, msg.as_string())
    print("Correo enviado correctamente.")
except Exception as e:
    print(f"Error al enviar el correo: {e}")

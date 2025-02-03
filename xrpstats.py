import pandas as pd
import matplotlib.pyplot as plt
import glob

# 🗂️ Obtener lista de archivos CSV en la carpeta actual
csv_files = sorted(glob.glob("fix_rich_*.csv"))

# 📊 Diccionario para almacenar la suma de "percentage" en cada archivo
percentage_sum = {}

# 🔄 Procesar cada archivo CSV
for file in csv_files:
    # 📅 Extraer la fecha desde el nombre del archivo
    date = file.split("_")[2] + "_" + file.split("_")[3].split(".")[0]
    
    # 📥 Leer el archivo CSV
    df = pd.read_csv(file)
    
    # 🔢 Calcular la nueva columna "percentage"
    df["Percentage"] = df["Total Balance"] / 100_000_000_000
    
    # ➕ Sumar los valores de la nueva columna "Percentage"
    percentage_sum[date] = df["Percentage"].sum()

# 📅 Convertir los datos en un DataFrame ordenado
df_plot = pd.DataFrame(list(percentage_sum.items()), columns=["Date", "Total Percentage"])
df_plot["Date"] = pd.to_datetime(df_plot["Date"], format="%m-%d_%Hhs")  # Ajustar formato de fecha
df_plot = df_plot.sort_values("Date")

# 📈 Graficar la evolución de la suma de "Percentage"
plt.figure(figsize=(10, 5))
plt.plot(df_plot["Date"], df_plot["Total Percentage"], marker="o", linestyle="-", color="b")
plt.xlabel("Fecha")
plt.ylabel("Suma de Percentage")
plt.title("Evolución de la Suma de Percentage en el Tiempo")
plt.xticks(rotation=45)
plt.grid(True)
plt.show()

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data_processing import load_files

st.set_page_config(page_title="Análisis IoT - Invernadero", page_icon="🌱", layout="wide")

DISPLAY = {
    "temperature_c": ("Temperatura", "°C"),
    "humidity_pct": ("Humedad relativa", "%"),
    "illumination_lux": ("Iluminación estimada", "lux"),
}

st.title("Sistema IoT de monitoreo de invernadero")
st.caption("Análisis de telemetría descargada desde Grafana · ESP32 · MQTT · InfluxDB")
st.info(
    "Carga el CSV exportado desde Grafana. Puedes subir un CSV combinado o varios CSV, "
    "uno por panel. La aplicación no genera mediciones ficticias."
)

uploads = st.file_uploader("Archivos CSV de Grafana", type=["csv"], accept_multiple_files=True)
if not uploads:
    st.markdown("### ¿Qué analiza esta aplicación?")
    st.write(
        "Temperatura, humedad relativa e iluminación estimada en lux; estadísticas "
        "descriptivas, evolución temporal, alertas configurables por umbral y correlación."
    )
    st.markdown(
        "**Formato esperado:** CSV de panel con columnas `Time` y `Value` (el nombre "
        "del archivo identifica la variable), CSV ancho con columnas por variable, o "
        "CSV largo de InfluxDB con `_time`, `_field` y `_value`."
    )
    st.stop()

try:
    data = load_files(uploads)
except Exception as exc:
    st.error(f"No fue posible leer los CSV: {exc}")
    st.stop()

available = [c for c in DISPLAY if c in data.columns and data[c].notna().any()]
if data.empty or not available:
    st.error(
        "No encontré columnas de fecha y variables reconocibles. Comprueba que el "
        "CSV tenga una columna Time/_time/timestamp y valores de temperatura, humedad "
        "o iluminación. Para CSV Time/Value, nombra los archivos temperatura.csv, "
        "humedad.csv o iluminacion.csv."
    )
    st.stop()

st.sidebar.header("Rangos de referencia")
st.sidebar.caption(
    "Valores iniciales editables para esta demostración académica; no son una "
    "recomendación agronómica universal. Ajusta los umbrales al cultivo real."
)
thresholds = {
    "temperature_c": (
        st.sidebar.number_input("Temperatura mínima (°C)", value=18.0, step=0.5),
        st.sidebar.number_input("Temperatura máxima (°C)", value=30.0, step=0.5),
    ),
    "humidity_pct": (
        st.sidebar.number_input("Humedad mínima (%)", value=40.0, step=1.0),
        st.sidebar.number_input("Humedad máxima (%)", value=80.0, step=1.0),
    ),
    "illumination_lux": (
        st.sidebar.number_input("Iluminación mínima (lux)", value=500.0, step=100.0),
        st.sidebar.number_input("Iluminación máxima (lux)", value=20000.0, step=500.0),
    ),
}

start, end = data["timestamp"].min(), data["timestamp"].max()
col1, col2, col3 = st.columns(3)
col1.metric("Registros", f"{len(data):,}")
col2.metric("Primera lectura", start.strftime("%Y-%m-%d %H:%M UTC") if pd.notna(start) else "—")
col3.metric("Última lectura", end.strftime("%Y-%m-%d %H:%M UTC") if pd.notna(end) else "—")

st.subheader("Resumen estadístico")
summary_rows = []
for field in available:
    values = data[field].dropna()
    label, unit = DISPLAY[field]
    summary_rows.append(
        {
            "Variable": label,
            "Unidad": unit,
            "Promedio": round(values.mean(), 2),
            "Mínimo": round(values.min(), 2),
            "Máximo": round(values.max(), 2),
            "Desviación estándar": round(values.std(), 2) if len(values) > 1 else 0.0,
        }
    )
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

st.subheader("Evolución de las variables")
for field in available:
    label, unit = DISPLAY[field]
    fig = px.line(data, x="timestamp", y=field, markers=True, title=f"{label} ({unit})")
    fig.update_layout(
        xaxis_title="Fecha y hora",
        yaxis_title=unit,
        margin=dict(l=10, r=10, t=50, b=10),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Alertas por umbral")
alert_rows = []
for field in available:
    low, high = thresholds[field]
    if low >= high:
        st.warning(f"El rango de {DISPLAY[field][0]} no es válido: el mínimo debe ser menor que el máximo.")
        continue
    series = data[field].dropna()
    out = series[(series < low) | (series > high)]
    percentage = (len(out) / len(series) * 100) if len(series) else 0
    alert_rows.append(
        {
            "Variable": DISPLAY[field][0],
            "Rango": f"{low:g}–{high:g} {DISPLAY[field][1]}",
            "Lecturas fuera de rango": int(len(out)),
            "Porcentaje fuera de rango": f"{percentage:.1f}%",
            "Estado": "Revisar" if len(out) else "Dentro del rango",
        }
    )
if alert_rows:
    st.dataframe(pd.DataFrame(alert_rows), use_container_width=True, hide_index=True)
    total_alerts = sum(row["Lecturas fuera de rango"] for row in alert_rows)
    if total_alerts:
        st.warning(f"Se detectaron {total_alerts} lecturas fuera de los rangos de referencia configurados.")
    else:
        st.success("Todas las lecturas cargadas están dentro de los rangos de referencia configurados.")

present = [field for field in DISPLAY if field in available]
if len(present) >= 2:
    st.subheader("Relación entre variables")
    correlation = data[present].corr(numeric_only=True)
    fig_corr = px.imshow(
        correlation,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        aspect="auto",
        title="Matriz de correlación",
    )
    st.plotly_chart(fig_corr, use_container_width=True)

st.subheader("Datos procesados")
show = data.copy()
show["timestamp"] = show["timestamp"].astype(str)
st.dataframe(show, use_container_width=True, hide_index=True)

csv_bytes = data.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Descargar datos unificados",
    data=csv_bytes,
    file_name="telemetria_invernadero_unificada.csv",
    mime="text/csv",
)
st.caption(
    "La correlación describe asociación lineal entre las mediciones; no demuestra "
    "causalidad. La interpretación depende del cultivo y de la calibración del sensor LDR."
)

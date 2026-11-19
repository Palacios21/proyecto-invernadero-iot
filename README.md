# Análisis IoT - Invernadero

Aplicación Streamlit para analizar los CSV exportados desde Grafana Cloud.

## Despliegue en Streamlit Community Cloud

1. Sube todos los archivos de esta carpeta a la raíz de un repositorio GitHub.
2. En Streamlit Community Cloud, crea una app desde ese repositorio.
3. Selecciona la rama `main` y el archivo principal `app.py`.
4. Streamlit instalará las dependencias desde `requirements.txt`.
5. En la app publicada, carga los CSV `temperatura.csv`, `humedad.csv` e `iluminacion.csv` simultáneamente.

## Formato CSV esperado

Se admiten CSV de Grafana con columnas de tiempo y valor (`Time`/`Value`), exportaciones anchas con las columnas `temperature_c`, `humidity_pct`, `illumination_lux`, o CSV largo con `_time`, `_field`, `_value`.

Para archivos `Time`/`Value`, usa estos nombres para que la app identifique cada variable:
- `temperatura.csv`
- `humedad.csv`
- `iluminacion.csv`

## Seguridad

No subas tokens, contraseñas ni certificados privados al repositorio. Los CSV de las mediciones se cargan desde la interfaz de Streamlit y no es necesario publicarlos en GitHub.

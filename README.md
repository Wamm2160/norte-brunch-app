# Norte Brunch Finanzas - App Web

Esta app usa Streamlit y Google Sheets.

## Archivos

- `app.py`: app web.
- `requirements.txt`: librerías necesarias.
- `.streamlit/secrets.toml.example`: ejemplo de configuración secreta.

## Estructura de Google Sheets

Crea un Google Sheet llamado:

`Norte Brunch Finanzas`

La app creará automáticamente estas hojas si no existen:

- Productos
- Ventas
- Gastos_Local
- Gastos_Familiares
- Inventario
- Saldos
- Diezmos
- Inversiones
- Categorias_Local
- Categorias_Familia
- Config

## Cómo correr en tu Mac

1. Instala las librerías:

```bash
python3 -m pip install -r requirements.txt
```

2. Crea el archivo `.streamlit/secrets.toml` usando como guía `.streamlit/secrets.toml.example`.

3. Ejecuta:

```bash
streamlit run app.py
```

## Cómo usarlo en Streamlit Cloud

1. Sube estos archivos a GitHub.
2. Entra a Streamlit Community Cloud.
3. Crea una app nueva desde el repositorio de GitHub.
4. En "Secrets", pega el contenido real de `.streamlit/secrets.toml`.
5. Abre la URL en tu iPhone.
6. En Safari, usa "Agregar a pantalla de inicio".

## Importante

El Google Sheet debe estar compartido con el email del service account, por ejemplo:

`tu-service-account@tu-project-id.iam.gserviceaccount.com`

Dale permiso de Editor.

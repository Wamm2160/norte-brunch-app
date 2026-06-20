import uuid
import base64
import time
import random
from datetime import datetime, date, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import APIError
from google.oauth2 import service_account


APP_TITLE = "Norte Brunch Finanzas"
TIMEZONE = ZoneInfo("America/Mexico_City")
TITHING_RATE = 0.10
CARD_FEE_RATE = 0.035
MIN_INVESTMENT_REPAYMENT_ALERT = 10000

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


SHEETS = {
    "productos": {
        "name": "Productos",
        "headers": ["producto", "precio", "ganancia_personal", "activo"],
        "default_rows": [
            ["Torta de adobada", 95, 40, "si"],
            ["Torta de pierna", 100, 40, "si"],
            ["Torta mixta", 125, 45, "si"],
            ["Pastel", 45, 15, "si"],
            ["Cafe", 20, 10, "si"],
            ["Refresco", 30, 10, "si"],
            ["Agua de litro", 45, 25, "si"],
            ["Agua de medio litro", 30, 20, "si"],
            ["Extra aguacate", 15, 0, "si"],
            ["Extra queso", 15, 0, "si"],
        ],
    },
    "pedidos": {
        "name": "Pedidos",
        "headers": [
            "fecha_hora",
            "fecha",
            "hora",
            "pedido_id",
            "pedido_numero",
            "estado",
            "producto",
            "cantidad",
            "precio_unitario",
            "ganancia_personal_unitaria",
            "total_linea",
            "ganancia_personal_linea",
            "dinero_norte_linea",
            "diezmo_linea",
            "nota",
        ],
        "default_rows": [],
    },
    "ventas": {
        "name": "Ventas",
        "headers": [
            "fecha_hora",
            "fecha",
            "hora",
            "pedido_id",
            "pedido_numero",
            "producto",
            "cantidad",
            "precio_unitario",
            "ganancia_personal_unitaria",
            "total_linea",
            "ganancia_personal_linea",
            "dinero_norte_linea",
            "diezmo_linea",
            "metodo_pago",
            "monto_efectivo_linea",
            "monto_tarjeta_linea",
            "monto_transferencia_linea",
            "comision_terminal_linea",
            "total_neto_linea",
            "nota",
        ],
        "default_rows": [],
    },
    "gastos_local": {
        "name": "Gastos_Local",
        "headers": [
            "fecha_hora",
            "fecha",
            "hora",
            "tipo_movimiento",
            "nombre",
            "categoria",
            "cantidad",
            "unidad",
            "costo_total",
            "pagado_por",
            "nota",
        ],
        "default_rows": [],
    },
    "gastos_familiares": {
        "name": "Gastos_Familiares",
        "headers": [
            "fecha_hora",
            "fecha",
            "hora",
            "tipo",
            "categoria",
            "producto",
            "monto",
            "metodo_pago",
            "nota",
        ],
        "default_rows": [],
    },
    "inventario": {
        "name": "Inventario",
        "headers": ["insumo", "cantidad", "unidad"],
        "default_rows": [],
    },
    "recetas": {
        "name": "Recetas",
        "headers": [
            "producto",
            "insumo",
            "cantidad_por_producto",
            "unidad",
            "costo_unitario",
            "activo",
        ],
        "default_rows": [
            ["Torta de adobada", "pan", 1, "pieza", 8, "si"],
            ["Torta de adobada", "carne adobada", 0.15, "kg", 95, "si"],
            ["Torta de adobada", "aguacate", 0.08, "kg", 60, "si"],
            ["Torta de pierna", "pan", 1, "pieza", 8, "si"],
            ["Torta de pierna", "pierna", 0.15, "kg", 95, "si"],
            ["Torta de pierna", "aguacate", 0.08, "kg", 60, "si"],
            ["Torta mixta", "pan", 1, "pieza", 8, "si"],
            ["Torta mixta", "carne adobada", 0.075, "kg", 95, "si"],
            ["Torta mixta", "pierna", 0.075, "kg", 95, "si"],
            ["Torta mixta", "aguacate", 0.08, "kg", 60, "si"],
            ["Pastel", "rebanada de pastel", 1, "pieza", 27, "si"],
            ["Cafe", "cafe preparado", 1, "pieza", 10, "si"],
            ["Refresco", "refresco 600 ml", 1, "pieza", 20, "si"],
            ["Agua de litro", "agua 1 litro", 1, "pieza", 20, "si"],
            ["Agua de medio litro", "agua 500 ml", 1, "pieza", 10, "si"],
            ["Extra aguacate", "aguacate", 0.08, "kg", 60, "si"],
            ["Extra queso", "queso", 0.04, "kg", 120, "si"],
        ],
    },
    "saldos": {
        "name": "Saldos",
        "headers": ["cuenta", "monto"],
        "default_rows": [
            ["dinero_norte_brunch", 0],
            ["ganancia_pendiente_personal", 0],
            ["ganancia_pagada_personal", 0],
            ["total_gastos_negocio", 0],
            ["gastos_pagados_norte", 0],
            ["gastos_pagados_personal", 0],
            ["inversion_inicial_personal", 0],
            ["inversion_personal_total", 0],
            ["deuda_inversion_personal", 0],
            ["inversion_pagada_personal", 0],
            ["dinero_familiar", 0],
            ["ingresos_familiares_totales", 0],
            ["gastos_familiares_totales", 0],
            ["diezmo_pendiente", 0],
            ["diezmo_pagado", 0],
        ],
    },
    "diezmos": {
        "name": "Diezmos",
        "headers": ["fecha_hora", "fecha", "hora", "monto", "frecuencia", "nota"],
        "default_rows": [],
    },
    "inversiones": {
        "name": "Inversiones",
        "headers": ["fecha_hora", "fecha", "hora", "tipo", "monto", "nota"],
        "default_rows": [],
    },
    "categorias_local": {
        "name": "Categorias_Local",
        "headers": ["categoria", "activo"],
        "default_rows": [
            ["insumos", "si"],
            ["local", "si"],
            ["transporte", "si"],
        ],
    },
    "categorias_familia": {
        "name": "Categorias_Familia",
        "headers": ["categoria", "activo"],
        "default_rows": [
            ["hogar", "si"],
        ],
    },
    "config": {
        "name": "Config",
        "headers": ["clave", "valor"],
        "default_rows": [["frecuencia_diezmo", "mensual"], ["frecuencia_pago_personal", "semanal"]],
    },
}


REQUIRED_PRODUCT_PRICES = {
    "Torta mixta": {"precio": 125, "ganancia_personal": 45},
    "Agua de litro": {"precio": 45, "ganancia_personal": 25},
    "Agua de medio litro": {"precio": 30, "ganancia_personal": 20},
}


# -----------------------------
# GOOGLE SHEETS
# -----------------------------

@st.cache_resource
def get_spreadsheet():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])


def google_call(func, *args, **kwargs):
    """Ejecuta llamadas a Google Sheets con reintentos para evitar fallas por cuota o red."""
    last_error = None

    for attempt in range(5):
        try:
            return func(*args, **kwargs)
        except APIError as error:
            last_error = error
            wait_time = min(2 ** attempt, 16)
            time.sleep(wait_time)
        except Exception as error:
            last_error = error
            wait_time = min(2 ** attempt, 8)
            time.sleep(wait_time)

    raise last_error


def get_worksheet_map():
    spreadsheet = get_spreadsheet()
    worksheets = google_call(spreadsheet.worksheets)
    return {ws.title: ws for ws in worksheets}


def get_ws(sheet_key):
    spreadsheet = get_spreadsheet()
    sheet_info = SHEETS[sheet_key]
    worksheet_map = get_worksheet_map()
    worksheet = worksheet_map.get(sheet_info["name"])

    if worksheet is None:
        worksheet = google_call(
            spreadsheet.add_worksheet,
            title=sheet_info["name"],
            rows=1000,
            cols=max(30, len(sheet_info["headers"]) + 5),
        )
        worksheet_map[sheet_info["name"]] = worksheet
        google_call(worksheet.append_row, sheet_info["headers"], value_input_option="USER_ENTERED")
        if sheet_info["default_rows"]:
            google_call(worksheet.append_rows, sheet_info["default_rows"], value_input_option="USER_ENTERED")

    return worksheet


def get_actual_headers(sheet_key):
    ws = get_ws(sheet_key)
    headers = google_call(ws.row_values, 1)
    return headers if headers else SHEETS[sheet_key]["headers"]


@st.cache_resource
def setup_workbook():
    """Crea hojas faltantes y agrega columnas nuevas sin borrar datos."""
    for key, sheet_info in SHEETS.items():
        ws = get_ws(key)
        first_row = google_call(ws.row_values, 1)

        if not first_row:
            google_call(ws.append_row, sheet_info["headers"], value_input_option="USER_ENTERED")
            if sheet_info["default_rows"]:
                google_call(ws.append_rows, sheet_info["default_rows"], value_input_option="USER_ENTERED")
            continue

        missing_headers = [header for header in sheet_info["headers"] if header not in first_row]
        if missing_headers:
            start_col = len(first_row) + 1
            for index, header in enumerate(missing_headers, start=start_col):
                google_call(ws.update_cell, 1, index, header)

    return True


@st.cache_data(ttl=120)
def load_df(sheet_key):
    """Carga una hoja con menos riesgo de error que get_all_records."""
    ws = get_ws(sheet_key)
    try:
        values = google_call(ws.get_all_values)
    except APIError as error:
        st.error(
            "Google Sheets no dejó leer la información en este momento. "
            "Espera 1 minuto y presiona Reboot/Refresh. "
            "Si sigue pasando, revisa que la hoja esté compartida con el correo del service account."
        )
        st.stop()
    except Exception as error:
        st.error("No se pudo leer Google Sheets. Revisa conexión, permisos o Secrets.")
        st.stop()

    if not values:
        return pd.DataFrame()

    headers = [str(h).strip() for h in values[0]]
    rows = values[1:]

    cleaned_rows = []
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        cleaned_rows.append(padded[:len(headers)])

    return pd.DataFrame(cleaned_rows, columns=headers)
def clear_data_cache():
    try:
        load_df.clear()
    except Exception:
        pass
    try:
        ensure_required_product_prices.clear()
    except Exception:
        pass


def append_record(sheet_key, record):
    """Agrega una fila respetando el orden real de columnas en la hoja."""
    ws = get_ws(sheet_key)
    headers = get_actual_headers(sheet_key)
    row = [record.get(header, "") for header in headers]
    google_call(ws.append_row, row, value_input_option="USER_ENTERED")
    clear_data_cache()


def replace_records(sheet_key, records):
    """Reemplaza datos de una hoja usando encabezados actuales."""
    ws = get_ws(sheet_key)
    headers = get_actual_headers(sheet_key)

    google_call(ws.clear)
    google_call(ws.append_row, headers, value_input_option="USER_ENTERED")

    rows = []
    for record in records:
        rows.append([record.get(header, "") for header in headers])

    if rows:
        google_call(ws.append_rows, rows, value_input_option="USER_ENTERED")

    clear_data_cache()


@st.cache_resource
def ensure_required_product_prices():
    """Actualiza precios clave que ya definió Wilson, sin tocar otros productos."""
    df = load_df("productos")
    if df.empty:
        return False

    changed = False
    records = []

    for _, row in df.iterrows():
        product = str(row.get("producto", "")).strip()
        record = {
            "producto": row.get("producto", ""),
            "precio": row.get("precio", 0),
            "ganancia_personal": row.get("ganancia_personal", 0),
            "activo": row.get("activo", "si"),
        }

        if product in REQUIRED_PRODUCT_PRICES:
            expected = REQUIRED_PRODUCT_PRICES[product]
            if to_float(record["precio"]) != float(expected["precio"]):
                record["precio"] = expected["precio"]
                changed = True
            if to_float(record["ganancia_personal"]) != float(expected["ganancia_personal"]):
                record["ganancia_personal"] = expected["ganancia_personal"]
                changed = True

        records.append(record)

    if changed:
        replace_records("productos", records)

    return changed


# -----------------------------
# UTILIDADES
# -----------------------------

def mx_now():
    return datetime.now(TIMEZONE)


def datetime_parts(selected_date, selected_time):
    dt = datetime.combine(selected_date, selected_time)
    return {
        "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha": selected_date.strftime("%Y-%m-%d"),
        "hora": selected_time.strftime("%H:%M:%S"),
    }


def datetime_inputs(prefix, label="Fecha y hora"):
    now = mx_now()
    st.write(f"**{label}**")
    col1, col2 = st.columns(2)
    selected_date = col1.date_input("Fecha", value=now.date(), key=f"{prefix}_fecha")
    selected_time = col2.time_input(
        "Hora",
        value=now.time().replace(microsecond=0),
        step=60,
        key=f"{prefix}_hora",
    )
    return datetime_parts(selected_date, selected_time)


def pesos(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def apply_branding():
    st.markdown(
        """
        <style>
        :root {
            --nb-red: #b42318;
            --nb-dark: #2b1b12;
            --nb-cream: #fff4df;
            --nb-gold: #d8952f;
            --nb-green: #157347;
        }

        .stApp {
            background: linear-gradient(180deg, #fff8ea 0%, #fff4df 45%, #ffffff 100%);
        }

        .nb-hero {
            background: linear-gradient(135deg, #2b1b12 0%, #5a2b18 55%, #b42318 100%);
            border-radius: 22px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: 0 8px 22px rgba(43, 27, 18, 0.18);
            color: white;
            border: 2px solid #d8952f;
        }

        .nb-title {
            font-size: 2.2rem;
            font-weight: 900;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }

        .nb-subtitle {
            font-size: 1rem;
            color: #ffe8b8;
        }

        .nb-total-red {
            background: #fff1f0;
            border: 3px solid #b42318;
            color: #b42318;
            border-radius: 18px;
            padding: 18px;
            text-align: center;
            font-weight: 900;
            font-size: 2.35rem;
            margin: 14px 0;
            box-shadow: 0 5px 14px rgba(180, 35, 24, 0.18);
        }

        .nb-total-green {
            background: #eafaf1;
            border: 3px solid #157347;
            color: #157347;
            border-radius: 18px;
            padding: 18px;
            text-align: center;
            font-weight: 900;
            font-size: 2.15rem;
            margin: 14px 0;
            box-shadow: 0 5px 14px rgba(21, 115, 71, 0.16);
        }

        .nb-warning-card {
            background: #fff7e6;
            border-left: 8px solid #d8952f;
            border-radius: 14px;
            padding: 16px;
            margin: 12px 0;
        }

        div.stButton > button {
            border-radius: 14px;
            font-weight: 700;
        }

        /* Corrección de contraste: fondo claro + letras oscuras */
        .stApp,
        .stApp p,
        .stApp div,
        .stApp span,
        .stApp label,
        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6 {
            color: #1F2933 !important;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span {
            color: #1F2933 !important;
        }

        [data-testid="stMetric"] label,
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {
            color: #1F2933 !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #1F2933 !important;
        }

        input,
        textarea,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {
            color: #111827 !important;
            background-color: #FFFFFF !important;
        }

        [data-baseweb="select"] div,
        [data-baseweb="select"] span {
            color: #111827 !important;
        }

        .stButton > button {
            color: #FFFFFF !important;
            background-color: #D8891E;
            border-radius: 10px;
            font-weight: 800;
        }

        .stButton > button p,
        .stButton > button div,
        .stButton > button span {
            color: #FFFFFF !important;
        }

        .nb-subtitle {
            color: #3A2A1A !important;
        }

        .nb-total-red,
        .nb-total-red div,
        .nb-total-red span {
            color: #1F2933 !important;
        }

        .nb-total-red .amount {
            color: #D32F2F !important;
        }

        .nb-total-green,
        .nb-total-green div,
        .nb-total-green span {
            color: #1F2933 !important;
        }

        .nb-total-green .amount {
            color: #2E7D32 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_header():
    logo_path = Path("logo.png")

    st.markdown(
        """
        <div class="nb-hero">
            <div class="nb-title">🥪 Norte Brunch</div>
            <div class="nb-subtitle">Sistema privado de ventas, gastos, pagos y recuperación de inversión</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if logo_path.exists():
        st.image(str(logo_path), width=140)
    elif "app" in st.secrets and "logo_url" in st.secrets["app"]:
        st.image(st.secrets["app"]["logo_url"], width=140)


def big_red_amount(label, amount):
    st.markdown(
        f'<div class="nb-total-red">{label}<br>{pesos(amount)}</div>',
        unsafe_allow_html=True,
    )


def big_green_amount(label, amount):
    st.markdown(
        f'<div class="nb-total-green">{label}<br>{pesos(amount)}</div>',
        unsafe_allow_html=True,
    )


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_numeric(df, columns):
    data = df.copy()
    for col in columns:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)
    return data


def prepare_datetime(df):
    data = df.copy()
    if data.empty:
        data["dt"] = pd.to_datetime([])
        return data

    if "fecha_hora" in data.columns:
        data["dt"] = pd.to_datetime(data["fecha_hora"], errors="coerce")
    else:
        data["dt"] = pd.NaT

    if "fecha" in data.columns:
        missing = data["dt"].isna()
        data.loc[missing, "dt"] = pd.to_datetime(data.loc[missing, "fecha"], errors="coerce")

    return data


def weekday_spanish(weekday):
    names = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
    return names.get(weekday, weekday)


def period_filter_ui(prefix):
    option = st.selectbox(
        "Periodo",
        ["Hoy", "Semana", "Mes", "Año", "Todo", "Rango personalizado"],
        key=f"{prefix}_periodo",
    )

    today = mx_now().date()

    if option == "Hoy":
        return today, today
    if option == "Semana":
        start = today - timedelta(days=today.weekday())
        return start, today
    if option == "Mes":
        return today.replace(day=1), today
    if option == "Año":
        return today.replace(month=1, day=1), today
    if option == "Todo":
        return date.min, today

    col1, col2 = st.columns(2)
    start = col1.date_input("Desde", value=today, key=f"{prefix}_desde")
    end = col2.date_input("Hasta", value=today, key=f"{prefix}_hasta")
    return start, end


def filter_date_range(df, start_date, end_date):
    if df.empty:
        return df

    data = prepare_datetime(df)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return data[(data["dt"] >= start) & (data["dt"] <= end)].copy()


# -----------------------------
# SALDOS, CONFIG Y CATEGORÍAS
# -----------------------------

def get_saldos():
    df = load_df("saldos")
    saldos = {}

    if not df.empty:
        for _, row in df.iterrows():
            cuenta = str(row.get("cuenta", "")).strip()
            if cuenta:
                saldos[cuenta] = to_float(row.get("monto", 0))

    for cuenta, monto in SHEETS["saldos"]["default_rows"]:
        saldos.setdefault(cuenta, float(monto))

    return saldos


def save_saldos(saldos):
    records = [{"cuenta": key, "monto": round(float(value), 2)} for key, value in saldos.items()]
    replace_records("saldos", records)


def change_saldo(saldos, key, amount):
    saldos[key] = round(to_float(saldos.get(key, 0)) + float(amount), 2)


def get_config_value(key, default=""):
    df = load_df("config")
    if not df.empty:
        for _, row in df.iterrows():
            if str(row.get("clave", "")) == key:
                return str(row.get("valor", default))
    return default


def set_config_value(key, value):
    df = load_df("config")
    records = []
    found = False

    if not df.empty:
        for _, row in df.iterrows():
            if str(row.get("clave", "")) == key:
                records.append({"clave": key, "valor": value})
                found = True
            else:
                records.append({"clave": row.get("clave", ""), "valor": row.get("valor", "")})

    if not found:
        records.append({"clave": key, "valor": value})

    replace_records("config", records)



def get_next_personal_payment_date(frequency, today=None):
    today = today or mx_now().date()
    frequency = str(frequency).lower().strip()

    if frequency == "semanal":
        # Domingo como cierre semanal.
        days_until_sunday = (6 - today.weekday()) % 7
        return today + timedelta(days=days_until_sunday)

    if frequency == "quincenal":
        if today.day <= 15:
            return today.replace(day=15)
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        return last_day

    # Mensual: último día del mes.
    next_month = today.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return last_day


def record_family_income_from_norte(fecha, producto, amount, nota):
    append_record("gastos_familiares", {
        **fecha,
        "tipo": "ingreso",
        "categoria": "pago de Norte Brunch",
        "producto": producto,
        "monto": amount,
        "metodo_pago": "Norte Brunch",
        "nota": nota,
    })


def claim_personal_profit(fecha):
    saldos = get_saldos()
    amount = round(float(saldos["ganancia_pendiente_personal"]), 2)

    if amount <= 0:
        st.error("No hay ganancia pendiente para pagarte.")
        return

    if amount > saldos["dinero_norte_brunch"]:
        st.error("Norte Brunch no tiene suficiente dinero para pagarte toda la ganancia pendiente.")
        return

    change_saldo(saldos, "dinero_norte_brunch", -amount)
    change_saldo(saldos, "ganancia_pendiente_personal", -amount)
    change_saldo(saldos, "ganancia_pagada_personal", amount)
    change_saldo(saldos, "dinero_familiar", amount)
    change_saldo(saldos, "ingresos_familiares_totales", amount)
    save_saldos(saldos)

    record_family_income_from_norte(
        fecha,
        "Pago de ganancia personal",
        amount,
        "Pago automático de ganancia personal de Norte Brunch",
    )

    big_green_amount("Pago personal realizado", amount)
    st.success("Se registró automáticamente como ingreso familiar.")


def calculate_investment_repayment_status(saldos):
    available = round(
        float(saldos["dinero_norte_brunch"]) - float(saldos["ganancia_pendiente_personal"]),
        2,
    )
    debt = round(float(saldos["deuda_inversion_personal"]), 2)

    if debt <= 0:
        return {
            "available": available,
            "debt": debt,
            "can_pay": False,
            "suggested_payment": 0,
            "message": "Norte Brunch no tiene deuda pendiente contigo.",
        }

    if available >= MIN_INVESTMENT_REPAYMENT_ALERT or (available >= debt and debt > 0):
        suggested = min(debt, available, MIN_INVESTMENT_REPAYMENT_ALERT if debt >= MIN_INVESTMENT_REPAYMENT_ALERT else debt)
        return {
            "available": available,
            "debt": debt,
            "can_pay": suggested > 0,
            "suggested_payment": round(suggested, 2),
            "message": "Norte Brunch ya tiene dinero disponible para abonarte a tu inversión.",
        }

    return {
        "available": available,
        "debt": debt,
        "can_pay": False,
        "suggested_payment": 0,
        "message": f"Aún no hay $10,000 libres para abonarte. Disponible estimado: {pesos(available)}.",
    }


def repay_investment_suggested(fecha):
    saldos = get_saldos()
    status = calculate_investment_repayment_status(saldos)
    amount = status["suggested_payment"]

    if amount <= 0:
        st.error("Aún no hay pago sugerido para recuperar inversión.")
        return

    if amount > saldos["dinero_norte_brunch"]:
        st.error("Norte Brunch no tiene suficiente dinero.")
        return

    change_saldo(saldos, "dinero_norte_brunch", -amount)
    change_saldo(saldos, "deuda_inversion_personal", -amount)
    change_saldo(saldos, "inversion_pagada_personal", amount)
    change_saldo(saldos, "dinero_familiar", amount)
    change_saldo(saldos, "ingresos_familiares_totales", amount)
    save_saldos(saldos)

    append_record("inversiones", {
        **fecha,
        "tipo": "pago_inversion",
        "monto": amount,
        "nota": "Abono automático sugerido para recuperar inversión",
    })

    record_family_income_from_norte(
        fecha,
        "Recuperación de inversión",
        amount,
        "Abono de Norte Brunch para recuperar inversión personal",
    )

    big_green_amount("Abono de inversión recuperado", amount)
    st.success("Se registró automáticamente como ingreso familiar.")


def load_categories(sheet_key):
    df = load_df(sheet_key)
    if df.empty:
        return []

    if "activo" not in df.columns:
        df["activo"] = "si"

    categories = []
    for _, row in df.iterrows():
        category = str(row.get("categoria", "")).strip()
        active = str(row.get("activo", "si")).lower().strip()
        if category and active != "no":
            categories.append(category)

    return sorted(set(categories))


def add_category(sheet_key, category):
    category = category.strip().lower()
    if not category:
        return
    current = [c.lower() for c in load_categories(sheet_key)]
    if category not in current:
        append_record(sheet_key, {"categoria": category, "activo": "si"})


def get_previous_values(sheet_key, column_name):
    """Regresa valores únicos ya usados para simular autocompletado con selectbox."""
    df = load_df(sheet_key)
    if df.empty or column_name not in df.columns:
        return []

    values = []
    for value in df[column_name].dropna().tolist():
        text = str(value).strip()
        if text and text.lower() not in [v.lower() for v in values]:
            values.append(text)

    return sorted(values, key=str.lower)


def autocomplete_or_new(label, previous_values, key_prefix, placeholder="Escribe el nombre"):
    """Permite elegir un valor anterior o escribir uno nuevo."""
    options = ["Escribir nuevo"] + previous_values
    choice = st.selectbox(label, options, key=f"{key_prefix}_choice")

    if choice == "Escribir nuevo":
        return st.text_input(placeholder, key=f"{key_prefix}_new").strip()

    custom = st.text_input(
        "Editar nombre si quieres",
        value=choice,
        key=f"{key_prefix}_edit",
    ).strip()
    return custom or choice


# -----------------------------
# SEGURIDAD
# -----------------------------

def check_password():
    if "app" not in st.secrets or "password" not in st.secrets["app"]:
        st.error("Falta configurar la contraseña en Streamlit Secrets.")
        st.info('Agrega:\n\n[app]\npassword = "TU_PASSWORD_AQUI"')
        return False

    if st.session_state.get("authenticated", False):
        return True

    st.subheader("Acceso privado")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        if password == st.secrets["app"]["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    return False


# -----------------------------
# PRODUCTOS
# -----------------------------

def load_active_products():
    df = load_df("productos")
    if df.empty:
        return df

    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
    df["ganancia_personal"] = pd.to_numeric(df["ganancia_personal"], errors="coerce").fillna(0)
    df["activo"] = df["activo"].astype(str).str.lower().fillna("si")
    return df[df["activo"] != "no"].copy()


def page_productos():
    st.header("Productos")

    df = load_df("productos")
    st.dataframe(df, use_container_width=True)

    st.subheader("Agregar o modificar producto")
    with st.form("producto_form"):
        producto = st.text_input("Producto")
        precio = st.number_input("Precio de venta", min_value=0.0, step=1.0)
        ganancia = st.number_input("Ganancia personal por unidad", min_value=0.0, step=1.0)
        activo = st.selectbox("Activo", ["si", "no"])
        guardar = st.form_submit_button("Guardar producto")

    if guardar:
        if not producto.strip():
            st.error("Escribe el nombre del producto.")
            return

        df = load_df("productos")
        records = []
        updated = False

        for _, row in df.iterrows():
            current = str(row.get("producto", "")).strip().lower()
            if current == producto.strip().lower():
                records.append({
                    "producto": producto.strip(),
                    "precio": precio,
                    "ganancia_personal": ganancia,
                    "activo": activo,
                })
                updated = True
            else:
                records.append({
                    "producto": row.get("producto", ""),
                    "precio": row.get("precio", 0),
                    "ganancia_personal": row.get("ganancia_personal", 0),
                    "activo": row.get("activo", "si"),
                })

        if not updated:
            records.append({
                "producto": producto.strip(),
                "precio": precio,
                "ganancia_personal": ganancia,
                "activo": activo,
            })

        replace_records("productos", records)
        st.success("Producto guardado.")
        st.rerun()


# -----------------------------
# PEDIDOS / VENTAS
# -----------------------------

def init_cart():
    if "cart" not in st.session_state:
        st.session_state.cart = []


def load_records_with_row_numbers(sheet_key):
    """Carga registros incluyendo el número real de fila en Google Sheets."""
    ws = get_ws(sheet_key)
    records = google_call(ws.get_all_records)
    result = []
    for index, record in enumerate(records, start=2):
        record["__row_number__"] = index
        result.append(record)
    return result


def update_cell_by_header(sheet_key, row_number, header, value):
    ws = get_ws(sheet_key)
    headers = get_actual_headers(sheet_key)
    if header not in headers:
        raise ValueError(f"No existe la columna {header} en {sheet_key}.")
    col = headers.index(header) + 1
    google_call(ws.update_cell, row_number, col, value)
    clear_data_cache()


def update_pedido_estado(pedido_id, new_status):
    records = load_records_with_row_numbers("pedidos")
    for record in records:
        if str(record.get("pedido_id", "")) == str(pedido_id):
            update_cell_by_header("pedidos", record["__row_number__"], "estado", new_status)
    clear_data_cache()


def add_product_to_cart(products, product, quantity=1):
    row = products[products["producto"] == product].iloc[0]
    unit_price = to_float(row["precio"])
    unit_profit = to_float(row["ganancia_personal"])

    line_total = round(quantity * unit_price, 2)
    line_profit = round(quantity * unit_profit, 2)
    line_norte = round(line_total - line_profit, 2)
    line_tithing = round(line_profit * TITHING_RATE, 2)

    st.session_state.cart.append({
        "producto": product,
        "cantidad": int(quantity),
        "precio_unitario": unit_price,
        "ganancia_personal_unitaria": unit_profit,
        "total_linea": line_total,
        "ganancia_personal_linea": line_profit,
        "dinero_norte_linea": line_norte,
        "diezmo_linea": line_tithing,
    })


def calculate_cart_totals(items):
    if not items:
        return {"total": 0, "profit": 0, "tithing": 0, "norte": 0}

    df = pd.DataFrame(items)
    return {
        "total": round(df["total_linea"].sum(), 2),
        "profit": round(df["ganancia_personal_linea"].sum(), 2),
        "tithing": round(df["diezmo_linea"].sum(), 2),
        "norte": round(df["dinero_norte_linea"].sum(), 2),
    }


def get_next_order_number_for_date(order_date):
    date_text = order_date.strftime("%Y-%m-%d")
    df = load_df("pedidos")

    if df.empty or "fecha" not in df.columns or "pedido_numero" not in df.columns:
        return 1

    same_day = df[df["fecha"].astype(str) == date_text]
    numbers = []

    for value in same_day["pedido_numero"].dropna().tolist():
        text = str(value).replace("Pedido", "").strip()
        try:
            numbers.append(int(text))
        except ValueError:
            continue

    return max(numbers, default=0) + 1


def create_pending_order(fecha, note):
    if not st.session_state.cart:
        st.error("El pedido está vacío.")
        return

    order_number = get_next_order_number_for_date(datetime.strptime(fecha["fecha"], "%Y-%m-%d").date())
    pedido_numero = f"Pedido {order_number}"
    pedido_id = f"{fecha['fecha'].replace('-', '')}-{order_number}-{str(uuid.uuid4())[:4]}"

    for item in st.session_state.cart:
        append_record("pedidos", {
            **fecha,
            "pedido_id": pedido_id,
            "pedido_numero": pedido_numero,
            "estado": "pendiente",
            "producto": item["producto"],
            "cantidad": item["cantidad"],
            "precio_unitario": item["precio_unitario"],
            "ganancia_personal_unitaria": item["ganancia_personal_unitaria"],
            "total_linea": item["total_linea"],
            "ganancia_personal_linea": item["ganancia_personal_linea"],
            "dinero_norte_linea": item["dinero_norte_linea"],
            "diezmo_linea": item["diezmo_linea"],
            "nota": note,
        })

    st.session_state.cart = []
    st.success(f"{pedido_numero} creado como pendiente. No cuenta como venta hasta que se pague.")
    st.rerun()


def get_pending_orders_df():
    df = load_df("pedidos")
    if df.empty:
        return df

    if "estado" not in df.columns:
        df["estado"] = ""

    df = df[df["estado"].astype(str).str.lower() == "pendiente"].copy()
    df = to_numeric(df, [
        "cantidad",
        "precio_unitario",
        "ganancia_personal_unitaria",
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
        "diezmo_linea",
    ])
    return df


def get_order_lines_with_rows(pedido_id):
    records = load_records_with_row_numbers("pedidos")
    lines = []
    for record in records:
        if (
            str(record.get("pedido_id", "")) == str(pedido_id)
            and str(record.get("estado", "")).lower() == "pendiente"
        ):
            lines.append(record)
    return lines


def append_line_to_pending_order(pedido_id, pedido_numero, fecha, product_row, quantity, note):
    unit_price = to_float(product_row["precio"])
    unit_profit = to_float(product_row["ganancia_personal"])
    quantity = int(quantity)

    line_total = round(quantity * unit_price, 2)
    line_profit = round(quantity * unit_profit, 2)
    line_norte = round(line_total - line_profit, 2)
    line_tithing = round(line_profit * TITHING_RATE, 2)

    append_record("pedidos", {
        **fecha,
        "pedido_id": pedido_id,
        "pedido_numero": pedido_numero,
        "estado": "pendiente",
        "producto": product_row["producto"],
        "cantidad": quantity,
        "precio_unitario": unit_price,
        "ganancia_personal_unitaria": unit_profit,
        "total_linea": line_total,
        "ganancia_personal_linea": line_profit,
        "dinero_norte_linea": line_norte,
        "diezmo_linea": line_tithing,
        "nota": note,
    })


def calculate_payment_amounts(total, method, cash_amount=0, card_amount=0, transfer_amount=0):
    if method == "Efectivo":
        cash_amount, card_amount, transfer_amount = total, 0, 0
    elif method == "Tarjeta":
        cash_amount, card_amount, transfer_amount = 0, total, 0
    elif method == "Transferencia":
        cash_amount, card_amount, transfer_amount = 0, 0, total

    cash_amount = round(float(cash_amount), 2)
    card_amount = round(float(card_amount), 2)
    transfer_amount = round(float(transfer_amount), 2)
    paid_total = round(cash_amount + card_amount + transfer_amount, 2)
    terminal_fee = round(card_amount * CARD_FEE_RATE, 2)
    net_received = round(paid_total - terminal_fee, 2)

    return {
        "cash": cash_amount,
        "card": card_amount,
        "transfer": transfer_amount,
        "paid_total": paid_total,
        "terminal_fee": terminal_fee,
        "net_received": net_received,
    }


def pay_pending_order(pedido_id, payment_date, method, amounts, note):
    lines = get_order_lines_with_rows(pedido_id)

    if not lines:
        st.error("Este pedido ya no tiene líneas pendientes.")
        return

    df = pd.DataFrame(lines)
    df = to_numeric(df, [
        "cantidad",
        "precio_unitario",
        "ganancia_personal_unitaria",
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
        "diezmo_linea",
    ])

    total = round(df["total_linea"].sum(), 2)
    profit = round(df["ganancia_personal_linea"].sum(), 2)
    tithing = round(df["diezmo_linea"].sum(), 2)

    if abs(amounts["paid_total"] - total) > 0.01:
        st.error(f"El total pagado debe ser igual a {pesos(total)}.")
        return

    if total <= 0:
        st.error("El pedido tiene total cero.")
        return

    for _, line in df.iterrows():
        share = to_float(line["total_linea"]) / total

        cash_line = round(amounts["cash"] * share, 2)
        card_line = round(amounts["card"] * share, 2)
        transfer_line = round(amounts["transfer"] * share, 2)
        fee_line = round(card_line * CARD_FEE_RATE, 2)

        total_line = to_float(line["total_linea"])
        profit_line = to_float(line["ganancia_personal_linea"])
        net_line = round(total_line - fee_line, 2)
        norte_line = round(total_line - profit_line - fee_line, 2)

        append_record("ventas", {
            **payment_date,
            "pedido_id": line.get("pedido_id", pedido_id),
            "pedido_numero": line.get("pedido_numero", ""),
            "producto": line.get("producto", ""),
            "cantidad": line.get("cantidad", 0),
            "precio_unitario": line.get("precio_unitario", 0),
            "ganancia_personal_unitaria": line.get("ganancia_personal_unitaria", 0),
            "total_linea": total_line,
            "ganancia_personal_linea": profit_line,
            "dinero_norte_linea": norte_line,
            "diezmo_linea": line.get("diezmo_linea", 0),
            "metodo_pago": method,
            "monto_efectivo_linea": cash_line,
            "monto_tarjeta_linea": card_line,
            "monto_transferencia_linea": transfer_line,
            "comision_terminal_linea": fee_line,
            "total_neto_linea": net_line,
            "nota": note,
        })

    update_pedido_estado(pedido_id, "pagado")

    saldos = get_saldos()
    change_saldo(saldos, "dinero_norte_brunch", amounts["net_received"])
    change_saldo(saldos, "ganancia_pendiente_personal", profit)
    change_saldo(saldos, "diezmo_pendiente", tithing)
    save_saldos(saldos)

    big_green_amount("PEDIDO PAGADO", amounts["net_received"])
    st.success(
        f"Pedido pagado. Total bruto: {pesos(total)} | Comisión terminal: {pesos(amounts['terminal_fee'])} | Neto recibido: {pesos(amounts['net_received'])}"
    )
    st.rerun()


def render_current_cart(products):
    st.subheader("Pedido nuevo en preparación")

    if not st.session_state.cart:
        st.info("El pedido nuevo está vacío.")
        return

    cart_df = pd.DataFrame(st.session_state.cart)
    st.dataframe(cart_df, use_container_width=True)

    totals = calculate_cart_totals(st.session_state.cart)

    big_red_amount("TOTAL A COBRAR", totals["total"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Ganancia", pesos(totals["profit"]))
    c2.metric("Diezmo", pesos(totals["tithing"]))
    c3.metric("Para Norte", pesos(totals["norte"]))

    st.write("**Quitar producto antes de crear el pedido**")
    labels = [
        f"{i + 1}. {item['producto']} x{item['cantidad']} - {pesos(item['total_linea'])}"
        for i, item in enumerate(st.session_state.cart)
    ]
    selected = st.selectbox("Producto a quitar", labels, key="remove_cart_select")

    col_remove, col_clear = st.columns(2)
    if col_remove.button("Quitar producto del pedido nuevo"):
        index = labels.index(selected)
        st.session_state.cart.pop(index)
        st.rerun()

    if col_clear.button("Vaciar pedido nuevo"):
        st.session_state.cart = []
        st.rerun()

    st.divider()
    fecha = datetime_inputs("pedido_nuevo", "Fecha y hora del pedido")
    note = st.text_input("Nota del pedido pendiente", placeholder="Opcional", key="nota_pedido_nuevo")

    if st.button("Crear pedido pendiente", type="primary"):
        create_pending_order(fecha, note)


def render_pending_orders(products):
    st.subheader("Pedidos pendientes")

    pending = get_pending_orders_df()
    if pending.empty:
        st.info("No hay pedidos pendientes.")
        return

    grouped = pending.groupby(["pedido_id", "pedido_numero", "fecha"]).agg({
        "total_linea": "sum",
        "ganancia_personal_linea": "sum",
        "diezmo_linea": "sum",
    }).reset_index()

    grouped = grouped.sort_values(["fecha", "pedido_numero"])
    labels = []
    label_to_id = {}

    for _, row in grouped.iterrows():
        label = f"{row['pedido_numero']} | {row['fecha']} | Total {pesos(row['total_linea'])}"
        labels.append(label)
        label_to_id[label] = row["pedido_id"]

    selected_label = st.selectbox("Selecciona pedido", labels)
    pedido_id = label_to_id[selected_label]
    lines = get_order_lines_with_rows(pedido_id)

    if not lines:
        st.warning("Este pedido ya no tiene productos pendientes.")
        return

    lines_df = pd.DataFrame(lines)
    lines_df = to_numeric(lines_df, [
        "cantidad",
        "precio_unitario",
        "total_linea",
        "ganancia_personal_linea",
        "diezmo_linea",
    ])

    pedido_numero = str(lines_df.iloc[0]["pedido_numero"])
    order_date = str(lines_df.iloc[0]["fecha"])
    order_time = str(lines_df.iloc[0]["hora"])

    st.write(f"### {pedido_numero}")
    st.caption(f"Creado: {order_date} {order_time}")
    st.dataframe(lines_df.drop(columns=["__row_number__"], errors="ignore"), use_container_width=True)

    total = round(lines_df["total_linea"].sum(), 2)
    profit = round(lines_df["ganancia_personal_linea"].sum(), 2)
    tithing = round(lines_df["diezmo_linea"].sum(), 2)

    big_red_amount("TOTAL A COBRAR", total)

    c1, c2 = st.columns(2)
    c1.metric("Ganancia personal", pesos(profit))
    c2.metric("Diezmo", pesos(tithing))

    with st.expander("Modificar pedido pendiente"):
        st.write("**Agregar producto**")
        product_names = products["producto"].tolist()

        with st.form(f"add_to_pending_{pedido_id}"):
            col1, col2 = st.columns([2, 1])
            product = col1.selectbox("Producto", product_names, key=f"prod_pending_{pedido_id}")
            quantity = col2.number_input("Cantidad", min_value=1, step=1, key=f"qty_pending_{pedido_id}")
            note = st.text_input("Nota", placeholder="Opcional", key=f"note_pending_{pedido_id}")
            add = st.form_submit_button("Agregar al pedido pendiente")

        if add:
            product_row = products[products["producto"] == product].iloc[0]
            fecha = {
                "fecha_hora": f"{order_date} {order_time}",
                "fecha": order_date,
                "hora": order_time,
            }
            append_line_to_pending_order(pedido_id, pedido_numero, fecha, product_row, quantity, note)
            st.success("Producto agregado al pedido pendiente.")
            st.rerun()

        st.write("**Quitar producto**")
        line_labels = []
        label_to_row = {}

        for _, row in lines_df.iterrows():
            label = f"{row['producto']} x{row['cantidad']} | {pesos(row['total_linea'])}"
            label = f"Fila {row['__row_number__']} - {label}"
            line_labels.append(label)
            label_to_row[label] = int(row["__row_number__"])

        selected_line = st.selectbox("Producto a quitar del pedido", line_labels, key=f"remove_pending_{pedido_id}")

        if st.button("Quitar producto seleccionado", key=f"btn_remove_pending_{pedido_id}"):
            update_cell_by_header("pedidos", label_to_row[selected_line], "estado", "eliminado")
            st.success("Producto quitado del pedido pendiente.")
            st.rerun()

        if st.button("Cancelar pedido completo", key=f"cancel_pending_{pedido_id}"):
            update_pedido_estado(pedido_id, "cancelado")
            st.success("Pedido cancelado.")
            st.rerun()

    st.divider()
    st.subheader("Cobrar pedido")

    big_red_amount("TOTAL PENDIENTE DE PAGO", total)

    payment_date = datetime_inputs(f"pago_{pedido_id}", "Fecha y hora de pago")
    method = st.radio(
        "Método de pago",
        ["Efectivo", "Tarjeta", "Transferencia", "Mixto"],
        horizontal=True,
        key=f"pay_method_{pedido_id}",
    )

    cash_amount = card_amount = transfer_amount = 0.0

    if method == "Mixto":
        st.caption("En pago mixto, la suma de efectivo + tarjeta + transferencia debe dar el total del pedido.")
        col1, col2, col3 = st.columns(3)
        cash_amount = col1.number_input("Efectivo", min_value=0.0, step=10.0, key=f"cash_{pedido_id}")
        card_amount = col2.number_input("Tarjeta", min_value=0.0, step=10.0, key=f"card_{pedido_id}")
        transfer_amount = col3.number_input("Transferencia", min_value=0.0, step=10.0, key=f"transfer_{pedido_id}")
    else:
        st.info(f"Se cobrará el total de {pesos(total)} como {method}.")

    amounts = calculate_payment_amounts(total, method, cash_amount, card_amount, transfer_amount)

    if amounts["card"] > 0:
        st.warning(
            f"Comisión de terminal 3.5% sobre tarjeta: {pesos(amounts['terminal_fee'])}. Neto recibido: {pesos(amounts['net_received'])}."
        )
    else:
        st.info(f"Neto recibido: {pesos(amounts['net_received'])}.")

    payment_note = st.text_input("Nota del pago", placeholder="Opcional", key=f"payment_note_{pedido_id}")

    if st.button("Marcar como pagado", type="primary", key=f"pay_{pedido_id}"):
        pay_pending_order(pedido_id, payment_date, method, amounts, payment_note)


def page_registrar_pedido():
    init_cart()
    st.header("Registrar pedido")

    products = load_active_products()
    if products.empty:
        st.warning("No hay productos activos.")
        return

    product_names = products["producto"].tolist()

    tab_new, tab_pending = st.tabs(["Nuevo pedido", "Pedidos pendientes"])

    with tab_new:
        st.subheader("Venta rápida")
        st.caption("Toca un botón para agregar 1 unidad al pedido nuevo.")

        for i in range(0, len(product_names), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                index = i + j
                if index >= len(product_names):
                    continue
                product = product_names[index]
                row = products[products["producto"] == product].iloc[0]
                label = f"{product}\n{pesos(row['precio'])}"
                if col.button(label, key=f"quick_{product}", use_container_width=True):
                    add_product_to_cart(products, product, 1)
                    st.rerun()

        st.divider()
        st.subheader("Agregar con cantidad")

        with st.form("add_to_cart"):
            col1, col2 = st.columns([2, 1])
            product = col1.selectbox("Producto", product_names)
            quantity = col2.number_input("Cantidad", min_value=1, step=1)
            add = st.form_submit_button("Agregar al pedido nuevo")

        if add:
            add_product_to_cart(products, product, quantity)
            st.rerun()

        st.divider()
        render_current_cart(products)

    with tab_pending:
        render_pending_orders(products)

# -----------------------------
# GASTOS LOCAL / INVENTARIO
# -----------------------------

def update_inventory(insumo, amount, unit):
    insumo = insumo.strip()
    if not insumo or amount == 0:
        return

    df = load_df("inventario")
    records = []
    updated = False

    if not df.empty:
        for _, row in df.iterrows():
            current = str(row.get("insumo", "")).strip().lower()
            if current == insumo.lower():
                records.append({
                    "insumo": row.get("insumo", insumo),
                    "cantidad": round(to_float(row.get("cantidad", 0)) + amount, 2),
                    "unidad": unit,
                })
                updated = True
            else:
                records.append({
                    "insumo": row.get("insumo", ""),
                    "cantidad": row.get("cantidad", 0),
                    "unidad": row.get("unidad", ""),
                })

    if not updated:
        records.append({"insumo": insumo, "cantidad": round(amount, 2), "unidad": unit})

    replace_records("inventario", records)


def page_gastos_inventario():
    st.header("Gastos e inventario de Norte Brunch")

    tab1, tab2 = st.tabs(["Registrar gasto", "Inventario"])

    with tab1:
        st.caption("Categorías simplificadas: insumos, local y transporte.")

        with st.form("gasto_local_form"):
            fecha = datetime_inputs("gasto_local", "Fecha y hora del gasto")

            categoria = st.selectbox(
                "Tipo de gasto de Norte Brunch",
                ["insumos", "local", "transporte"],
            )

            previous_names = get_previous_values("gastos_local", "nombre")
            nombre = autocomplete_or_new(
                "Producto / gasto",
                previous_names,
                "local_product",
                placeholder="Ej. pan, carne, renta, gas, Uber, gasolina",
            )

            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad", value="piezas")
            costo = st.number_input("Costo total", min_value=0.0, step=10.0)
            pagado_por = st.radio("Pagado por", ["Norte Brunch", "Personal/Familiar"], horizontal=True)
            nota = st.text_input("Nota", placeholder="Opcional")
            guardar = st.form_submit_button("Guardar gasto")

        if guardar:
            if not nombre.strip() or costo <= 0:
                st.error("Falta nombre del producto/gasto o costo.")
                return

            tipo_movimiento = "Compra de insumo" if categoria == "insumos" else "Gasto del local"

            append_record("gastos_local", {
                **fecha,
                "tipo_movimiento": tipo_movimiento,
                "nombre": nombre.strip(),
                "categoria": categoria,
                "cantidad": cantidad,
                "unidad": unidad,
                "costo_total": costo,
                "pagado_por": pagado_por,
                "nota": nota,
            })

            saldos = get_saldos()
            change_saldo(saldos, "total_gastos_negocio", costo)

            if pagado_por == "Norte Brunch":
                change_saldo(saldos, "dinero_norte_brunch", -costo)
                change_saldo(saldos, "gastos_pagados_norte", costo)
            else:
                change_saldo(saldos, "gastos_pagados_personal", costo)
                change_saldo(saldos, "inversion_personal_total", costo)
                change_saldo(saldos, "deuda_inversion_personal", costo)
                change_saldo(saldos, "dinero_familiar", -costo)
                change_saldo(saldos, "gastos_familiares_totales", costo)
                append_record("gastos_familiares", {
                    **fecha,
                    "tipo": "gasto",
                    "categoria": "hogar",
                    "producto": f"Norte Brunch - {nombre.strip()}",
                    "monto": costo,
                    "metodo_pago": "Personal/Familiar",
                    "nota": "Gasto de Norte Brunch pagado con dinero personal/familiar",
                })

            save_saldos(saldos)

            if categoria == "insumos":
                update_inventory(nombre.strip(), cantidad, unidad)

            st.success("Gasto guardado.")
            st.rerun()

    with tab2:
        st.subheader("Inventario")
        st.dataframe(load_df("inventario"), use_container_width=True)

        with st.form("descontar_inventario"):
            previous_items = get_previous_values("inventario", "insumo")
            insumo = autocomplete_or_new(
                "Insumo",
                previous_items,
                "inventory_item",
                placeholder="Ej. pan, carne, queso",
            )
            cantidad_usada = st.number_input("Cantidad usada", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad", value="piezas")
            descontar = st.form_submit_button("Descontar")

        if descontar:
            update_inventory(insumo, -cantidad_usada, unidad)
            st.success("Inventario actualizado.")
            st.rerun()


# -----------------------------
# FINANZAS FAMILIARES
# -----------------------------

def page_finanzas_familiares():
    st.header("Finanzas familiares")

    saldos = get_saldos()
    col1, col2, col3 = st.columns(3)
    col1.metric("Dinero familiar", pesos(saldos["dinero_familiar"]))
    col2.metric("Ingresos familiares", pesos(saldos["ingresos_familiares_totales"]))
    col3.metric("Gastos familiares", pesos(saldos["gastos_familiares_totales"]))

    tab1, tab2 = st.tabs(["Registrar movimiento", "Reporte"])

    with tab1:
        st.caption("Gastos familiares: categoría Hogar. Ingresos manuales: solo Otros ingresos. Los pagos de Norte Brunch se registran automáticamente cuando te pagas.")

        with st.form("movimiento_familiar_form"):
            fecha = datetime_inputs("familia", "Fecha y hora del movimiento")
            tipo = st.radio("Tipo", ["gasto", "ingreso"], horizontal=True)

            if tipo == "gasto":
                categoria = "hogar"
                previous_products = get_previous_values("gastos_familiares", "producto")
                producto = autocomplete_or_new(
                    "Producto / gasto familiar",
                    previous_products,
                    "family_product",
                    placeholder="Ej. leche, despensa, pañales, gas, internet",
                )
            else:
                categoria = "otros ingresos"
                producto = st.text_input("Origen del ingreso", value="Otros ingresos")

            monto = st.number_input("Monto", min_value=0.0, step=50.0)
            metodo_pago = st.selectbox("Método / origen", ["Efectivo", "Tarjeta", "Transferencia", "Otro"])
            nota = st.text_input("Nota")
            guardar = st.form_submit_button("Guardar movimiento")

        if guardar:
            if monto <= 0:
                st.error("El monto debe ser mayor que cero.")
                return
            if not producto.strip():
                st.error("Escribe el producto, gasto u origen.")
                return

            append_record("gastos_familiares", {
                **fecha,
                "tipo": tipo,
                "categoria": categoria,
                "producto": producto.strip(),
                "monto": monto,
                "metodo_pago": metodo_pago,
                "nota": nota,
            })

            saldos = get_saldos()
            if tipo == "ingreso":
                change_saldo(saldos, "dinero_familiar", monto)
                change_saldo(saldos, "ingresos_familiares_totales", monto)
            else:
                change_saldo(saldos, "dinero_familiar", -monto)
                change_saldo(saldos, "gastos_familiares_totales", monto)

            save_saldos(saldos)
            st.success("Movimiento familiar guardado.")
            st.rerun()

    with tab2:
        start, end = period_filter_ui("familia")
        df = filter_date_range(load_df("gastos_familiares"), start, end)
        df = to_numeric(df, ["monto"])

        ingresos = df[df["tipo"] == "ingreso"]["monto"].sum() if not df.empty else 0
        gastos = df[df["tipo"] == "gasto"]["monto"].sum() if not df.empty else 0
        balance = ingresos - gastos

        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos", pesos(ingresos))
        c2.metric("Gastos", pesos(gastos))
        c3.metric("Balance", pesos(balance))

        if not df.empty:
            st.subheader("Resumen por producto")
            st.dataframe(df.groupby(["tipo", "categoria", "producto"])["monto"].sum().reset_index(), use_container_width=True)
            st.subheader("Movimientos")
            st.dataframe(df, use_container_width=True)


# -----------------------------
# REPORTES LOCAL Y CORTE
# -----------------------------

def page_reportes_local():
    st.header("Reportes del local")

    start_date, end_date = period_filter_ui("local")
    ventas = filter_date_range(load_df("ventas"), start_date, end_date)
    gastos = filter_date_range(load_df("gastos_local"), start_date, end_date)

    ventas = to_numeric(ventas, [
        "cantidad",
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
        "diezmo_linea",
        "monto_efectivo_linea",
        "monto_tarjeta_linea",
        "monto_transferencia_linea",
        "comision_terminal_linea",
        "total_neto_linea",
    ])
    gastos = to_numeric(gastos, ["costo_total"])

    total_ventas = ventas["total_linea"].sum() if not ventas.empty else 0
    total_recibido = ventas["total_neto_linea"].sum() if "total_neto_linea" in ventas.columns and not ventas.empty else total_ventas
    total_comision = ventas["comision_terminal_linea"].sum() if "comision_terminal_linea" in ventas.columns and not ventas.empty else 0
    total_ganancia = ventas["ganancia_personal_linea"].sum() if not ventas.empty else 0
    total_diezmo = ventas["diezmo_linea"].sum() if "diezmo_linea" in ventas.columns and not ventas.empty else round(total_ganancia * TITHING_RATE, 2)
    total_norte = ventas["dinero_norte_linea"].sum() if not ventas.empty else 0
    total_gastos = gastos["costo_total"].sum() if not gastos.empty else 0
    resultado = total_norte - total_gastos
    margen = (resultado / total_ventas * 100) if total_ventas else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventas brutas", pesos(total_ventas))
    col2.metric("Neto recibido", pesos(total_recibido))
    col3.metric("Comisión terminal", pesos(total_comision))
    col4.metric("Gastos", pesos(total_gastos))

    col5, col6, col7 = st.columns(3)
    col5.metric("Ganancia personal", pesos(total_ganancia))
    col6.metric("Diezmo", pesos(total_diezmo))
    col7.metric("Para Norte Brunch", pesos(total_norte))

    st.metric("Resultado neto del local", pesos(resultado), f"{margen:.2f}%")

    if resultado < 0:
        st.error("ROJO - El local perdió dinero en este periodo.")
    elif margen < 20:
        st.warning("AMARILLO - Hay ganancia, pero baja rentabilidad.")
    else:
        st.success("VERDE - Rentabilidad saludable.")

    if not ventas.empty:
        st.subheader("Ventas por producto")
        st.dataframe(
            ventas.groupby("producto").agg({
                "cantidad": "sum",
                "total_linea": "sum",
                "ganancia_personal_linea": "sum",
                "diezmo_linea": "sum",
                "comision_terminal_linea": "sum",
                "dinero_norte_linea": "sum",
            }).reset_index(),
            use_container_width=True,
        )

        st.subheader("Ventas por método de pago")
        payment_summary = pd.DataFrame({
            "método": ["Efectivo", "Tarjeta", "Transferencia"],
            "monto": [
                ventas["monto_efectivo_linea"].sum() if "monto_efectivo_linea" in ventas.columns else 0,
                ventas["monto_tarjeta_linea"].sum() if "monto_tarjeta_linea" in ventas.columns else 0,
                ventas["monto_transferencia_linea"].sum() if "monto_transferencia_linea" in ventas.columns else 0,
            ],
        })
        st.dataframe(payment_summary, use_container_width=True)

        ventas["dia_semana"] = ventas["dt"].dt.day_name().map(weekday_spanish)
        best_day = ventas.groupby("dia_semana")["total_linea"].sum().sort_values(ascending=False)
        if not best_day.empty:
            st.info(f"Mejor día del periodo: **{best_day.index[0]}** con {pesos(best_day.iloc[0])}.")

    if not gastos.empty:
        st.subheader("Gastos por categoría")
        st.dataframe(gastos.groupby("categoria")["costo_total"].sum().reset_index(), use_container_width=True)

    with st.expander("Ver datos detallados"):
        st.subheader("Ventas pagadas")
        st.dataframe(ventas, use_container_width=True)
        st.subheader("Gastos")
        st.dataframe(gastos, use_container_width=True)


def page_corte_caja():
    st.header("Corte de caja")

    selected_date = st.date_input("Fecha del corte", value=mx_now().date())
    ventas = filter_date_range(load_df("ventas"), selected_date, selected_date)
    gastos = filter_date_range(load_df("gastos_local"), selected_date, selected_date)

    ventas = to_numeric(ventas, [
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
        "diezmo_linea",
        "monto_efectivo_linea",
        "monto_tarjeta_linea",
        "monto_transferencia_linea",
        "comision_terminal_linea",
        "total_neto_linea",
    ])
    gastos = to_numeric(gastos, ["costo_total"])

    if ventas.empty:
        st.warning("No hay ventas pagadas en esa fecha.")
        return

    total_ventas = ventas["total_linea"].sum()
    total_recibido = ventas["total_neto_linea"].sum() if "total_neto_linea" in ventas.columns else total_ventas
    total_comision = ventas["comision_terminal_linea"].sum() if "comision_terminal_linea" in ventas.columns else 0
    ganancia = ventas["ganancia_personal_linea"].sum()
    diezmo = ventas["diezmo_linea"].sum() if "diezmo_linea" in ventas.columns else round(ganancia * TITHING_RATE, 2)
    dinero_norte = ventas["dinero_norte_linea"].sum()
    gastos_total = gastos["costo_total"].sum() if not gastos.empty else 0

    efectivo = ventas["monto_efectivo_linea"].sum() if "monto_efectivo_linea" in ventas.columns else 0
    tarjeta = ventas["monto_tarjeta_linea"].sum() if "monto_tarjeta_linea" in ventas.columns else 0
    transferencia = ventas["monto_transferencia_linea"].sum() if "monto_transferencia_linea" in ventas.columns else 0

    gastos_pagados_norte = 0
    if not gastos.empty and "pagado_por" in gastos.columns:
        gastos_pagados_norte = gastos[
            gastos["pagado_por"].astype(str).str.lower().str.contains("norte")
        ]["costo_total"].sum()

    efectivo_esperado = efectivo - gastos_pagados_norte

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas brutas", pesos(total_ventas))
    c2.metric("Neto recibido", pesos(total_recibido))
    c3.metric("Comisión terminal", pesos(total_comision))
    c4.metric("Gastos del día", pesos(gastos_total))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Ganancia personal", pesos(ganancia))
    c6.metric("Diezmo", pesos(diezmo))
    c7.metric("Para Norte Brunch", pesos(dinero_norte))
    c8.metric("Efectivo esperado", pesos(efectivo_esperado))

    st.subheader("Resumen por método de pago")
    st.dataframe(
        pd.DataFrame({
            "método": ["Efectivo", "Tarjeta", "Transferencia"],
            "monto": [efectivo, tarjeta, transferencia],
        }),
        use_container_width=True,
    )

    with st.expander("Ver ventas y gastos del día"):
        st.subheader("Ventas pagadas")
        st.dataframe(ventas, use_container_width=True)
        st.subheader("Gastos")
        st.dataframe(gastos, use_container_width=True)


# -----------------------------
# PLANEACIÓN DE COMPRAS / REINVERSIÓN
# -----------------------------

def get_sales_for_days(days):
    today = mx_now().date()
    start = today - timedelta(days=days - 1)
    ventas = filter_date_range(load_df("ventas"), start, today)
    ventas = to_numeric(ventas, ["cantidad", "total_linea"])
    return ventas, start, today


def get_recipe_df():
    recetas = load_df("recetas")
    if recetas.empty:
        return recetas

    recetas = to_numeric(recetas, ["cantidad_por_producto", "costo_unitario"])
    recetas["activo"] = recetas["activo"].astype(str).str.lower().replace("", "si")
    recetas = recetas[recetas["activo"] != "no"].copy()
    return recetas


def get_inventory_lookup():
    inventario = load_df("inventario")
    lookup = {}

    if inventario.empty:
        return lookup

    inventario = to_numeric(inventario, ["cantidad"])

    for _, row in inventario.iterrows():
        insumo = str(row.get("insumo", "")).strip().lower()
        unidad = str(row.get("unidad", "")).strip().lower()
        key = (insumo, unidad)
        lookup[key] = lookup.get(key, 0) + to_float(row.get("cantidad", 0))

    return lookup


def build_shopping_forecast(ventas, days_analyzed, projection_days, safety_margin):
    active_products = load_active_products()
    recetas = get_recipe_df()

    if active_products.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "No hay productos activos."

    product_names = active_products["producto"].tolist()

    if ventas.empty:
        sold_summary = pd.DataFrame({
            "producto": product_names,
            "cantidad_vendida": [0 for _ in product_names],
            "venta_total": [0 for _ in product_names],
            "promedio_diario": [0 for _ in product_names],
            "proyección_unidades": [0 for _ in product_names],
            "estado": ["Sin ventas en el periodo" for _ in product_names],
        })
        return sold_summary, pd.DataFrame(), recetas, "No hay ventas pagadas en el periodo elegido."

    by_product = ventas.groupby("producto").agg({
        "cantidad": "sum",
        "total_linea": "sum",
    }).reset_index()

    records = []
    for product in product_names:
        match = by_product[by_product["producto"] == product]
        if match.empty:
            qty = 0
            total = 0
        else:
            qty = to_float(match.iloc[0]["cantidad"])
            total = to_float(match.iloc[0]["total_linea"])

        daily_avg = qty / max(days_analyzed, 1)
        projected_units = daily_avg * projection_days * (1 + safety_margin)

        if qty == 0:
            status = "No se vendió"
        elif daily_avg >= 5:
            status = "Se mueve bien"
        elif daily_avg >= 1:
            status = "Se mueve poco"
        else:
            status = "Muy lento"

        records.append({
            "producto": product,
            "cantidad_vendida": round(qty, 2),
            "venta_total": round(total, 2),
            "promedio_diario": round(daily_avg, 2),
            "proyección_unidades": round(projected_units, 2),
            "estado": status,
        })

    sold_summary = pd.DataFrame(records)

    if recetas.empty:
        return sold_summary, pd.DataFrame(), recetas, "Falta configurar la hoja Recetas."

    inventory = get_inventory_lookup()
    shopping = []

    for _, product_row in sold_summary.iterrows():
        product = product_row["producto"]
        projected_units = to_float(product_row["proyección_unidades"])
        recipe_lines = recetas[recetas["producto"] == product]

        for _, recipe in recipe_lines.iterrows():
            insumo = str(recipe.get("insumo", "")).strip()
            unidad = str(recipe.get("unidad", "")).strip()
            cantidad_por_producto = to_float(recipe.get("cantidad_por_producto", 0))
            costo_unitario = to_float(recipe.get("costo_unitario", 0))

            required_qty = projected_units * cantidad_por_producto
            current_qty = inventory.get((insumo.lower(), unidad.lower()), 0)
            buy_qty = max(required_qty - current_qty, 0)
            estimated_cost = buy_qty * costo_unitario

            shopping.append({
                "producto_origen": product,
                "insumo": insumo,
                "unidad": unidad,
                "cantidad_requerida": round(required_qty, 3),
                "inventario_actual": round(current_qty, 3),
                "cantidad_a_comprar": round(buy_qty, 3),
                "costo_unitario": round(costo_unitario, 2),
                "costo_estimado": round(estimated_cost, 2),
            })

    shopping_df = pd.DataFrame(shopping)

    if not shopping_df.empty:
        shopping_summary = shopping_df.groupby(["insumo", "unidad"]).agg({
            "cantidad_requerida": "sum",
            "inventario_actual": "max",
            "cantidad_a_comprar": "sum",
            "costo_estimado": "sum",
        }).reset_index()
        shopping_summary["cantidad_requerida"] = shopping_summary["cantidad_requerida"].round(3)
        shopping_summary["cantidad_a_comprar"] = shopping_summary["cantidad_a_comprar"].round(3)
        shopping_summary["costo_estimado"] = shopping_summary["costo_estimado"].round(2)
    else:
        shopping_summary = pd.DataFrame()

    return sold_summary, shopping_summary, recetas, ""


def page_planeacion_compras():
    st.header("Planeación de compras y reinversión")
    st.caption("La app analiza ventas pagadas, productos que se mueven o no, y calcula cuánto comprar para la siguiente semana.")

    col1, col2, col3 = st.columns(3)
    days_analyzed = col1.number_input("Días a analizar", min_value=1, max_value=90, value=14, step=1)
    projection_days = col2.number_input("Días a proyectar", min_value=1, max_value=30, value=7, step=1)
    margin_pct = col3.number_input("Margen extra de seguridad (%)", min_value=0, max_value=100, value=15, step=5)

    ventas, start, end = get_sales_for_days(int(days_analyzed))
    sold_summary, shopping_summary, recetas, message = build_shopping_forecast(
        ventas,
        int(days_analyzed),
        int(projection_days),
        float(margin_pct) / 100,
    )

    st.info(f"Periodo analizado: {start.strftime('%Y-%m-%d')} a {end.strftime('%Y-%m-%d')}. Proyección: próximos {int(projection_days)} días.")

    if message:
        st.warning(message)

    if not sold_summary.empty:
        st.subheader("Qué se vende y qué no")
        st.dataframe(sold_summary, use_container_width=True)

        not_sold = sold_summary[sold_summary["cantidad_vendida"] <= 0]
        slow = sold_summary[sold_summary["estado"].isin(["Muy lento", "Se mueve poco"])]

        if not not_sold.empty:
            st.warning("Productos sin venta en el periodo: " + ", ".join(not_sold["producto"].tolist()))
        if not slow.empty:
            st.info("Productos lentos o con baja venta: " + ", ".join(slow["producto"].tolist()))

    if not shopping_summary.empty:
        total_to_spend = shopping_summary["costo_estimado"].sum()

        st.subheader("Lista estimada de compras")
        st.dataframe(shopping_summary, use_container_width=True)
        big_red_amount("Dinero estimado para reinvertir en compras", total_to_spend)

        st.subheader("Lectura rápida")
        for _, row in shopping_summary.iterrows():
            qty = to_float(row["cantidad_a_comprar"])
            if qty > 0:
                st.write(
                    f"- Comprar **{qty:g} {row['unidad']}** de **{row['insumo']}** "
                    f"≈ **{pesos(row['costo_estimado'])}**"
                )
    else:
        st.info("Todavía no hay lista de compras porque faltan ventas o recetas.")

    st.divider()
    st.subheader("Configurar recetas e insumos")
    st.caption("Edita aquí cuánto insumo usa cada producto y cuánto cuesta cada unidad. Esto alimenta la planeación.")

    with st.expander("Ver recetas actuales"):
        st.dataframe(recetas, use_container_width=True)

    with st.form("receta_form"):
        productos = load_active_products()["producto"].tolist()
        producto = st.selectbox("Producto vendido", productos)
        insumo = st.text_input("Insumo", placeholder="Ej. carne adobada, aguacate, pan")
        cantidad = st.number_input("Cantidad usada por producto", min_value=0.0, step=0.01, format="%.3f")
        unidad = st.selectbox("Unidad", ["kg", "pieza", "litro", "paquete", "otro"])
        costo_unitario = st.number_input("Costo por unidad", min_value=0.0, step=1.0)
        activo = st.selectbox("Activo", ["si", "no"])
        guardar = st.form_submit_button("Agregar receta/insumo")

    if guardar:
        if not insumo.strip() or cantidad <= 0:
            st.error("Falta insumo o cantidad.")
            return

        append_record("recetas", {
            "producto": producto,
            "insumo": insumo.strip().lower(),
            "cantidad_por_producto": cantidad,
            "unidad": unidad,
            "costo_unitario": costo_unitario,
            "activo": activo,
        })
        st.success("Receta agregada.")
        st.rerun()


# -----------------------------
# SALDOS, INVERSIONES Y DIEZMO
# -----------------------------

def page_saldos_local():
    st.header("Saldos del local")

    saldos = get_saldos()
    disponible_deuda = float(saldos["dinero_norte_brunch"]) - float(saldos["ganancia_pendiente_personal"])
    status = calculate_investment_repayment_status(saldos)

    c1, c2, c3 = st.columns(3)
    c1.metric("Dinero Norte Brunch", pesos(saldos["dinero_norte_brunch"]))
    c2.metric("Ganancia pendiente para mí", pesos(saldos["ganancia_pendiente_personal"]))
    c3.metric("Deuda de Norte Brunch hacia mí", pesos(saldos["deuda_inversion_personal"]))

    c4, c5, c6 = st.columns(3)
    c4.metric("Ganancia pagada", pesos(saldos["ganancia_pagada_personal"]))
    c5.metric("Inversión recuperada", pesos(saldos["inversion_pagada_personal"]))
    c6.metric("Disponible para deuda", pesos(disponible_deuda))

    st.info("La deuda hacia ti se genera automáticamente cuando pagas gastos de Norte Brunch con dinero personal/familiar.")

    if status["debt"] <= 0:
        st.success("Norte Brunch no tiene deuda pendiente contigo.")
    elif status["can_pay"]:
        st.markdown(
            f"""
            <div class="nb-warning-card">
                <b>Ya hay pago para recuperar inversión.</b><br>
                Disponible estimado después de apartar tu ganancia: <b>{pesos(status['available'])}</b><br>
                Deuda pendiente: <b>{pesos(status['debt'])}</b><br>
                Abono sugerido: <b>{pesos(status['suggested_payment'])}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning(status["message"])


def page_pago_personal():
    st.header("Pago personal")

    saldos = get_saldos()
    frecuencia_actual = get_config_value("frecuencia_pago_personal", "semanal")
    opciones = ["semanal", "quincenal", "mensual"]

    st.subheader("Frecuencia de pago")
    nueva_frecuencia = st.selectbox(
        "Elige cada cuándo quieres pagarte",
        opciones,
        index=opciones.index(frecuencia_actual) if frecuencia_actual in opciones else 0,
    )

    if st.button("Guardar frecuencia de pago"):
        set_config_value("frecuencia_pago_personal", nueva_frecuencia)
        st.success("Frecuencia guardada.")
        st.rerun()

    next_date = get_next_personal_payment_date(nueva_frecuencia)
    pending = float(saldos["ganancia_pendiente_personal"])

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Tu pago acumulado", pesos(pending))
    c2.metric("Próxima fecha sugerida", next_date.strftime("%Y-%m-%d"))
    c3.metric("Dinero Norte Brunch", pesos(saldos["dinero_norte_brunch"]))

    if pending > 0:
        big_green_amount("Pago personal disponible", pending)
    else:
        st.info("Todavía no hay ganancia pendiente para pagarte.")

    fecha = datetime_inputs("pago_personal", "Fecha y hora del pago personal")

    if st.button("Reclamar mi pago completo", type="primary"):
        claim_personal_profit(fecha)
        st.rerun()

    st.divider()
    st.subheader("Recuperación de inversión")

    status = calculate_investment_repayment_status(get_saldos())
    st.write(status["message"])

    if status["debt"] > 0:
        c4, c5, c6 = st.columns(3)
        c4.metric("Deuda pendiente", pesos(status["debt"]))
        c5.metric("Disponible estimado", pesos(status["available"]))
        c6.metric("Abono sugerido", pesos(status["suggested_payment"]))

    fecha_inv = datetime_inputs("abono_inversion", "Fecha y hora del abono de inversión")

    if status["can_pay"]:
        if st.button("Registrar abono sugerido para recuperar inversión", type="primary"):
            repay_investment_suggested(fecha_inv)
            st.rerun()
    else:
        st.info("El botón de recuperación aparecerá cuando haya al menos $10,000 disponibles o cuando la deuda final sea menor y ya pueda cubrirse.")


def page_diezmo():
    st.header("Diezmo")
    st.info("El diezmo pendiente se calcula automáticamente como 10% de la ganancia personal al guardar cada pedido.")

    saldos = get_saldos()
    frecuencia = get_config_value("frecuencia_diezmo", "mensual")

    c1, c2, c3 = st.columns(3)
    c1.metric("Frecuencia", frecuencia)
    c2.metric("Diezmo pendiente", pesos(saldos["diezmo_pendiente"]))
    c3.metric("Diezmo pagado", pesos(saldos["diezmo_pagado"]))

    nueva = st.selectbox(
        "Frecuencia de pago",
        ["semanal", "quincenal", "mensual"],
        index=["semanal", "quincenal", "mensual"].index(frecuencia) if frecuencia in ["semanal", "quincenal", "mensual"] else 2,
    )
    if st.button("Guardar frecuencia"):
        set_config_value("frecuencia_diezmo", nueva)
        st.success("Frecuencia guardada.")
        st.rerun()

    st.divider()
    st.subheader("Registrar pago de diezmo")

    fecha = datetime_inputs("diezmo", "Fecha y hora del pago")
    amount = st.number_input("Monto a pagar", min_value=0.0, step=10.0, value=float(saldos["diezmo_pendiente"]) if saldos["diezmo_pendiente"] > 0 else 0.0)
    note = st.text_input("Nota")

    if st.button("Pagar diezmo", type="primary"):
        if amount <= 0:
            st.error("El monto debe ser mayor que cero.")
            return
        if amount > saldos["diezmo_pendiente"]:
            st.error("No tienes tanto diezmo pendiente.")
            return
        if amount > saldos["dinero_familiar"]:
            st.error("No hay suficiente dinero familiar.")
            return

        change_saldo(saldos, "dinero_familiar", -amount)
        change_saldo(saldos, "gastos_familiares_totales", amount)
        change_saldo(saldos, "diezmo_pendiente", -amount)
        change_saldo(saldos, "diezmo_pagado", amount)
        save_saldos(saldos)

        append_record("diezmos", {**fecha, "monto": amount, "frecuencia": frecuencia, "nota": note})
        append_record("gastos_familiares", {
            **fecha,
            "tipo": "gasto",
            "categoria": "hogar",
            "producto": "Diezmo",
            "monto": amount,
            "metodo_pago": "Efectivo/Transferencia",
            "nota": "Pago de diezmo",
        })

        st.success("Diezmo registrado.")
        st.rerun()

    st.divider()
    start, end = period_filter_ui("diezmo_reporte")
    df = filter_date_range(load_df("diezmos"), start, end)
    df = to_numeric(df, ["monto"])
    st.metric("Diezmo pagado en el periodo", pesos(df["monto"].sum() if not df.empty else 0))
    st.dataframe(df, use_container_width=True)


# -----------------------------
# APP
# -----------------------------

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🥪", layout="wide")
    apply_branding()
    render_brand_header()
    st.caption("Zona horaria: México / America/Mexico_City")

    if not check_password():
        st.stop()

    try:
        setup_workbook()
        ensure_required_product_prices()
    except Exception as error:
        st.error("No se pudo conectar con Google Sheets.")
        st.write("Revisa tus secrets, el permiso del service account y la cuota de Google Sheets.")
        st.exception(error)
        st.stop()

    if st.sidebar.button("Cerrar sesión"):
        st.session_state["authenticated"] = False
        st.rerun()

    page = st.sidebar.radio(
        "Menú",
        [
            "Registrar pedido",
            "Corte de caja",
            "Reportes del local",
            "Planeación de compras",
            "Saldos del local",
            "Pago personal",
            "Gastos e inventario",
            "Finanzas familiares",
            "Diezmo",
            "Productos",
        ],
    )

    if page == "Registrar pedido":
        page_registrar_pedido()
    elif page == "Corte de caja":
        page_corte_caja()
    elif page == "Reportes del local":
        page_reportes_local()
    elif page == "Planeación de compras":
        page_planeacion_compras()
    elif page == "Saldos del local":
        page_saldos_local()
    elif page == "Pago personal":
        page_pago_personal()
    elif page == "Gastos e inventario":
        page_gastos_inventario()
    elif page == "Finanzas familiares":
        page_finanzas_familiares()
    elif page == "Diezmo":
        page_diezmo()
    elif page == "Productos":
        page_productos()


if __name__ == "__main__":
    main()

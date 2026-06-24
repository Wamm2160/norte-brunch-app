
import base64
import calendar
import re
import time
import uuid
from datetime import datetime, date, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError


APP_TITLE = "Norte Brunch"
TZ = ZoneInfo("America/Mexico_City")
CARD_FEE_RATE = 0.035
TITHING_RATE = 0.10
DEBT_ALERT_MIN_BALANCE = 10000

DEFAULT_PRODUCTS = [
    ["Torta de adobada", 95, 40, "si"],
    ["Torta de pierna", 100, 40, "si"],
    ["Torta mixta", 125, 40, "si"],
    ["Extra aguacate", 15, 0, "si"],
    ["Extra queso", 10, 0, "si"],
    ["Agua de litro", 45, 25, "si"],
    ["Agua de medio litro", 30, 20, "si"],
    ["Refresco 600 ml", 35, 10, "si"],
    ["Pastel", 45, 20, "si"],
    ["Cafe", 20, 10, "si"],
]

SHEETS = {
    "productos": {
        "name": "Productos",
        "headers": ["producto", "precio", "ganancia_personal", "activo"],
        "default_rows": DEFAULT_PRODUCTS,
    },
    "pedidos": {
        "name": "Pedidos",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "pedido_id", "pedido_numero", "estado",
            "producto", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
            "total_linea", "ganancia_personal_linea", "dinero_norte_linea", "nota",
        ],
        "default_rows": [],
    },
    "movimientos": {
        "name": "Movimientos",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "tipo", "movimiento_id",
            "pedido_id", "pedido_numero",
            "producto", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
            "total_linea", "ganancia_personal_linea", "dinero_norte_linea",
            "metodo_pago", "comision_terminal_linea", "total_neto_linea",
            "monto", "pagado_con", "nota",
        ],
        "default_rows": [],
    },
}

NUMERIC_PRODUCT_COLUMNS = ["precio", "ganancia_personal"]
NUMERIC_ORDER_COLUMNS = [
    "pedido_numero", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
    "total_linea", "ganancia_personal_linea", "dinero_norte_linea",
]
NUMERIC_MOVEMENT_COLUMNS = [
    "pedido_numero", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
    "total_linea", "ganancia_personal_linea", "dinero_norte_linea",
    "comision_terminal_linea", "total_neto_linea", "monto",
]


# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

def now_mx():
    return datetime.now(TZ)


def new_id():
    return str(uuid.uuid4())


def pesos(value):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return f"${value:,.2f} MXN"


def parse_money(value):
    """Convierte texto de dinero a float.

    Acepta:
    202
    202.5
    202.50
    202,50
    $202.50
    1,202.50
    1.202,50
    """
    if value is None:
        return 0.0

    text = str(value).strip()
    text = text.replace("$", "").replace("MXN", "").replace("mxn", "")
    text = text.replace(" ", "")

    if not text:
        return 0.0

    # Dejar solo números, coma, punto y signo negativo.
    text = re.sub(r"[^0-9,.\-]", "", text)

    if not text:
        return 0.0

    if "," in text and "." in text:
        # El último separador suele ser decimal.
        if text.rfind(",") > text.rfind("."):
            # 1.202,50 -> 1202.50
            text = text.replace(".", "").replace(",", ".")
        else:
            # 1,202.50 -> 1202.50
            text = text.replace(",", "")
    elif "," in text:
        # 202,50 -> 202.50
        text = text.replace(",", ".")

    try:
        return round(float(text), 2)
    except Exception:
        return 0.0


def parse_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def record_datetime(dt=None):
    if dt is None:
        dt = now_mx()
    return {
        "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha": dt.strftime("%Y-%m-%d"),
        "hora": dt.strftime("%H:%M:%S"),
    }


def datetime_picker(prefix, label="Fecha y hora", default_dt=None):
    st.caption(label)
    if default_dt is None:
        default_dt = now_mx()
    c1, c2 = st.columns(2)
    selected_date = c1.date_input("Fecha", value=default_dt.date(), key=f"{prefix}_date")
    selected_time = c2.time_input("Hora", value=default_dt.time().replace(second=0, microsecond=0), key=f"{prefix}_time")
    dt = datetime.combine(selected_date, selected_time).replace(tzinfo=TZ)
    return record_datetime(dt)


def money_input(label, key, value="", placeholder="Ej. 202.50"):
    if value is None:
        value = ""
    return st.text_input(label, value=str(value), placeholder=placeholder, key=key)


def is_saturday_after_6pm():
    n = now_mx()
    return n.weekday() == 5 and n.time() >= dtime(18, 0)


def next_saturday_6pm():
    n = now_mx()
    days_ahead = (5 - n.weekday()) % 7
    candidate = datetime.combine(n.date() + timedelta(days=days_ahead), dtime(18, 0), tzinfo=TZ)
    if candidate <= n:
        candidate += timedelta(days=7)
    return candidate


def weekday_es(value):
    names = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }
    try:
        return names.get(int(value), "")
    except Exception:
        return ""


def month_end(day):
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def period_dates(kind):
    today = now_mx().date()
    if kind == "Hoy":
        return today, today
    if kind == "Semana":
        return today - timedelta(days=today.weekday()), today
    if kind == "Quincena":
        if today.day <= 15:
            return today.replace(day=1), today.replace(day=15)
        return today.replace(day=16), month_end(today)
    if kind == "Mes":
        return today.replace(day=1), month_end(today)
    if kind == "Año":
        return today.replace(month=1, day=1), today.replace(month=12, day=31)
    return today, today


def period_picker(prefix):
    today = now_mx().date()
    option = st.selectbox(
        "Periodo",
        ["Hoy", "Semana", "Quincena", "Mes", "Año", "Personalizado"],
        key=f"{prefix}_period",
    )
    if option != "Personalizado":
        return period_dates(option)

    c1, c2 = st.columns(2)
    start = c1.date_input("Desde", value=today - timedelta(days=7), key=f"{prefix}_start")
    end = c2.date_input("Hasta", value=today, key=f"{prefix}_end")
    return start, end


# -------------------------------------------------
# ESTILO
# -------------------------------------------------

def apply_style():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-left: .8rem;
            padding-right: .8rem;
            max-width: 760px;
        }
        .nb-logo-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: .25rem;
        }
        .nb-logo-wrap img {
            max-width: 210px;
            width: min(64vw, 210px);
            height: auto;
        }
        .nb-subtitle {
            text-align: center;
            font-weight: 800;
            font-size: .85rem;
            color: #5C3D1E;
            margin-bottom: .8rem;
        }
        .nb-total {
            border: 2px solid #D32F2F;
            border-radius: 18px;
            padding: .95rem;
            margin: .85rem 0;
            text-align: center;
            background: #FFF8F8;
        }
        .nb-total .label {
            font-weight: 900;
            font-size: .9rem;
            color: #4B5563;
        }
        .nb-total .amount {
            font-weight: 1000;
            font-size: 2.3rem;
            line-height: 1;
            color: #D32F2F;
        }
        .nb-paid {
            border: 2px solid #2E7D32;
            border-radius: 18px;
            padding: .95rem;
            margin: .85rem 0;
            text-align: center;
            background: #F1FFF3;
        }
        .nb-paid .label {
            font-weight: 900;
            font-size: .9rem;
            color: #1F2933;
        }
        .nb-paid .amount {
            font-weight: 1000;
            font-size: 2.2rem;
            line-height: 1;
            color: #2E7D32;
        }
        .stButton > button {
            min-height: 3rem;
            border-radius: 14px;
            font-weight: 850;
            width: 100%;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: .7rem;
            background: #FFFFFF;
        }
        input, textarea {
            color: #111827 !important;
        }
        label, p, div, span, h1, h2, h3 {
            color: #1F2933;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header():
    logo = Path("logo.png")
    if logo.exists():
        b64 = base64.b64encode(logo.read_bytes()).decode("utf-8")
        st.markdown(f'<div class="nb-logo-wrap"><img src="data:image/png;base64,{b64}"></div>', unsafe_allow_html=True)
    else:
        st.title("Norte Brunch")
    st.markdown('<div class="nb-subtitle">Control simple del negocio</div>', unsafe_allow_html=True)


def big_total(label, amount):
    st.markdown(
        f"""
        <div class="nb-total">
            <div class="label">{label}</div>
            <div class="amount">{pesos(amount)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def big_paid(label, amount):
    st.markdown(
        f"""
        <div class="nb-paid">
            <div class="label">{label}</div>
            <div class="amount">{pesos(amount)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------
# GOOGLE SHEETS
# -------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def get_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Falta [gcp_service_account] en Streamlit Secrets.")
        st.stop()
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def get_workbook():
    client = get_client()

    spreadsheet_id = st.secrets.get("spreadsheet_id", "")
    if not spreadsheet_id:
        spreadsheet_id = st.secrets.get("google_sheet", {}).get("spreadsheet_id", "")
    if not spreadsheet_id:
        spreadsheet_id = st.secrets.get("app", {}).get("spreadsheet_id", "")

    if not spreadsheet_id:
        st.error("Falta spreadsheet_id en Secrets. Puedes usar [google_sheet] spreadsheet_id.")
        st.stop()

    return client.open_by_key(str(spreadsheet_id).strip())


def google_call(func, *args, **kwargs):
    last_error = None
    for attempt in range(5):
        try:
            return func(*args, **kwargs)
        except APIError as error:
            last_error = error
            time.sleep(min(2 ** attempt, 16))
        except Exception as error:
            last_error = error
            time.sleep(min(2 ** attempt, 8))
    raise last_error


@st.cache_resource
def get_ws(sheet_key):
    wb = get_workbook()
    info = SHEETS[sheet_key]
    try:
        return google_call(wb.worksheet, info["name"])
    except Exception:
        ws = google_call(
            wb.add_worksheet,
            title=info["name"],
            rows=1500,
            cols=max(len(info["headers"]) + 4, 12),
        )
        google_call(ws.append_row, info["headers"], value_input_option="USER_ENTERED")
        if info["default_rows"]:
            google_call(ws.append_rows, info["default_rows"], value_input_option="USER_ENTERED")
        return ws


def ensure_headers(sheet_key):
    ws = get_ws(sheet_key)
    expected = SHEETS[sheet_key]["headers"]
    values = google_call(ws.get_all_values)

    if not values:
        google_call(ws.append_row, expected, value_input_option="USER_ENTERED")
        if SHEETS[sheet_key]["default_rows"]:
            google_call(ws.append_rows, SHEETS[sheet_key]["default_rows"], value_input_option="USER_ENTERED")
        return

    headers = [str(h).strip() for h in values[0]]
    changed = False
    for h in expected:
        if h not in headers:
            headers.append(h)
            changed = True
    if changed:
        google_call(ws.update, "1:1", [headers])


def setup_sheets():
    for key in SHEETS:
        get_ws(key)
        ensure_headers(key)


def clear_cache():
    try:
        load_df.clear()
    except Exception:
        pass


@st.cache_data(ttl=60)
def load_df(sheet_key):
    ws = get_ws(sheet_key)
    values = google_call(ws.get_all_values)
    if not values:
        return pd.DataFrame(columns=SHEETS[sheet_key]["headers"])

    headers = [str(h).strip() for h in values[0]]
    rows = values[1:]

    clean = []
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        clean.append(padded[:len(headers)])

    return pd.DataFrame(clean, columns=headers)


def append_record(sheet_key, record):
    ws = get_ws(sheet_key)
    ensure_headers(sheet_key)
    headers = google_call(ws.row_values, 1)
    row = [record.get(h, "") for h in headers]
    google_call(ws.append_row, row, value_input_option="USER_ENTERED")
    clear_cache()


def append_record_verified(sheet_key, record):
    """Guarda una fila y verifica que Google Sheets sí la haya agregado.

    Esto se usa especialmente para gastos, porque ahí necesitamos
    confirmación clara de guardado.
    """
    ws = get_ws(sheet_key)
    ensure_headers(sheet_key)

    before_values = google_call(ws.get_all_values)
    before_count = len(before_values)

    headers = google_call(ws.row_values, 1)
    row = [record.get(h, "") for h in headers]

    google_call(ws.append_row, row, value_input_option="USER_ENTERED")

    after_values = google_call(ws.get_all_values)
    after_count = len(after_values)

    clear_cache()

    if after_count <= before_count:
        raise RuntimeError(
            f"Google Sheets no agregó la fila. Filas antes: {before_count}, filas después: {after_count}"
        )

    return before_count, after_count


def append_records(sheet_key, records):
    if not records:
        return
    ws = get_ws(sheet_key)
    ensure_headers(sheet_key)
    headers = google_call(ws.row_values, 1)
    rows = [[r.get(h, "") for h in headers] for r in records]
    google_call(ws.append_rows, rows, value_input_option="USER_ENTERED")
    clear_cache()


def replace_records(sheet_key, records):
    ws = get_ws(sheet_key)
    headers = SHEETS[sheet_key]["headers"]
    google_call(ws.clear)
    google_call(ws.append_row, headers, value_input_option="USER_ENTERED")
    if records:
        rows = [[r.get(h, "") for h in headers] for r in records]
        google_call(ws.append_rows, rows, value_input_option="USER_ENTERED")
    clear_cache()


# -------------------------------------------------
# NORMALIZAR DATA
# -------------------------------------------------

def load_products(active_only=True):
    df = load_df("productos")
    if df.empty:
        return pd.DataFrame(columns=SHEETS["productos"]["headers"])

    df = df.copy()

    for col in SHEETS["productos"]["headers"]:
        if col not in df.columns:
            df[col] = ""

    for col in NUMERIC_PRODUCT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    df["producto"] = df["producto"].astype(str).str.strip()
    df["activo"] = df["activo"].astype(str).str.lower().str.strip().replace("", "si")
    df = df[df["producto"] != ""]

    if active_only:
        df = df[df["activo"] != "no"]

    return df.reset_index(drop=True)


def save_products(df):
    records = []
    seen = set()

    for _, row in df.iterrows():
        name = str(row.get("producto", "")).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "producto": name,
            "precio": parse_money(row.get("precio", 0)),
            "ganancia_personal": parse_money(row.get("ganancia_personal", 0)),
            "activo": str(row.get("activo", "si")).strip().lower() or "si",
        })

    replace_records("productos", records)


def load_orders():
    df = load_df("pedidos")
    if df.empty:
        return pd.DataFrame(columns=SHEETS["pedidos"]["headers"])

    df = df.copy()
    for col in SHEETS["pedidos"]["headers"]:
        if col not in df.columns:
            df[col] = ""

    for col in NUMERIC_ORDER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    df["estado"] = df["estado"].astype(str).str.lower().str.strip()
    return df


def save_orders(df):
    records = []
    for _, row in df.iterrows():
        record = {}
        for h in SHEETS["pedidos"]["headers"]:
            val = row.get(h, "")
            if pd.isna(val):
                val = ""
            record[h] = val
        records.append(record)
    replace_records("pedidos", records)


def normalize_movements(df):
    if df.empty:
        return pd.DataFrame(columns=SHEETS["movimientos"]["headers"])

    df = df.copy()

    for col in SHEETS["movimientos"]["headers"]:
        if col not in df.columns:
            df[col] = ""

    for col in NUMERIC_MOVEMENT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    df["tipo"] = df["tipo"].astype(str).str.lower().str.strip()
    df["producto"] = df["producto"].astype(str).str.strip()
    df["pagado_con"] = df["pagado_con"].astype(str).str.strip()
    df["metodo_pago"] = df["metodo_pago"].astype(str).str.strip()

    df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["fecha_date"] = df["fecha_dt"].dt.date
    df["weekday"] = df["fecha_dt"].dt.weekday
    df["dia_semana"] = df["weekday"].apply(lambda x: weekday_es(x) if pd.notna(x) else "")

    return df


def movements_df():
    return normalize_movements(load_df("movimientos"))


def ventas_df():
    df = movements_df()
    return df[df["tipo"] == "venta"].copy() if not df.empty else df


def gastos_df(include_void=False):
    df = movements_df()
    if df.empty:
        return df
    if include_void:
        return df[df["tipo"].isin(["gasto", "gasto_anulado"])].copy()
    gastos = df[df["tipo"] == "gasto"].copy()
    return gastos[gastos["monto"] > 0].copy()


def debt_movements_df():
    df = movements_df()
    if df.empty:
        return df

    personal_expense = (df["tipo"] == "gasto") & (df["pagado_con"].str.lower() == "mi dinero personal")
    debt_payment = df["tipo"] == "pago_deuda"
    debt_adjust = df["tipo"] == "ajuste_deuda"

    return df[personal_expense | debt_payment | debt_adjust].copy()


def filter_dates(df, start, end):
    if df.empty or "fecha_date" not in df.columns:
        return df
    return df[(df["fecha_date"] >= start) & (df["fecha_date"] <= end)].copy()


def save_movements_df(df):
    records = []
    for _, row in df.iterrows():
        record = {}
        for h in SHEETS["movimientos"]["headers"]:
            val = row.get(h, "")
            if pd.isna(val):
                val = ""
            record[h] = val
        records.append(record)
    replace_records("movimientos", records)


# -------------------------------------------------
# CÁLCULOS
# -------------------------------------------------

def calculate_line(product, qty, price, profit, card_fee=0):
    qty = parse_int(qty, 0)
    price = parse_money(price)
    profit = parse_money(profit)
    card_fee = parse_money(card_fee)

    total = round(qty * price, 2)
    profit_line = round(qty * profit, 2)
    net = round(total - card_fee, 2)
    norte = round(total - profit_line - card_fee, 2)

    return {
        "producto": product,
        "cantidad": qty,
        "precio_unitario": price,
        "ganancia_personal_unitaria": profit,
        "total_linea": total,
        "ganancia_personal_linea": profit_line,
        "dinero_norte_linea": norte,
        "comision_terminal_linea": card_fee,
        "total_neto_linea": net,
    }


def calculate_balances():
    df = movements_df()

    result = {
        "saldo_norte": 0.0,
        "deuda": 0.0,
        "paga_pendiente": 0.0,
        "paga_pagada": 0.0,
        "ventas_brutas": 0.0,
        "ventas_netas": 0.0,
        "para_norte": 0.0,
        "gastos_total": 0.0,
        "gastos_norte": 0.0,
        "gastos_personal": 0.0,
        "comisiones": 0.0,
        "pagos_deuda": 0.0,
        "ultimo_movimiento_saldo": "",
    }

    if df.empty:
        return result

    tipo = df["tipo"]
    paid = df["pagado_con"].str.lower()

    ventas = df[tipo == "venta"]
    gastos = df[tipo == "gasto"]
    gastos_norte = gastos[paid == "dinero de norte brunch"]
    gastos_personal = gastos[paid == "mi dinero personal"]
    pagos_personales = df[tipo == "pago_personal"]
    pagos_deuda = df[tipo == "pago_deuda"]
    ajustes_saldo = df[tipo == "ajuste_saldo"]
    ajustes_deuda = df[tipo == "ajuste_deuda"]

    ventas_brutas = float(ventas["total_linea"].sum())
    ventas_netas = float(ventas["total_neto_linea"].sum())
    profit_total = float(ventas["ganancia_personal_linea"].sum())
    para_norte = float(ventas["dinero_norte_linea"].sum())
    comisiones = float(ventas["comision_terminal_linea"].sum())

    gastos_total = float(gastos["monto"].sum())
    gastos_norte_total = float(gastos_norte["monto"].sum())
    gastos_personal_total = float(gastos_personal["monto"].sum())

    pagos_personales_total = float(pagos_personales["monto"].sum())
    pagos_deuda_total = float(pagos_deuda["monto"].sum())
    ajustes_saldo_total = float(ajustes_saldo["monto"].sum())
    ajustes_deuda_total = float(ajustes_deuda["monto"].sum())

    saldo = ventas_netas - gastos_norte_total - pagos_personales_total - pagos_deuda_total + ajustes_saldo_total
    deuda = gastos_personal_total + ajustes_deuda_total - pagos_deuda_total
    paga_pendiente = profit_total - pagos_personales_total

    affecting = df[tipo.isin(["venta", "gasto", "pago_personal", "pago_deuda", "ajuste_saldo"])]
    if not affecting.empty:
        last = pd.to_datetime(affecting["fecha_hora"], errors="coerce").max()
        if pd.notna(last):
            result["ultimo_movimiento_saldo"] = last.strftime("%Y-%m-%d %H:%M:%S")

    result.update({
        "saldo_norte": round(saldo, 2),
        "deuda": round(max(0.0, deuda), 2),
        "paga_pendiente": round(max(0.0, paga_pendiente), 2),
        "paga_pagada": round(pagos_personales_total, 2),
        "ventas_brutas": round(ventas_brutas, 2),
        "ventas_netas": round(ventas_netas, 2),
        "para_norte": round(para_norte, 2),
        "gastos_total": round(gastos_total, 2),
        "gastos_norte": round(gastos_norte_total, 2),
        "gastos_personal": round(gastos_personal_total, 2),
        "comisiones": round(comisiones, 2),
        "pagos_deuda": round(pagos_deuda_total, 2),
    })
    return result


def debt_alert():
    bal = calculate_balances()
    if bal["deuda"] <= 0:
        return False, "No hay deuda pendiente."
    if bal["saldo_norte"] < DEBT_ALERT_MIN_BALANCE:
        return False, "Saldo menor a $10,000."

    last_text = bal.get("ultimo_movimiento_saldo", "")
    if not last_text:
        return True, "Hay saldo suficiente y no hay último movimiento."

    try:
        last_dt = datetime.strptime(last_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
        days = (now_mx() - last_dt).days
    except Exception:
        return True, "Hay saldo suficiente."

    if days >= 7:
        return True, f"El saldo lleva {days} días sin movimiento."
    return False, f"Último movimiento: {last_text}."


# -------------------------------------------------
# PEDIDOS
# -------------------------------------------------

def next_order_number():
    today = now_mx().strftime("%Y-%m-%d")
    df = load_orders()
    if df.empty:
        return 1
    today_rows = df[df["fecha"].astype(str) == today]
    if today_rows.empty:
        return 1
    return int(pd.to_numeric(today_rows["pedido_numero"], errors="coerce").fillna(0).max()) + 1


def create_order():
    rec = record_datetime()
    pedido_id = new_id()
    num = next_order_number()
    append_record("pedidos", {
        **rec,
        "pedido_id": pedido_id,
        "pedido_numero": num,
        "estado": "pendiente",
        "producto": "",
        "cantidad": 0,
        "precio_unitario": 0,
        "ganancia_personal_unitaria": 0,
        "total_linea": 0,
        "ganancia_personal_linea": 0,
        "dinero_norte_linea": 0,
        "nota": "",
    })
    return pedido_id, num


def pending_orders():
    df = load_orders()
    if df.empty:
        return []
    pending = df[df["estado"] == "pendiente"].copy()
    if pending.empty:
        return []

    orders = []
    for pedido_id, group in pending.groupby("pedido_id", sort=False):
        if not str(pedido_id).strip():
            continue
        num = int(pd.to_numeric(group["pedido_numero"], errors="coerce").fillna(0).max())
        fecha = str(group["fecha"].iloc[0])
        total = float(group["total_linea"].sum())
        orders.append({
            "pedido_id": pedido_id,
            "pedido_numero": num,
            "label": f"Pedido {num} · {fecha} · {pesos(total)}",
        })
    return orders


def get_order_lines(pedido_id, keep_index=False):
    df = load_orders()
    if df.empty:
        return pd.DataFrame(columns=SHEETS["pedidos"]["headers"])
    lines = df[
        (df["pedido_id"].astype(str) == str(pedido_id))
        & (df["estado"] == "pendiente")
        & (df["producto"].astype(str).str.strip() != "")
    ].copy()
    return lines if keep_index else lines.reset_index(drop=True)


def add_product_to_order(pedido_id, product_name, qty):
    products = load_products(active_only=True)
    row = products[products["producto"] == product_name]
    if row.empty:
        st.error("No encontré el producto.")
        return

    product = row.iloc[0]
    line = calculate_line(product["producto"], qty, product["precio"], product["ganancia_personal"])

    orders = load_orders()
    current = orders[orders["pedido_id"] == pedido_id]
    if current.empty:
        st.error("No encontré el pedido.")
        return

    num = int(current["pedido_numero"].max())

    append_record("pedidos", {
        **record_datetime(),
        "pedido_id": pedido_id,
        "pedido_numero": num,
        "estado": "pendiente",
        "producto": line["producto"],
        "cantidad": line["cantidad"],
        "precio_unitario": line["precio_unitario"],
        "ganancia_personal_unitaria": line["ganancia_personal_unitaria"],
        "total_linea": line["total_linea"],
        "ganancia_personal_linea": line["ganancia_personal_linea"],
        "dinero_norte_linea": line["dinero_norte_linea"],
        "nota": "",
    })


def remove_order_line(row_index):
    df = load_orders()
    if row_index in df.index:
        df.loc[row_index, "estado"] = "eliminado"
        save_orders(df)


def cancel_order(pedido_id):
    df = load_orders()
    if df.empty:
        return
    mask = (df["pedido_id"].astype(str) == str(pedido_id)) & (df["estado"] == "pendiente")
    df.loc[mask, "estado"] = "cancelado"
    save_orders(df)


def order_totals(lines):
    if lines.empty:
        return {"total": 0.0, "profit": 0.0, "norte": 0.0}
    return {
        "total": round(float(lines["total_linea"].sum()), 2),
        "profit": round(float(lines["ganancia_personal_linea"].sum()), 2),
        "norte": round(float(lines["dinero_norte_linea"].sum()), 2),
    }


def pay_order(pedido_id, method, sale_datetime, note):
    lines = get_order_lines(pedido_id)
    if lines.empty:
        st.error("Este pedido no tiene artículos.")
        return

    totals = order_totals(lines)
    total = totals["total"]
    if total <= 0:
        st.error("El pedido tiene total cero.")
        return

    fee_total = round(total * CARD_FEE_RATE, 2) if method == "Tarjeta" else 0
    records = []

    for _, item in lines.iterrows():
        share = parse_money(item["total_linea"]) / total
        fee_line = round(fee_total * share, 2)
        line = calculate_line(
            item["producto"],
            item["cantidad"],
            item["precio_unitario"],
            item["ganancia_personal_unitaria"],
            card_fee=fee_line,
        )
        records.append({
            **sale_datetime,
            "tipo": "venta",
            "movimiento_id": new_id(),
            "pedido_id": pedido_id,
            "pedido_numero": item.get("pedido_numero", ""),
            **line,
            "metodo_pago": method,
            "monto": 0,
            "pagado_con": "",
            "nota": note,
        })

    append_records("movimientos", records)

    df = load_orders()
    mask = (df["pedido_id"].astype(str) == str(pedido_id)) & (df["estado"] == "pendiente")
    df.loc[mask, "estado"] = "pagado"
    save_orders(df)

    big_paid("PEDIDO PAGADO", sum(r["total_neto_linea"] for r in records))
    st.success("Venta guardada correctamente.")
    st.rerun()


# -------------------------------------------------
# EDITAR / ANULAR GASTOS
# -------------------------------------------------

def movement_label(idx, row):
    fecha = str(row.get("fecha_hora", ""))
    tipo = str(row.get("tipo", ""))
    producto = str(row.get("producto", ""))
    amount = row.get("monto", 0) if parse_money(row.get("monto", 0)) else row.get("total_linea", 0)
    return f"{idx} · {fecha} · {tipo} · {producto} · {pesos(amount)}"


def edit_expense(row_index, rec, name, amount_text, paid_with, note):
    df = movements_df()
    if df.empty or row_index not in df.index:
        return False, "No encontré el gasto."

    if str(df.loc[row_index, "tipo"]) != "gasto":
        return False, "Solo se pueden editar gastos activos."

    amount = parse_money(amount_text)
    if amount <= 0:
        return False, "El monto debe ser mayor que cero."

    if not str(name).strip():
        return False, "El gasto no puede quedar vacío."

    df.loc[row_index, "fecha_hora"] = rec["fecha_hora"]
    df.loc[row_index, "fecha"] = rec["fecha"]
    df.loc[row_index, "hora"] = rec["hora"]
    df.loc[row_index, "producto"] = str(name).strip()
    df.loc[row_index, "monto"] = amount
    df.loc[row_index, "pagado_con"] = paid_with
    df.loc[row_index, "nota"] = note

    for col in [
        "pedido_id", "pedido_numero", "cantidad", "precio_unitario",
        "ganancia_personal_unitaria", "total_linea", "ganancia_personal_linea",
        "dinero_norte_linea", "metodo_pago", "comision_terminal_linea", "total_neto_linea",
    ]:
        if col in df.columns:
            df.loc[row_index, col] = "" if col in ["pedido_id", "pedido_numero", "metodo_pago"] else 0

    save_movements_df(df)
    return True, "Gasto actualizado."


def void_expenses(row_indices, reason):
    df = movements_df()
    if df.empty:
        return 0

    count = 0
    for idx in row_indices:
        if idx not in df.index:
            continue
        if str(df.loc[idx, "tipo"]) != "gasto":
            continue
        old_note = str(df.loc[idx, "nota"])
        df.loc[idx, "tipo"] = "gasto_anulado"
        df.loc[idx, "nota"] = f"{old_note} | ANULADO: {reason}".strip(" |")
        count += 1

    if count:
        save_movements_df(df)
    return count


# -------------------------------------------------
# PÁGINAS
# -------------------------------------------------

def page_pedidos():
    st.header("Pedidos")

    products = load_products(True)
    if products.empty:
        st.warning("No hay productos activos.")
        return

    if st.button("Crear nuevo pedido"):
        _, num = create_order()
        st.success(f"Pedido {num} creado.")
        st.rerun()

    orders = pending_orders()
    if not orders:
        st.info("No hay pedidos pendientes.")
        return

    label = st.selectbox("Pedido pendiente", [o["label"] for o in orders])
    selected = next(o for o in orders if o["label"] == label)
    pedido_id = selected["pedido_id"]

    st.subheader(f"Pedido {selected['pedido_numero']}")

    cols = st.columns(2)
    for i, row in products.iterrows():
        button_label = f"{row['producto']} · {pesos(row['precio'])}"
        if cols[i % 2].button(button_label, key=f"fast_{pedido_id}_{i}"):
            add_product_to_order(pedido_id, row["producto"], 1)
            st.rerun()

    with st.expander("Agregar con cantidad"):
        c1, c2 = st.columns([2, 1])
        product_name = c1.selectbox("Producto", products["producto"].tolist(), key=f"prod_{pedido_id}")
        qty = c2.number_input("Cantidad", min_value=1, value=1, step=1, key=f"qty_{pedido_id}")
        if st.button("Agregar al pedido", key=f"add_{pedido_id}"):
            add_product_to_order(pedido_id, product_name, qty)
            st.rerun()

    st.divider()
    lines = get_order_lines(pedido_id, keep_index=True)

    if lines.empty:
        st.info("Este pedido todavía no tiene artículos.")
    else:
        for idx, item in lines.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{item['producto']}** x {parse_int(item['cantidad'])}")
            c2.write(pesos(item["total_linea"]))
            if c3.button("Quitar", key=f"remove_{pedido_id}_{idx}"):
                remove_order_line(idx)
                st.rerun()

        totals = order_totals(lines)
        big_total("TOTAL A COBRAR", totals["total"])

        c1, c2 = st.columns(2)
        c1.metric("Para mi paga", pesos(totals["profit"]))
        c2.metric("Para Norte Brunch", pesos(totals["norte"]))

        sale_dt = datetime_picker(f"sale_{pedido_id}", "Fecha y hora de la venta")
        method = st.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key=f"method_{pedido_id}")
        if method == "Tarjeta":
            st.warning(f"Comisión terminal: {pesos(totals['total'] * CARD_FEE_RATE)}")
        note = st.text_input("Nota", key=f"note_{pedido_id}")

        if st.button("Cobrar pedido", key=f"pay_{pedido_id}"):
            pay_order(pedido_id, method, sale_dt, note)

    st.divider()
    if st.button("Cancelar pedido completo", key=f"cancel_{pedido_id}"):
        cancel_order(pedido_id)
        st.success("Pedido cancelado.")
        st.rerun()


def page_gastos():
    st.header("Gastos")

    if "expense_form_id" not in st.session_state:
        st.session_state.expense_form_id = 0

    if "last_expense_message" in st.session_state:
        st.success(st.session_state.last_expense_message)

    if "last_expense_error" in st.session_state:
        st.error(st.session_state.last_expense_error)

    form_id = st.session_state.expense_form_id

    st.subheader("Registrar gasto")
    expense_dt = datetime_picker(f"expense_new_{form_id}", "Fecha y hora del gasto")
    name = st.text_input("Gasto", placeholder="Ej. pan", key=f"expense_name_{form_id}")
    amount_text = money_input("Monto", key=f"expense_amount_{form_id}", placeholder="Ej. 202.50")
    st.caption("Escribe el gasto y el monto. Luego toca Guardar gasto una sola vez.")
    paid_with = st.radio("Pagado con", ["Dinero de Norte Brunch", "Mi dinero personal"], key=f"expense_paid_{form_id}")
    note = st.text_input("Nota", placeholder="Opcional", key=f"expense_note_{form_id}")

    if st.button("Guardar gasto", key=f"save_expense_{form_id}"):
        # Limpiar mensajes anteriores
        st.session_state.pop("last_expense_message", None)
        st.session_state.pop("last_expense_error", None)

        amount = parse_money(amount_text)

        if not name.strip():
            st.session_state.last_expense_error = "No se guardó: escribe el nombre del gasto. Ejemplo: pan"
            st.rerun()

        if amount <= 0:
            st.session_state.last_expense_error = f"No se guardó: escribe un monto válido. Recibí: '{amount_text}'. Ejemplo correcto: 202.50"
            st.rerun()

        record = {
            **expense_dt,
            "tipo": "gasto",
            "movimiento_id": new_id(),
            "pedido_id": "",
            "pedido_numero": "",
            "producto": name.strip(),
            "cantidad": 0,
            "precio_unitario": 0,
            "ganancia_personal_unitaria": 0,
            "total_linea": 0,
            "ganancia_personal_linea": 0,
            "dinero_norte_linea": 0,
            "metodo_pago": "",
            "comision_terminal_linea": 0,
            "total_neto_linea": 0,
            "monto": amount,
            "pagado_con": paid_with,
            "nota": note,
        }

        try:
            before_count, after_count = append_record_verified("movimientos", record)
            st.session_state.last_expense_message = (
                f"Gasto guardado correctamente: {name.strip()} · {pesos(amount)}. "
                f"Filas en Movimientos: {before_count} → {after_count}."
            )
            st.session_state.expense_form_id += 1
            st.rerun()
        except Exception as error:
            st.session_state.last_expense_error = f"No se pudo guardar el gasto. Error: {error}"
            st.rerun()

    st.divider()
    start, end = period_picker("gastos")
    gastos = filter_dates(gastos_df(), start, end)
    st.metric("Gastos del periodo", pesos(gastos["monto"].sum() if not gastos.empty else 0))
    st.dataframe(gastos, use_container_width=True)

    if not gastos.empty:
        label_map = {movement_label(idx, row): idx for idx, row in gastos.iterrows()}

        with st.expander("Editar gasto"):
            selected_label = st.selectbox("Selecciona gasto", list(label_map.keys()), key="edit_expense_select")
            idx = label_map[selected_label]
            row = gastos.loc[idx]

            current_dt = pd.to_datetime(row.get("fecha_hora", ""), errors="coerce")
            if pd.isna(current_dt):
                current_dt = now_mx()
            else:
                current_dt = current_dt.to_pydatetime().replace(tzinfo=TZ)

            edit_dt = datetime_picker("expense_edit", "Fecha y hora corregida", current_dt)
            edit_name = st.text_input("Gasto", value=str(row.get("producto", "")), key="edit_expense_name")
            edit_amount = money_input("Monto", key="edit_expense_amount", value=str(parse_money(row.get("monto", 0))), placeholder="Ej. 202.50")

            options = ["Dinero de Norte Brunch", "Mi dinero personal"]
            current_paid = str(row.get("pagado_con", "Dinero de Norte Brunch"))
            paid_index = options.index(current_paid) if current_paid in options else 0
            edit_paid = st.radio("Pagado con", options, index=paid_index, key="edit_expense_paid")
            edit_note = st.text_input("Nota", value=str(row.get("nota", "")), key="edit_expense_note")

            if st.button("Guardar cambios del gasto", key="save_edit_expense"):
                ok, msg = edit_expense(idx, edit_dt, edit_name, edit_amount, edit_paid, edit_note)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with st.expander("Anular gastos duplicados o equivocados"):
            selected_void = st.multiselect("Selecciona gastos para anular", list(label_map.keys()))
            reason = st.text_input("Motivo", placeholder="Ej. duplicado", key="void_reason")
            if st.button("Anular gastos seleccionados"):
                indices = [label_map[x] for x in selected_void]
                count = void_expenses(indices, reason)
                st.success(f"Gastos anulados: {count}")
                st.rerun()

        with st.expander("Gastos más grandes"):
            st.dataframe(gastos.sort_values("monto", ascending=False).head(20), use_container_width=True)



def page_saldos():
    st.header("Saldo y deuda")

    bal = calculate_balances()
    alert, reason = debt_alert()
    if alert:
        st.warning(f"Norte Brunch puede abonarte a la deuda. {reason}")

    c1, c2 = st.columns(2)
    c1.metric("Saldo Norte Brunch", pesos(bal["saldo_norte"]))
    c2.metric("Mi paga pendiente", pesos(bal["paga_pendiente"]))

    st.divider()
    st.subheader("Balance operativo")
    b1, b2 = st.columns(2)
    b1.metric("Ventas netas", pesos(bal["ventas_netas"]))
    b2.metric("Gastos", pesos(bal["gastos_total"]))
    st.metric("Balance ventas - gastos", pesos(bal["ventas_netas"] - bal["gastos_total"]))

    with st.expander("Detalle"):
        d1, d2 = st.columns(2)
        d1.metric("Gastos pagados con Norte", pesos(bal["gastos_norte"]))
        d2.metric("Gastos pagados por mí", pesos(bal["gastos_personal"]))
        d3, d4 = st.columns(2)
        d3.metric("Comisiones terminal", pesos(bal["comisiones"]))
        d4.metric("Para Norte Brunch por ventas", pesos(bal["para_norte"]))

    st.divider()
    st.subheader("Deuda hacia mí")
    d1, d2 = st.columns(2)
    d1.metric("Deuda actual", pesos(bal["deuda"]))
    d2.metric("Pagos de deuda", pesos(bal["pagos_deuda"]))

    tab1, tab2, tab3 = st.tabs(["Ajustar saldo", "Ajustar deuda", "Pagar deuda"])

    with tab1:
        st.caption("Crea un ajuste por la diferencia entre saldo actual y saldo real.")
        new_balance_text = money_input("Saldo real de Norte Brunch", key="saldo_real", value=str(max(bal["saldo_norte"], 0)), placeholder="Ej. 10000.50")
        note = st.text_input("Nota", placeholder="Ej. conteo de caja", key="saldo_note")
        if st.button("Guardar ajuste de saldo"):
            new_balance = parse_money(new_balance_text)
            delta = round(new_balance - bal["saldo_norte"], 2)
            append_record("movimientos", {
                **record_datetime(),
                "tipo": "ajuste_saldo",
                "movimiento_id": new_id(),
                "monto": delta,
                "nota": note or f"Ajuste de saldo a {pesos(new_balance)}",
            })
            st.success("Saldo ajustado.")
            st.rerun()

    with tab2:
        st.caption("Crea un ajuste por la diferencia entre deuda actual y deuda real.")
        new_debt_text = money_input("Deuda real de Norte Brunch hacia mí", key="deuda_real", value=str(max(bal["deuda"], 0)), placeholder="Ej. 1500.50")
        note = st.text_input("Nota", placeholder="Ej. ajuste inicial", key="debt_note")
        if st.button("Guardar ajuste de deuda"):
            new_debt = parse_money(new_debt_text)
            delta = round(new_debt - bal["deuda"], 2)
            append_record("movimientos", {
                **record_datetime(),
                "tipo": "ajuste_deuda",
                "movimiento_id": new_id(),
                "monto": delta,
                "nota": note or f"Ajuste de deuda a {pesos(new_debt)}",
            })
            st.success("Deuda ajustada.")
            st.rerun()

    with tab3:
        suggested = min(bal["deuda"], max(bal["saldo_norte"] - DEBT_ALERT_MIN_BALANCE, 0))
        st.info(f"Pago sugerido sin bajar de $10,000: {pesos(suggested)}")
        pay_text = money_input("Monto para pagar deuda", key="pago_deuda", value=str(max(suggested, 0)), placeholder="Ej. 500.50")
        note = st.text_input("Nota", placeholder="Ej. abono de deuda", key="pay_debt_note")
        if st.button("Registrar pago de deuda"):
            amount = parse_money(pay_text)
            max_pay = min(bal["deuda"], bal["saldo_norte"])
            if amount <= 0:
                st.error("El monto debe ser mayor a cero.")
            elif amount > max_pay:
                st.error(f"No puedes pagar más de {pesos(max_pay)}.")
            else:
                append_record("movimientos", {
                    **record_datetime(),
                    "tipo": "pago_deuda",
                    "movimiento_id": new_id(),
                    "monto": amount,
                    "nota": note,
                })
                st.success("Pago de deuda registrado.")
                st.rerun()

    with st.expander("Movimientos de deuda"):
        st.dataframe(debt_movements_df(), use_container_width=True)


def page_pago_personal():
    st.header("Pago personal semanal")

    bal = calculate_balances()
    st.metric("Mi paga pendiente", pesos(bal["paga_pendiente"]))

    allowed = is_saturday_after_6pm()

    if allowed:
        st.success("Ya es sábado después de las 6:00 pm. Puedes registrar tu pago.")
    else:
        nxt = next_saturday_6pm()
        st.warning(f"Solo puedes pagarte sábado después de las 6:00 pm. Próximo corte: {nxt.strftime('%Y-%m-%d %H:%M')}")

    if bal["paga_pendiente"] <= 0:
        st.info("No tienes paga pendiente.")
        allowed = False

    if bal["saldo_norte"] < bal["paga_pendiente"]:
        st.error("Norte Brunch no tiene saldo suficiente para pagar toda tu paga pendiente.")
        allowed = False

    with st.expander("Realizar pago personal"):
        amount = bal["paga_pendiente"]
        tithe = round(amount * TITHING_RATE, 2)
        free = round(amount - tithe, 2)

        st.write(f"Pago bruto: **{pesos(amount)}**")
        st.write(f"Diezmo sugerido de este pago: **{pesos(tithe)}**")
        st.write(f"Pago libre estimado: **{pesos(free)}**")

        confirm = st.checkbox("Confirmo que deseo registrar mi pago personal", disabled=not allowed)
        if st.button("Registrar pago personal", disabled=(not allowed or not confirm)):
            append_record("movimientos", {
                **record_datetime(),
                "tipo": "pago_personal",
                "movimiento_id": new_id(),
                "monto": amount,
                "nota": f"Diezmo sugerido: {pesos(tithe)}. Pago libre: {pesos(free)}.",
            })
            st.success("Pago personal registrado.")
            st.rerun()


def page_productos():
    st.header("Productos")

    df = load_products(active_only=False)
    st.dataframe(df, use_container_width=True)

    st.subheader("Agregar o modificar")
    options = ["Nuevo producto"] + df["producto"].tolist()
    selected = st.selectbox("Producto", options)

    if selected == "Nuevo producto":
        default = {"producto": "", "precio": "", "ganancia_personal": "", "activo": "si"}
    else:
        default = df[df["producto"] == selected].iloc[0].to_dict()

    name = st.text_input("Nombre", value=str(default.get("producto", "")), key="product_name")
    price_text = money_input("Precio", key="product_price", value=str(default.get("precio", "")), placeholder="Ej. 95")
    profit_text = money_input("Ganancia personal", key="product_profit", value=str(default.get("ganancia_personal", "")), placeholder="Ej. 40")
    active = st.selectbox("Activo", ["si", "no"], index=0 if str(default.get("activo", "si")) != "no" else 1)

    if st.button("Guardar producto"):
        if not name.strip():
            st.error("Escribe el nombre.")
        else:
            df = load_products(active_only=False)
            record = {
                "producto": name.strip(),
                "precio": parse_money(price_text),
                "ganancia_personal": parse_money(profit_text),
                "activo": active,
            }

            if selected != "Nuevo producto" and selected in df["producto"].tolist():
                df.loc[df["producto"] == selected, ["producto", "precio", "ganancia_personal", "activo"]] = [
                    record["producto"], record["precio"], record["ganancia_personal"], record["activo"]
                ]
            elif name.strip() in df["producto"].tolist():
                df.loc[df["producto"] == name.strip(), ["precio", "ganancia_personal", "activo"]] = [
                    record["precio"], record["ganancia_personal"], record["activo"]
                ]
            else:
                df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

            save_products(df)
            st.success("Producto guardado.")
            st.rerun()


def report_data(ventas):
    if ventas.empty:
        return None, None, None, pd.DataFrame(), pd.DataFrame()

    by_day = ventas.groupby("dia_semana").agg(
        ventas=("total_linea", "sum"),
        cantidad=("cantidad", "sum"),
        ganancia=("ganancia_personal_linea", "sum"),
    ).reset_index().sort_values("ventas", ascending=False)

    by_product = ventas.groupby("producto").agg(
        cantidad=("cantidad", "sum"),
        ventas=("total_linea", "sum"),
        ganancia=("ganancia_personal_linea", "sum"),
    ).reset_index()

    top_day = by_day.iloc[0] if not by_day.empty else None
    top_sold = by_product.sort_values("cantidad", ascending=False).iloc[0] if not by_product.empty else None
    top_profit = by_product.sort_values("ganancia", ascending=False).iloc[0] if not by_product.empty else None

    return top_day, top_sold, top_profit, by_day, by_product


def show_period_report(title, start, end):
    ventas = filter_dates(ventas_df(), start, end)
    st.subheader(title)

    if ventas.empty:
        st.info("No hay ventas en este periodo.")
        return

    top_day, top_sold, top_profit, by_day, by_product = report_data(ventas)

    c1, c2 = st.columns(2)
    c1.metric("Ventas", pesos(ventas["total_linea"].sum()))
    c2.metric("Ganancia personal", pesos(ventas["ganancia_personal_linea"].sum()))

    if top_day is not None:
        st.write(f"**Día que más vende:** {top_day['dia_semana']} con {pesos(top_day['ventas'])}.")
    if top_sold is not None:
        st.write(f"**Producto más vendido:** {top_sold['producto']} con {top_sold['cantidad']:g} unidades.")
    if top_profit is not None:
        st.write(f"**Producto con más ganancia:** {top_profit['producto']} con {pesos(top_profit['ganancia'])}.")

    with st.expander("Detalle"):
        st.write("Por producto")
        st.dataframe(by_product.sort_values("ganancia", ascending=False), use_container_width=True)
        st.write("Por día")
        st.dataframe(by_day, use_container_width=True)


def page_reportes():
    st.header("Reportes")

    start, end = period_picker("reportes")
    ventas = filter_dates(ventas_df(), start, end)
    gastos = filter_dates(gastos_df(), start, end)

    ventas_brutas = ventas["total_linea"].sum() if not ventas.empty else 0
    ventas_netas = ventas["total_neto_linea"].sum() if not ventas.empty else 0
    mi_paga = ventas["ganancia_personal_linea"].sum() if not ventas.empty else 0
    gastos_total = gastos["monto"].sum() if not gastos.empty else 0

    c1, c2 = st.columns(2)
    c1.metric("Ventas brutas", pesos(ventas_brutas))
    c2.metric("Ventas netas", pesos(ventas_netas))
    c3, c4 = st.columns(2)
    c3.metric("Mi paga generada", pesos(mi_paga))
    c4.metric("Gastos", pesos(gastos_total))
    st.metric("Balance ventas - gastos", pesos(ventas_netas - gastos_total))

    if not ventas.empty:
        top_day, top_sold, top_profit, by_day, by_product = report_data(ventas)
        st.subheader("Resumen")
        if top_day is not None:
            st.write(f"**Día que más se vende:** {top_day['dia_semana']} con {pesos(top_day['ventas'])}.")
        if top_sold is not None:
            st.write(f"**Producto más vendido:** {top_sold['producto']} con {top_sold['cantidad']:g} unidades.")
        if top_profit is not None:
            st.write(f"**Producto con más ganancia:** {top_profit['producto']} con {pesos(top_profit['ganancia'])}.")
        st.write("Productos")
        st.dataframe(by_product.sort_values("ganancia", ascending=False), use_container_width=True)
        st.write("Días")
        st.dataframe(by_day, use_container_width=True)

    st.divider()
    st.subheader("Comparativo")
    for title in ["Semana", "Quincena", "Mes", "Año"]:
        with st.expander(title):
            s, e = period_dates(title)
            show_period_report(title, s, e)


def page_historial():
    st.header("Historial")

    df = movements_df()
    if df.empty:
        st.info("Todavía no hay movimientos.")
        return

    start, end = period_picker("historial")
    filtered = filter_dates(df, start, end)

    types = sorted([t for t in filtered["tipo"].astype(str).unique().tolist() if t])
    selected_type = st.selectbox("Tipo", ["Todos"] + types)

    if selected_type != "Todos":
        filtered = filtered[filtered["tipo"] == selected_type].copy()

    query = st.text_input("Buscar", placeholder="Ej. pan, carne, tarjeta, pago")
    if query.strip():
        q = query.strip().lower()
        mask = (
            filtered["producto"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["nota"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["pagado_con"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["metodo_pago"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["tipo"].astype(str).str.lower().str.contains(q, na=False)
        )
        filtered = filtered[mask].copy()

    ventas = filtered[filtered["tipo"] == "venta"]
    gastos = filtered[filtered["tipo"] == "gasto"]
    pagos_personales = filtered[filtered["tipo"] == "pago_personal"]
    pagos_deuda = filtered[filtered["tipo"] == "pago_deuda"]

    c1, c2 = st.columns(2)
    c1.metric("Ventas netas", pesos(ventas["total_neto_linea"].sum() if not ventas.empty else 0))
    c2.metric("Gastos", pesos(gastos["monto"].sum() if not gastos.empty else 0))
    c3, c4 = st.columns(2)
    c3.metric("Pagos personales", pesos(pagos_personales["monto"].sum() if not pagos_personales.empty else 0))
    c4.metric("Pagos de deuda", pesos(pagos_deuda["monto"].sum() if not pagos_deuda.empty else 0))

    cols = [
        "fecha_hora", "tipo", "producto", "cantidad", "total_linea",
        "monto", "pagado_con", "metodo_pago", "nota",
    ]
    cols = [c for c in cols if c in filtered.columns]
    st.dataframe(filtered.sort_values("fecha_hora", ascending=False)[cols], use_container_width=True)

    with st.expander("Resumen por tipo"):
        summary = filtered.groupby("tipo").agg(
            filas=("tipo", "count"),
            monto=("monto", "sum"),
            ventas=("total_linea", "sum"),
            ganancia=("ganancia_personal_linea", "sum"),
        ).reset_index()
        st.dataframe(summary, use_container_width=True)

    with st.expander("Tabla completa"):
        st.dataframe(filtered.sort_values("fecha_hora", ascending=False), use_container_width=True)


def page_diagnostico():
    st.header("Diagnóstico")

    if st.button("Probar guardado rápido en Movimientos"):
        try:
            before_count, after_count = append_record_verified("movimientos", {
                **record_datetime(),
                "tipo": "diagnostico",
                "movimiento_id": new_id(),
                "producto": "prueba",
                "monto": 1,
                "nota": "Prueba de guardado desde la app",
            })
            st.success(f"Prueba guardada. Filas en Movimientos: {before_count} → {after_count}.")
        except Exception as error:
            st.error(f"No se pudo guardar la prueba: {error}")

    for key, info in SHEETS.items():
        df = load_df(key)
        st.write(f"**{info['name']}** · {len(df)} filas")
        with st.expander(f"Ver {info['name']}"):
            st.dataframe(df.head(100), use_container_width=True)


def check_password():
    password = st.secrets.get("app", {}).get("password", "")
    if not password:
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.subheader("Acceso")
    entered = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    return False


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🥪", layout="centered")
    apply_style()
    header()

    if not check_password():
        return

    try:
        setup_sheets()
    except Exception as error:
        st.error("No se pudo conectar con Google Sheets.")
        st.exception(error)
        st.stop()

    if st.sidebar.button("Actualizar datos"):
        clear_cache()
        st.rerun()

    page = st.sidebar.radio(
        "Menú",
        [
            "Pedidos",
            "Gastos",
            "Saldo y deuda",
            "Pago personal",
            "Productos",
            "Reportes",
            "Historial",
            "Diagnóstico",
        ],
    )

    if page == "Pedidos":
        page_pedidos()
    elif page == "Gastos":
        page_gastos()
    elif page == "Saldo y deuda":
        page_saldos()
    elif page == "Pago personal":
        page_pago_personal()
    elif page == "Productos":
        page_productos()
    elif page == "Reportes":
        page_reportes()
    elif page == "Historial":
        page_historial()
    elif page == "Diagnóstico":
        page_diagnostico()


if __name__ == "__main__":
    main()


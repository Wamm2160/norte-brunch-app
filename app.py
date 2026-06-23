
import base64
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
TIMEZONE = ZoneInfo("America/Mexico_City")
CARD_FEE_RATE = 0.035
TITHING_RATE = 0.10
DEBT_PAYMENT_ALERT_AMOUNT = 10000


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
    "ventas": {
        "name": "Ventas",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "venta_id", "pedido_id", "pedido_numero",
            "producto", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
            "total_linea", "ganancia_personal_linea", "dinero_norte_linea",
            "metodo_pago", "comision_terminal_linea", "total_neto_linea", "nota",
        ],
        "default_rows": [],
    },
    "gastos": {
        "name": "Gastos",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "gasto_id", "producto_gasto", "monto",
            "pagado_con", "aumenta_deuda", "nota",
        ],
        "default_rows": [],
    },
    "pagos_personales": {
        "name": "Pagos_Personales",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "pago_id", "monto_pago_bruto", "diezmo_sugerido",
            "pago_libre_estimado", "nota",
        ],
        "default_rows": [],
    },
    "deuda_movimientos": {
        "name": "Deuda_Movimientos",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "movimiento_id", "tipo", "monto", "deuda_resultante", "nota",
        ],
        "default_rows": [],
    },
    "ajustes_saldo": {
        "name": "Ajustes_Saldo",
        "headers": [
            "fecha_hora", "fecha", "hora",
            "ajuste_id", "tipo", "monto", "saldo_resultante", "nota",
        ],
        "default_rows": [],
    },
    "saldos": {
        "name": "Saldos",
        "headers": ["clave", "valor"],
        "default_rows": [
            ["saldo_norte_brunch", 0],
            ["deuda_norte_a_mi", 0],
            ["ganancia_personal_pendiente", 0],
            ["ganancia_personal_pagada", 0],
            ["ventas_totales_brutas", 0],
            ["ventas_totales_netas", 0],
            ["total_para_norte", 0],
            ["total_gastos_negocio", 0],
            ["gastos_pagados_norte", 0],
            ["gastos_pagados_personal", 0],
            ["total_comisiones_terminal", 0],
            ["ultimo_movimiento_saldo", ""],
        ],
    },
}


def mx_now():
    return datetime.now(TIMEZONE)


def pesos(value):
    try:
        value = float(value)
    except Exception:
        value = 0
    return f"${value:,.2f} MXN"


def to_float(value):
    if value is None:
        return 0.0
    text = str(value).replace("$", "").replace(",", "").strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def now_record():
    now = mx_now()
    return {
        "fecha_hora": now.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha": now.strftime("%Y-%m-%d"),
        "hora": now.strftime("%H:%M:%S"),
    }


def selected_datetime_record(prefix):
    today = mx_now().date()
    now_t = mx_now().time().replace(second=0, microsecond=0)
    c1, c2 = st.columns(2)
    selected_date = c1.date_input("Fecha", value=today, key=f"{prefix}_fecha")
    selected_time = c2.time_input("Hora", value=now_t, key=f"{prefix}_hora")
    dt = datetime.combine(selected_date, selected_time).replace(tzinfo=TIMEZONE)
    return {
        "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha": dt.strftime("%Y-%m-%d"),
        "hora": dt.strftime("%H:%M:%S"),
    }


def is_saturday_after_6pm():
    now = mx_now()
    return now.weekday() == 5 and now.time() >= dtime(18, 0)


def next_saturday_6pm():
    now = mx_now()
    days_ahead = (5 - now.weekday()) % 7
    candidate = datetime.combine(now.date() + timedelta(days=days_ahead), dtime(18, 0), tzinfo=TIMEZONE)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def apply_mobile_style():
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
            max-width: 220px;
            width: min(64vw, 220px);
            height: auto;
            display: block;
            margin: 0 auto;
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
            font-size: 2.45rem;
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
            font-size: 2.25rem;
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
        label, p, div, span, h1, h2, h3 {
            color: #1F2933;
        }
        input, textarea {
            color: #111827 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    logo_path = Path("logo.png")
    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        st.markdown(
            f'<div class="nb-logo-wrap"><img src="data:image/png;base64,{b64}" alt="Norte Brunch"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.title("Norte Brunch")
    st.markdown('<div class="nb-subtitle">Control del negocio</div>', unsafe_allow_html=True)


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


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def get_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Falta configurar [gcp_service_account] en Streamlit Secrets.")
        st.stop()

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
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
        st.error("Falta spreadsheet_id en Streamlit Secrets. Puedes usar [google_sheet] spreadsheet_id como antes.")
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
    workbook = get_workbook()
    info = SHEETS[sheet_key]
    try:
        return google_call(workbook.worksheet, info["name"])
    except Exception:
        ws = google_call(workbook.add_worksheet, title=info["name"], rows=1000, cols=max(len(info["headers"]) + 4, 12))
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

    current = values[0]
    changed = False
    for header in expected:
        if header not in current:
            current.append(header)
            changed = True

    if changed:
        google_call(ws.update, "1:1", [current])


def setup_workbook():
    for key in SHEETS:
        get_ws(key)
        ensure_headers(key)


def clear_cache():
    try:
        load_df.clear()
    except Exception:
        pass


@st.cache_data(ttl=120)
def load_df(sheet_key):
    ws = get_ws(sheet_key)
    values = google_call(ws.get_all_values)
    if not values:
        return pd.DataFrame(columns=SHEETS[sheet_key]["headers"])

    headers = [str(h).strip() for h in values[0]]
    rows = values[1:]
    cleaned = []
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        cleaned.append(padded[:len(headers)])
    return pd.DataFrame(cleaned, columns=headers)


def append_record(sheet_key, record):
    ws = get_ws(sheet_key)
    ensure_headers(sheet_key)
    headers = google_call(ws.row_values, 1)
    row = [record.get(h, "") for h in headers]
    google_call(ws.append_row, row, value_input_option="USER_ENTERED")
    clear_cache()


def replace_records(sheet_key, records):
    ws = get_ws(sheet_key)
    headers = SHEETS[sheet_key]["headers"]
    google_call(ws.clear)
    google_call(ws.append_row, headers, value_input_option="USER_ENTERED")
    rows = [[record.get(h, "") for h in headers] for record in records]
    if rows:
        google_call(ws.append_rows, rows, value_input_option="USER_ENTERED")
    clear_cache()


def get_saldos():
    df = load_df("saldos")
    saldos = {}

    if not df.empty:
        for _, row in df.iterrows():
            key = str(row.get("clave", "")).strip()
            if key:
                saldos[key] = row.get("valor", 0)

    for row in SHEETS["saldos"]["default_rows"]:
        saldos.setdefault(row[0], row[1])

    numeric_keys = [
        "saldo_norte_brunch", "deuda_norte_a_mi", "ganancia_personal_pendiente",
        "ganancia_personal_pagada", "ventas_totales_brutas", "ventas_totales_netas",
        "total_para_norte", "total_gastos_negocio", "gastos_pagados_norte",
        "gastos_pagados_personal", "total_comisiones_terminal",
    ]

    for key in numeric_keys:
        saldos[key] = to_float(saldos.get(key, 0))

    saldos["ultimo_movimiento_saldo"] = str(saldos.get("ultimo_movimiento_saldo", "")).strip()
    return saldos


def save_saldos(saldos):
    records = []
    for key, _ in SHEETS["saldos"]["default_rows"]:
        records.append({"clave": key, "valor": saldos.get(key, "")})
    replace_records("saldos", records)


def change_saldo(saldos, key, amount):
    saldos[key] = round(to_float(saldos.get(key, 0)) + float(amount), 2)


def mark_saldo_movement(saldos):
    saldos["ultimo_movimiento_saldo"] = mx_now().strftime("%Y-%m-%d %H:%M:%S")


def set_saldo_manual(new_amount, note):
    saldos = get_saldos()
    saldos["saldo_norte_brunch"] = round(to_float(new_amount), 2)
    mark_saldo_movement(saldos)
    save_saldos(saldos)

    append_record("ajustes_saldo", {
        **now_record(),
        "ajuste_id": str(uuid.uuid4()),
        "tipo": "ajuste manual",
        "monto": new_amount,
        "saldo_resultante": saldos["saldo_norte_brunch"],
        "nota": note,
    })


def set_deuda_manual(new_amount, note):
    saldos = get_saldos()
    saldos["deuda_norte_a_mi"] = round(to_float(new_amount), 2)
    save_saldos(saldos)

    append_record("deuda_movimientos", {
        **now_record(),
        "movimiento_id": str(uuid.uuid4()),
        "tipo": "ajuste manual",
        "monto": new_amount,
        "deuda_resultante": saldos["deuda_norte_a_mi"],
        "nota": note,
    })


def pay_debt(amount, note):
    amount = round(to_float(amount), 2)
    saldos = get_saldos()
    amount = min(amount, saldos["deuda_norte_a_mi"], saldos["saldo_norte_brunch"])

    if amount <= 0:
        st.error("No hay saldo suficiente o no hay deuda.")
        return

    change_saldo(saldos, "saldo_norte_brunch", -amount)
    change_saldo(saldos, "deuda_norte_a_mi", -amount)
    mark_saldo_movement(saldos)
    save_saldos(saldos)

    append_record("deuda_movimientos", {
        **now_record(),
        "movimiento_id": str(uuid.uuid4()),
        "tipo": "pago",
        "monto": amount,
        "deuda_resultante": saldos["deuda_norte_a_mi"],
        "nota": note,
    })

    append_record("ajustes_saldo", {
        **now_record(),
        "ajuste_id": str(uuid.uuid4()),
        "tipo": "pago de deuda",
        "monto": -amount,
        "saldo_resultante": saldos["saldo_norte_brunch"],
        "nota": note,
    })


def can_alert_debt_payment():
    saldos = get_saldos()
    if saldos["deuda_norte_a_mi"] <= 0:
        return False, "No hay deuda pendiente."
    if saldos["saldo_norte_brunch"] < DEBT_PAYMENT_ALERT_AMOUNT:
        return False, f"Saldo menor a {pesos(DEBT_PAYMENT_ALERT_AMOUNT)}."

    last = saldos.get("ultimo_movimiento_saldo", "")
    if not last:
        return True, "Hay saldo suficiente y no hay fecha de último movimiento."

    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE)
    except Exception:
        return True, "Hay saldo suficiente."

    days = (mx_now() - last_dt).days
    if days >= 7:
        return True, f"El saldo lleva {days} días sin movimiento."
    return False, f"El saldo todavía se movió recientemente. Último movimiento: {last}."


def load_products(active_only=True):
    df = load_df("productos")
    if df.empty:
        return pd.DataFrame(columns=SHEETS["productos"]["headers"])
    df = df.copy()
    for col in ["precio", "ganancia_personal"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    if "activo" not in df.columns:
        df["activo"] = "si"
    df["activo"] = df["activo"].astype(str).str.lower().replace("", "si")
    if active_only:
        df = df[df["activo"] != "no"]
    return df.reset_index(drop=True)


def save_products(df):
    records = []
    for _, row in df.iterrows():
        records.append({
            "producto": str(row.get("producto", "")).strip(),
            "precio": to_float(row.get("precio", 0)),
            "ganancia_personal": to_float(row.get("ganancia_personal", 0)),
            "activo": str(row.get("activo", "si")).strip().lower() or "si",
        })
    replace_records("productos", records)


def calculate_line(product, quantity, price, profit, card_fee=0):
    quantity = int(quantity)
    price = to_float(price)
    profit = to_float(profit)
    card_fee = to_float(card_fee)

    total = round(quantity * price, 2)
    profit_line = round(quantity * profit, 2)
    norte = round(total - profit_line - card_fee, 2)
    net = round(total - card_fee, 2)

    return {
        "producto": product,
        "cantidad": quantity,
        "precio_unitario": price,
        "ganancia_personal_unitaria": profit,
        "total_linea": total,
        "ganancia_personal_linea": profit_line,
        "dinero_norte_linea": norte,
        "comision_terminal_linea": card_fee,
        "total_neto_linea": net,
    }


def load_pedidos():
    df = load_df("pedidos")
    if df.empty:
        return pd.DataFrame(columns=SHEETS["pedidos"]["headers"])

    numeric = [
        "pedido_numero", "cantidad", "precio_unitario", "ganancia_personal_unitaria",
        "total_linea", "ganancia_personal_linea", "dinero_norte_linea",
    ]
    for col in numeric:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "estado" not in df.columns:
        df["estado"] = ""
    return df


def save_pedidos_df(df):
    records = []
    for _, row in df.iterrows():
        records.append({h: row.get(h, "") for h in SHEETS["pedidos"]["headers"]})
    replace_records("pedidos", records)


def get_next_order_number(today_text=None):
    if today_text is None:
        today_text = mx_now().strftime("%Y-%m-%d")
    df = load_pedidos()
    if df.empty:
        return 1

    today_orders = df[df["fecha"].astype(str) == str(today_text)]
    if today_orders.empty:
        return 1

    nums = pd.to_numeric(today_orders["pedido_numero"], errors="coerce").fillna(0)
    max_num = int(nums.max()) if not nums.empty else 0
    return max_num + 1


def create_pending_order(note=""):
    fecha = now_record()
    pedido_id = str(uuid.uuid4())
    pedido_numero = get_next_order_number(fecha["fecha"])

    append_record("pedidos", {
        **fecha,
        "pedido_id": pedido_id,
        "pedido_numero": pedido_numero,
        "estado": "pendiente",
        "producto": "",
        "cantidad": 0,
        "precio_unitario": 0,
        "ganancia_personal_unitaria": 0,
        "total_linea": 0,
        "ganancia_personal_linea": 0,
        "dinero_norte_linea": 0,
        "nota": note,
    })
    return pedido_id, pedido_numero


def pending_order_ids():
    df = load_pedidos()
    if df.empty:
        return []

    pending = df[df["estado"].astype(str).str.lower() == "pendiente"].copy()
    if pending.empty:
        return []

    result = []
    for pedido_id, group in pending.groupby("pedido_id", sort=False):
        if str(pedido_id).strip() == "":
            continue
        numero = int(pd.to_numeric(group["pedido_numero"], errors="coerce").fillna(0).max())
        fecha = str(group["fecha"].iloc[0])
        total = float(group["total_linea"].sum())
        result.append({
            "pedido_id": pedido_id,
            "pedido_numero": numero,
            "fecha": fecha,
            "total": total,
            "label": f"Pedido {numero} · {fecha} · {pesos(total)}",
        })
    return result


def add_line_to_order(pedido_id, product_name, quantity):
    products = load_products(active_only=True)
    row = products[products["producto"] == product_name].iloc[0]
    line = calculate_line(row["producto"], quantity, row["precio"], row["ganancia_personal"])

    df = load_pedidos()
    order_rows = df[df["pedido_id"] == pedido_id]
    if order_rows.empty:
        st.error("No encontré el pedido.")
        return

    pedido_numero = int(pd.to_numeric(order_rows["pedido_numero"], errors="coerce").fillna(0).max())

    append_record("pedidos", {
        **now_record(),
        "pedido_id": pedido_id,
        "pedido_numero": pedido_numero,
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
    df = load_pedidos()
    if df.empty:
        return
    if row_index in df.index:
        df.loc[row_index, "estado"] = "eliminado"
        save_pedidos_df(df)


def cancel_order(pedido_id):
    df = load_pedidos()
    if df.empty:
        return
    mask = (df["pedido_id"].astype(str) == str(pedido_id)) & (df["estado"].astype(str).str.lower() == "pendiente")
    df.loc[mask, "estado"] = "cancelado"
    save_pedidos_df(df)


def get_order_lines(pedido_id, keep_index=False):
    df = load_pedidos()
    if df.empty:
        return pd.DataFrame(columns=SHEETS["pedidos"]["headers"])

    lines = df[
        (df["pedido_id"].astype(str) == str(pedido_id))
        & (df["estado"].astype(str).str.lower() == "pendiente")
        & (df["producto"].astype(str).str.strip() != "")
    ].copy()
    return lines if keep_index else lines.reset_index(drop=True)


def order_totals(lines):
    if lines.empty:
        return {"total": 0, "profit": 0, "norte": 0}
    return {
        "total": round(float(lines["total_linea"].sum()), 2),
        "profit": round(float(lines["ganancia_personal_linea"].sum()), 2),
        "norte": round(float(lines["dinero_norte_linea"].sum()), 2),
    }


def pay_order(pedido_id, payment_method, note):
    lines = get_order_lines(pedido_id)
    if lines.empty:
        st.error("Este pedido no tiene artículos pendientes.")
        return

    totals = order_totals(lines)
    total = totals["total"]
    venta_id = str(uuid.uuid4())

    card_total = total if payment_method == "Tarjeta" else 0
    fee_total = round(card_total * CARD_FEE_RATE, 2)

    total_profit = 0
    total_norte = 0
    total_net = 0

    for _, item in lines.iterrows():
        share = to_float(item["total_linea"]) / total if total else 0
        fee_line = round(fee_total * share, 2)

        line = calculate_line(
            item["producto"],
            item["cantidad"],
            item["precio_unitario"],
            item["ganancia_personal_unitaria"],
            card_fee=fee_line,
        )

        total_profit += line["ganancia_personal_linea"]
        total_norte += line["dinero_norte_linea"]
        total_net += line["total_neto_linea"]

        append_record("ventas", {
            **now_record(),
            "venta_id": venta_id,
            "pedido_id": pedido_id,
            "pedido_numero": item.get("pedido_numero", ""),
            **line,
            "metodo_pago": payment_method,
            "nota": note,
        })

    total_profit = round(total_profit, 2)
    total_norte = round(total_norte, 2)
    total_net = round(total_net, 2)

    df = load_pedidos()
    mask = (df["pedido_id"].astype(str) == str(pedido_id)) & (df["estado"].astype(str).str.lower() == "pendiente")
    df.loc[mask, "estado"] = "pagado"
    save_pedidos_df(df)

    saldos = get_saldos()
    change_saldo(saldos, "saldo_norte_brunch", total_net)
    change_saldo(saldos, "ganancia_personal_pendiente", total_profit)
    change_saldo(saldos, "ventas_totales_brutas", total)
    change_saldo(saldos, "ventas_totales_netas", total_net)
    change_saldo(saldos, "total_para_norte", total_norte)
    change_saldo(saldos, "total_comisiones_terminal", fee_total)
    mark_saldo_movement(saldos)
    save_saldos(saldos)

    big_paid("PEDIDO PAGADO", total_net)
    st.success(
        f"Venta bruta: {pesos(total)} | Para tu paga: {pesos(total_profit)} | "
        f"Para Norte Brunch: {pesos(total_norte)}"
    )
    st.rerun()


def ventas_df():
    df = load_df("ventas")
    if df.empty:
        return df
    numeric = [
        "cantidad", "precio_unitario", "ganancia_personal_unitaria", "total_linea",
        "ganancia_personal_linea", "dinero_norte_linea",
        "comision_terminal_linea", "total_neto_linea",
    ]
    for col in numeric:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    return df


def gastos_df():
    df = load_df("gastos")
    if df.empty:
        return df
    if "monto" not in df.columns:
        df["monto"] = 0
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0.0).astype(float)
    return df


def filter_by_period(df, start_date, end_date):
    if df.empty or "fecha" not in df.columns:
        return df
    temp = df.copy()
    temp["fecha_dt"] = pd.to_datetime(temp["fecha"], errors="coerce").dt.date
    return temp[(temp["fecha_dt"] >= start_date) & (temp["fecha_dt"] <= end_date)].drop(columns=["fecha_dt"])


def period_picker(prefix):
    today = mx_now().date()
    option = st.selectbox(
        "Periodo",
        ["Hoy", "Esta semana", "Este mes", "Personalizado"],
        key=f"{prefix}_periodo",
    )

    if option == "Hoy":
        return today, today

    if option == "Esta semana":
        start = today - timedelta(days=today.weekday())
        return start, today

    if option == "Este mes":
        return today.replace(day=1), today

    c1, c2 = st.columns(2)
    start = c1.date_input("Desde", value=today - timedelta(days=7), key=f"{prefix}_start")
    end = c2.date_input("Hasta", value=today, key=f"{prefix}_end")
    return start, end


def page_venta():
    st.header("Pedidos")

    products = load_products(active_only=True)
    if products.empty:
        st.warning("No hay productos activos.")
        return

    if st.button("Crear nuevo pedido"):
        _, numero = create_pending_order()
        st.success(f"Pedido {numero} creado.")
        st.rerun()

    pedidos = pending_order_ids()
    if not pedidos:
        st.info("No hay pedidos pendientes. Crea un pedido para empezar.")
        return

    selected_label = st.selectbox("Pedido pendiente", [p["label"] for p in pedidos])
    selected = next(p for p in pedidos if p["label"] == selected_label)
    pedido_id = selected["pedido_id"]

    st.subheader(f"Pedido {selected['pedido_numero']}")

    st.write("Agregar artículos")
    cols = st.columns(2)
    for idx, row in products.iterrows():
        label = f"{row['producto']} · {pesos(row['precio'])}"
        if cols[idx % 2].button(label, key=f"order_quick_{pedido_id}_{idx}"):
            add_line_to_order(pedido_id, row["producto"], 1)
            st.rerun()

    with st.expander("Agregar con cantidad"):
        c1, c2 = st.columns([2, 1])
        product_name = c1.selectbox("Producto", products["producto"].tolist(), key=f"select_{pedido_id}")
        qty = c2.number_input("Cantidad", min_value=1, value=1, step=1, key=f"qty_{pedido_id}")
        if st.button("Agregar al pedido", key=f"add_{pedido_id}"):
            add_line_to_order(pedido_id, product_name, qty)
            st.rerun()

    st.divider()
    st.subheader("Artículos del pedido")
    lines = get_order_lines(pedido_id, keep_index=True)

    if lines.empty:
        st.info("Este pedido todavía no tiene artículos.")
    else:
        for original_idx, item in lines.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{item['producto']}** x {int(to_float(item['cantidad']))}")
            c2.write(pesos(item["total_linea"]))
            if c3.button("Quitar", key=f"remove_line_{pedido_id}_{original_idx}"):
                remove_order_line(original_idx)
                st.rerun()

        totals = order_totals(lines)
        big_total("TOTAL A COBRAR", totals["total"])

        c1, c2 = st.columns(2)
        c1.metric("Para mi paga", pesos(totals["profit"]))
        c2.metric("Para Norte Brunch", pesos(totals["norte"]))

        payment_method = st.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key=f"pay_method_{pedido_id}")
        if payment_method == "Tarjeta":
            st.warning(f"Comisión terminal: {pesos(totals['total'] * CARD_FEE_RATE)}")

        note = st.text_input("Nota", placeholder="Opcional", key=f"note_{pedido_id}")

        if st.button("Cobrar pedido", key=f"pay_{pedido_id}"):
            pay_order(pedido_id, payment_method, note)

    st.divider()
    if st.button("Cancelar pedido completo", key=f"cancel_{pedido_id}"):
        cancel_order(pedido_id)
        st.success("Pedido cancelado.")
        st.rerun()


def page_gastos():
    st.header("Gastos de Norte Brunch")

    with st.form("gasto_form"):
        fecha = selected_datetime_record("gasto_form")
        producto_gasto = st.text_input("Gasto", placeholder="Ej. pan, carne, renta, gasolina")
        monto = st.number_input("Monto", min_value=0.0, step=10.0)
        pagado_con = st.radio("Pagado con", ["Dinero de Norte Brunch", "Mi dinero personal"], horizontal=False)
        nota = st.text_input("Nota", placeholder="Opcional")
        guardar = st.form_submit_button("Guardar gasto")

    if guardar:
        if not producto_gasto.strip() or monto <= 0:
            st.error("Falta gasto o monto.")
            return

        gasto_id = str(uuid.uuid4())
        saldos = get_saldos()

        aumenta_deuda = "no"
        if pagado_con == "Dinero de Norte Brunch":
            change_saldo(saldos, "saldo_norte_brunch", -monto)
            change_saldo(saldos, "gastos_pagados_norte", monto)
            mark_saldo_movement(saldos)
        else:
            change_saldo(saldos, "deuda_norte_a_mi", monto)
            change_saldo(saldos, "gastos_pagados_personal", monto)
            aumenta_deuda = "si"

        change_saldo(saldos, "total_gastos_negocio", monto)
        save_saldos(saldos)

        append_record("gastos", {
            **fecha,
            "gasto_id": gasto_id,
            "producto_gasto": producto_gasto.strip(),
            "monto": monto,
            "pagado_con": pagado_con,
            "aumenta_deuda": aumenta_deuda,
            "nota": nota,
        })

        if aumenta_deuda == "si":
            append_record("deuda_movimientos", {
                **fecha,
                "movimiento_id": str(uuid.uuid4()),
                "tipo": "aumento por gasto pagado por mí",
                "monto": monto,
                "deuda_resultante": saldos["deuda_norte_a_mi"],
                "nota": producto_gasto.strip(),
            })

        st.success("Gasto guardado.")
        st.rerun()

    st.divider()
    start, end = period_picker("gastos")
    df = filter_by_period(gastos_df(), start, end)
    st.metric("Gastos del periodo", pesos(df["monto"].sum() if not df.empty else 0))
    st.dataframe(df, use_container_width=True)


def page_saldos():
    st.header("Saldo y deuda")

    saldos = get_saldos()

    alert, reason = can_alert_debt_payment()
    if alert:
        st.warning(
            f"Norte Brunch puede abonarte a la deuda. "
            f"Saldo: {pesos(saldos['saldo_norte_brunch'])}. Deuda: {pesos(saldos['deuda_norte_a_mi'])}. {reason}"
        )

    c1, c2 = st.columns(2)
    c1.metric("Saldo Norte Brunch", pesos(saldos["saldo_norte_brunch"]))
    c2.metric("Mi paga pendiente", pesos(saldos["ganancia_personal_pendiente"]))

    st.divider()
    st.subheader("Balance operativo")
    st.caption("Ventas contra gastos del negocio. No incluye la deuda de Norte Brunch hacia ti.")

    b1, b2 = st.columns(2)
    b1.metric("Ventas netas acumuladas", pesos(saldos["ventas_totales_netas"]))
    b2.metric("Gastos del negocio", pesos(saldos["total_gastos_negocio"]))

    balance_operativo = saldos["ventas_totales_netas"] - saldos["total_gastos_negocio"]
    st.metric("Balance ventas - gastos", pesos(balance_operativo))

    st.divider()
    st.subheader("Balance de deuda hacia mí")
    st.caption("Aquí solo se maneja deuda y pagos de deuda. No se mezclan pagos de ganancia personal.")

    debt_df = load_df("deuda_movimientos")
    if not debt_df.empty:
        debt_df["monto"] = pd.to_numeric(debt_df["monto"], errors="coerce").fillna(0.0)
        pagos_deuda = debt_df[debt_df["tipo"].astype(str).str.lower().str.contains("pago")]["monto"].sum()
        aumentos_deuda = debt_df[~debt_df["tipo"].astype(str).str.lower().str.contains("pago")]["monto"].sum()
    else:
        pagos_deuda = 0
        aumentos_deuda = 0

    d1, d2 = st.columns(2)
    d1.metric("Deuda actual", pesos(saldos["deuda_norte_a_mi"]))
    d2.metric("Pagos de deuda hacia mí", pesos(pagos_deuda))

    d3, d4 = st.columns(2)
    d3.metric("Aumentos de deuda", pesos(aumentos_deuda))
    d4.metric("Deuda restante", pesos(saldos["deuda_norte_a_mi"]))

    st.divider()
    st.subheader("Ajustes manuales")

    tab1, tab2, tab3 = st.tabs(["Ajustar saldo", "Ajustar deuda", "Pagar deuda"])

    with tab1:
        with st.form("ajuste_saldo_form"):
            nuevo_saldo = st.number_input("Nuevo saldo de Norte Brunch", min_value=0.0, step=100.0)
            nota = st.text_input("Nota del ajuste", placeholder="Ej. conteo de caja")
            guardar = st.form_submit_button("Guardar ajuste de saldo")
        if guardar:
            set_saldo_manual(nuevo_saldo, nota)
            st.success("Saldo ajustado.")
            st.rerun()

    with tab2:
        with st.form("ajuste_deuda_form"):
            nueva_deuda = st.number_input("Nueva deuda de Norte Brunch hacia mí", min_value=0.0, step=100.0)
            nota = st.text_input("Nota", placeholder="Ej. ajuste inicial")
            guardar = st.form_submit_button("Guardar ajuste de deuda")
        if guardar:
            set_deuda_manual(nueva_deuda, nota)
            st.success("Deuda ajustada.")
            st.rerun()

    with tab3:
        sugerido = min(saldos["deuda_norte_a_mi"], max(saldos["saldo_norte_brunch"] - DEBT_PAYMENT_ALERT_AMOUNT, 0))
        st.info(f"Pago sugerido sin bajar de $10,000: {pesos(sugerido)}")
        if st.button("Registrar abono sugerido a deuda"):
            pay_debt(sugerido, "Abono sugerido a deuda")
            st.success("Abono registrado.")
            st.rerun()

    with st.expander("Ver movimientos de deuda"):
        st.dataframe(debt_df, use_container_width=True)


def page_pago_personal():
    st.header("Pago personal semanal")

    saldos = get_saldos()
    st.metric("Mi paga pendiente", pesos(saldos["ganancia_personal_pendiente"]))

    if is_saturday_after_6pm():
        st.success("Ya es sábado después de las 6:00 pm. Puedes hacer tu corte semanal.")
        permitido = True
    else:
        siguiente = next_saturday_6pm()
        st.warning(f"Solo puedes pagarte los sábados después de las 6:00 pm. Próximo corte: {siguiente.strftime('%Y-%m-%d %H:%M')}")
        permitido = False

    if saldos["ganancia_personal_pendiente"] <= 0:
        st.info("No tienes paga pendiente.")
        permitido = False

    if saldos["saldo_norte_brunch"] < saldos["ganancia_personal_pendiente"]:
        st.error("Norte Brunch no tiene saldo suficiente para pagarte toda tu paga pendiente.")
        permitido = False

    with st.expander("Realizar pago personal"):
        amount = saldos["ganancia_personal_pendiente"]
        diezmo = round(amount * TITHING_RATE, 2)
        libre = round(amount - diezmo, 2)
        st.write(f"Pago bruto: **{pesos(amount)}**")
        st.write(f"Diezmo sugerido de este pago: **{pesos(diezmo)}**")
        st.write(f"Pago libre estimado: **{pesos(libre)}**")

        confirmar = st.checkbox("Confirmo que deseo registrar mi pago personal", disabled=not permitido)

        if st.button("Registrar mi pago semanal", disabled=(not permitido or not confirmar)):
            change_saldo(saldos, "saldo_norte_brunch", -amount)
            change_saldo(saldos, "ganancia_personal_pendiente", -amount)
            change_saldo(saldos, "ganancia_personal_pagada", amount)
            mark_saldo_movement(saldos)
            save_saldos(saldos)

            append_record("pagos_personales", {
                **now_record(),
                "pago_id": str(uuid.uuid4()),
                "monto_pago_bruto": amount,
                "diezmo_sugerido": diezmo,
                "pago_libre_estimado": libre,
                "nota": "Pago personal semanal",
            })

            big_paid("PAGO PERSONAL REGISTRADO", amount)
            st.success(f"Diezmo sugerido de este pago: {pesos(diezmo)}. Libre estimado: {pesos(libre)}.")
            st.rerun()


def page_productos():
    st.header("Productos")

    df = load_products(active_only=False)
    st.dataframe(df, use_container_width=True)

    st.subheader("Agregar o modificar producto")
    productos = ["Nuevo producto"] + df["producto"].tolist()
    selected = st.selectbox("Producto", productos)

    if selected == "Nuevo producto":
        default_name = ""
        default_price = 0.0
        default_profit = 0.0
        default_active = "si"
    else:
        row = df[df["producto"] == selected].iloc[0]
        default_name = row["producto"]
        default_price = to_float(row["precio"])
        default_profit = to_float(row["ganancia_personal"])
        default_active = str(row["activo"])

    with st.form("producto_form"):
        name = st.text_input("Nombre", value=default_name)
        price = st.number_input("Precio de venta", min_value=0.0, value=float(default_price), step=5.0)
        profit = st.number_input("Ganancia personal", min_value=0.0, value=float(default_profit), step=5.0)
        active = st.selectbox("Activo", ["si", "no"], index=0 if default_active != "no" else 1)
        save = st.form_submit_button("Guardar producto")

    if save:
        if not name.strip():
            st.error("Escribe el nombre.")
            return

        df = load_products(active_only=False)
        record = {
            "producto": name.strip(),
            "precio": price,
            "ganancia_personal": profit,
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


def page_reportes():
    st.header("Reportes")

    start, end = period_picker("reportes")
    ventas = filter_by_period(ventas_df(), start, end)
    gastos = filter_by_period(gastos_df(), start, end)

    ventas_brutas = ventas["total_linea"].sum() if not ventas.empty else 0
    ventas_netas = ventas["total_neto_linea"].sum() if not ventas.empty else 0
    mi_paga = ventas["ganancia_personal_linea"].sum() if not ventas.empty else 0
    norte = ventas["dinero_norte_linea"].sum() if not ventas.empty else 0
    gastos_total = gastos["monto"].sum() if not gastos.empty else 0
    balance_periodo = ventas_netas - gastos_total

    c1, c2 = st.columns(2)
    c1.metric("Ventas brutas", pesos(ventas_brutas))
    c2.metric("Ventas netas", pesos(ventas_netas))

    c3, c4 = st.columns(2)
    c3.metric("Mi paga generada", pesos(mi_paga))
    c4.metric("Para Norte Brunch", pesos(norte))

    c5, c6 = st.columns(2)
    c5.metric("Gastos", pesos(gastos_total))
    c6.metric("Balance ventas - gastos", pesos(balance_periodo))

    st.caption("La deuda hacia ti no se incluye en este balance. Tus pagos de deuda aparecen aparte en Saldo y deuda.")

    if not ventas.empty:
        st.subheader("Productos vendidos")
        resumen = ventas.groupby("producto").agg({
            "cantidad": "sum",
            "total_linea": "sum",
            "ganancia_personal_linea": "sum",
            "dinero_norte_linea": "sum",
        }).reset_index()
        st.dataframe(resumen, use_container_width=True)

    with st.expander("Ventas"):
        st.dataframe(ventas, use_container_width=True)
    with st.expander("Gastos"):
        st.dataframe(gastos, use_container_width=True)


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
    apply_mobile_style()
    render_header()

    if not check_password():
        return

    try:
        setup_workbook()
    except Exception as error:
        st.error("No se pudo conectar con Google Sheets. Revisa permisos, Secrets o cuota.")
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
        ],
    )

    if page == "Pedidos":
        page_venta()
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


if __name__ == "__main__":
    main()

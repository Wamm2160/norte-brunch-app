import uuid
import time
import random
from datetime import datetime, date, timedelta, time as dt_time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import gspread
from google.oauth2 import service_account


APP_TITLE = "Norte Brunch Finanzas"
TIMEZONE = ZoneInfo("America/Mexico_City")
TITHING_RATE = 0.10

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
            ["Torta mixta", 110, 45, "si"],
            ["Pastel", 45, 15, "si"],
            ["Cafe", 20, 10, "si"],
            ["Refresco", 30, 10, "si"],
            ["Agua de litro", 45, 25, "si"],
            ["Agua de medio litro", 30, 20, "si"],
            ["Extra aguacate", 15, 0, "si"],
            ["Extra queso", 15, 0, "si"],
        ],
    },
    "ventas": {
        "name": "Ventas",
        "headers": [
            "fecha_hora",
            "fecha",
            "hora",
            "pedido_id",
            "producto",
            "cantidad",
            "precio_unitario",
            "ganancia_personal_unitaria",
            "total_linea",
            "ganancia_personal_linea",
            "dinero_norte_linea",
            "diezmo_linea",
            "metodo_pago",
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
            ["renta/local", "si"],
            ["luz", "si"],
            ["agua", "si"],
            ["gas", "si"],
            ["internet/teléfono", "si"],
            ["transporte", "si"],
            ["mantenimiento", "si"],
            ["equipo/herramientas", "si"],
            ["publicidad", "si"],
            ["permisos", "si"],
            ["limpieza", "si"],
            ["otros", "si"],
        ],
    },
    "categorias_familia": {
        "name": "Categorias_Familia",
        "headers": ["categoria", "activo"],
        "default_rows": [
            ["comida", "si"],
            ["servicios", "si"],
            ["deudas", "si"],
            ["diezmo", "si"],
            ["renta/casa", "si"],
            ["escuela", "si"],
            ["salud", "si"],
            ["transporte", "si"],
            ["gasolina", "si"],
            ["ropa", "si"],
            ["ahorro", "si"],
            ["otros", "si"],
        ],
    },
    "config": {
        "name": "Config",
        "headers": ["clave", "valor"],
        "default_rows": [["frecuencia_diezmo", "mensual"]],
    },
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
    """Ejecuta una llamada a Google Sheets con reintentos si aparece error 429."""
    delay = 1.0
    for attempt in range(5):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as error:
            message = str(error)
            if "429" in message and attempt < 4:
                time.sleep(delay + random.random())
                delay *= 2
                continue
            raise


@st.cache_resource
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


@st.cache_data(ttl=15)
def load_df(sheet_key):
    ws = get_ws(sheet_key)
    records = google_call(ws.get_all_records)
    expected = SHEETS[sheet_key]["headers"]
    df = pd.DataFrame(records)

    if df.empty:
        return pd.DataFrame(columns=expected)

    for col in expected:
        if col not in df.columns:
            df[col] = ""

    return df


def clear_data_cache():
    load_df.clear()


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


def page_registrar_pedido():
    init_cart()
    st.header("Registrar pedido")

    products = load_active_products()
    if products.empty:
        st.warning("No hay productos activos.")
        return

    product_names = products["producto"].tolist()

    st.subheader("Venta rápida")
    st.caption("Toca un botón para agregar 1 unidad al pedido.")

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
                st.success(f"Agregado: {product}")
                st.rerun()

    st.divider()
    st.subheader("Agregar con cantidad")

    with st.form("add_to_cart"):
        col1, col2 = st.columns([2, 1])
        product = col1.selectbox("Producto", product_names)
        quantity = col2.number_input("Cantidad", min_value=1, step=1)
        add = st.form_submit_button("Agregar al pedido")

    if add:
        add_product_to_cart(products, product, quantity)
        st.success("Producto agregado.")
        st.rerun()

    if not st.session_state.cart:
        st.info("El pedido está vacío.")
        return

    st.subheader("Pedido actual")
    cart_df = pd.DataFrame(st.session_state.cart)
    st.dataframe(cart_df, use_container_width=True)

    total = cart_df["total_linea"].sum()
    profit = cart_df["ganancia_personal_linea"].sum()
    tithing = cart_df["diezmo_linea"].sum()
    norte = cart_df["dinero_norte_linea"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total a pagar", pesos(total))
    col2.metric("Ganancia para mí", pesos(profit))
    col3.metric("Diezmo", pesos(tithing))
    col4.metric("Para Norte Brunch", pesos(norte))

    st.divider()
    fecha = datetime_inputs("venta", "Fecha y hora de la venta")
    metodo_pago = st.radio(
        "Método de pago",
        ["Efectivo", "Tarjeta", "Transferencia", "Mixto"],
        horizontal=True,
    )
    nota = st.text_input("Nota de la venta", placeholder="Opcional")

    col_save, col_clear = st.columns(2)

    if col_save.button("Guardar pedido", type="primary"):
        pedido_id = str(uuid.uuid4())[:8]

        for item in st.session_state.cart:
            append_record("ventas", {
                **fecha,
                "pedido_id": pedido_id,
                "producto": item["producto"],
                "cantidad": item["cantidad"],
                "precio_unitario": item["precio_unitario"],
                "ganancia_personal_unitaria": item["ganancia_personal_unitaria"],
                "total_linea": item["total_linea"],
                "ganancia_personal_linea": item["ganancia_personal_linea"],
                "dinero_norte_linea": item["dinero_norte_linea"],
                "diezmo_linea": item["diezmo_linea"],
                "metodo_pago": metodo_pago,
                "nota": nota,
            })

        saldos = get_saldos()
        change_saldo(saldos, "dinero_norte_brunch", total)
        change_saldo(saldos, "ganancia_pendiente_personal", profit)
        change_saldo(saldos, "diezmo_pendiente", tithing)
        save_saldos(saldos)

        st.session_state.cart = []
        st.success(f"Pedido guardado. Diezmo agregado: {pesos(tithing)}")
        st.rerun()

    if col_clear.button("Vaciar pedido"):
        st.session_state.cart = []
        st.rerun()


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
    st.header("Gastos e inventario del local")

    tab1, tab2, tab3 = st.tabs(["Registrar gasto", "Inventario", "Categorías local"])

    with tab1:
        categories = load_categories("categorias_local")

        with st.form("gasto_local_form"):
            fecha = datetime_inputs("gasto_local", "Fecha y hora del gasto")

            tipo_movimiento = st.selectbox(
                "Tipo de movimiento",
                ["Compra de insumo", "Gasto del local"],
            )

            categoria = st.selectbox("Categoría del gasto", categories)
            nombre = st.text_input("Nombre / descripción", placeholder="Ej. pan, carne, renta, luz, gasolina")
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad", value="piezas")
            costo = st.number_input("Costo total", min_value=0.0, step=10.0)
            pagado_por = st.radio("Pagado por", ["Norte Brunch", "Personal/Familiar"], horizontal=True)
            nota = st.text_input("Nota", placeholder="Opcional")
            guardar = st.form_submit_button("Guardar gasto")

        if guardar:
            if not nombre.strip() or costo <= 0:
                st.error("Falta nombre o costo.")
                return

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
                    "categoria": "otros",
                    "monto": costo,
                    "metodo_pago": "Personal/Familiar",
                    "nota": f"Gasto del local pagado personalmente: {nombre.strip()}",
                })

            save_saldos(saldos)

            if tipo_movimiento == "Compra de insumo":
                update_inventory(nombre.strip(), cantidad, unidad)

            st.success("Gasto guardado.")
            st.rerun()

    with tab2:
        st.subheader("Inventario")
        st.dataframe(load_df("inventario"), use_container_width=True)

        with st.form("descontar_inventario"):
            insumo = st.text_input("Insumo a descontar")
            cantidad_usada = st.number_input("Cantidad usada", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad", value="piezas")
            descontar = st.form_submit_button("Descontar")

        if descontar:
            update_inventory(insumo, -cantidad_usada, unidad)
            st.success("Inventario actualizado.")
            st.rerun()

    with tab3:
        st.subheader("Categorías del local")
        st.dataframe(load_df("categorias_local"), use_container_width=True)
        nueva = st.text_input("Nueva categoría local")
        if st.button("Agregar categoría local"):
            add_category("categorias_local", nueva)
            st.success("Categoría agregada.")
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

    tab1, tab2, tab3 = st.tabs(["Registrar movimiento", "Reporte", "Categorías familiares"])

    with tab1:
        categories = load_categories("categorias_familia")

        with st.form("movimiento_familiar_form"):
            fecha = datetime_inputs("familia", "Fecha y hora del movimiento")
            tipo = st.radio("Tipo", ["ingreso", "gasto"], horizontal=True)

            if tipo == "gasto":
                categoria = st.selectbox("Tipo de gasto familiar", categories)
            else:
                categoria = st.selectbox("Tipo de ingreso", ["ingreso general", "pago de Norte Brunch", "otros"])

            monto = st.number_input("Monto", min_value=0.0, step=50.0)
            metodo_pago = st.selectbox("Método / origen", ["Efectivo", "Tarjeta", "Transferencia", "Norte Brunch", "Otro"])
            nota = st.text_input("Nota")
            guardar = st.form_submit_button("Guardar movimiento")

        if guardar:
            if monto <= 0:
                st.error("El monto debe ser mayor que cero.")
                return

            append_record("gastos_familiares", {
                **fecha,
                "tipo": tipo,
                "categoria": categoria,
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
            st.subheader("Resumen por categoría")
            st.dataframe(df.groupby(["tipo", "categoria"])["monto"].sum().reset_index(), use_container_width=True)
            st.subheader("Movimientos")
            st.dataframe(df, use_container_width=True)

    with tab3:
        st.dataframe(load_df("categorias_familia"), use_container_width=True)
        nueva = st.text_input("Nueva categoría familiar")
        if st.button("Agregar categoría familiar"):
            add_category("categorias_familia", nueva)
            st.success("Categoría agregada.")
            st.rerun()


# -----------------------------
# REPORTES LOCAL Y CORTE
# -----------------------------

def page_reportes_local():
    st.header("Reportes del local")

    start, end = period_filter_ui("local")
    ventas = filter_date_range(load_df("ventas"), start, end)
    gastos = filter_date_range(load_df("gastos_local"), start, end)

    ventas = to_numeric(ventas, [
        "cantidad",
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
        "diezmo_linea",
    ])
    gastos = to_numeric(gastos, ["costo_total"])

    total_ventas = ventas["total_linea"].sum() if not ventas.empty else 0
    total_ganancia = ventas["ganancia_personal_linea"].sum() if not ventas.empty else 0
    total_diezmo = ventas["diezmo_linea"].sum() if "diezmo_linea" in ventas.columns and not ventas.empty else round(total_ganancia * TITHING_RATE, 2)
    total_norte = ventas["dinero_norte_linea"].sum() if not ventas.empty else 0
    total_gastos = gastos["costo_total"].sum() if not gastos.empty else 0
    resultado = total_norte - total_gastos
    margen = (resultado / total_ventas * 100) if total_ventas else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventas", pesos(total_ventas))
    col2.metric("Ganancia personal", pesos(total_ganancia))
    col3.metric("Diezmo", pesos(total_diezmo))
    col4.metric("Gastos", pesos(total_gastos))

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
                "dinero_norte_linea": "sum",
            }).reset_index(),
            use_container_width=True,
        )

        st.subheader("Ventas por método de pago")
        ventas["metodo_pago"] = ventas["metodo_pago"].replace("", "No especificado").fillna("No especificado")
        st.dataframe(ventas.groupby("metodo_pago")["total_linea"].sum().reset_index(), use_container_width=True)

        ventas["dia_semana"] = ventas["dt"].dt.day_name().map(weekday_spanish)
        best_day = ventas.groupby("dia_semana")["total_linea"].sum().sort_values(ascending=False)
        if not best_day.empty:
            st.info(f"Mejor día del periodo: **{best_day.index[0]}** con {pesos(best_day.iloc[0])}.")

    if not gastos.empty:
        st.subheader("Gastos por categoría")
        st.dataframe(gastos.groupby("categoria")["costo_total"].sum().reset_index(), use_container_width=True)

    with st.expander("Ver datos detallados"):
        st.subheader("Ventas")
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
    ])
    gastos = to_numeric(gastos, ["costo_total"])

    if ventas.empty:
        st.warning("No hay ventas en esa fecha.")
        return

    total_ventas = ventas["total_linea"].sum()
    ganancia = ventas["ganancia_personal_linea"].sum()
    diezmo = ventas["diezmo_linea"].sum() if "diezmo_linea" in ventas.columns else round(ganancia * TITHING_RATE, 2)
    dinero_norte = ventas["dinero_norte_linea"].sum()
    gastos_total = gastos["costo_total"].sum() if not gastos.empty else 0

    ventas["metodo_pago"] = ventas["metodo_pago"].replace("", "No especificado").fillna("No especificado")
    pago = ventas.groupby("metodo_pago")["total_linea"].sum().reset_index()

    gastos_pagados_norte = 0
    if not gastos.empty and "pagado_por" in gastos.columns:
        gastos_pagados_norte = gastos[
            gastos["pagado_por"].astype(str).str.lower().str.contains("norte")
        ]["costo_total"].sum()

    efectivo_ventas = pago[pago["metodo_pago"].astype(str).str.lower() == "efectivo"]["total_linea"].sum()
    efectivo_esperado = efectivo_ventas - gastos_pagados_norte

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas totales", pesos(total_ventas))
    c2.metric("Ganancia personal", pesos(ganancia))
    c3.metric("Diezmo", pesos(diezmo))
    c4.metric("Para Norte Brunch", pesos(dinero_norte))

    c5, c6, c7 = st.columns(3)
    c5.metric("Gastos del día", pesos(gastos_total))
    c6.metric("Gastos pagados por Norte", pesos(gastos_pagados_norte))
    c7.metric("Efectivo esperado", pesos(efectivo_esperado))

    st.subheader("Resumen por método de pago")
    st.dataframe(pago, use_container_width=True)

    with st.expander("Ver ventas y gastos del día"):
        st.subheader("Ventas")
        st.dataframe(ventas, use_container_width=True)
        st.subheader("Gastos")
        st.dataframe(gastos, use_container_width=True)


# -----------------------------
# SALDOS, INVERSIONES Y DIEZMO
# -----------------------------

def page_saldos_local():
    st.header("Saldos del local")

    saldos = get_saldos()
    disponible = (
        saldos["dinero_norte_brunch"]
        - saldos["ganancia_pendiente_personal"]
        - saldos["deuda_inversion_personal"]
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Dinero Norte Brunch", pesos(saldos["dinero_norte_brunch"]))
    c2.metric("Ganancia pendiente para mí", pesos(saldos["ganancia_pendiente_personal"]))
    c3.metric("Deuda inversión hacia mí", pesos(saldos["deuda_inversion_personal"]))

    c4, c5, c6 = st.columns(3)
    c4.metric("Ganancia pagada", pesos(saldos["ganancia_pagada_personal"]))
    c5.metric("Inversión total", pesos(saldos["inversion_personal_total"]))
    c6.metric("Dinero libre real", pesos(disponible))

    st.divider()
    st.subheader("Registrar movimiento")

    action = st.selectbox(
        "Movimiento",
        [
            "Pagarme ganancia personal",
            "Registrar inversión inicial",
            "Registrar inversión extra",
            "Pagarme deuda de inversión",
            "Ajustar dinero de Norte Brunch",
        ],
    )

    fecha = datetime_inputs("mov_local", "Fecha y hora del movimiento")
    amount = st.number_input("Monto", min_value=0.0, step=50.0)
    note = st.text_input("Nota")

    if st.button("Guardar movimiento", type="primary"):
        if amount <= 0:
            st.error("El monto debe ser mayor que cero.")
            return

        saldos = get_saldos()

        if action == "Pagarme ganancia personal":
            if amount > saldos["ganancia_pendiente_personal"]:
                st.error("No hay suficiente ganancia pendiente.")
                return
            if amount > saldos["dinero_norte_brunch"]:
                st.error("Norte Brunch no tiene suficiente dinero.")
                return

            change_saldo(saldos, "dinero_norte_brunch", -amount)
            change_saldo(saldos, "ganancia_pendiente_personal", -amount)
            change_saldo(saldos, "ganancia_pagada_personal", amount)
            change_saldo(saldos, "dinero_familiar", amount)
            change_saldo(saldos, "ingresos_familiares_totales", amount)

            append_record("gastos_familiares", {
                **fecha,
                "tipo": "ingreso",
                "categoria": "pago de Norte Brunch",
                "monto": amount,
                "metodo_pago": "Norte Brunch",
                "nota": "Pago de ganancia personal",
            })
            st.success("Ganancia pagada. El diezmo ya se calculó al registrar ventas.")

        elif action == "Registrar inversión inicial":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            change_saldo(saldos, "inversion_inicial_personal", amount)
            change_saldo(saldos, "inversion_personal_total", amount)
            change_saldo(saldos, "deuda_inversion_personal", amount)
            change_saldo(saldos, "dinero_familiar", -amount)
            change_saldo(saldos, "gastos_familiares_totales", amount)

            append_record("inversiones", {**fecha, "tipo": "inversion_inicial", "monto": amount, "nota": note})
            append_record("gastos_familiares", {
                **fecha,
                "tipo": "gasto",
                "categoria": "otros",
                "monto": amount,
                "metodo_pago": "Personal/Familiar",
                "nota": "Inversión inicial en Norte Brunch",
            })
            st.success("Inversión inicial registrada.")

        elif action == "Registrar inversión extra":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            change_saldo(saldos, "inversion_personal_total", amount)
            change_saldo(saldos, "deuda_inversion_personal", amount)
            change_saldo(saldos, "dinero_familiar", -amount)
            change_saldo(saldos, "gastos_familiares_totales", amount)

            append_record("inversiones", {**fecha, "tipo": "inversion_extra", "monto": amount, "nota": note})
            st.success("Inversión extra registrada.")

        elif action == "Pagarme deuda de inversión":
            if amount > saldos["deuda_inversion_personal"]:
                st.error("Norte Brunch no debe tanto de inversión.")
                return
            if amount > saldos["dinero_norte_brunch"]:
                st.error("Norte Brunch no tiene suficiente dinero.")
                return

            change_saldo(saldos, "dinero_norte_brunch", -amount)
            change_saldo(saldos, "deuda_inversion_personal", -amount)
            change_saldo(saldos, "inversion_pagada_personal", amount)
            change_saldo(saldos, "dinero_familiar", amount)
            change_saldo(saldos, "ingresos_familiares_totales", amount)

            append_record("inversiones", {**fecha, "tipo": "pago_inversion", "monto": amount, "nota": note})
            append_record("gastos_familiares", {
                **fecha,
                "tipo": "ingreso",
                "categoria": "pago de Norte Brunch",
                "monto": amount,
                "metodo_pago": "Norte Brunch",
                "nota": "Pago de deuda de inversión",
            })
            st.success("Pago de inversión registrado.")

        elif action == "Ajustar dinero de Norte Brunch":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            st.success("Saldo ajustado.")

        save_saldos(saldos)
        st.rerun()


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
            "categoria": "diezmo",
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
    st.title("🥪 Norte Brunch Finanzas")
    st.caption("Zona horaria: México / America/Mexico_City")

    if not check_password():
        st.stop()

    try:
        setup_workbook()
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
            "Saldos del local",
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
    elif page == "Saldos del local":
        page_saldos_local()
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

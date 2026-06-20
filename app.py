import uuid
import time
import random
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
import gspread
from google.oauth2 import service_account


APP_TITLE = "Norte Brunch Finanzas"

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
            "pedido_id",
            "producto",
            "cantidad",
            "precio_unitario",
            "ganancia_personal_unitaria",
            "total_linea",
            "ganancia_personal_linea",
            "dinero_norte_linea",
        ],
        "default_rows": [],
    },
    "gastos_local": {
        "name": "Gastos_Local",
        "headers": [
            "fecha_hora",
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
        "headers": ["fecha_hora", "tipo", "categoria", "monto", "nota"],
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
        "headers": ["fecha_hora", "monto", "frecuencia", "nota"],
        "default_rows": [],
    },
    "inversiones": {
        "name": "Inversiones",
        "headers": ["fecha_hora", "tipo", "monto", "nota"],
        "default_rows": [],
    },
    "categorias_local": {
        "name": "Categorias_Local",
        "headers": ["categoria"],
        "default_rows": [["insumos"], ["local"], ["transporte"], ["otros"]],
    },
    "categorias_familia": {
        "name": "Categorias_Familia",
        "headers": ["categoria"],
        "default_rows": [["comida"], ["servicios"], ["deudas"], ["diezmo"], ["otros"]],
    },
    "config": {
        "name": "Config",
        "headers": ["clave", "valor"],
        "default_rows": [["frecuencia_diezmo", "mensual"]],
    },
}


# -----------------------------
# CONEXION A GOOGLE SHEETS
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
    """Ejecuta llamadas a Google Sheets con reintento si aparece error 429."""
    delay = 1

    for attempt in range(5):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as error:
            message = str(error)
            if "429" in message and attempt < 4:
                time.sleep(delay + random.random())
                delay *= 2
            else:
                raise


@st.cache_resource
def get_worksheet_map():
    """Lee una sola vez la lista de hojas y la guarda en cache."""
    spreadsheet = get_spreadsheet()
    worksheets = google_call(spreadsheet.worksheets)
    return {ws.title: ws for ws in worksheets}


def get_ws(sheet_key):
    spreadsheet = get_spreadsheet()
    sheet_info = SHEETS[sheet_key]
    name = sheet_info["name"]
    worksheet_map = get_worksheet_map()

    worksheet = worksheet_map.get(name)

    if worksheet is None:
        worksheet = google_call(
            spreadsheet.add_worksheet,
            title=name,
            rows=1000,
            cols=max(30, len(sheet_info["headers"]) + 5),
        )
        worksheet_map[name] = worksheet
        google_call(worksheet.append_row, sheet_info["headers"], value_input_option="USER_ENTERED")
        if sheet_info["default_rows"]:
            google_call(worksheet.append_rows, sheet_info["default_rows"], value_input_option="USER_ENTERED")

    return worksheet


@st.cache_resource
def setup_workbook():
    """Crea hojas faltantes y encabezados solo una vez por reinicio de la app."""
    for key, sheet_info in SHEETS.items():
        worksheet = get_ws(key)
        first_row = google_call(worksheet.row_values, 1)

        if not first_row:
            google_call(worksheet.append_row, sheet_info["headers"], value_input_option="USER_ENTERED")
            if sheet_info["default_rows"]:
                google_call(worksheet.append_rows, sheet_info["default_rows"], value_input_option="USER_ENTERED")
        elif first_row != sheet_info["headers"]:
            st.warning(
                f"La hoja {sheet_info['name']} existe, pero sus encabezados no coinciden con la app."
            )

    return True


def records_to_df(records, columns):
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records)


@st.cache_data(ttl=20)
def load_df(sheet_key):
    """Lee una hoja y guarda el resultado por 20 segundos para evitar exceso de lecturas."""
    ws = get_ws(sheet_key)
    records = google_call(ws.get_all_records)
    return records_to_df(records, SHEETS[sheet_key]["headers"])


def clear_data_cache():
    load_df.clear()


def append_row(sheet_key, row):
    ws = get_ws(sheet_key)
    google_call(ws.append_row, row, value_input_option="USER_ENTERED")
    clear_data_cache()


def replace_sheet(sheet_key, rows):
    ws = get_ws(sheet_key)
    headers = SHEETS[sheet_key]["headers"]
    google_call(ws.clear)
    google_call(ws.append_row, headers, value_input_option="USER_ENTERED")
    if rows:
        google_call(ws.append_rows, rows, value_input_option="USER_ENTERED")
    clear_data_cache()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pesos(value):
    return f"${float(value):,.2f}"


# -----------------------------
# SALDOS Y CONFIG
# -----------------------------

def get_saldos():
    df = load_df("saldos")
    saldos = {}

    for _, row in df.iterrows():
        saldos[str(row["cuenta"])] = float(row["monto"])

    for row in SHEETS["saldos"]["default_rows"]:
        saldos.setdefault(row[0], float(row[1]))

    return saldos


def save_saldos(saldos):
    rows = [[key, round(float(value), 2)] for key, value in saldos.items()]
    replace_sheet("saldos", rows)


def change_saldo(saldos, key, amount):
    saldos[key] = round(float(saldos.get(key, 0)) + float(amount), 2)


def get_config_value(key, default=""):
    df = load_df("config")

    for _, row in df.iterrows():
        if str(row["clave"]) == key:
            return str(row["valor"])

    return default


def set_config_value(key, value):
    df = load_df("config")
    found = False
    rows = []

    for _, row in df.iterrows():
        if str(row["clave"]) == key:
            rows.append([key, value])
            found = True
        else:
            rows.append([row["clave"], row["valor"]])

    if not found:
        rows.append([key, value])

    replace_sheet("config", rows)


# -----------------------------
# FECHAS Y REPORTES
# -----------------------------

def start_date_for(period):
    today = date.today()

    if period == "Hoy":
        return today
    if period == "Semana":
        return today - timedelta(days=today.weekday())
    if period == "Mes":
        return today.replace(day=1)
    if period == "Año":
        return today.replace(month=1, day=1)

    return date.min


def filter_by_period(df, date_column, period):
    if df.empty:
        return df

    data = df.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    start = pd.Timestamp(start_date_for(period))
    return data[data[date_column] >= start]


def convert_numeric(df, columns):
    data = df.copy()
    for col in columns:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)
    return data


def weekday_spanish(weekday):
    names = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miercoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sabado",
        "Sunday": "Domingo",
    }
    return names.get(weekday, weekday)


# -----------------------------
# PRODUCTOS
# -----------------------------

def load_active_products():
    df = load_df("productos")
    if df.empty:
        return df

    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
    df["ganancia_personal"] = pd.to_numeric(df["ganancia_personal"], errors="coerce").fillna(0)
    df["activo"] = df["activo"].astype(str).str.lower()
    return df[df["activo"] == "si"]


def page_productos():
    st.header("Productos y precios")

    df = load_df("productos")
    st.dataframe(df, use_container_width=True)

    st.subheader("Agregar o modificar producto")
    with st.form("form_producto"):
        producto = st.text_input("Producto")
        precio = st.number_input("Precio de venta", min_value=0.0, step=1.0)
        ganancia = st.number_input("Ganancia personal por unidad", min_value=0.0, step=1.0)
        activo = st.selectbox("Activo", ["si", "no"])
        submitted = st.form_submit_button("Guardar producto")

    if submitted:
        if not producto.strip():
            st.error("Escribe el nombre del producto.")
            return

        df = load_df("productos")
        rows = []
        updated = False

        for _, row in df.iterrows():
            if str(row["producto"]).strip().lower() == producto.strip().lower():
                rows.append([producto.strip(), precio, ganancia, activo])
                updated = True
            else:
                rows.append([row["producto"], row["precio"], row["ganancia_personal"], row["activo"]])

        if not updated:
            rows.append([producto.strip(), precio, ganancia, activo])

        replace_sheet("productos", rows)
        st.success("Producto guardado.")
        st.rerun()


# -----------------------------
# REGISTRAR PEDIDO
# -----------------------------

def init_cart():
    if "cart" not in st.session_state:
        st.session_state.cart = []


def page_registrar_pedido():
    init_cart()

    st.header("Registrar pedido")

    products = load_active_products()

    if products.empty:
        st.warning("No hay productos activos.")
        return

    product_names = products["producto"].tolist()

    with st.form("add_to_cart"):
        col1, col2 = st.columns([2, 1])
        with col1:
            product = st.selectbox("Producto", product_names)
        with col2:
            quantity = st.number_input("Cantidad", min_value=1, step=1)

        add = st.form_submit_button("Agregar al pedido")

    if add:
        row = products[products["producto"] == product].iloc[0]
        unit_price = float(row["precio"])
        unit_profit = float(row["ganancia_personal"])
        line_total = round(quantity * unit_price, 2)
        line_profit = round(quantity * unit_profit, 2)
        norte_money = round(line_total - line_profit, 2)

        st.session_state.cart.append({
            "producto": product,
            "cantidad": int(quantity),
            "precio_unitario": unit_price,
            "ganancia_personal_unitaria": unit_profit,
            "total_linea": line_total,
            "ganancia_personal_linea": line_profit,
            "dinero_norte_linea": norte_money,
        })
        st.success("Producto agregado.")

    if st.session_state.cart:
        st.subheader("Pedido actual")
        cart_df = pd.DataFrame(st.session_state.cart)
        st.dataframe(cart_df, use_container_width=True)

        total = cart_df["total_linea"].sum()
        profit = cart_df["ganancia_personal_linea"].sum()
        norte = cart_df["dinero_norte_linea"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total a pagar", pesos(total))
        col2.metric("Ganancia para mí", pesos(profit))
        col3.metric("Para Norte Brunch", pesos(norte))

        col_save, col_clear = st.columns(2)

        if col_save.button("Guardar pedido", type="primary"):
            pedido_id = str(uuid.uuid4())[:8]
            fecha_hora = now_text()

            for item in st.session_state.cart:
                append_row("ventas", [
                    fecha_hora,
                    pedido_id,
                    item["producto"],
                    item["cantidad"],
                    item["precio_unitario"],
                    item["ganancia_personal_unitaria"],
                    item["total_linea"],
                    item["ganancia_personal_linea"],
                    item["dinero_norte_linea"],
                ])

            saldos = get_saldos()
            change_saldo(saldos, "dinero_norte_brunch", total)
            change_saldo(saldos, "ganancia_pendiente_personal", profit)
            save_saldos(saldos)

            st.session_state.cart = []
            st.success("Pedido guardado correctamente.")
            st.rerun()

        if col_clear.button("Vaciar pedido"):
            st.session_state.cart = []
            st.rerun()


# -----------------------------
# LOCAL: REPORTES, SALDOS, GASTOS, INVERSIONES
# -----------------------------

def page_reportes_local():
    st.header("Reportes del local")

    period = st.selectbox("Periodo", ["Hoy", "Semana", "Mes", "Año"], key="period_local")
    ventas = filter_by_period(load_df("ventas"), "fecha_hora", period)
    gastos = filter_by_period(load_df("gastos_local"), "fecha_hora", period)

    ventas = convert_numeric(ventas, [
        "cantidad",
        "total_linea",
        "ganancia_personal_linea",
        "dinero_norte_linea",
    ])
    gastos = convert_numeric(gastos, ["costo_total"])

    total_ventas = ventas["total_linea"].sum() if not ventas.empty else 0
    total_ganancia = ventas["ganancia_personal_linea"].sum() if not ventas.empty else 0
    total_norte = ventas["dinero_norte_linea"].sum() if not ventas.empty else 0
    total_gastos = gastos["costo_total"].sum() if not gastos.empty else 0
    resultado_neto = total_norte - total_gastos
    margen = (resultado_neto / total_ventas * 100) if total_ventas > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventas", pesos(total_ventas))
    col2.metric("Ganancia para mí", pesos(total_ganancia))
    col3.metric("Para Norte Brunch", pesos(total_norte))
    col4.metric("Gastos", pesos(total_gastos))

    st.metric("Resultado neto del local", pesos(resultado_neto), f"{margen:.2f}%")

    if resultado_neto < 0:
        st.error("ROJO - El local perdió dinero en este periodo.")
    elif margen < 20:
        st.warning("AMARILLO - Hay ganancia, pero la rentabilidad es baja.")
    else:
        st.success("VERDE - La rentabilidad es saludable.")

    st.subheader("Ventas por producto")
    if ventas.empty:
        st.info("No hay ventas en este periodo.")
    else:
        by_product = ventas.groupby("producto").agg({
            "cantidad": "sum",
            "total_linea": "sum",
            "ganancia_personal_linea": "sum",
            "dinero_norte_linea": "sum",
        }).reset_index()
        st.dataframe(by_product, use_container_width=True)

        ventas["dia_semana"] = pd.to_datetime(ventas["fecha_hora"]).dt.day_name().map(weekday_spanish)
        best_day = ventas.groupby("dia_semana")["total_linea"].sum().sort_values(ascending=False)
        if not best_day.empty:
            st.subheader("Mejor día de venta")
            st.write(f"**{best_day.index[0]}** con {pesos(best_day.iloc[0])} en ventas.")

        st.subheader("Mejor día por producto")
        product_day = ventas.groupby(["producto", "dia_semana"])["cantidad"].sum().reset_index()
        if not product_day.empty:
            idx = product_day.groupby("producto")["cantidad"].idxmax()
            st.dataframe(product_day.loc[idx], use_container_width=True)

    st.subheader("Gastos por categoría")
    if gastos.empty:
        st.info("No hay gastos en este periodo.")
    else:
        by_cat = gastos.groupby("categoria")["costo_total"].sum().reset_index()
        st.dataframe(by_cat, use_container_width=True)


def page_saldos_local():
    st.header("Saldos del local")

    saldos = get_saldos()
    disponible = (
        saldos["dinero_norte_brunch"]
        - saldos["ganancia_pendiente_personal"]
        - saldos["deuda_inversion_personal"]
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Dinero Norte Brunch", pesos(saldos["dinero_norte_brunch"]))
    col2.metric("Ganancia pendiente para mí", pesos(saldos["ganancia_pendiente_personal"]))
    col3.metric("Deuda de inversión hacia mí", pesos(saldos["deuda_inversion_personal"]))

    col4, col5, col6 = st.columns(3)
    col4.metric("Ganancia pagada", pesos(saldos["ganancia_pagada_personal"]))
    col5.metric("Inversión inicial", pesos(saldos["inversion_inicial_personal"]))
    col6.metric("Dinero libre real", pesos(disponible))

    if disponible < 0:
        st.warning("El dinero libre real es negativo porque faltan ganancias o deuda por cubrir.")

    st.divider()
    st.subheader("Movimientos del local")

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
    amount = st.number_input("Monto", min_value=0.0, step=50.0)
    note = st.text_input("Nota opcional")

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

            diezmo = round(amount * 0.10, 2)
            change_saldo(saldos, "diezmo_pendiente", diezmo)

            append_row("gastos_familiares", [now_text(), "ingreso", "otros", amount, "Pago de ganancia de Norte Brunch"])
            st.success(f"Ganancia pagada. Diezmo sugerido agregado como pendiente: {pesos(diezmo)}")

        elif action == "Registrar inversión inicial":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            change_saldo(saldos, "inversion_inicial_personal", amount)
            change_saldo(saldos, "inversion_personal_total", amount)
            change_saldo(saldos, "deuda_inversion_personal", amount)

            change_saldo(saldos, "dinero_familiar", -amount)
            change_saldo(saldos, "gastos_familiares_totales", amount)

            append_row("inversiones", [now_text(), "inversion_inicial", amount, note])
            append_row("gastos_familiares", [now_text(), "gasto", "otros", amount, "Inversión inicial en Norte Brunch"])
            st.success("Inversión inicial registrada.")

        elif action == "Registrar inversión extra":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            change_saldo(saldos, "inversion_personal_total", amount)
            change_saldo(saldos, "deuda_inversion_personal", amount)

            change_saldo(saldos, "dinero_familiar", -amount)
            change_saldo(saldos, "gastos_familiares_totales", amount)

            append_row("inversiones", [now_text(), "inversion_extra", amount, note])
            append_row("gastos_familiares", [now_text(), "gasto", "otros", amount, "Inversión extra en Norte Brunch"])
            st.success("Inversión extra registrada.")

        elif action == "Pagarme deuda de inversión":
            if amount > saldos["deuda_inversion_personal"]:
                st.error("Norte Brunch no debe tanto dinero de inversión.")
                return
            if amount > saldos["dinero_norte_brunch"]:
                st.error("Norte Brunch no tiene suficiente dinero.")
                return

            change_saldo(saldos, "dinero_norte_brunch", -amount)
            change_saldo(saldos, "deuda_inversion_personal", -amount)
            change_saldo(saldos, "inversion_pagada_personal", amount)

            change_saldo(saldos, "dinero_familiar", amount)
            change_saldo(saldos, "ingresos_familiares_totales", amount)

            append_row("inversiones", [now_text(), "pago_inversion", amount, note])
            append_row("gastos_familiares", [now_text(), "ingreso", "otros", amount, "Pago de deuda de inversión de Norte Brunch"])
            st.success("Pago de inversión registrado.")

        elif action == "Ajustar dinero de Norte Brunch":
            change_saldo(saldos, "dinero_norte_brunch", amount)
            st.success("Saldo ajustado.")

        save_saldos(saldos)
        st.rerun()


def page_gastos_inventario():
    st.header("Gastos e inventario del local")

    tab1, tab2, tab3 = st.tabs(["Registrar gasto/insumo", "Inventario", "Categorías"])

    with tab1:
        local_categories = load_df("categorias_local")["categoria"].tolist()

        with st.form("form_gasto_local"):
            tipo = st.selectbox("Tipo", ["Insumo", "Gasto general"])
            nombre = st.text_input("Nombre")
            categoria = "insumos" if tipo == "Insumo" else st.selectbox("Categoría", local_categories)
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad", value="piezas")
            costo = st.number_input("Costo total", min_value=0.0, step=10.0)
            pagado_por = st.radio("Pagado por", ["Norte Brunch", "Personal/Familiar"])
            nota = st.text_input("Nota")
            submitted = st.form_submit_button("Guardar")

        if submitted:
            if not nombre.strip() or costo <= 0:
                st.error("Falta nombre o costo.")
                return

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
                append_row("gastos_familiares", [now_text(), "gasto", "otros", costo, f"Gasto del local: {nombre}"])

            save_saldos(saldos)
            append_row("gastos_local", [now_text(), nombre, categoria, cantidad, unidad, costo, pagado_por, nota])

            if tipo == "Insumo":
                update_inventory(nombre, cantidad, unidad)

            st.success("Registro guardado.")
            st.rerun()

    with tab2:
        inventario = load_df("inventario")
        st.dataframe(inventario, use_container_width=True)

        with st.form("uso_inventario"):
            insumo = st.text_input("Insumo usado")
            cantidad_usada = st.number_input("Cantidad usada", min_value=0.0, step=1.0)
            unidad = st.text_input("Unidad usada", value="piezas")
            usar = st.form_submit_button("Descontar insumo")

        if usar:
            update_inventory(insumo, -cantidad_usada, unidad)
            st.success("Inventario actualizado.")
            st.rerun()

    with tab3:
        st.write(load_df("categorias_local"))
        nueva = st.text_input("Nueva categoría local")
        if st.button("Agregar categoría local"):
            append_row("categorias_local", [nueva.strip().lower()])
            st.success("Categoría agregada.")
            st.rerun()


def update_inventory(insumo, amount, unit):
    if not insumo.strip() or amount == 0:
        return

    df = load_df("inventario")
    rows = []
    updated = False

    for _, row in df.iterrows():
        if str(row["insumo"]).strip().lower() == insumo.strip().lower():
            current = float(row["cantidad"] or 0)
            rows.append([row["insumo"], round(current + amount, 2), unit])
            updated = True
        else:
            rows.append([row["insumo"], row["cantidad"], row["unidad"]])

    if not updated:
        rows.append([insumo.strip(), round(amount, 2), unit])

    replace_sheet("inventario", rows)


# -----------------------------
# FINANZAS FAMILIARES Y DIEZMO
# -----------------------------

def page_finanzas_familiares():
    st.header("Finanzas familiares")

    saldos = get_saldos()

    col1, col2, col3 = st.columns(3)
    col1.metric("Dinero familiar", pesos(saldos["dinero_familiar"]))
    col2.metric("Ingresos familiares", pesos(saldos["ingresos_familiares_totales"]))
    col3.metric("Gastos familiares", pesos(saldos["gastos_familiares_totales"]))

    tab1, tab2, tab3 = st.tabs(["Registrar movimiento", "Reporte", "Categorías"])

    with tab1:
        categories = load_df("categorias_familia")["categoria"].tolist()

        with st.form("familia_movimiento"):
            tipo = st.radio("Tipo", ["ingreso", "gasto"])
            categoria = "ingreso" if tipo == "ingreso" else st.selectbox("Categoría", categories)
            monto = st.number_input("Monto", min_value=0.0, step=50.0)
            nota = st.text_input("Nota")
            submitted = st.form_submit_button("Guardar movimiento")

        if submitted:
            if monto <= 0:
                st.error("El monto debe ser mayor que cero.")
                return

            saldos = get_saldos()
            if tipo == "ingreso":
                change_saldo(saldos, "dinero_familiar", monto)
                change_saldo(saldos, "ingresos_familiares_totales", monto)
            else:
                change_saldo(saldos, "dinero_familiar", -monto)
                change_saldo(saldos, "gastos_familiares_totales", monto)

            save_saldos(saldos)
            append_row("gastos_familiares", [now_text(), tipo, categoria, monto, nota])
            st.success("Movimiento familiar guardado.")
            st.rerun()

    with tab2:
        period = st.selectbox("Periodo familiar", ["Hoy", "Semana", "Mes", "Año"])
        df = filter_by_period(load_df("gastos_familiares"), "fecha_hora", period)
        df = convert_numeric(df, ["monto"])

        ingresos = df[df["tipo"] == "ingreso"]["monto"].sum() if not df.empty else 0
        gastos = df[df["tipo"] == "gasto"]["monto"].sum() if not df.empty else 0
        neto = ingresos - gastos

        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos", pesos(ingresos))
        col2.metric("Gastos", pesos(gastos))
        col3.metric("Balance", pesos(neto))

        if not df.empty:
            resumen = df.groupby(["tipo", "categoria"])["monto"].sum().reset_index()
            st.dataframe(resumen, use_container_width=True)

    with tab3:
        st.write(load_df("categorias_familia"))
        nueva = st.text_input("Nueva categoría familiar")
        if st.button("Agregar categoría familiar"):
            append_row("categorias_familia", [nueva.strip().lower()])
            st.success("Categoría agregada.")
            st.rerun()


def page_diezmo():
    st.header("Diezmo")

    saldos = get_saldos()
    frecuencia_actual = get_config_value("frecuencia_diezmo", "mensual")

    col1, col2, col3 = st.columns(3)
    col1.metric("Frecuencia", frecuencia_actual)
    col2.metric("Diezmo pendiente", pesos(saldos["diezmo_pendiente"]))
    col3.metric("Diezmo pagado", pesos(saldos["diezmo_pagado"]))

    nueva_frecuencia = st.selectbox("Frecuencia de pago", ["semanal", "quincenal", "mensual"], index=["semanal", "quincenal", "mensual"].index(frecuencia_actual) if frecuencia_actual in ["semanal", "quincenal", "mensual"] else 2)
    if st.button("Guardar frecuencia"):
        set_config_value("frecuencia_diezmo", nueva_frecuencia)
        st.success("Frecuencia guardada.")
        st.rerun()

    st.divider()
    st.subheader("Pagar diezmo")

    amount = st.number_input("Monto a pagar", min_value=0.0, step=10.0, value=float(saldos["diezmo_pendiente"]) if saldos["diezmo_pendiente"] > 0 else 0.0)
    note = st.text_input("Nota")

    if st.button("Registrar pago de diezmo", type="primary"):
        saldos = get_saldos()

        if amount <= 0:
            st.error("El monto debe ser mayor que cero.")
            return
        if amount > saldos["diezmo_pendiente"]:
            st.error("No tienes tanto diezmo pendiente.")
            return
        if amount > saldos["dinero_familiar"]:
            st.error("No hay suficiente dinero familiar para pagar ese diezmo.")
            return

        change_saldo(saldos, "dinero_familiar", -amount)
        change_saldo(saldos, "gastos_familiares_totales", amount)
        change_saldo(saldos, "diezmo_pendiente", -amount)
        change_saldo(saldos, "diezmo_pagado", amount)
        save_saldos(saldos)

        append_row("diezmos", [now_text(), amount, frecuencia_actual, note])
        append_row("gastos_familiares", [now_text(), "gasto", "diezmo", amount, "Pago de diezmo"])
        st.success("Diezmo registrado.")
        st.rerun()

    st.divider()
    period = st.selectbox("Reporte de diezmo", ["Hoy", "Semana", "Mes", "Año"])
    diezmos = filter_by_period(load_df("diezmos"), "fecha_hora", period)
    diezmos = convert_numeric(diezmos, ["monto"])

    total_pagado = diezmos["monto"].sum() if not diezmos.empty else 0
    st.metric("Diezmo pagado en el periodo", pesos(total_pagado))
    st.dataframe(diezmos, use_container_width=True)


# -----------------------------
# MAIN APP
# -----------------------------

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🥪", layout="wide")
    st.title("🥪 Norte Brunch Finanzas")

    try:
        setup_workbook()
    except Exception as error:
        st.error("No se pudo conectar con Google Sheets.")
        st.write("Revisa que tus secrets estén configurados y que la hoja esté compartida con el service account.")
        st.exception(error)
        st.stop()

    page = st.sidebar.radio(
        "Menú",
        [
            "Registrar pedido",
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

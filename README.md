# Norte Brunch App v33 - Estable simple

Versión hecha desde cero para corregir el guardado de gastos.

## Hojas usadas
Solo usa 3 hojas:
- Productos
- Pedidos
- Movimientos

## Corrección principal
La sección de gastos ya no usa formularios de Streamlit.
Ahora:
1. Escribes el gasto.
2. Escribes el monto como texto.
3. Tocas `Guardar gasto` una sola vez.

Acepta montos:
- 202
- 202.5
- 202.50
- 202,50

## Incluye
- Pedidos pendientes.
- Ventas con fecha anterior.
- Gastos simples.
- Editar gastos.
- Anular gastos.
- Historial.
- Reportes.
- Saldo y deuda calculados desde Movimientos.
- Diagnóstico con prueba de guardado.


## Versión 34 - Guardado de gastos verificado

Cambios:
- El botón `Guardar gasto` ahora verifica que Google Sheets sí agregue la fila.
- Muestra confirmación con número de filas antes y después.
- Si falla, muestra el error exacto en pantalla.
- El formulario de gasto se limpia después de guardar correctamente.
- Diagnóstico también usa guardado verificado.


## Versión 35 - Sin cache, gastos reflejados

Correcciones:
- La app ya no usa cache para leer Google Sheets.
- Después de guardar un gasto, los balances leen la hoja fresca.
- Se agregó periodo `Todos` para evitar que los gastos se oculten por filtro de fecha.
- En `Gastos` se muestran los últimos movimientos crudos de Google Sheets.
- En `Saldo y deuda` se muestra cuántos movimientos se están leyendo.

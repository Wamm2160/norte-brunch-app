# Norte Brunch App v30 - Desde cero

Esta versión fue hecha desde cero para evitar errores acumulados de versiones anteriores.

## Hojas de Google Sheets
Solo usa 3 hojas:
- Productos
- Pedidos
- Movimientos

No usa hoja de saldos. Los saldos se calculan siempre desde Movimientos, para evitar acumulados inflados.

## Incluye
- Pedidos pendientes.
- Agregar/quitar artículos antes de cobrar.
- Cobrar pedido con fecha y hora manual.
- Registrar ventas de días anteriores.
- Gastos simples sin categorías.
- Editar gastos.
- Anular gastos duplicados o equivocados.
- Saldo de Norte Brunch calculado desde movimientos.
- Deuda hacia Wilson calculada desde gastos pagados con dinero personal.
- Ajuste manual de saldo y deuda.
- Pago de deuda.
- Pago personal solo sábado después de 6:00 pm.
- Diezmo solo se muestra al realizar pago personal.
- Reportes por día de semana, producto más vendido y producto con más ganancia.
- Reportes por semana, quincena, mes y año.
- Historial completo.
- Diagnóstico.

## Fórmulas principales
Saldo Norte Brunch =
ventas netas - gastos pagados con Norte Brunch - pagos personales - pagos de deuda + ajustes de saldo

Deuda Norte Brunch hacia Wilson =
gastos pagados con dinero personal + ajustes de deuda - pagos de deuda

Mi paga pendiente =
ganancia personal generada por ventas - pagos personales

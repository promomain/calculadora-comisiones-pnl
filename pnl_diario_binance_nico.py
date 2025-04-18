
import pandas as pd
import matplotlib.pyplot as plt

# --- Cargar archivos ---
# ventas_p2p = pd.read_csv("ruta/a/ventas.csv")
# compras_externas = pd.read_csv("ruta/a/compras.csv")

# 1. LIMPIEZA Y PREPARACIÓN DE DATOS

# Convertir fechas
ventas_p2p['Created Time'] = pd.to_datetime(ventas_p2p['Created Time'])
compras_externas['Fecha'] = pd.to_datetime(compras_externas['Fecha'], dayfirst=True)

# Limpiar columnas numéricas
ventas_p2p['Total Price'] = pd.to_numeric(ventas_p2p['Total Price'], errors='coerce')
ventas_p2p['Quantity'] = pd.to_numeric(ventas_p2p['Quantity'], errors='coerce')
ventas_p2p['Price'] = pd.to_numeric(ventas_p2p['Price'], errors='coerce')
ventas_p2p['Maker Fee'] = pd.to_numeric(ventas_p2p['Maker Fee'], errors='coerce')
ventas_p2p['Taker Fee'] = pd.to_numeric(ventas_p2p['Taker Fee'], errors='coerce')

# Calcular comisiones reales en CLP
ventas_p2p['Fee_USDT'] = ventas_p2p[['Maker Fee', 'Taker Fee']].sum(axis=1, skipna=True)
ventas_p2p['Fee_CLP'] = ventas_p2p['Fee_USDT'] * ventas_p2p['Price']

# Filtrar solo ventas
ventas = ventas_p2p[ventas_p2p['Order Type'] == 'Sell'].copy()

# Filtrar solo compras P2P
compras_p2p = ventas_p2p[ventas_p2p['Order Type'] == 'Buy'].copy()
compras_p2p['Precio_CLP'] = compras_p2p['Total Price'] / compras_p2p['Quantity']
compras_p2p_formatted = pd.DataFrame({
    'Fecha': compras_p2p['Created Time'],
    'Monto_CLP': compras_p2p['Total Price'],
    'Precio_CLP': compras_p2p['Precio_CLP'],
    'Cantidad_USDT': compras_p2p['Quantity']
})

# Limpiar archivo de compras externas
compras_externas['Monto_CLP'] = compras_externas['Monto_CLP'].replace('[\$,]', '', regex=True).astype(float)
compras_externas['Precio_CLP'] = compras_externas['Precio_CLP'].replace('[\$,]', '', regex=True).astype(float)
compras_externas['Cantidad_USDT'] = compras_externas['Monto_CLP'] / compras_externas['Precio_CLP']

# Unir compras externas y compras p2p
compras = pd.concat([compras_externas[['Fecha', 'Monto_CLP', 'Precio_CLP', 'Cantidad_USDT']],
                     compras_p2p_formatted], ignore_index=True)

# Calcular costo promedio de compra ponderado
total_usdt_comprado = compras['Cantidad_USDT'].sum()
total_clp_comprado = compras['Monto_CLP'].sum()
precio_promedio_compra = total_clp_comprado / total_usdt_comprado

# 2. AGRUPAR Y CALCULAR PNL POR DÍA

# Agrupar ventas por día
ventas['Fecha'] = ventas['Created Time'].dt.date
ventas_diarias = ventas.groupby('Fecha').agg({
    'Quantity': 'sum',
    'Total Price': 'sum',
    'Fee_CLP': 'sum'
}).rename(columns={
    'Quantity': 'USDT_Vendido',
    'Total Price': 'CLP_Venta_Bruta',
    'Fee_CLP': 'Comisiones_CLP'
})
ventas_diarias['CLP_Venta_Neta'] = ventas_diarias['CLP_Venta_Bruta'] - ventas_diarias['Comisiones_CLP']

# Agrupar compras por día
compras['Fecha'] = compras['Fecha'].dt.date
compras_diarias = compras.groupby('Fecha').agg({
    'Cantidad_USDT': 'sum',
    'Monto_CLP': 'sum'
}).rename(columns={
    'Cantidad_USDT': 'USDT_Comprado',
    'Monto_CLP': 'CLP_Compras'
})

# Unir compras y ventas por fecha
pnl_diario = pd.merge(ventas_diarias, compras_diarias, how='left', left_index=True, right_index=True).fillna(0)

# Aplicar método costo promedio para calcular PNL
pnl_diario['Costo_USDT_Vendido'] = pnl_diario['USDT_Vendido'] * precio_promedio_compra
pnl_diario['PNL_Neto'] = pnl_diario['CLP_Venta_Neta'] - pnl_diario['Costo_USDT_Vendido']

# 3. GRAFICAR RESULTADO

fechas = pnl_diario.index.astype(str)
plt.figure(figsize=(10, 5))
plt.plot(fechas, pnl_diario['PNL_Neto'], marker='o', color='orange', linewidth=2)
plt.xticks(rotation=45)
plt.title("PNL Neto Diario (CLP)")
plt.xlabel("Fecha")
plt.ylabel("PNL Neto (CLP)")
plt.grid(True)
plt.tight_layout()
plt.show()

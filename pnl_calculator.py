import pandas as pd
import csv
import matplotlib.pyplot as plt
import os
from datetime import datetime
import numpy as np

def procesar_archivo_compras(archivo_csv):
    """
    Procesa el archivo CSV de compras y retorna un DataFrame con las compras por día
    """
    try:
        # Leer el archivo CSV con precisión completa
        df = pd.read_csv(archivo_csv, float_precision='high')
        
        # Convertir columnas monetarias - sin redondeo
        df['Monto Cerrado'] = df['Monto Cerrado'].str.replace('$', '').str.replace(',', '').astype(float)
        df['Precio'] = df['Precio'].str.replace('$', '').str.replace(',', '').astype(float)
        
        # Calcular USD comprado con precisión completa
        df['USD Comprado'] = df['Monto Cerrado'] / df['Precio']
        
        # Convertir la fecha a formato estándar
        df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        
        # Si la conversión falló, intentar con otro formato
        if df['Fecha'].isna().all():
            df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m', errors='coerce')
        
        # Asegurarse que el año sea el actual si no está especificado
        current_year = datetime.now().year
        df['Fecha'] = df['Fecha'].apply(lambda x: x.replace(year=current_year) if pd.notnull(x) else x)
        
        # Agrupar por fecha y calcular totales sin redondeo
        compras_por_dia = df.groupby('Fecha').agg({
            'Monto Cerrado': 'sum',
            'USD Comprado': 'sum'
        }).reset_index()
        
        # Calcular precio promedio de compra con precisión completa
        compras_por_dia['Precio Promedio Compra'] = compras_por_dia['Monto Cerrado'] / compras_por_dia['USD Comprado']
        
        print(f"Datos de compras procesados: {len(compras_por_dia)} días")
        return compras_por_dia
    
    except Exception as e:
        print(f"Error al procesar archivo de compras: {e}")
        return None

def procesar_archivo_ventas(archivo_csv):
    """
    Procesa el archivo CSV de Binance P2P y retorna DataFrames con las ventas y compras por día
    """
    try:
        # Leer el archivo CSV con precisión completa
        df = pd.read_csv(archivo_csv, float_precision='high')
        
        # Filtrar solo transacciones completadas
        df = df[df['Status'] == 'Completed']
        
        # Convertir columnas monetarias y numéricas sin redondeo
        df['Total Price'] = pd.to_numeric(df['Total Price'], errors='coerce')
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        
        # Convertir columnas de comisiones, manejar valores vacíos sin redondeo
        df['Maker Fee'] = pd.to_numeric(df['Maker Fee'], errors='coerce').fillna(0)
        df['Taker Fee'] = pd.to_numeric(df['Taker Fee'], errors='coerce').fillna(0)
        df['Comisiones'] = df[['Maker Fee', 'Taker Fee']].sum(axis=1)
        
        # Extraer la fecha de 'Created Time'
        df['Fecha'] = pd.to_datetime(df['Created Time']).dt.date
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        
        # Separar ventas y compras
        df_ventas = df[df['Order Type'] == 'Sell']
        df_compras = df[df['Order Type'] == 'Buy']
        
        # Procesar ventas
        ventas_por_dia = None
        if not df_ventas.empty:
            ventas_por_dia = df_ventas.groupby('Fecha').agg({
                'Total Price': 'sum',
                'Quantity': 'sum',
                'Comisiones': 'sum'
            }).reset_index()
            
            # Calcular precio promedio de venta
            ventas_por_dia['Precio Promedio Venta'] = ventas_por_dia['Total Price'] / ventas_por_dia['Quantity']
            print(f"Datos de ventas procesados: {len(ventas_por_dia)} días")
        
        # Procesar compras (nuevas)
        compras_por_dia = None
        if not df_compras.empty:
            # Agrupar compras por día
            compras_por_dia = df_compras.groupby('Fecha').agg({
                'Total Price': 'sum',
                'Quantity': 'sum',
                'Comisiones': 'sum'
            }).reset_index()
            
            # Renombrar columnas para hacerlas compatibles con el formato del archivo de compras
            compras_por_dia = compras_por_dia.rename(columns={
                'Total Price': 'Monto Cerrado',
                'Quantity': 'USD Comprado'
            })
            
            # Calcular precio promedio de compra
            compras_por_dia['Precio Promedio Compra'] = compras_por_dia['Monto Cerrado'] / compras_por_dia['USD Comprado']
            
            print(f"Se encontraron {len(df_compras)} operaciones de compra en el archivo de Binance P2P")
            print(f"Datos de compras P2P procesados: {len(compras_por_dia)} días")
        
        # Retornar ambos DataFrames
        return ventas_por_dia, compras_por_dia
    
    except Exception as e:
        print(f"Error al procesar archivo de ventas: {e}")
        return None, None

def calcular_pnl_diario(compras_df, ventas_df):
    """
    Calcula el PNL diario combinando datos de compras y ventas
    """
    try:
        # Si alguno de los dataframes es None o está vacío, retornar None
        if compras_df is None or ventas_df is None:
            if compras_df is None:
                print("No hay datos de compras disponibles")
            if ventas_df is None:
                print("No hay datos de ventas disponibles")
            return None
        
        # Imprimir información sobre los dataframes para depuración
        print(f"DataFrame de compras tiene {len(compras_df)} filas con columnas: {compras_df.columns.tolist()}")
        print(f"DataFrame de ventas tiene {len(ventas_df)} filas con columnas: {ventas_df.columns.tolist()}")
        
        # Crear una lista de todas las fechas únicas ordenadas
        todas_fechas = pd.concat([compras_df['Fecha'], ventas_df['Fecha']]).unique()
        todas_fechas = sorted(todas_fechas)
        
        # Crear un DataFrame para almacenar los resultados
        resultados = pd.DataFrame(todas_fechas, columns=['Fecha'])
        
        # Inicializar columnas necesarias con valores sin redondeo
        resultados['USD Comprado'] = 0.0
        resultados['Monto Compra'] = 0.0
        resultados['Precio Promedio Compra'] = 0.0
        resultados['USD Vendido'] = 0.0
        resultados['Monto Venta'] = 0.0
        resultados['Precio Promedio Venta'] = 0.0
        resultados['Precio Promedio Stock'] = 0.0
        resultados['Margen'] = 0.0
        resultados['PNL Bruto'] = 0.0
        resultados['Comisiones'] = 0.0
        resultados['PNL Neto'] = 0.0
        resultados['Remanente USD'] = 0.0
        resultados['Precio Promedio Remanente'] = 0.0
        
        # Variables para llevar el control del remanente con precisión completa
        remanente_usd = 0.0
        remanente_monto = 0.0  # Para calcular el precio promedio ponderado
        
        # Procesar cada día con precisión completa
        for idx, row in resultados.iterrows():
            fecha_actual = row['Fecha']
            
            # Obtener datos de compra para esta fecha (si existen)
            compra_hoy = compras_df[compras_df['Fecha'] == fecha_actual]
            if not compra_hoy.empty:
                usd_comprado_hoy = compra_hoy['USD Comprado'].values[0]
                monto_comprado_hoy = compra_hoy['Monto Cerrado'].values[0]
                precio_compra_hoy = compra_hoy['Precio Promedio Compra'].values[0]
                
                resultados.at[idx, 'USD Comprado'] = usd_comprado_hoy
                resultados.at[idx, 'Monto Compra'] = monto_comprado_hoy
                resultados.at[idx, 'Precio Promedio Compra'] = precio_compra_hoy
            else:
                usd_comprado_hoy = 0
                monto_comprado_hoy = 0
                precio_compra_hoy = 0
            
            # Sumar el remanente anterior al stock disponible, con precisión completa
            stock_disponible = remanente_usd + usd_comprado_hoy
            
            # Calcular el precio promedio ponderado del stock disponible con máxima precisión
            if stock_disponible > 0:
                precio_promedio_stock = (remanente_monto + monto_comprado_hoy) / stock_disponible
                resultados.at[idx, 'Precio Promedio Stock'] = precio_promedio_stock
            else:
                precio_promedio_stock = 0
                resultados.at[idx, 'Precio Promedio Stock'] = 0
            
            # Obtener datos de venta para esta fecha (si existen)
            venta_hoy = ventas_df[ventas_df['Fecha'] == fecha_actual]
            if not venta_hoy.empty:
                usd_vendido_hoy = venta_hoy['Quantity'].values[0]
                monto_vendido_hoy = venta_hoy['Total Price'].values[0]
                precio_venta_hoy = venta_hoy['Precio Promedio Venta'].values[0]
                comisiones_hoy = venta_hoy['Comisiones'].values[0]
                
                resultados.at[idx, 'USD Vendido'] = usd_vendido_hoy
                resultados.at[idx, 'Monto Venta'] = monto_vendido_hoy
                resultados.at[idx, 'Precio Promedio Venta'] = precio_venta_hoy
                resultados.at[idx, 'Comisiones'] = comisiones_hoy
                
                # Solo calcular PNL si hay ventas y hay stock disponible
                if stock_disponible > 0:
                    # Asegurarse de que no se venda más de lo disponible
                    usd_vendido_efectivo = min(usd_vendido_hoy, stock_disponible)
                    
                    # Calcular margen y PNL con máxima precisión
                    margen = precio_venta_hoy - precio_promedio_stock
                    pnl_bruto_clp = margen * usd_vendido_efectivo
                    # Convertir PNL bruto de CLP a USD sin redondeo
                    pnl_bruto_usd = pnl_bruto_clp / precio_promedio_stock if precio_promedio_stock > 0 else 0
                    # Restar comisiones que ya están en USD sin redondeo
                    pnl_neto_usd = pnl_bruto_usd - comisiones_hoy
                    
                    resultados.at[idx, 'Margen'] = margen
                    resultados.at[idx, 'PNL Bruto'] = pnl_bruto_usd
                    resultados.at[idx, 'PNL Neto'] = pnl_neto_usd
                    
                    # Actualizar remanente sin redondeo
                    remanente_usd = stock_disponible - usd_vendido_efectivo - comisiones_hoy
                    # Verificar que el remanente no sea negativo (por precaución)
                    if remanente_usd < 0:
                        remanente_usd = 0
                    # Actualizar el monto del remanente para mantener el precio promedio ponderado
                    remanente_monto = remanente_usd * precio_promedio_stock
                else:
                    usd_vendido_efectivo = 0
                    remanente_usd = stock_disponible
                    remanente_monto = remanente_usd * precio_promedio_stock
            else:
                # Si no hay ventas, el remanente es todo el stock disponible
                remanente_usd = stock_disponible
                remanente_monto = remanente_usd * precio_promedio_stock
            
            # Guardar información del remanente sin redondeo
            resultados.at[idx, 'Remanente USD'] = remanente_usd
            if remanente_usd > 0:
                resultados.at[idx, 'Precio Promedio Remanente'] = remanente_monto / remanente_usd
        
        # Imprimir suma de resultados para depuración
        print(f"Resultados calculados con éxito: {len(resultados)} días")
        print(f"Total USD comprado: {resultados['USD Comprado'].sum():.2f}")
        print(f"Total USD vendido: {resultados['USD Vendido'].sum():.2f}")
        print(f"Remanente final: {remanente_usd:.2f} USD")
        
        return resultados
    
    except Exception as e:
        print(f"Error al calcular PNL diario: {e}")
        import traceback
        traceback.print_exc()
        return None

def generar_grafico_pnl(df_resultados, nombre_salida):
    """
    Genera un gráfico de barras con el PNL neto diario
    """
    try:
        if df_resultados is None:
            return False
        
        # Convertir fechas a formato string para mejor visualización
        fechas = df_resultados['Fecha'].dt.strftime('%Y-%m-%d').tolist()
        pnl_neto = df_resultados['PNL Neto'].tolist()
        
        plt.figure(figsize=(12, 6))
        
        # Crear barras para PNL neto
        bars = plt.bar(fechas, pnl_neto, color=['#4CAF50' if x >= 0 else '#F44336' for x in pnl_neto], alpha=0.7)
        
        # Agregar etiquetas de valor encima de cada barra
        for bar, valor in zip(bars, pnl_neto):
            color = 'green' if valor >= 0 else 'red'
            vertical_offset = 1 if valor >= 0 else -20
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + vertical_offset,
                     f"{valor:,.2f}", ha='center', va='bottom', color=color, fontweight='bold')
        
        # Configurar gráfico
        plt.title('PNL Neto Diario', fontsize=16, pad=20)
        plt.xlabel('Fecha', fontsize=12)
        plt.ylabel('PNL Neto (USD)', fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # Guardar el gráfico
        plt.savefig(nombre_salida)
        plt.close()  # Cerrar el gráfico para liberar memoria
        
        return True
    
    except Exception as e:
        print(f"Error al generar gráfico PNL: {e}")
        return False

def generar_informe_pnl(archivo_compras, archivo_ventas, guardar_grafico=True, nombre_salida="pnl_resultado"):
    """
    Función principal que procesa los archivos y genera el informe completo de PNL
    """
    try:
        print("\n--- Iniciando generación de informe PNL ---")
        
        # Procesar archivos
        compras_df = procesar_archivo_compras(archivo_compras)
        ventas_df, compras_df_binance = procesar_archivo_ventas(archivo_ventas)
        
        # Combinar las compras de Fugiro con las compras de Binance P2P si existen
        if compras_df_binance is not None and not compras_df_binance.empty:
            if compras_df is not None:
                print(f"Combinando {len(compras_df)} compras de Fugiro con {len(compras_df_binance)} compras de Binance P2P")
                
                # Concatenar los dos DataFrames
                compras_df = pd.concat([compras_df, compras_df_binance], ignore_index=True)
                
                # Agrupar por fecha para combinar operaciones del mismo día
                compras_df = compras_df.groupby('Fecha').agg({
                    'Monto Cerrado': 'sum',
                    'USD Comprado': 'sum'
                }).reset_index()
                
                # Recalcular precio promedio de compra
                compras_df['Precio Promedio Compra'] = compras_df['Monto Cerrado'] / compras_df['USD Comprado']
                
                print(f"Total combinado: {len(compras_df)} días con operaciones de compra")
            else:
                print("No se pudieron procesar las compras de Fugiro, usando solo compras de Binance P2P")
                compras_df = compras_df_binance
        elif compras_df is None and compras_df_binance is not None:
            print("No se encontraron compras de Fugiro, usando solo compras de Binance P2P")
            compras_df = compras_df_binance
        
        # Calcular PNL diario
        resultados_df = calcular_pnl_diario(compras_df, ventas_df)
        
        if resultados_df is None:
            print("Error: No se pudo calcular el PNL diario")
            return None
        
        # Generar gráfico
        if guardar_grafico:
            generar_grafico_pnl(resultados_df, f"{nombre_salida}_grafico.png")
        
        # Guardar resultados en CSV
        resultados_df.to_csv(f"{nombre_salida}_informe.csv", index=False)
        
        # Crear resumen de texto para mostrar
        resumen = []
        resumen.append("Resumen de PNL Diario:")
        resumen.append("-" * 50)
        
        total_pnl_neto = 0
        
        for _, row in resultados_df.iterrows():
            fecha = row['Fecha'].strftime('%Y-%m-%d')
            usd_comprado = row['USD Comprado']
            precio_compra = row['Precio Promedio Compra']
            usd_vendido = row['USD Vendido']
            precio_venta = row['Precio Promedio Venta']
            margen = row['Margen']
            pnl_bruto = row['PNL Bruto']
            comisiones = row['Comisiones']
            pnl_neto = row['PNL Neto']
            remanente = row['Remanente USD']
            
            # Solo incluir días con operaciones
            if usd_comprado > 0 or usd_vendido > 0:
                resumen.append(f"{fecha}:")
                if usd_comprado > 0:
                    resumen.append(f"  Comprado: {usd_comprado:.2f} USD a precio promedio: ${precio_compra:.2f}")
                if usd_vendido > 0:
                    resumen.append(f"  Vendido: {usd_vendido:.2f} USD a precio promedio: ${precio_venta:.2f}")
                    precio_stock = row['Precio Promedio Stock']
                    resumen.append(f"  Precio promedio stock disponible: ${precio_stock:.2f}")
                    resumen.append(f"  Margen: ${margen:.2f} | PNL Bruto: {pnl_bruto:.2f} USD | Comisiones: {comisiones:.2f} USD")
                    resumen.append(f"  PNL Neto: {pnl_neto:.2f} USD")
                resumen.append(f"  Remanente: {remanente:.2f} USD (comisiones ya descontadas)")
                resumen.append("-" * 30)
                
                total_pnl_neto += pnl_neto
        
        resumen.append("-" * 50)
        resumen.append(f"PNL Neto Total: {total_pnl_neto:.2f} USD")
        
        # Guardar resumen en archivo de texto
        with open(f"{nombre_salida}_informe.txt", "w") as f:
            f.write("\n".join(resumen))
        
        print("--- Informe PNL generado con éxito ---\n")
        return {
            'resultados_df': resultados_df,
            'resumen_texto': "\n".join(resumen),
            'total_pnl_neto': total_pnl_neto
        }
    
    except Exception as e:
        print(f"Error al generar informe PNL: {e}")
        import traceback
        traceback.print_exc()
        return None 
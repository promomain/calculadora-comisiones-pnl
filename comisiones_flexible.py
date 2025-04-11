import pandas as pd
import csv
import matplotlib.pyplot as plt
import argparse
import os
from datetime import datetime

# Función para calcular las comisiones por día
def calcular_comisiones_por_dia(archivo_csv):
    # Inicializar un diccionario para almacenar las comisiones por día
    comisiones_por_dia = {}
    
    # Leer el archivo CSV
    with open(archivo_csv, 'r') as file:
        csv_reader = csv.DictReader(file)
        
        # Verificamos que las columnas necesarias existan
        primera_fila = next(csv_reader, None)
        if primera_fila is None:
            raise ValueError("El archivo CSV está vacío")
        
        # Reiniciamos el lector para volver al principio
        file.seek(0)
        csv_reader = csv.DictReader(file)
        
        # Identificar las columnas correctas
        columnas = list(next(csv_reader, {}).keys())
        file.seek(0)
        csv_reader = csv.DictReader(file)
        
        # Buscar columnas de comisiones, fecha y estado
        columna_maker = None
        columna_taker = None
        columna_fecha = None
        columna_estado = None
        
        for col in columnas:
            if "Maker" in col and "Fee" in col:
                columna_maker = col
            if "Taker" in col and "Fee" in col:
                columna_taker = col
            if "Time" in col or "Date" in col or "Fecha" in col:
                columna_fecha = col
            if "Status" in col or "Estado" in col:
                columna_estado = col
        
        if not (columna_maker and columna_taker and columna_fecha):
            raise ValueError("No se encontraron las columnas necesarias en el CSV")
        
        if not columna_estado:
            print("ADVERTENCIA: No se encontró la columna de estado. Se procesarán todas las transacciones.")
        
        # Iterar sobre cada fila del CSV
        for row in csv_reader:
            # Verificar si la transacción está completada
            if columna_estado and row[columna_estado] != "Completed":
                continue  # Saltar esta fila si no está completada
            
            # Extraer la fecha
            fecha_hora = row[columna_fecha]
            # Manejar diferentes formatos de fecha posibles
            partes_fecha = fecha_hora.split(' ')[0]  # Obtener solo la fecha (YYYY-MM-DD)
            
            # Obtener las comisiones
            maker_fee = row[columna_maker]
            taker_fee = row[columna_taker]
            
            # Convertir a float si hay un valor, o 0 si está vacío
            maker_fee = float(maker_fee) if maker_fee else 0
            taker_fee = float(taker_fee) if taker_fee else 0
            
            # Sumar la comisión al día correspondiente
            comision = maker_fee + taker_fee
            
            # Actualizar el diccionario
            if partes_fecha in comisiones_por_dia:
                comisiones_por_dia[partes_fecha] += comision
            else:
                comisiones_por_dia[partes_fecha] = comision
    
    return comisiones_por_dia

# Función para contar transacciones por día
def contar_transacciones_por_dia(archivo_csv):
    transacciones_por_dia = {}
    
    # Leer el archivo CSV
    with open(archivo_csv, 'r') as file:
        csv_reader = csv.DictReader(file)
        
        # Identificar la columna de fecha y estado
        columnas = list(next(csv_reader, {}).keys())
        file.seek(0)
        csv_reader = csv.DictReader(file)
        
        columna_fecha = None
        columna_estado = None
        
        for col in columnas:
            if "Time" in col or "Date" in col or "Fecha" in col:
                columna_fecha = col
            if "Status" in col or "Estado" in col:
                columna_estado = col
        
        if not columna_fecha:
            raise ValueError("No se encontró la columna de fecha en el CSV")
        
        # Iterar sobre cada fila del CSV
        for row in csv_reader:
            # Verificar si la transacción está completada
            if columna_estado and row[columna_estado] != "Completed":
                continue  # Saltar esta fila si no está completada
            
            # Extraer la fecha
            fecha_hora = row[columna_fecha]
            partes_fecha = fecha_hora.split(' ')[0]  # Obtener solo la fecha (YYYY-MM-DD)
            
            # Actualizar el contador
            if partes_fecha in transacciones_por_dia:
                transacciones_por_dia[partes_fecha] += 1
            else:
                transacciones_por_dia[partes_fecha] = 1
    
    return transacciones_por_dia

# Función para generar el informe completo y el gráfico
def generar_informe(archivo_csv, guardar_grafico=True, nombre_salida="comisiones"):
    try:
        # Obtener el nombre base del archivo sin extensión para los archivos de salida
        nombre_base = os.path.splitext(os.path.basename(archivo_csv))[0]
        nombre_salida = f"{nombre_salida}_{nombre_base}" if nombre_salida == "comisiones" else nombre_salida
        
        comisiones = calcular_comisiones_por_dia(archivo_csv)
        transacciones = contar_transacciones_por_dia(archivo_csv)
        
        # Ordenar por fecha
        fechas_ordenadas = sorted(comisiones.keys())
        
        # Preparar datos para el gráfico
        fechas = []
        valores_comisiones = []
        num_transacciones = []
        
        # Crear informe de texto
        informe = []
        informe.append("Comisiones por día (solo transacciones completadas):")
        informe.append("-----------------")
        total_comisiones = 0
        total_transacciones = 0
        
        for fecha in fechas_ordenadas:
            informe.append(f"{fecha}: {comisiones[fecha]:.2f} (Transacciones: {transacciones[fecha]})")
            total_comisiones += comisiones[fecha]
            total_transacciones += transacciones[fecha]
            
            # Agregar datos para el gráfico
            fechas.append(fecha)
            valores_comisiones.append(comisiones[fecha])
            num_transacciones.append(transacciones[fecha])
        
        informe.append("-----------------")
        informe.append(f"Total de días operados: {len(fechas_ordenadas)}")
        informe.append(f"Total de transacciones completadas: {total_transacciones}")
        informe.append(f"Total de comisiones: {total_comisiones:.2f}")
        
        # Guardar informe en un archivo de texto
        with open(f"{nombre_salida}_informe.txt", "w") as f:
            f.write("\n".join(informe))
        
        # Mostrar informe en consola
        print("\n".join(informe))
        
        # Crear gráfico de barras si se solicita
        if guardar_grafico and fechas:
            plt.figure(figsize=(12, 8))
            
            # Barras para comisiones
            bars = plt.bar(fechas, valores_comisiones, color='skyblue', alpha=0.7)
            
            # Agregar etiquetas de valor encima de cada barra
            for bar, valor, num_trans in zip(bars, valores_comisiones, num_transacciones):
                plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                        f"{valor:.2f}\n({num_trans})", ha='center', va='bottom')
            
            # Agregar línea para número de transacciones (eje secundario)
            ax2 = plt.twinx()
            ax2.plot(fechas, num_transacciones, 'ro-', linewidth=2, markersize=8)
            ax2.set_ylabel('Número de Transacciones Completadas', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            
            # Configurar gráfico
            plt.title('Comisiones y Número de Transacciones Completadas por Día')
            plt.xlabel('Fecha')
            plt.ylabel('Comisiones')
            plt.xticks(rotation=45)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            
            # Guardar el gráfico
            plt.savefig(f"{nombre_salida}_grafico.png")
            print(f"Gráfico guardado como '{nombre_salida}_grafico.png'")
            plt.close()  # Cerrar el gráfico para liberar memoria
        
        return {
            'comisiones': comisiones,
            'transacciones': transacciones,
            'total_comisiones': total_comisiones,
            'total_transacciones': total_transacciones
        }
        
    except Exception as e:
        print(f"Error al procesar el archivo: {e}")
        # Intentar diagnóstico adicional
        try:
            if 'archivo_csv' in locals():
                with open(archivo_csv, 'r') as file:
                    lector = csv.reader(file)
                    encabezados = next(lector, [])
                    print(f"\nColumnas detectadas en el archivo: {encabezados}")
        except Exception:
            pass
        return None

# Función principal
def main():
    # Configurar el parser de argumentos
    parser = argparse.ArgumentParser(description='Analiza comisiones en un archivo CSV')
    parser.add_argument('archivo', help='Ruta al archivo CSV para analizar', nargs='?', 
                        default='69eeb674-161a-11f0-ac27-0a8dd44a981d-1.csv')
    parser.add_argument('--no-grafico', help='No generar gráfico', action='store_true')
    parser.add_argument('--salida', help='Nombre base para los archivos de salida', default='comisiones')
    
    # Analizar argumentos
    args = parser.parse_args()
    
    # Verificar si el archivo existe
    if not os.path.exists(args.archivo):
        print(f"Error: El archivo '{args.archivo}' no existe.")
        return
    
    # Generar informe
    generar_informe(args.archivo, not args.no_grafico, args.salida)

if __name__ == "__main__":
    main() 
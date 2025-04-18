from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
import os
import uuid
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')  # Configuración para usar sin interfaz gráfica
import matplotlib.pyplot as plt
from comisiones_flexible import calcular_comisiones_por_dia, contar_transacciones_por_dia, generar_informe
from pnl_calculator import generar_informe_pnl
import pandas as pd
import json
import datetime
import time
import csv
# Importar el módulo de comparador P2P
from binance_p2p_comparador import comparar_precios, iniciar_scheduler, historial_precios, ultimos_datos, ohlc_data, actualizar_precio_personalizado

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Configuración de carga de archivos
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'csv'}
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'resultados')

# Crear carpetas si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)  # Asegurar que existe la carpeta static

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_analysis_history():
    """Obtiene el historial de análisis realizados"""
    history = []
    resultados_path = app.config['OUTPUT_FOLDER']
    
    # Obtener todos los archivos de la carpeta de resultados
    files = os.listdir(resultados_path)
    
    # Identificar los IDs únicos de análisis (cada análisis tiene varios archivos con el mismo ID)
    unique_ids = set()
    for file in files:
        if '_informe.txt' in file:
            # Extraer el ID del nombre del archivo
            file_id = file.split('_informe.txt')[0]
            unique_ids.add(file_id)
    
    # Para cada ID, reunir información sobre el análisis
    for file_id in unique_ids:
        analysis_info = {'id': file_id, 'tipo': 'desconocido', 'fecha': None}
        
        # Detectar tipo de análisis (comisiones o PNL)
        csv_exists = os.path.exists(os.path.join(resultados_path, f"{file_id}_informe.csv"))
        analysis_info['tipo'] = 'pnl' if csv_exists else 'comisiones'
        
        # Obtener fecha de creación del archivo como fecha del análisis
        informe_path = os.path.join(resultados_path, f"{file_id}_informe.txt")
        if os.path.exists(informe_path):
            timestamp = os.path.getmtime(informe_path)
            analysis_info['fecha'] = timestamp
            
            # Leer las primeras líneas del informe para obtener información adicional
            try:
                with open(informe_path, 'r') as f:
                    contenido = f.read(500)  # Leer solo las primeras 500 caracteres
                    analysis_info['resumen'] = contenido.split('\n')[0] if contenido else "Sin resumen disponible"
            except:
                analysis_info['resumen'] = "Error al leer el resumen"
        
        history.append(analysis_info)
    
    # Ordenar por fecha (más reciente primero)
    history.sort(key=lambda x: x['fecha'] if x['fecha'] else 0, reverse=True)
    
    return history

@app.route('/favicon.png')
def favicon():
    return send_from_directory('static', 'favicon.png')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/comisiones')
def comisiones():
    return render_template('comisiones.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No se ha seleccionado ningún archivo', 'error')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No se ha seleccionado ningún archivo', 'error')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generar un nombre único para evitar colisiones
        unique_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        base_name, extension = os.path.splitext(filename)
        
        # Nombre para guardar el archivo
        saved_filename = f"{base_name}_{unique_id}{extension}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        
        # Guardar el archivo
        file.save(file_path)
        
        # Generar resultados
        try:
            resultado_nombre = f"{unique_id}"
            resultado = generar_informe(file_path, True, os.path.join(app.config['OUTPUT_FOLDER'], resultado_nombre))
            
            if resultado:
                return redirect(url_for('resultados', file_id=unique_id, original_name=base_name))
            else:
                flash('Error al procesar el archivo. Asegúrate de que tiene el formato correcto.', 'error')
                return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error al procesar el archivo: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    flash('Tipo de archivo no permitido. Solo se aceptan archivos CSV.', 'error')
    return redirect(url_for('index'))

@app.route('/resultados/<file_id>')
def resultados(file_id):
    original_name = request.args.get('original_name', 'archivo')
    
    # Verificar que los archivos existan
    informe_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{file_id}_informe.txt")
    grafico_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{file_id}_grafico.png")
    
    if not os.path.exists(informe_path):
        flash('No se encontró el informe para este archivo', 'error')
        return redirect(url_for('index'))
    
    # Leer el informe
    with open(informe_path, 'r') as f:
        informe_contenido = f.read()
    
    # Extraer datos para mostrar en la página
    lineas = informe_contenido.strip().split('\n')
    
    # Buscar totales
    total_comisiones = "0.00"
    total_dias = "0"
    total_transacciones = "0"
    
    for linea in lineas:
        if "Total de comisiones:" in linea:
            total_comisiones = linea.split(':')[1].strip()
        elif "Total de días operados:" in linea:
            total_dias = linea.split(':')[1].strip()
        elif "Total de transacciones completadas:" in linea:
            total_transacciones = linea.split(':')[1].strip()
    
    # Extraer datos diarios (eliminar cabeceras y pie)
    datos_diarios = []
    capturando = False
    
    for linea in lineas:
        if linea == "-----------------":
            if not capturando:
                capturando = True
                continue
            else:
                break
        
        if capturando and linea and ":" in linea:
            partes = linea.split(':', 1)
            if len(partes) == 2:
                fecha = partes[0].strip()
                resto = partes[1].strip()
                if "Transacciones:" in resto:
                    valor, transacciones_str = resto.split("(", 1)
                    valor = valor.strip()
                    transacciones = transacciones_str.replace("Transacciones:", "").replace(")", "").strip()
                    datos_diarios.append({
                        'fecha': fecha,
                        'valor': valor,
                        'transacciones': transacciones
                    })
    
    # Verificar si existe el gráfico
    tiene_grafico = os.path.exists(grafico_path)
    
    return render_template(
        'resultados.html',
        original_name=original_name,
        file_id=file_id,
        informe=informe_contenido,
        total_comisiones=total_comisiones,
        total_dias=total_dias,
        total_transacciones=total_transacciones,
        datos_diarios=datos_diarios,
        tiene_grafico=tiene_grafico
    )

@app.route('/descargar/<tipo>/<file_id>')
def descargar(tipo, file_id):
    if tipo == 'informe':
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            f"{file_id}_informe.txt",
            as_attachment=True,
            download_name="informe_comisiones.txt"
        )
    elif tipo == 'grafico':
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            f"{file_id}_grafico.png",
            as_attachment=True,
            download_name="grafico_comisiones.png"
        )
    else:
        return redirect(url_for('index'))

# Nuevas rutas para la calculadora de PNL
@app.route('/pnl')
def pnl_calculator():
    return render_template('pnl_calculator.html')

@app.route('/pnl/upload', methods=['POST'])
def upload_pnl_files():
    # Verificar si ambos archivos están presentes
    if 'file_compras' not in request.files or 'file_ventas' not in request.files:
        flash('Debes seleccionar ambos archivos CSV: compras y ventas', 'error')
        return redirect(url_for('pnl_calculator'))
    
    file_compras = request.files['file_compras']
    file_ventas = request.files['file_ventas']
    
    # Verificar que ambos archivos tengan nombre
    if file_compras.filename == '' or file_ventas.filename == '':
        flash('Debes seleccionar ambos archivos CSV: compras y ventas', 'error')
        return redirect(url_for('pnl_calculator'))
    
    # Verificar que ambos archivos sean del tipo permitido
    if not (allowed_file(file_compras.filename) and allowed_file(file_ventas.filename)):
        flash('Tipo de archivo no permitido. Solo se aceptan archivos CSV.', 'error')
        return redirect(url_for('pnl_calculator'))
    
    try:
        # Generar un ID único para este proceso
        unique_id = str(uuid.uuid4())
        
        # Guardar el archivo de compras
        filename_compras = secure_filename(file_compras.filename)
        base_name_compras, extension_compras = os.path.splitext(filename_compras)
        saved_filename_compras = f"{base_name_compras}_{unique_id}{extension_compras}"
        file_path_compras = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename_compras)
        file_compras.save(file_path_compras)
        
        # Guardar el archivo de ventas
        filename_ventas = secure_filename(file_ventas.filename)
        base_name_ventas, extension_ventas = os.path.splitext(filename_ventas)
        saved_filename_ventas = f"{base_name_ventas}_{unique_id}{extension_ventas}"
        file_path_ventas = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename_ventas)
        file_ventas.save(file_path_ventas)
        
        # Generar informe de PNL
        resultado_nombre = os.path.join(app.config['OUTPUT_FOLDER'], unique_id)
        resultado = generar_informe_pnl(file_path_compras, file_path_ventas, True, resultado_nombre)
        
        if resultado:
            return redirect(url_for('pnl_resultados', file_id=unique_id))
        else:
            flash('Error al procesar los archivos. Asegúrate de que tienen el formato correcto.', 'error')
            return redirect(url_for('pnl_calculator'))
        
    except Exception as e:
        flash(f'Error al procesar los archivos: {str(e)}', 'error')
        return redirect(url_for('pnl_calculator'))

@app.route('/pnl/resultados/<file_id>')
def pnl_resultados(file_id):
    # Verificar que los archivos existan
    informe_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{file_id}_informe.txt")
    grafico_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{file_id}_grafico.png")
    csv_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{file_id}_informe.csv")
    
    if not os.path.exists(informe_path) or not os.path.exists(csv_path):
        flash('No se encontraron los resultados para estos archivos', 'error')
        return redirect(url_for('pnl_calculator'))
    
    try:
        # Leer el informe de texto
        with open(informe_path, 'r') as f:
            resumen_texto = f.read()
        
        # Importar pandas aquí para leer el CSV
        resultados_df = pd.read_csv(csv_path)
        
        # Convertir la columna de fecha y formatea como string para evitar problemas
        resultados_df['Fecha'] = pd.to_datetime(resultados_df['Fecha'])
        resultados_df['Fecha'] = resultados_df['Fecha'].dt.strftime('%Y-%m-%d')
        
        # Calcular totales
        total_pnl_neto = float(resultados_df['PNL Neto'].sum())
        total_usd_comprado = float(resultados_df['USD Comprado'].sum())
        total_usd_vendido = float(resultados_df['USD Vendido'].sum())
        
        # Recuperar los archivos originales para obtener detalles
        # Buscar los archivos originales en la carpeta de uploads
        uploads_path = app.config['UPLOAD_FOLDER']
        uploaded_files = os.listdir(uploads_path)
        
        # Filtrar los archivos que pertenecen a este file_id
        related_files = [f for f in uploaded_files if file_id in f]
        compras_file = next((os.path.join(uploads_path, f) for f in related_files if "compra" in f.lower()), None)
        ventas_file = next((os.path.join(uploads_path, f) for f in related_files if "venta" in f.lower() or "p2p" in f.lower()), None)
        
        # Datos detallados para cada día
        detalles_por_dia = {}
        
        print(f"\n--- Procesando detalles para visualización ---")
        print(f"Archivo de compras: {compras_file}")
        print(f"Archivo de ventas/P2P: {ventas_file}")
        
        if compras_file or ventas_file:
            # Cargar archivos originales
            try:
                # Procesar archivo de compras
                compras_por_dia = None
                if compras_file:
                    try:
                        # Leer el archivo CSV con precisión completa
                        compras_por_dia = pd.read_csv(compras_file, float_precision='high')
                        print(f"Columnas en archivo de compras: {compras_por_dia.columns.tolist()}")
                        
                        # Convertir columnas monetarias sin redondeo si existen
                        if 'Monto Cerrado' in compras_por_dia.columns:
                            try:
                                # Intentar primero convertir directamente si ya es numérico
                                if compras_por_dia['Monto Cerrado'].dtype.kind in 'ifc':
                                    pass  # Ya es numérico
                                else:
                                    # Intentar limpiar y convertir
                                    compras_por_dia['Monto Cerrado'] = compras_por_dia['Monto Cerrado'].astype(str).str.replace('$', '').str.replace(',', '').astype(float)
                                print(f"Monto Cerrado convertido correctamente")
                            except Exception as e:
                                print(f"Error convirtiendo Monto Cerrado: {e}")
                        
                        if 'Precio' in compras_por_dia.columns:
                            try:
                                # Intentar primero convertir directamente si ya es numérico
                                if compras_por_dia['Precio'].dtype.kind in 'ifc':
                                    pass  # Ya es numérico
                                else:
                                    # Intentar limpiar y convertir
                                    compras_por_dia['Precio'] = compras_por_dia['Precio'].astype(str).str.replace('$', '').str.replace(',', '').astype(float)
                                print(f"Precio convertido correctamente")
                            except Exception as e:
                                print(f"Error convirtiendo Precio: {e}")
                        
                        # Convertir la fecha a formato estándar
                        if 'Fecha' in compras_por_dia.columns:
                            # Intentar varios formatos de fecha
                            try:
                                compras_por_dia['Fecha'] = pd.to_datetime(compras_por_dia['Fecha'], format='%d/%m/%Y', errors='coerce')
                            except:
                                pass
                                
                            # Si la conversión falló, intentar con otro formato
                            if compras_por_dia['Fecha'].isna().all():
                                try:
                                    compras_por_dia['Fecha'] = pd.to_datetime(compras_por_dia['Fecha'], format='%d/%m', errors='coerce')
                                except:
                                    pass
                            
                            # Probar otros formatos si aún hay fechas nulas
                            if compras_por_dia['Fecha'].isna().any():
                                try:
                                    # Intentar formato yyyy-mm-dd
                                    fechas_tmp = pd.to_datetime(compras_por_dia['Fecha'], errors='coerce')
                                    # Reemplazar solo los valores nulos
                                    compras_por_dia.loc[compras_por_dia['Fecha'].isna(), 'Fecha'] = fechas_tmp.loc[compras_por_dia['Fecha'].isna()]
                                except:
                                    pass
                            
                            # Asegurarse que el año sea el actual si no está especificado
                            current_year = datetime.now().year
                            compras_por_dia['Fecha'] = compras_por_dia['Fecha'].apply(lambda x: x.replace(year=current_year) if pd.notnull(x) and x.year < 2000 else x)
                            
                            # Convertir a formato de string para la comparación - MISMO FORMATO QUE RESULTADOS_DF
                            compras_por_dia['Fecha'] = compras_por_dia['Fecha'].dt.strftime('%Y-%m-%d')
                            
                            # Imprimir para depuración
                            print(f"Fechas únicas en compras: {compras_por_dia['Fecha'].unique()}")
                    except Exception as e:
                        print(f"Error al procesar archivo de compras: {e}")
                        compras_por_dia = None
                
                # Procesar archivo de ventas/P2P
                ventas_por_dia = None
                if ventas_file:
                    try:
                        # Leer el archivo CSV con precisión completa
                        ventas_por_dia = pd.read_csv(ventas_file, float_precision='high')
                        print(f"Columnas en archivo de ventas/P2P: {ventas_por_dia.columns.tolist()}")
                        
                        # Verificar si es un archivo de Binance P2P
                        es_binance_p2p = 'Order Type' in ventas_por_dia.columns and 'Status' in ventas_por_dia.columns
                        
                        if es_binance_p2p:
                            # Filtrar solo transacciones completadas
                            ventas_por_dia = ventas_por_dia[ventas_por_dia['Status'] == 'Completed']
                            
                            # Convertir columnas monetarias y numéricas sin redondeo
                            for col in ['Total Price', 'Price', 'Quantity']:
                                if col in ventas_por_dia.columns:
                                    ventas_por_dia[col] = pd.to_numeric(ventas_por_dia[col], errors='coerce')
                            
                            # Convertir columnas de comisiones
                            for col in ['Maker Fee', 'Taker Fee']:
                                if col in ventas_por_dia.columns:
                                    ventas_por_dia[col] = pd.to_numeric(ventas_por_dia[col], errors='coerce').fillna(0)
                            
                            # Extraer la fecha de 'Created Time'
                            if 'Created Time' in ventas_por_dia.columns:
                                ventas_por_dia['Fecha'] = pd.to_datetime(ventas_por_dia['Created Time']).dt.date
                                ventas_por_dia['Fecha'] = pd.to_datetime(ventas_por_dia['Fecha'])
                                ventas_por_dia['Fecha'] = ventas_por_dia['Fecha'].dt.strftime('%Y-%m-%d')
                                
                            # Separar ventas y compras si necesario
                            if 'Order Type' in ventas_por_dia.columns:
                                ventas_p2p = ventas_por_dia[ventas_por_dia['Order Type'] == 'Sell']
                                compras_p2p = ventas_por_dia[ventas_por_dia['Order Type'] == 'Buy']
                                
                                # Combinar con compras existentes si es necesario
                                if not compras_p2p.empty and compras_por_dia is None:
                                    compras_por_dia = compras_p2p
                                elif not compras_p2p.empty:
                                    # Usar solo el dataframe de Binance P2P para compras
                                    compras_p2p_procesadas = compras_p2p.copy()
                                    compras_p2p_procesadas['Monto Cerrado'] = compras_p2p_procesadas['Total Price']
                                    compras_p2p_procesadas['Precio'] = compras_p2p_procesadas['Price']
                                    
                                    # Concatenar con las compras existentes
                                    compras_por_dia = pd.concat([compras_por_dia, compras_p2p_procesadas], ignore_index=True)
                                
                                # Usar solo ventas P2P
                                ventas_por_dia = ventas_p2p
                    except Exception as e:
                        print(f"Error al procesar archivo de ventas/P2P: {e}")
                        ventas_por_dia = None
                
                # Generar detalle para cada fecha en resultados_df
                print(f"Fechas en resultados_df: {resultados_df['Fecha'].unique()}")
                
                for _, row in resultados_df.iterrows():
                    fecha_str = row['Fecha']
                    print(f"Procesando fecha: {fecha_str}")
                    
                    # Detalles de compra de este día
                    compras_dia = pd.DataFrame()
                    if compras_por_dia is not None and 'Fecha' in compras_por_dia.columns:
                        compras_dia = compras_por_dia[compras_por_dia['Fecha'] == fecha_str]
                        print(f"  Encontradas {len(compras_dia)} compras para fecha {fecha_str}")
                    
                    # Detalles de venta de este día
                    ventas_dia = pd.DataFrame()
                    if ventas_por_dia is not None and 'Fecha' in ventas_por_dia.columns:
                        ventas_dia = ventas_por_dia[ventas_por_dia['Fecha'] == fecha_str]
                        print(f"  Encontradas {len(ventas_dia)} ventas para fecha {fecha_str}")
                    
                    # Guardar los detalles solo si hay datos
                    if not compras_dia.empty or not ventas_dia.empty:
                        detalles_por_dia[fecha_str] = {
                            'compras': compras_dia.to_dict('records') if not compras_dia.empty else [],
                            'ventas': ventas_dia.to_dict('records') if not ventas_dia.empty else []
                        }
                        print(f"Fecha {fecha_str}: {len(compras_dia)} compras, {len(ventas_dia)} ventas")
                
                # Imprimir información de depuración
                print(f"Total de días con detalles: {len(detalles_por_dia)}")
                for fecha, detalles in detalles_por_dia.items():
                    print(f"  {fecha}: {len(detalles['compras'])} compras, {len(detalles['ventas'])} ventas")
                
            except Exception as e:
                print(f"Error al procesar detalles: {e}")
                import traceback
                traceback.print_exc()
                # Si hay error en los detalles, continuamos sin ellos
                detalles_por_dia = {}
        
        # Verificar si existe el gráfico
        tiene_grafico = os.path.exists(grafico_path)
        
        return render_template(
            'pnl_resultados.html',
            file_id=file_id,
            resumen_texto=resumen_texto,
            resultados_df=resultados_df.to_dict('records'),
            total_pnl_neto=total_pnl_neto,
            total_usd_comprado=total_usd_comprado,
            total_usd_vendido=total_usd_vendido,
            tiene_grafico=tiene_grafico,
            detalles_por_dia=detalles_por_dia
        )
    
    except Exception as e:
        flash(f'Error al mostrar los resultados: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
        return redirect(url_for('pnl_calculator'))

@app.route('/pnl/descargar/<tipo>/<file_id>')
def descargar_pnl(tipo, file_id):
    if tipo == 'informe':
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            f"{file_id}_informe.txt",
            as_attachment=True,
            download_name="informe_pnl.txt"
        )
    elif tipo == 'grafico':
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            f"{file_id}_grafico.png",
            as_attachment=True,
            download_name="grafico_pnl.png"
        )
    elif tipo == 'csv':
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            f"{file_id}_informe.csv",
            as_attachment=True,
            download_name="informe_pnl.csv"
        )
    else:
        return redirect(url_for('pnl_calculator'))

@app.route('/historial')
def historial():
    """Muestra el historial de análisis realizados"""
    history = get_analysis_history()
    
    # Formatear fechas para mostrar
    import datetime
    for item in history:
        if item['fecha']:
            timestamp = item['fecha']
            item['fecha_formateada'] = datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
    
    return render_template('historial.html', history=history)

# Inicializar el scheduler para el comparador de precios P2P
scheduler = iniciar_scheduler()

# Ruta principal para mostrar el comparador P2P
@app.route('/comparador')
def comparador_p2p():
    return render_template('comparador_p2p.html')

# API para obtener datos actuales del comparador
@app.route('/api/comparador')
def api_comparador():
    # Verificar si hay datos disponibles
    if not ultimos_datos.get("timestamp"):
        # Si no hay datos, realizar una actualización
        datos = comparar_precios()
        if datos:
            return jsonify(datos)
        return jsonify({"error": "No se pudieron obtener los precios"}), 500
    
    return jsonify(ultimos_datos)

# API para obtener historial de precios
@app.route('/api/comparador/historial')
def api_historial():
    # Devolver el historial almacenado (últimos 100 registros)
    return jsonify(historial_precios)

# API para obtener datos OHLC
@app.route('/api/comparador/ohlc/<tipo>/<intervalo>')
def api_ohlc(tipo, intervalo):
    """Endpoint para obtener datos OHLC para gráficos de velas"""
    from binance_p2p_comparador import ohlc_data
    
    # Validar parámetros
    if tipo not in ohlc_data or (intervalo != '1h' and intervalo != '1d' and intervalo != 'all'):
        return jsonify([])
    
    # Para "all", combinar datos de ambos intervalos
    if intervalo == 'all':
        # Combinar datos de 1h (recientes) y 1d (históricos)
        df_1h = ohlc_data[tipo]['1h']
        df_1d = ohlc_data[tipo]['1d']
        
        # Convertir a listas de diccionarios para JSON
        datos_1h = df_1h.to_dict('records') if not df_1h.empty else []
        datos_1d = df_1d.to_dict('records') if not df_1d.empty else []
        
        # Combinar los datasets, evitando duplicados por timestamp
        resultados = {}
        for dato in datos_1d:
            resultados[dato['timestamp']] = dato
        
        # Agregar datos más recientes de 1h (sobrescribiendo duplicados)
        for dato in datos_1h:
            resultados[dato['timestamp']] = dato
        
        # Convertir a lista y ordenar por timestamp
        datos_combinados = list(resultados.values())
        datos_combinados.sort(key=lambda x: x['timestamp'])
        
        return jsonify(datos_combinados)
    
    # Para intervalos regulares
    df = ohlc_data[tipo][intervalo]
    if df.empty:
        return jsonify([])
    
    # Convertir a lista de diccionarios para JSON
    resultados = df.to_dict('records')
    return jsonify(resultados)

@app.route('/api/comparador/actualizar', methods=['POST'])
def api_actualizar():
    datos = comparar_precios()
    if datos:
        return jsonify({"success": True, "datos": datos})
    return jsonify({"success": False, "error": "No se pudieron actualizar los datos"})

@app.route('/api/comparador/precio-personalizado', methods=['POST'])
def api_precio_personalizado():
    """Endpoint para actualizar el precio personalizado ingresado por el usuario"""
    try:
        data = request.get_json()
        if not data or 'precio' not in data:
            return jsonify({"success": False, "error": "Precio no proporcionado"})
        
        precio = float(data['precio'])
        if precio <= 0:
            return jsonify({"success": False, "error": "El precio debe ser mayor que cero"})
        
        # Actualizar el precio personalizado
        if actualizar_precio_personalizado(precio):
            # Forzar una actualización para recalcular márgenes
            datos = comparar_precios()
            if datos:
                return jsonify({
                    "success": True, 
                    "mensaje": f"Precio personalizado actualizado a {precio} CLP",
                    "datos": ultimos_datos
                })
        
        return jsonify({"success": False, "error": "No se pudo actualizar el precio personalizado"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/comparador/datos')
def api_datos():
    return jsonify(ultimos_datos)

if __name__ == '__main__':
    # Configuración para el entorno de producción
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 
import requests
import json
import datetime
import logging
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import re
import random  # Para pequeña variación en datos sintéticos

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("comparador_p2p.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("comparador_p2p")

# Variables globales para almacenar los datos más recientes
ultimos_datos = {
    "precio_p2p_compra": None,   # Precio al que la gente compra USDT (nosotros vendemos)
    "precio_p2p_venta": None,    # Precio al que la gente vende USDT (nosotros compramos)
    "precio_mercado": None,      # Precio oficial del dólar
    "margen_promedio": None,     # Margen con el promedio (referencial)
    "margen_compra": None,       # Margen entre precio mercado y precio P2P compra
    "margen_venta": None,        # Margen entre precio mercado y precio P2P venta
    "margen_personalizado": None, # Margen con precio personalizado
    "precio_personalizado": 0,   # Precio personalizado ingresado por el usuario
    "alerta": False,             # Si hay alerta de margen significativo
    "timestamp": None            # Timestamp de la actualización
}

# Historial de precios (últimos 100 registros)
historial_precios = []

# Estructuras para almacenar datos OHLC
ohlc_data = {
    'p2p_compra': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    },
    'p2p_venta': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    },
    'mercado': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    },
    'margen_promedio': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    },
    'margen_compra': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    },
    'margen_venta': {
        '1h': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
        '1d': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    }
}

def obtener_precio_p2p_binance(fiat="CLP", crypto="USDT", tipo="BUY"):
    """Obtiene el precio promedio de las 5 mejores ofertas del P2P de Binance"""
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    
    payload = {
        "page": 1,
        "rows": 10,
        "payTypes": [],
        "asset": crypto,
        "tradeType": tipo,
        "fiat": fiat,
        "publisherType": None
    }
    
    headers = {
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Verificar si hay errores HTTP
        data = response.json()
        
        if data and "data" in data:
            # Extraer los precios de las 5 primeras ofertas
            precios = []
            for oferta in data["data"][:5]:
                precios.append(float(oferta["adv"]["price"]))
            
            # Calcular precio promedio
            if precios:
                return sum(precios) / len(precios)
            else:
                logger.warning(f"No se encontraron ofertas de {crypto}/{fiat}")
        else:
            logger.warning(f"Respuesta de API sin datos: {data}")
    except Exception as e:
        logger.error(f"Error obteniendo precio P2P Binance: {str(e)}")
    
    return None

def obtener_precio_mercado_general():
    """Obtiene el precio oficial del dólar en pesos chilenos (CLP)"""
    # Opciones de fuentes para obtener el precio del dólar
    fuentes = [
        obtener_precio_dolar_bcentral,  # Banco Central (scraping)
        obtener_precio_dolar_cmf,       # Comisión para el Mercado Financiero (scraping)
        obtener_precio_dolar_yahoofin,  # Yahoo Finance API
        obtener_precio_dolar_exchangerate  # ExchangeRate API (gratuita)
    ]
    
    # Intentar con cada fuente hasta obtener un precio válido
    for fuente in fuentes:
        try:
            valor = fuente()
            if valor is not None:
                return valor
        except Exception as e:
            logger.error(f"Error con fuente {fuente.__name__}: {str(e)}")
    
    # Si todo falla, usamos un valor fijo cercano al actual
    valor_predeterminado = 970.0  # Valor cercano al actual
    logger.warning(f"No se pudo obtener precio del dólar de ninguna fuente. Usando valor predeterminado: {valor_predeterminado}")
    return valor_predeterminado

def obtener_precio_dolar_bcentral():
    """Obtiene el precio del dólar mediante scraping del Banco Central de Chile"""
    try:
        url = "https://si3.bcentral.cl/indicadoressiete/secure/Serie.aspx?gcode=PRE_TCO"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Buscar el valor en la tabla
            tabla = soup.find('table', {'id': 'gr'})
            if tabla:
                filas = tabla.find_all('tr')
                if len(filas) > 1:  # Primera fila es encabezado
                    ultima_fila = filas[-1]
                    celdas = ultima_fila.find_all('td')
                    if len(celdas) > 1:
                        valor_texto = celdas[1].text.strip()
                        # Limpiar y convertir a float
                        valor_texto = re.sub(r'[^\d,]', '', valor_texto).replace(',', '.')
                        valor = float(valor_texto)
                        logger.info(f"Precio dólar obtenido del Banco Central: {valor} CLP")
                        return valor
    except Exception as e:
        logger.error(f"Error obteniendo precio del Banco Central: {str(e)}")
    
    return None

def obtener_precio_dolar_cmf():
    """Obtiene el precio del dólar mediante scraping de la Comisión para el Mercado Financiero"""
    try:
        url = "https://www.cmfchile.cl/portal/menu/625"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Buscar la tabla de indicadores
            tabla = soup.find('table', {'class': 'table'})
            if tabla:
                # Buscar la fila del dólar observado
                filas = tabla.find_all('tr')
                for fila in filas:
                    celdas = fila.find_all('td')
                    if len(celdas) >= 2 and 'Dólar' in celdas[0].text:
                        valor_texto = celdas[1].text.strip()
                        # Limpiar y convertir a float
                        valor_texto = re.sub(r'[^\d,]', '', valor_texto).replace(',', '.')
                        valor = float(valor_texto)
                        logger.info(f"Precio dólar obtenido de la CMF: {valor} CLP")
                        return valor
    except Exception as e:
        logger.error(f"Error obteniendo precio de la CMF: {str(e)}")
    
    return None

def obtener_precio_dolar_yahoofin():
    """Obtiene el precio del dólar desde Yahoo Finance (sin usar yfinance)"""
    try:
        # Consultar la API de Yahoo Finance directamente
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDCLP=X"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Extraer el precio actual
            if data and 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                result = data['chart']['result'][0]
                if 'meta' in result and 'regularMarketPrice' in result['meta']:
                    valor = float(result['meta']['regularMarketPrice'])
                    logger.info(f"Precio dólar obtenido de Yahoo Finance: {valor} CLP")
                    return valor
    except Exception as e:
        logger.error(f"Error obteniendo precio de Yahoo Finance: {str(e)}")
    
    return None

def obtener_precio_dolar_exchangerate():
    """Obtiene el precio del dólar desde ExchangeRate-API (gratuita, con límite de peticiones)"""
    try:
        # API gratuita de ExchangeRate-API
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'rates' in data and 'CLP' in data['rates']:
                valor = float(data['rates']['CLP'])
                logger.info(f"Precio dólar obtenido de ExchangeRate-API: {valor} CLP")
                return valor
    except Exception as e:
        logger.error(f"Error obteniendo precio de ExchangeRate-API: {str(e)}")
    
    return None

def obtener_datos_historicos_dolar(dias=30):
    """Obtiene datos históricos del dólar para inicializar los gráficos de velas"""
    # Intentar obtener datos históricos de Yahoo Finance
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/USDCLP=X?interval=1d&range={dias}d"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            datos_historicos = []
            
            if data and 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                result = data['chart']['result'][0]
                
                # Obtener timestamps
                timestamps = result.get('timestamp', [])
                # Obtener precios
                quote = result.get('indicators', {}).get('quote', [{}])[0]
                opens = quote.get('open', [])
                highs = quote.get('high', [])
                lows = quote.get('low', [])
                closes = quote.get('close', [])
                volumes = quote.get('volume', [])
                
                # Crear datos OHLC
                for i in range(len(timestamps)):
                    if i < len(opens) and i < len(highs) and i < len(lows) and i < len(closes):
                        # Verificar valores nulos
                        if opens[i] is None or highs[i] is None or lows[i] is None or closes[i] is None:
                            continue
                        
                        # Convertir timestamp a fecha legible
                        fecha = datetime.datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d %H:%M:%S")
                        
                        datos_historicos.append({
                            'timestamp': fecha,
                            'open': opens[i],
                            'high': highs[i],
                            'low': lows[i],
                            'close': closes[i],
                            'volume': volumes[i] if i < len(volumes) and volumes[i] is not None else 5
                        })
                
                if datos_historicos:
                    logger.info(f"Datos históricos obtenidos con éxito de Yahoo Finance: {len(datos_historicos)} registros")
                    return datos_historicos
    except Exception as e:
        logger.error(f"Error obteniendo datos históricos de Yahoo Finance: {str(e)}")
    
    # Si no se pudieron obtener datos históricos, creamos datos sintéticos
    logger.warning("No se pudieron obtener datos históricos reales. Generando datos sintéticos.")
    return None

def actualizar_ohlc(tipo, intervalo, nuevo_valor):
    """Actualiza los datos OHLC para el tipo e intervalo especificado"""
    global ohlc_data
    
    if not nuevo_valor or tipo not in ohlc_data or intervalo not in ohlc_data[tipo]:
        return
    
    ahora = datetime.datetime.now()
    
    # Determinar el timestamp del intervalo actual
    if intervalo == '1h':
        # Redondear a la hora actual
        timestamp = datetime.datetime(ahora.year, ahora.month, ahora.day, ahora.hour)
    elif intervalo == '1d':
        # Redondear al día actual
        timestamp = datetime.datetime(ahora.year, ahora.month, ahora.day)
    else:
        return
    
    # Convertir timestamp a formato string para comparación
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    # Si ya existe una vela para este intervalo, actualizar
    df = ohlc_data[tipo][intervalo]
    if not df.empty and df.iloc[-1]['timestamp'] == timestamp_str:
        # Actualizar high/low/close
        df.at[df.index[-1], 'high'] = max(df.iloc[-1]['high'], nuevo_valor)
        df.at[df.index[-1], 'low'] = min(df.iloc[-1]['low'], nuevo_valor)
        df.at[df.index[-1], 'close'] = nuevo_valor
        df.at[df.index[-1], 'volume'] += 1
    else:
        # Crear nueva vela
        nueva_vela = {
            'timestamp': timestamp_str,
            'open': nuevo_valor,
            'high': nuevo_valor,
            'low': nuevo_valor,
            'close': nuevo_valor,
            'volume': 1
        }
        ohlc_data[tipo][intervalo] = pd.concat([df, pd.DataFrame([nueva_vela])], ignore_index=True)
        
        # Mantener solo los últimos 7 días o 168 horas
        limite = 168 if intervalo == '1h' else 30
        if len(ohlc_data[tipo][intervalo]) > limite:
            ohlc_data[tipo][intervalo] = ohlc_data[tipo][intervalo].tail(limite)

def comparar_precios():
    """
    Compara los precios del P2P de Binance y el mercado general.
    Actualiza las variables globales con los datos obtenidos.
    Calcula diferentes tipos de márgenes para diferentes estrategias.
    """
    global ultimos_datos, historial_precios
    
    try:
        # Obtener precios actuales
        precio_p2p_compra = obtener_precio_p2p_binance(tipo="BUY")
        precio_p2p_venta = obtener_precio_p2p_binance(tipo="SELL")
        precio_mercado = obtener_precio_mercado_general()
        
        # Verificar si se obtuvieron todos los precios
        if precio_p2p_compra and precio_p2p_venta and precio_mercado:
            # Calcular el promedio P2P (referencial)
            precio_p2p_promedio = (precio_p2p_compra + precio_p2p_venta) / 2
            
            # SIMPLIFICACIÓN DE MÁRGENES
            # 1. Margen para comprar dólares oficiales y ponerme a venderlos en P2P
            # Positivo significa que puedo comprar dólares oficiales y venderlos como USDT en P2P con ganancia
            margen_compra = precio_p2p_compra - precio_mercado
            
            # 2. Margen personalizado: Diferencia entre precio P2P de compra y precio personalizado ingresado
            # Positivo significa que hay ganancia respecto al precio personalizado ingresado
            margen_personalizado = None
            if ultimos_datos["precio_personalizado"] > 0:
                margen_personalizado = precio_p2p_compra - ultimos_datos["precio_personalizado"]
            
            # Determinar si hay alertas
            alerta_compra = margen_compra > 4  # Alerta si el margen de compra es mayor a 4 pesos
            alerta_personalizada = margen_personalizado and margen_personalizado > 4  # Alerta para precio personalizado
            
            # Cualquier alerta activa la alerta general
            alerta = alerta_compra or alerta_personalizada
            
            # Actualizar datos globales
            timestamp = datetime.datetime.now()
            
            nuevos_datos = {
                "precio_p2p_compra": precio_p2p_compra,
                "precio_p2p_venta": precio_p2p_venta,
                "precio_p2p_promedio": precio_p2p_promedio,
                "precio_mercado": precio_mercado,
                "margen_compra": margen_compra,
                "margen_personalizado": margen_personalizado,
                "precio_personalizado": ultimos_datos["precio_personalizado"],
                "alerta": alerta,
                "alerta_compra": alerta_compra,
                "alerta_personalizada": alerta_personalizada,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            ultimos_datos = nuevos_datos
            
            # Guardar en historial
            historial_precios.append(nuevos_datos)
            # Mantener solo los últimos 100 registros
            if len(historial_precios) > 100:
                historial_precios = historial_precios[-100:]
            
            # Registrar información
            logger.info(f"Precios actualizados:")
            logger.info(f"  P2P Compra={precio_p2p_compra:.2f} | P2P Venta={precio_p2p_venta:.2f} | Mercado={precio_mercado:.2f}")
            logger.info(f"  Margen Compra={margen_compra:.2f}")
            
            # Verificar si hay que enviar alerta
            if alerta:
                enviar_alertas_margenes(nuevos_datos)
            
            # Actualizar datos OHLC para todos los precios y márgenes
            actualizar_ohlc('p2p_compra', '1h', precio_p2p_compra)
            actualizar_ohlc('p2p_compra', '1d', precio_p2p_compra)
            
            actualizar_ohlc('p2p_venta', '1h', precio_p2p_venta)
            actualizar_ohlc('p2p_venta', '1d', precio_p2p_venta)
            
            actualizar_ohlc('mercado', '1h', precio_mercado)
            actualizar_ohlc('mercado', '1d', precio_mercado)
            
            actualizar_ohlc('margen_compra', '1h', margen_compra)
            actualizar_ohlc('margen_compra', '1d', margen_compra)
            
            return nuevos_datos
        else:
            logger.warning("No se pudieron obtener todos los precios necesarios")
    except Exception as e:
        logger.error(f"Error en comparación de precios: {str(e)}")
    
    return None

def enviar_alertas_margenes(datos):
    """Función para enviar alertas cuando cualquier margen supera el umbral"""
    
    mensaje = "¡ALERTA DE MÁRGENES!\n\n"
    
    # Alerta de margen de compra
    if datos["alerta_compra"]:
        mensaje += f"🟢 MARGEN DE COMPRA: {datos['margen_compra']:.2f} pesos\n"
        mensaje += f"  Puedes comprar dólares a {datos['precio_mercado']:.2f} CLP (precio oficial) "
        mensaje += f"y venderlos como USDT a {datos['precio_p2p_compra']:.2f} CLP en P2P\n\n"
    
    # Alerta de margen personalizado
    if datos["alerta_personalizada"]:
        mensaje += f"🟡 MARGEN PERSONALIZADO: {datos['margen_personalizado']:.2f} pesos\n"
        mensaje += f"  Compraste a {datos['precio_personalizado']:.2f} CLP y ahora "
        mensaje += f"puedes vender a {datos['precio_p2p_compra']:.2f} CLP en P2P\n\n"
    
    logger.warning(mensaje)
    
    # Aquí podrías implementar envío de alertas por correo, Telegram, etc.
    # Por ejemplo:
    # enviar_correo("alerta@ejemplo.com", "Alerta de márgenes USD/CLP", mensaje)
    # enviar_telegram(mensaje)

def actualizar_precio_personalizado(nuevo_precio):
    """Actualiza el precio personalizado ingresado por el usuario"""
    global ultimos_datos
    
    try:
        precio = float(nuevo_precio)
        if precio > 0:
            ultimos_datos["precio_personalizado"] = precio
            logger.info(f"Precio personalizado actualizado a: {precio} CLP")
            
            # Recalcular margen personalizado
            if ultimos_datos["precio_p2p_compra"]:
                ultimos_datos["margen_personalizado"] = ultimos_datos["precio_p2p_compra"] - precio
            
            return True
    except (ValueError, TypeError) as e:
        logger.error(f"Error al actualizar precio personalizado: {str(e)}")
    
    return False

def generar_datos_iniciales():
    """Genera datos OHLC iniciales para el precio del mercado (dólar)"""
    global ohlc_data
    
    # Intentar obtener datos históricos reales
    datos_historicos = obtener_datos_historicos_dolar(30)
    
    if datos_historicos:
        # Usar datos históricos reales solo para el mercado (dólar)
        for dato in datos_historicos:
            # Para los datos diarios del mercado
            actualizar_ohlc_con_datos('mercado', '1d', dato['timestamp'], 
                open_val=dato['open'],
                high_val=dato['high'],
                low_val=dato['low'],
                close_val=dato['close'],
                volume_val=dato['volume']
            )
            
            # También crear datos horarios para el último día
            if dato == datos_historicos[-1]:  # Solo para el último día
                hora_actual = datetime.datetime.now()
                valor_base = dato['close']
                
                # Crear 24 horas basadas en el precio de cierre del último día
                for h in range(24, 0, -1):
                    hora_anterior = hora_actual - datetime.timedelta(hours=h)
                    timestamp = datetime.datetime(hora_anterior.year, hora_anterior.month, hora_anterior.day, hora_anterior.hour)
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Agregar el valor del dólar para esta hora (sin variación, solo para tener datos)
                    actualizar_ohlc_con_datos('mercado', '1h', timestamp_str,
                        open_val=valor_base,
                        high_val=valor_base,
                        low_val=valor_base,
                        close_val=valor_base,
                        volume_val=1
                    )
        
        logger.info("Datos históricos del dólar cargados con éxito")
    else:
        logger.warning("No se pudieron obtener datos históricos del dólar. Los gráficos estarán vacíos hasta que se recolecten datos.")

def actualizar_ohlc_con_datos(tipo, intervalo, timestamp_str, valor_base=None, open_val=None, high_val=None, low_val=None, close_val=None, volume_val=None):
    """Actualiza OHLC con datos predefinidos"""
    global ohlc_data
    
    # Si se proporciona valor_base pero no los demás valores
    if valor_base is not None and (open_val is None or high_val is None or low_val is None or close_val is None):
        # Crear variaciones pequeñas para OHLC
        variacion = valor_base * 0.005  # 0.5% de variación
        
        # Valores por defecto
        open_val = open_val or (valor_base - variacion / 2)
        high_val = high_val or (valor_base + variacion)
        low_val = low_val or (valor_base - variacion)
        close_val = close_val or (valor_base + variacion / 3)
    
    # Si no se proporciona volume_val, usar valor por defecto
    volume_val = volume_val or 5
    
    # Crear datos de vela
    nueva_vela = {
        'timestamp': timestamp_str,
        'open': open_val,
        'high': high_val,
        'low': low_val,
        'close': close_val,
        'volume': volume_val
    }
    
    # Añadir al dataframe correspondiente
    df = ohlc_data[tipo][intervalo]
    ohlc_data[tipo][intervalo] = pd.concat([df, pd.DataFrame([nueva_vela])], ignore_index=True)

def iniciar_scheduler():
    """Inicia el programador para actualizar precios periódicamente"""
    # Generar datos de prueba iniciales para la visualización inmediata
    generar_datos_iniciales()
    
    # Iniciar el scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(comparar_precios, 'interval', minutes=1)
    scheduler.start()
    logger.info("Scheduler iniciado, actualizando precios cada 1 minuto")
    return scheduler

# Para ejecutar de forma independiente
if __name__ == "__main__":
    print("Iniciando comparador de precios Binance P2P vs Mercado general...")
    scheduler = iniciar_scheduler()
    
    # Primera ejecución inmediata
    comparar_precios()
    
    try:
        # Mantener el script corriendo
        import time
        while True:
            time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("\nComparador detenido.") 
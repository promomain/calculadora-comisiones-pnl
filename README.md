# Calculadora de Comisiones y PNL

Aplicación web desarrollada con Flask para calcular y analizar comisiones y ganancias/pérdidas en operaciones financieras P2P.

## Características

- **Calculadora de Comisiones**: Analiza las comisiones generadas por operaciones completadas
- **Calculadora de PNL (Profit and Loss)**: Calcula ganancias y pérdidas en operaciones P2P
- **Historial de Análisis**: Permite revisar análisis anteriores sin tener que cargar nuevamente los archivos
- **Informes Detallados**: Genera informes en texto, gráficos y archivos CSV

## Estructura del Proyecto

- `app.py`: Aplicación web Flask principal
- `comisiones_flexible.py`: Script para analizar archivos CSV
- `templates/`: Plantillas HTML para la interfaz web
- `uploads/`: Carpeta donde se guardan los archivos CSV subidos
- `resultados/`: Carpeta donde se guardan los informes y gráficos generados

## Requisitos

- Python 3.7+
- Flask
- Pandas
- Matplotlib
- Werkzeug

## Instalación

1. Clonar el repositorio:
```
git clone https://github.com/tu-usuario/calculadora-comisiones-pnl.git
cd calculadora-comisiones-pnl
```

2. Instalar dependencias:
```
pip install -r requirements.txt
```

3. Ejecutar la aplicación:
```
python app.py
```

4. Abrir en el navegador:
```
http://localhost:5000
```

## Uso

1. Sube archivos CSV con el formato adecuado
2. La aplicación procesará los datos y generará informes detallados
3. Podrás descargar informes en formato texto, CSV y gráficos

## Formato de CSV Esperado

El archivo CSV debe contener al menos las siguientes columnas:
- `Maker Fee`: Comisiones como maker
- `Taker Fee`: Comisiones como taker
- `Created Time`: Fecha y hora de la transacción (formato YYYY-MM-DD HH:MM:SS)
- `Status`: Estado de la transacción (solo se procesan las "Completed")

## Importante

- Solo se consideran las transacciones con estado "Completed" para los cálculos de comisiones.
- Las transacciones con estados como "System cancelled" o "Unpaid" son automáticamente excluidas.
- Si el archivo CSV no contiene una columna de estado, se mostrará una advertencia y se procesarán todas las transacciones.

## Licencia

MIT

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abra un issue primero para discutir lo que le gustaría cambiar. 
# Calculadora de Comisiones

Una aplicación web para analizar comisiones de transacciones completadas a partir de archivos CSV, generando informes detallados y visualizaciones gráficas por día.

## Características

- Análisis de comisiones agrupadas por día
- Filtrado automático de transacciones (solo considera las completadas)
- Soporte para diferentes formatos de CSV (detección automática de columnas)
- Generación de informes detallados
- Visualización gráfica de comisiones vs. transacciones
- Descarga de informes y gráficos
- Interfaz web amigable

## Estructura del Proyecto

- `app.py`: Aplicación web Flask principal
- `comisiones_flexible.py`: Script para analizar archivos CSV
- `templates/`: Plantillas HTML para la interfaz web
- `uploads/`: Carpeta donde se guardan los archivos CSV subidos
- `resultados/`: Carpeta donde se guardan los informes y gráficos generados

## Requisitos

- Python 3.8 o superior
- Dependencias listadas en `requirements.txt`

## Instalación

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tuusuario/calculadora-comisiones.git
   cd calculadora-comisiones
   ```

2. Crea un entorno virtual:
   ```bash
   python -m venv venv
   ```

3. Activa el entorno virtual:
   - En Windows:
     ```bash
     venv\Scripts\activate
     ```
   - En macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

### Aplicación Web

1. Inicia la aplicación web:
   ```bash
   python app.py
   ```

2. Abre tu navegador y ve a `http://127.0.0.1:5000/`

3. Sube tu archivo CSV y visualiza los resultados

### Línea de Comandos

También puedes usar el script desde la línea de comandos:

```bash
python comisiones_flexible.py ruta/a/tu/archivo.csv
```

Opciones adicionales:
- `--no-grafico`: No generar gráfico
- `--salida nombre`: Especificar un nombre base para los archivos de salida

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

Este proyecto está licenciado bajo la Licencia MIT - vea el archivo LICENSE para más detalles.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abra un issue primero para discutir lo que le gustaría cambiar. 
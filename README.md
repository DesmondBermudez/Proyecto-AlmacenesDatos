# ETL Dolar Canasta

Este ETL tiene como funcion extraer, transformar y cargar datos de tipo de cambio, combustibles y canasta basica en la base de datos `DW_Dolar_Canasta`.

La funcionalidad principal del proceso no es solo mover datos, sino asegurar que siempre exista una fuente util para la carga:

- tipo de cambio con consulta directa a API y respaldo en CSV
- combustibles con consulta directa a API y respaldo en CSV
- canasta basica sintetica generada localmente para garantizar la carga

## Como funciona el ETL

El flujo general es este:

1. Leer los parametros de consola.
2. Construir la conexion a SQL Server.
3. Obtener datos de tipo de cambio.
4. Obtener datos de combustibles.
5. Generar el historico sintetico de canasta.
6. Transformar y normalizar los datos necesarios.
7. Insertar los datos en tablas `staging`.
8. Insertar automaticamente los catalogos base requeridos por el DW.
9. Ejecutar los procedimientos almacenados del DW.

## Insercion automatica de catalogos base

Antes de ejecutar las transformaciones finales, el ETL verifica que existan los catalogos minimos necesarios en el Data Warehouse y los inserta si hacen falta.

Esto incluye:

- fuentes de datos base en `DimFuenteDatos`
- monedas base en `DimMoneda`

Con esto, el ETL no depende de una carga manual adicional para que las tablas de hechos puedan relacionarse correctamente con sus dimensiones.

## Fuentes y logica de consumo

### Tipo de cambio

El ETL usa como fuente principal la API de Hacienda.

Comportamiento:

- si la API responde, usa esos datos
- si la opcion de historicos esta activa, actualiza `data/raw/tipo_cambio_historico.csv`
- si la API falla, usa `data/raw/tipo_cambio_historico.csv`
- si el CSV no existe, lo crea automaticamente
- en modo historico, si no hay datos suficientes, simula los faltantes

### Combustibles

El ETL usa como fuente principal la API de ARESEP.

Comportamiento:

- si la API responde, usa esos datos
- si la opcion de historicos esta activa, actualiza `data/raw/combustible_historico.csv`
- si la API falla, usa `data/raw/combustible_historico.csv`
- si el CSV no existe, lo crea automaticamente

### Canasta basica

La canasta no se obtiene desde una fuente externa en esta version del ETL.

Comportamiento:

- se genera localmente como historico sintetico
- se guarda en `data/raw/historico_canasta_cr.csv`
- se usa inmediatamente para la carga
- este archivo siempre se genera, incluso si no se actualizan los otros historicos

## Modos de carga

### `direct-insert`

Usa el tipo de cambio actual y ejecuta la carga normal del ETL.

### `historico`

Recorre el historico del tipo de cambio desde el anio 2000, intentando primero API, luego CSV y finalmente simulacion si hace falta.

## Parametros de consola

```bash
python ETL_dolar_canasta.py
python ETL_dolar_canasta.py --modo-carga direct-insert
python ETL_dolar_canasta.py --modo-carga historico
python ETL_dolar_canasta.py --trusted-connection
python ETL_dolar_canasta.py --no-trusted-connection
python ETL_dolar_canasta.py --server . --database DW_Dolar_Canasta --username sa --password secret
python ETL_dolar_canasta.py --generar-historicos
python ETL_dolar_canasta.py --no-generar-historicos
```

- `--modo-carga`
  Define el modo de ejecucion del ETL.
  Valores: `direct-insert`, `historico`

- `--server`
  Servidor SQL Server.
  Default: `localhost`

- `--database`
  Base de datos destino.
  Default: `DW_Dolar_Canasta`

- `--driver`
  Driver ODBC.
  Default: `"ODBC Driver 17 for SQL Server"`

- `--username`
  Usuario SQL opcional

- `--password`
  Contrasena SQL opcional

- `--trusted-connection`
  Usa autenticacion integrada de Windows

- `--no-trusted-connection`
  Desactiva la autenticacion integrada cuando quieras forzar otra forma de conexion

- `--generar-historicos`
  Actualiza los CSV historicos de tipo de cambio y combustibles

- `--no-generar-historicos`
  No actualiza esos CSV, pero mantiene el uso de respaldos si las APIs fallan

## Comportamiento por defecto

Al ejecutar:

```bash
python ETL_dolar_canasta.py
```

el ETL hace esto por defecto:

- usa servidor local
- usa base `DW_Dolar_Canasta`
- usa `TrustServerCertificate=yes`
- usa `Trusted_Connection=yes`
- corre en modo `direct-insert`
- genera o actualiza historicos de tipo de cambio y combustibles
- genera siempre el historico sintetico de canasta
- inserta catalogos base si no existen
- carga todo en la base de datos

## Independencia de parametros

Los parametros son independientes entre si. Puedes cambiar uno sin afectar los demas.

Ejemplos:

Cambiar solo el servidor:

```bash
python ETL_dolar_canasta.py --server .\\SQLEXPRESS
```

Cambiar solo el modo:

```bash
python ETL_dolar_canasta.py --modo-carga historico
```

Desactivar solo la actualizacion de historicos:

```bash
python ETL_dolar_canasta.py --no-generar-historicos
```

Usar autenticacion SQL:

```bash
python ETL_dolar_canasta.py --server localhost --database DW_Dolar_Canasta --username sa --password secret
```

## Estructura funcional

```text
etl_dolar_canasta/
|-- ETL_dolar_canasta.py
|-- README.md
|-- requirements.txt
|-- data/
|   `-- raw/
|       |-- combustible_historico.csv
|       |-- historico_canasta_cr.csv
|       `-- tipo_cambio_historico.csv
`-- src/
    `-- etl_dolar_canasta/
        |-- __init__.py
        |-- app.py
        |-- cli.py
        |-- config.py
        |-- db.py
        |-- extract.py
        |-- load.py
        |-- models.py
        `-- transform.py
```

## Pruebas

Se agrego una zona de pruebas para validar la estabilidad base del proyecto sin cambiar el flujo principal del ETL.

### Instalar dependencias de desarrollo

```bash
python -m pip install -r etl_dolar_canasta/requirements-dev.txt
```

### Ejecutar pruebas unitarias

```bash
python -m pytest -q etl_dolar_canasta/tests/unit
```

Estas pruebas cubren:

- fallback unificado de fuentes
- transformaciones principales
- carga de staging para canasta
- orden de ejecucion de procedimientos almacenados

### Smoke test SQL opcional

Existe una prueba `smoke_sql` para validar carga real sobre SQL Server cuando el entorno esta disponible.

Se ejecuta solo si defines:

- `ETL_SMOKE_SQL=1`
- `ETL_SQL_SERVER`
- opcionalmente `ETL_SQL_DRIVER`, `ETL_SQL_USERNAME`, `ETL_SQL_PASSWORD`, `ETL_SQL_TRUSTED_CONNECTION`

Ejemplo:

```bash
python -m pytest -q etl_dolar_canasta/tests/smoke -m smoke_sql
```

## Procedimientos almacenados del DW

El ETL no implementa toda la logica analitica en Python. Una parte importante del procesamiento final ocurre en los procedimientos almacenados definidos en [01 - DW_Canasta.sql](C:/Users/d3smo/Desktop/CUC/Almacenes%20de%20datos/Nueva%20carpeta/Proyecto-AlmacenesDatos/dw_database/01%20-%20DW_Canasta.sql).

### `sp_InsertarTipoCambioStaging`

Este procedimiento recibe la fecha, el tipo de cambio de compra, el de venta y los identificadores de moneda y fuente.

Su funcion es:

- calcular `FechaID` en formato `YYYYMMDD`
- insertar la fecha en `StagingFecha` si todavia no existe
- insertar el registro en `StagingTipoCambio` si todavia no existe para esa fecha
- calcular el tipo de cambio promedio antes de guardar

En el flujo del ETL, este procedimiento se usa durante la carga del tipo de cambio.

### `sp_Transform_DimFecha`

Este procedimiento toma los registros almacenados en `StagingFecha` y los lleva a `DimFecha`.

Su funcion es:

- generar los atributos calendarios a partir de la fecha
- poblar dia, mes, nombre del mes, trimestre y anio
- evitar insertar fechas repetidas

En el flujo del ETL, este procedimiento se ejecuta antes de poblar hechos, porque la dimension fecha sirve como base para las demas relaciones.

### `sp_Transform_DimProducto`

Este procedimiento toma los registros de `StagingProducto` y sincroniza la tabla `DimProducto`.

Su funcion es:

- normalizar nombres de productos
- insertar productos nuevos
- actualizar categoria, unidad, condicion de importado, precio base y factor canasta si el producto ya existe

En el flujo del ETL, este procedimiento permite convertir el catalogo crudo cargado desde Python en una dimension consistente para analisis.

### `sp_Transform_DimRegion`

Este procedimiento toma los registros geograficos de `StagingHistoricoCanasta` y llena `DimRegion`.

Su funcion es:

- tomar provincia, canton y distrito
- insertar solo regiones nuevas
- evitar duplicados por combinacion de provincia y canton

En el flujo del ETL, este procedimiento prepara la dimension geografica que luego sera referenciada por la tabla de hechos de canasta.

### `sp_Transform_FactTipoCambio`

Este procedimiento toma `StagingTipoCambio` y la transforma hacia `FactTipoCambio`.

Su funcion es:

- convertir la fecha a la llave `FechaID`
- mapear las monedas de origen y referencia
- insertar nuevos registros o actualizar los existentes si la combinacion fecha-moneda ya existe
- asegurar que solo entren valores positivos de compra y venta

En el flujo del ETL, este procedimiento materializa la tabla de hechos del tipo de cambio.

### `sp_Load_FactPreciosCanasta`

Este procedimiento toma `StagingHistoricoCanasta` y la integra en `FactPreciosCanasta`.

Su funcion es:

- unir datos de staging con `DimFecha`, `DimProducto` y `DimRegion`
- cargar el precio de cada producto por fecha y region
- calcular `CostoCanastaTotal` usando el `FactorCanasta`
- calcular un valor de `IPC` usando un precio base global
- evitar insertar registros duplicados para la misma combinacion fecha-producto-region

En el flujo del ETL, este procedimiento representa la carga final de la tabla de hechos de canasta.

## Dependencias

Instalacion:

```bash
pip install -r requirements.txt
```

Requisitos:

- Python 3.11 o superior
- `ODBC Driver 17 for SQL Server`
- SQL Server accesible desde el equipo

## Nota final

La logica del Data Warehouse se mantiene en los procedimientos almacenados definidos en el script SQL. El ETL prepara los datos, los carga a `staging` y dispara las transformaciones del DW.

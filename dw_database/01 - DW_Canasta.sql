USE master
GO

/*
    Script simplificado y portable para crear el DW de dolar y canasta.
    - No usa rutas fisicas para MDF/LDF.
    - No depende de opciones especificas de una version de SQL Server.
    - Mantiene la estructura, tablas, relaciones, indices y procedimientos.
*/

IF DB_ID('DW_Dolar_Canasta') IS NULL
BEGIN
    CREATE DATABASE DW_Dolar_Canasta;
END
GO

USE DW_Dolar_Canasta
GO


/* ==============================
   TABLAS DEL DW
   ============================== */

/* ==============================
   DIMENSIONES DEL DW
   ============================== */
IF OBJECT_ID('dbo.DimFecha', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimFecha (
        FechaID INT NOT NULL PRIMARY KEY,
        Fecha DATE NOT NULL,
        Dia INT NULL,
        Mes INT NULL,
        NombreMes VARCHAR(30) NULL,
        Año INT NULL,
        Trimestre INT NULL
    );
END
GO

IF OBJECT_ID('dbo.DimFuenteDatos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimFuenteDatos (
        FuenteID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreFuente VARCHAR(100) NULL,
        Descripcion VARCHAR(255) NULL
    );
END
GO

IF OBJECT_ID('dbo.DimMoneda', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimMoneda (
        MonedaID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreMoneda VARCHAR(50) NULL,
        CodigoMoneda VARCHAR(10) NULL
    );
END
GO

IF OBJECT_ID('dbo.DimProducto', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimProducto (
        ProductoID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreProducto VARCHAR(100) NOT NULL,
        Categoria VARCHAR(50) NULL,
        EsImportado BIT NULL,
        UnidadMedida VARCHAR(20) NULL,
        FactorCanasta DECIMAL(18,2) NULL CONSTRAINT DF_DimProducto_FactorCanasta DEFAULT (1.0),
        PrecioBaseReferencia DECIMAL(18,2) NULL CONSTRAINT DF_DimProducto_PrecioBaseReferencia DEFAULT (1.0)
    );
END
GO

IF OBJECT_ID('dbo.DimRegion', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimRegion (
        RegionID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Provincia VARCHAR(50) NULL,
        Canton VARCHAR(50) NULL,
        Zona VARCHAR(200) NULL
    );
END
GO

IF OBJECT_ID('dbo.DimZonaClimatica', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimZonaClimatica (
        ZonaClimaticaID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreZona NVARCHAR(200) NOT NULL,
        Latitud DECIMAL(9,6) NOT NULL,
        Longitud DECIMAL(9,6) NOT NULL
    );
END
GO

/* ==============================
   HECHOS DEL DW
   ============================== */
IF OBJECT_ID('dbo.FactPreciosCanasta', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactPreciosCanasta (
        FactPrecioID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FechaID INT NOT NULL,
        ProductoID INT NOT NULL,
        RegionID INT NOT NULL,
        MonedaID INT NOT NULL,
        FuenteID INT NOT NULL,
        Precio DECIMAL(18,4) NOT NULL,
        IPC DECIMAL(10,4) NULL,
        CostoCanastaTotal DECIMAL(18,4) NULL,
        CONSTRAINT FK_FactPrecio_Fecha FOREIGN KEY (FechaID) REFERENCES dbo.DimFecha(FechaID),
        CONSTRAINT FK_FactPrecio_Producto FOREIGN KEY (ProductoID) REFERENCES dbo.DimProducto(ProductoID),
        CONSTRAINT FK_FactPrecio_Region FOREIGN KEY (RegionID) REFERENCES dbo.DimRegion(RegionID),
        CONSTRAINT FK_FactPrecio_Moneda FOREIGN KEY (MonedaID) REFERENCES dbo.DimMoneda(MonedaID),
        CONSTRAINT FK_FactPrecio_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.FactTipoCambio', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactTipoCambio (
        FactTipoCambioID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FechaID INT NOT NULL,
        MonedaBaseID INT NOT NULL,
        MonedaReferenciaID INT NOT NULL,
        FuenteID INT NOT NULL,
        TipoCambioCompra DECIMAL(18,4) NOT NULL,
        TipoCambioVenta DECIMAL(18,4) NOT NULL,
        TipoCambioPromedio AS ((TipoCambioCompra + TipoCambioVenta) / 2.0) PERSISTED,
        CONSTRAINT FK_FactTC_Fecha FOREIGN KEY (FechaID) REFERENCES dbo.DimFecha(FechaID),
        CONSTRAINT FK_FactTC_MonedaBase FOREIGN KEY (MonedaBaseID) REFERENCES dbo.DimMoneda(MonedaID),
        CONSTRAINT FK_FactTC_MonedaRef FOREIGN KEY (MonedaReferenciaID) REFERENCES dbo.DimMoneda(MonedaID),
        CONSTRAINT FK_FactTC_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.FactPrecioCombustible', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactPrecioCombustible (
        FactPrecioCombustibleID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FechaID INT NOT NULL,
        ProductoID INT NOT NULL,
        MonedaID INT NOT NULL,
        FuenteID INT NOT NULL,
        Precio DECIMAL(18,4) NOT NULL,
        CONSTRAINT FK_FactPrecioCombustible_Fecha FOREIGN KEY (FechaID) REFERENCES dbo.DimFecha(FechaID),
        CONSTRAINT FK_FactPrecioCombustible_Producto FOREIGN KEY (ProductoID) REFERENCES dbo.DimProducto(ProductoID),
        CONSTRAINT FK_FactPrecioCombustible_Moneda FOREIGN KEY (MonedaID) REFERENCES dbo.DimMoneda(MonedaID),
        CONSTRAINT FK_FactPrecioCombustible_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.FactClimaMensual', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactClimaMensual (
        FactClimaMensualID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FechaID INT NOT NULL,
        ZonaClimaticaID INT NOT NULL,
        FuenteID INT NOT NULL,
        TempMax DECIMAL(18,4) NOT NULL,
        TempMin DECIMAL(18,4) NOT NULL,
        Precipitacion DECIMAL(18,4) NOT NULL,
        Humedad DECIMAL(18,4) NOT NULL,
        RadiacionSolar DECIMAL(18,4) NOT NULL,
        CONSTRAINT FK_FactClimaMensual_Fecha FOREIGN KEY (FechaID) REFERENCES dbo.DimFecha(FechaID),
        CONSTRAINT FK_FactClimaMensual_Zona FOREIGN KEY (ZonaClimaticaID) REFERENCES dbo.DimZonaClimatica(ZonaClimaticaID),
        CONSTRAINT FK_FactClimaMensual_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

/* ==============================
   TABLAS DE STAGING
   ============================== */
IF OBJECT_ID('dbo.StagingFecha', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingFecha (
        FechaID INT NOT NULL,
        Fecha DATE NOT NULL,
        Dia INT NULL,
        Mes INT NULL,
        NombreMes VARCHAR(30) NULL,
        Año INT NULL,
        Trimestre INT NULL
    );
END
GO

IF OBJECT_ID('dbo.StagingHistoricoCanasta', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingHistoricoCanasta (
        Fecha DATE NULL,
        NombreProductoRaw NVARCHAR(255) NULL,
        Provincia NVARCHAR(100) NULL,
        Canton NVARCHAR(100) NULL,
        Distrito NVARCHAR(100) NULL,
        PrecioColones DECIMAL(18,2) NULL,
        FuenteID INT NULL
    );
END
GO

IF OBJECT_ID('dbo.StagingPrecioGasolina', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingPrecioGasolina (
        FechaRaw NVARCHAR(50) NULL,
        NombreProductoRaw NVARCHAR(255) NULL,
        Precio DECIMAL(18,2) NULL,
        FuenteID INT NULL CONSTRAINT DF_StagingPrecioGasolina_Fuente DEFAULT (3)
    );
END
GO

IF OBJECT_ID('dbo.StagingProducto', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingProducto (
        StagingProductoID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreRaw NVARCHAR(255) NULL,
        NombreNormalizado NVARCHAR(255) NULL,
        Categoria NVARCHAR(100) NULL,
        SubCategoria NVARCHAR(100) NULL,
        UnidadMedida NVARCHAR(50) NULL,
        FuenteID INT NULL,
        EsImportado BIT NULL CONSTRAINT DF_StagingProducto_EsImportado DEFAULT (1),
        PrecioBaseReferencia DECIMAL(18,2) NULL,
        FactorCanasta DECIMAL(18,2) NULL
    );
END
GO

IF OBJECT_ID('dbo.StagingTipoCambio', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingTipoCambio (
        StagingID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Fecha DATE NULL,
        FechaID INT NULL,
        MonedaBaseID INT NULL,
        MonedaReferenciaID INT NULL,
        FuenteID INT NULL,
        TipoCambioCompra DECIMAL(18,4) NULL,
        TipoCambioVenta DECIMAL(18,4) NULL,
        TipoCambioPromedio DECIMAL(18,4) NULL,
        FechaCarga DATETIME NULL CONSTRAINT DF_StagingTipoCambio_FechaCarga DEFAULT (GETDATE())
    );
END
GO

IF OBJECT_ID('dbo.StagingZonaClimatica', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingZonaClimatica (
        StagingZonaClimaticaID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreZona NVARCHAR(200) NOT NULL,
        Latitud DECIMAL(9,6) NOT NULL,
        Longitud DECIMAL(9,6) NOT NULL,
        FuenteID INT NULL CONSTRAINT DF_StagingZonaClimatica_Fuente DEFAULT (4)
    );
END
GO

IF OBJECT_ID('dbo.StagingClimaMensual', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingClimaMensual (
        StagingClimaMensualID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Fecha DATE NOT NULL,
        FechaID INT NOT NULL,
        NombreZona NVARCHAR(200) NOT NULL,
        Latitud DECIMAL(9,6) NOT NULL,
        Longitud DECIMAL(9,6) NOT NULL,
        TempMax DECIMAL(18,4) NOT NULL,
        TempMin DECIMAL(18,4) NOT NULL,
        Precipitacion DECIMAL(18,4) NOT NULL,
        Humedad DECIMAL(18,4) NOT NULL,
        RadiacionSolar DECIMAL(18,4) NOT NULL,
        FuenteID INT NULL CONSTRAINT DF_StagingClimaMensual_Fuente DEFAULT (4),
        FechaCarga DATETIME NULL CONSTRAINT DF_StagingClimaMensual_FechaCarga DEFAULT (GETDATE())
    );
END
GO

/* ==============================
   INDICES
   ============================== */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecio_Fecha' AND object_id = OBJECT_ID('dbo.FactPreciosCanasta'))
    CREATE INDEX IX_FactPrecio_Fecha ON dbo.FactPreciosCanasta (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecio_Producto' AND object_id = OBJECT_ID('dbo.FactPreciosCanasta'))
    CREATE INDEX IX_FactPrecio_Producto ON dbo.FactPreciosCanasta (ProductoID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactTC_Fecha' AND object_id = OBJECT_ID('dbo.FactTipoCambio'))
    CREATE INDEX IX_FactTC_Fecha ON dbo.FactTipoCambio (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecioCombustible_Fecha' AND object_id = OBJECT_ID('dbo.FactPrecioCombustible'))
    CREATE INDEX IX_FactPrecioCombustible_Fecha ON dbo.FactPrecioCombustible (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecioCombustible_Producto' AND object_id = OBJECT_ID('dbo.FactPrecioCombustible'))
    CREATE INDEX IX_FactPrecioCombustible_Producto ON dbo.FactPrecioCombustible (ProductoID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactClimaMensual_Fecha' AND object_id = OBJECT_ID('dbo.FactClimaMensual'))
    CREATE INDEX IX_FactClimaMensual_Fecha ON dbo.FactClimaMensual (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactClimaMensual_Zona' AND object_id = OBJECT_ID('dbo.FactClimaMensual'))
    CREATE INDEX IX_FactClimaMensual_Zona ON dbo.FactClimaMensual (ZonaClimaticaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingFecha_FechaID' AND object_id = OBJECT_ID('dbo.StagingFecha'))
    CREATE INDEX IX_StagingFecha_FechaID ON dbo.StagingFecha (FechaID, Fecha);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingTipoCambio_Clave' AND object_id = OBJECT_ID('dbo.StagingTipoCambio'))
    CREATE INDEX IX_StagingTipoCambio_Clave ON dbo.StagingTipoCambio (FechaID, MonedaBaseID, MonedaReferenciaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingProducto_NombreFuente' AND object_id = OBJECT_ID('dbo.StagingProducto'))
    CREATE INDEX IX_StagingProducto_NombreFuente ON dbo.StagingProducto (NombreRaw, FuenteID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingPrecioGasolina_Clave' AND object_id = OBJECT_ID('dbo.StagingPrecioGasolina'))
    CREATE INDEX IX_StagingPrecioGasolina_Clave ON dbo.StagingPrecioGasolina (FechaRaw, NombreProductoRaw);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingHistoricoCanasta_Clave' AND object_id = OBJECT_ID('dbo.StagingHistoricoCanasta'))
    CREATE INDEX IX_StagingHistoricoCanasta_Clave
        ON dbo.StagingHistoricoCanasta (Fecha, NombreProductoRaw, Provincia, Canton, Distrito);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingZonaClimatica_Clave' AND object_id = OBJECT_ID('dbo.StagingZonaClimatica'))
    CREATE INDEX IX_StagingZonaClimatica_Clave
        ON dbo.StagingZonaClimatica (NombreZona, Latitud, Longitud);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingClimaMensual_Clave' AND object_id = OBJECT_ID('dbo.StagingClimaMensual'))
    CREATE INDEX IX_StagingClimaMensual_Clave
        ON dbo.StagingClimaMensual (FechaID, NombreZona, Latitud, Longitud);
GO

/* ==============================
   PROCEDIMIENTOS ALMACENADOS
   ============================== */
DROP PROCEDURE IF EXISTS dbo.sp_InsertarTipoCambioStaging;
GO

CREATE PROCEDURE dbo.sp_InsertarTipoCambioStaging
    @Fecha DATE,
    @Compra DECIMAL(18,4),
    @Venta DECIMAL(18,4),
    @MonedaBaseID INT,
    @MonedaRefID INT,
    @FuenteID INT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        DECLARE @FechaID INT = CAST(FORMAT(@Fecha, 'yyyyMMdd') AS INT);

        IF NOT EXISTS (
            SELECT 1
            FROM dbo.StagingFecha
            WHERE FechaID = @FechaID
        )
        BEGIN
            INSERT INTO dbo.StagingFecha (
                FechaID,
                Fecha,
                Dia,
                Mes,
                NombreMes,
                Trimestre,
                Año
            )
            VALUES (
                @FechaID,
                @Fecha,
                DAY(@Fecha),
                MONTH(@Fecha),
                DATENAME(MONTH, @Fecha),
                DATEPART(QUARTER, @Fecha),
                YEAR(@Fecha)
            );
        END

        IF NOT EXISTS (
            SELECT 1
            FROM dbo.StagingTipoCambio
            WHERE FechaID = @FechaID
        )
        BEGIN
            DECLARE @Promedio DECIMAL(18,4) = (@Compra + @Venta) / 2;

            INSERT INTO dbo.StagingTipoCambio (
                Fecha,
                FechaID,
                MonedaBaseID,
                MonedaReferenciaID,
                FuenteID,
                TipoCambioCompra,
                TipoCambioVenta,
                TipoCambioPromedio
            )
            VALUES (
                @Fecha,
                @FechaID,
                @MonedaBaseID,
                @MonedaRefID,
                @FuenteID,
                @Compra,
                @Venta,
                @Promedio
            );
        END

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Load_FactPreciosCanasta;
GO

CREATE PROCEDURE dbo.sp_Load_FactPreciosCanasta
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @PrecioBaseGlobal DECIMAL(18,2) = 800.00;

    MERGE dbo.FactPreciosCanasta AS Target
    USING (
        SELECT
            f.FechaID,
            p.ProductoID,
            r.RegionID,
            CAST(AVG(s.PrecioColones) AS DECIMAL(18,4)) AS Precio,
            2 AS MonedaID,
            MAX(s.FuenteID) AS FuenteID,
            CAST(AVG(s.PrecioColones * ISNULL(p.FactorCanasta, 1.0)) AS DECIMAL(18,4)) AS CostoCanastaTotal,
            CAST(AVG(ROUND((s.PrecioColones / @PrecioBaseGlobal) * 100, 2)) AS DECIMAL(10,4)) AS IPC
        FROM dbo.StagingHistoricoCanasta s
        INNER JOIN dbo.DimFecha f
            ON s.Fecha = f.Fecha
        INNER JOIN dbo.DimProducto p
            ON TRIM(UPPER(s.NombreProductoRaw)) = p.NombreProducto
        INNER JOIN dbo.DimRegion r
            ON TRIM(UPPER(s.Provincia)) = TRIM(UPPER(r.Provincia))
           AND TRIM(UPPER(s.Canton)) = TRIM(UPPER(r.Canton))
           AND TRIM(UPPER(s.Distrito)) = TRIM(UPPER(r.Zona))
        GROUP BY f.FechaID, p.ProductoID, r.RegionID
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.ProductoID = Source.ProductoID
       AND Target.RegionID = Source.RegionID
    WHEN MATCHED THEN
        UPDATE SET
            Target.Precio = Source.Precio,
            Target.MonedaID = Source.MonedaID,
            Target.FuenteID = Source.FuenteID,
            Target.CostoCanastaTotal = Source.CostoCanastaTotal,
            Target.IPC = Source.IPC
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            FechaID,
            ProductoID,
            RegionID,
            Precio,
            MonedaID,
            FuenteID,
            CostoCanastaTotal,
            IPC
        )
        VALUES (
            Source.FechaID,
            Source.ProductoID,
            Source.RegionID,
            Source.Precio,
            Source.MonedaID,
            Source.FuenteID,
            Source.CostoCanastaTotal,
            Source.IPC
        );

    PRINT 'FactPreciosCanasta cargada con metricas calculadas.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimFecha;
GO

CREATE PROCEDURE dbo.sp_Transform_DimFecha
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.DimFecha (
        FechaID,
        Fecha,
        Dia,
        Mes,
        NombreMes,
        Trimestre,
        Año
    )
    SELECT DISTINCT
        CONVERT(INT, FORMAT(s.Fecha, 'yyyyMMdd')),
        s.Fecha,
        DAY(s.Fecha),
        MONTH(s.Fecha),
        FORMAT(s.Fecha, 'MMMM', 'es-CR'),
        DATEPART(QUARTER, s.Fecha),
        YEAR(s.Fecha)
    FROM dbo.StagingFecha s
    WHERE NOT EXISTS (
        SELECT 1
        FROM dbo.DimFecha d
        WHERE d.Fecha = s.Fecha
    );

    PRINT 'DimFecha actualizada desde StagingFecha.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimProducto;
GO

CREATE PROCEDURE dbo.sp_Transform_DimProducto
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimProducto AS Target
    USING (
        SELECT
            TRIM(UPPER(COALESCE(NULLIF(NombreNormalizado, ''), NombreRaw))) AS NombreProducto,
            MAX(TRIM(Categoria)) AS Categoria,
            MAX(TRIM(UnidadMedida)) AS UnidadMedida,
            CAST(MAX(CAST(ISNULL(EsImportado, 0) AS INT)) AS BIT) AS EsImportado,
            CAST(MAX(ISNULL(PrecioBaseReferencia, 0)) AS DECIMAL(18,2)) AS PrecioBaseReferencia,
            CAST(AVG(ISNULL(FactorCanasta, 1.0)) AS DECIMAL(18,2)) AS FactorCanasta
        FROM dbo.StagingProducto
        WHERE COALESCE(NULLIF(NombreNormalizado, ''), NombreRaw) IS NOT NULL
        GROUP BY TRIM(UPPER(COALESCE(NULLIF(NombreNormalizado, ''), NombreRaw)))
    ) AS Source
        ON Target.NombreProducto = Source.NombreProducto
    WHEN MATCHED THEN
        UPDATE SET
            Target.Categoria = Source.Categoria,
            Target.UnidadMedida = Source.UnidadMedida,
            Target.EsImportado = Source.EsImportado,
            Target.PrecioBaseReferencia = Source.PrecioBaseReferencia,
            Target.FactorCanasta = Source.FactorCanasta,
            Target.NombreProducto = UPPER(Source.NombreProducto)
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            NombreProducto,
            Categoria,
            UnidadMedida,
            EsImportado,
            PrecioBaseReferencia,
            FactorCanasta
        )
        VALUES (
            UPPER(Source.NombreProducto),
            Source.Categoria,
            Source.UnidadMedida,
            Source.EsImportado,
            Source.PrecioBaseReferencia,
            Source.FactorCanasta
        );

    PRINT 'DimProducto sincronizada con parametros de Python.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimRegion;
GO

CREATE PROCEDURE dbo.sp_Transform_DimRegion
AS
BEGIN
    SET NOCOUNT ON;

    WITH SourceRegion AS (
        SELECT
            TRIM(UPPER(s.Provincia)) AS Provincia,
            TRIM(UPPER(s.Canton)) AS Canton,
            TRIM(UPPER(s.Distrito)) AS Zona
        FROM dbo.StagingHistoricoCanasta s
        WHERE s.Provincia IS NOT NULL
          AND s.Canton IS NOT NULL
          AND s.Distrito IS NOT NULL
        GROUP BY
            TRIM(UPPER(s.Provincia)),
            TRIM(UPPER(s.Canton)),
            TRIM(UPPER(s.Distrito))
    )
    INSERT INTO dbo.DimRegion (
        Provincia,
        Canton,
        Zona
    )
    SELECT
        s.Provincia,
        s.Canton,
        s.Zona
    FROM SourceRegion s
    WHERE NOT EXISTS (
        SELECT 1
        FROM dbo.DimRegion d
        WHERE TRIM(UPPER(d.Provincia)) = s.Provincia
          AND TRIM(UPPER(d.Canton)) = s.Canton
          AND TRIM(UPPER(d.Zona)) = s.Zona
    );
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimZonaClimatica;
GO

CREATE PROCEDURE dbo.sp_Transform_DimZonaClimatica
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimZonaClimatica AS Target
    USING (
        SELECT DISTINCT
            TRIM(UPPER(NombreZona)) AS NombreZona,
            CAST(Latitud AS DECIMAL(9,6)) AS Latitud,
            CAST(Longitud AS DECIMAL(9,6)) AS Longitud
        FROM dbo.StagingZonaClimatica
        WHERE NombreZona IS NOT NULL
    ) AS Source
        ON TRIM(UPPER(Target.NombreZona)) = Source.NombreZona
       AND Target.Latitud = Source.Latitud
       AND Target.Longitud = Source.Longitud
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            NombreZona,
            Latitud,
            Longitud
        )
        VALUES (
            Source.NombreZona,
            Source.Latitud,
            Source.Longitud
        );

    PRINT 'DimZonaClimatica sincronizada desde staging.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_FactTipoCambio;
GO

CREATE PROCEDURE dbo.sp_Transform_FactTipoCambio
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.FactTipoCambio AS Target
    USING (
        SELECT
            FechaID AS FechaKey,
            MonedaBaseID,
            MonedaReferenciaID,
            CAST(MAX(TipoCambioCompra) AS DECIMAL(18,4)) AS Compra,
            CAST(MAX(TipoCambioVenta) AS DECIMAL(18,4)) AS Venta,
            MAX(FuenteID) AS FuenteID
        FROM dbo.StagingTipoCambio
        WHERE TipoCambioCompra > 0
          AND TipoCambioVenta > 0
          AND FechaID IS NOT NULL
        GROUP BY FechaID, MonedaBaseID, MonedaReferenciaID
    ) AS Source
        ON Target.FechaID = Source.FechaKey
       AND Target.MonedaBaseID = Source.MonedaBaseID
       AND Target.MonedaReferenciaID = Source.MonedaReferenciaID
    WHEN MATCHED THEN
        UPDATE SET
            Target.TipoCambioCompra = Source.Compra,
            Target.TipoCambioVenta = Source.Venta,
            Target.FuenteID = Source.FuenteID
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            FechaID,
            MonedaBaseID,
            MonedaReferenciaID,
            TipoCambioCompra,
            TipoCambioVenta,
            FuenteID
        )
        VALUES (
            Source.FechaKey,
            Source.MonedaBaseID,
            Source.MonedaReferenciaID,
            Source.Compra,
            Source.Venta,
            Source.FuenteID
        );

    PRINT 'Transformacion completa de StagingTipoCambio a FactTipoCambio.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Load_FactPrecioCombustible;
GO

CREATE PROCEDURE dbo.sp_Load_FactPrecioCombustible
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.FactPrecioCombustible AS Target
    USING (
        SELECT
            f.FechaID,
            p.ProductoID,
            2 AS MonedaID,
            MAX(s.FuenteID) AS FuenteID,
            CAST(MAX(s.Precio) AS DECIMAL(18,4)) AS Precio
        FROM dbo.StagingPrecioGasolina s
        INNER JOIN dbo.DimFecha f
            ON TRY_CONVERT(DATE, LEFT(s.FechaRaw, 10)) = f.Fecha
        INNER JOIN dbo.DimProducto p
            ON TRIM(UPPER(s.NombreProductoRaw)) = p.NombreProducto
        WHERE TRY_CONVERT(DATE, LEFT(s.FechaRaw, 10)) IS NOT NULL
          AND s.Precio > 0
          AND s.NombreProductoRaw IS NOT NULL
        GROUP BY f.FechaID, p.ProductoID
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.ProductoID = Source.ProductoID
    WHEN MATCHED THEN
        UPDATE SET
            Target.MonedaID = Source.MonedaID,
            Target.FuenteID = Source.FuenteID,
            Target.Precio = Source.Precio
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            FechaID,
            ProductoID,
            MonedaID,
            FuenteID,
            Precio
        )
        VALUES (
            Source.FechaID,
            Source.ProductoID,
            Source.MonedaID,
            Source.FuenteID,
            Source.Precio
        );

    PRINT 'FactPrecioCombustible cargada desde staging.';
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Load_FactClimaMensual;
GO

CREATE PROCEDURE dbo.sp_Load_FactClimaMensual
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.FactClimaMensual AS Target
    USING (
        SELECT
            f.FechaID,
            z.ZonaClimaticaID,
            MAX(s.FuenteID) AS FuenteID,
            CAST(MAX(s.TempMax) AS DECIMAL(18,4)) AS TempMax,
            CAST(MAX(s.TempMin) AS DECIMAL(18,4)) AS TempMin,
            CAST(MAX(s.Precipitacion) AS DECIMAL(18,4)) AS Precipitacion,
            CAST(MAX(s.Humedad) AS DECIMAL(18,4)) AS Humedad,
            CAST(MAX(s.RadiacionSolar) AS DECIMAL(18,4)) AS RadiacionSolar
        FROM dbo.StagingClimaMensual s
        INNER JOIN dbo.DimFecha f
            ON s.Fecha = f.Fecha
        INNER JOIN dbo.DimZonaClimatica z
            ON TRIM(UPPER(s.NombreZona)) = TRIM(UPPER(z.NombreZona))
           AND CAST(s.Latitud AS DECIMAL(9,6)) = z.Latitud
           AND CAST(s.Longitud AS DECIMAL(9,6)) = z.Longitud
        WHERE s.TempMax IS NOT NULL
          AND s.TempMin IS NOT NULL
          AND s.Precipitacion IS NOT NULL
          AND s.Humedad IS NOT NULL
          AND s.RadiacionSolar IS NOT NULL
        GROUP BY f.FechaID, z.ZonaClimaticaID
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.ZonaClimaticaID = Source.ZonaClimaticaID
    WHEN MATCHED THEN
        UPDATE SET
            Target.FuenteID = Source.FuenteID,
            Target.TempMax = Source.TempMax,
            Target.TempMin = Source.TempMin,
            Target.Precipitacion = Source.Precipitacion,
            Target.Humedad = Source.Humedad,
            Target.RadiacionSolar = Source.RadiacionSolar
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            FechaID,
            ZonaClimaticaID,
            FuenteID,
            TempMax,
            TempMin,
            Precipitacion,
            Humedad,
            RadiacionSolar
        )
        VALUES (
            Source.FechaID,
            Source.ZonaClimaticaID,
            Source.FuenteID,
            Source.TempMax,
            Source.TempMin,
            Source.Precipitacion,
            Source.Humedad,
            Source.RadiacionSolar
        );

    PRINT 'FactClimaMensual cargada desde staging.';
END
GO

/* Azure SQL Database:
   Ejecutar este script conectado previamente a la base de datos de destino.
   Se omiten USE master, CREATE DATABASE y USE porque no aplican en este entorno. */
GO

/* ==============================
   DIMENSIONES
   ============================== */
IF OBJECT_ID('dbo.DimFecha', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimFecha (
        FechaID INT NOT NULL PRIMARY KEY,
        Fecha DATE NOT NULL,
        Dia INT NULL,
        Mes INT NULL,
        NombreMes VARCHAR(30) NULL,
        Anio INT NULL,
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
        NombreRaw NVARCHAR(255) NOT NULL,
        NombreProducto VARCHAR(100) NOT NULL,
        Categoria VARCHAR(50) NOT NULL,
        SubCategoria NVARCHAR(100) NOT NULL,
        FuenteID INT NOT NULL,
        EsImportado BIT NOT NULL,
        UnidadMedida VARCHAR(20) NOT NULL,
        FactorCanasta DECIMAL(18,2) NOT NULL CONSTRAINT DF_DimProducto_FactorCanasta DEFAULT (1.0),
        PrecioBaseReferencia DECIMAL(18,2) NOT NULL CONSTRAINT DF_DimProducto_PrecioBaseReferencia DEFAULT (1.0),
        CONSTRAINT FK_DimProducto_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.DimZonaClimatica', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimZonaClimatica (
        ZonaClimaticaID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreZona NVARCHAR(200) NOT NULL,
        Latitud DECIMAL(9,6) NOT NULL,
        Longitud DECIMAL(9,6) NOT NULL,
        FuenteID INT NOT NULL,
        CONSTRAINT FK_DimZonaClimatica_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.DimZonaCBA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimZonaCBA (
        ZonaCBAID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreZona NVARCHAR(50) NOT NULL,
        FuenteID INT NOT NULL,
        CONSTRAINT FK_DimZonaCBA_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

IF OBJECT_ID('dbo.DimCategoriaCBA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimCategoriaCBA (
        CategoriaCBAID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NombreCategoria NVARCHAR(255) NOT NULL,
        FuenteID INT NOT NULL,
        CONSTRAINT FK_DimCategoriaCBA_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
    );
END
GO

/* ==============================
   HECHOS
   ============================== */
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

IF OBJECT_ID('dbo.FactCanastaInecOficial', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactCanastaInecOficial (
        CBAOficialKey BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FechaID INT NOT NULL,
        ZonaCBAID INT NOT NULL,
        CategoriaCBAID INT NOT NULL,
        Zona NVARCHAR(50) NOT NULL,
        CategoriaNombre NVARCHAR(255) NOT NULL,
        PeriodoTextoOriginal NVARCHAR(50) NOT NULL,
        FuenteID INT NOT NULL,
        CostoPerCapita DECIMAL(18,4) NOT NULL,
        ArchivoOrigen NVARCHAR(255) NOT NULL,
        FechaCarga DATETIME NOT NULL CONSTRAINT DF_FactCanastaInecOficial_FechaCarga DEFAULT (GETDATE()),
        CONSTRAINT FK_FactCanastaInecOficial_Fecha FOREIGN KEY (FechaID) REFERENCES dbo.DimFecha(FechaID),
        CONSTRAINT FK_FactCanastaInecOficial_Zona FOREIGN KEY (ZonaCBAID) REFERENCES dbo.DimZonaCBA(ZonaCBAID),
        CONSTRAINT FK_FactCanastaInecOficial_Categoria FOREIGN KEY (CategoriaCBAID) REFERENCES dbo.DimCategoriaCBA(CategoriaCBAID),
        CONSTRAINT FK_FactCanastaInecOficial_Fuente FOREIGN KEY (FuenteID) REFERENCES dbo.DimFuenteDatos(FuenteID)
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
   STAGING
   ============================== */
IF OBJECT_ID('dbo.StagingFecha', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingFecha (
        FechaID INT NOT NULL,
        Fecha DATE NOT NULL,
        Dia INT NULL,
        Mes INT NULL,
        NombreMes VARCHAR(30) NULL,
        Anio INT NULL,
        Trimestre INT NULL
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
        EsImportado BIT NULL CONSTRAINT DF_StagingProducto_EsImportado DEFAULT (0),
        PrecioBaseReferencia DECIMAL(18,2) NULL,
        FactorCanasta DECIMAL(18,2) NULL
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

IF OBJECT_ID('dbo.StagingInec', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StagingInec (
        StagingInecID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Fecha DATE NOT NULL,
        FechaID INT NOT NULL,
        Zona NVARCHAR(50) NOT NULL,
        CategoriaNombre NVARCHAR(255) NOT NULL,
        PeriodoTextoOriginal NVARCHAR(50) NOT NULL,
        CostoPerCapita DECIMAL(18,4) NOT NULL,
        ArchivoOrigen NVARCHAR(255) NOT NULL,
        FuenteID INT NOT NULL CONSTRAINT DF_StagingInec_Fuente DEFAULT (5)
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
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactTC_Fecha' AND object_id = OBJECT_ID('dbo.FactTipoCambio'))
    CREATE INDEX IX_FactTC_Fecha ON dbo.FactTipoCambio (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecioCombustible_Fecha' AND object_id = OBJECT_ID('dbo.FactPrecioCombustible'))
    CREATE INDEX IX_FactPrecioCombustible_Fecha ON dbo.FactPrecioCombustible (FechaID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactPrecioCombustible_Producto' AND object_id = OBJECT_ID('dbo.FactPrecioCombustible'))
    CREATE INDEX IX_FactPrecioCombustible_Producto ON dbo.FactPrecioCombustible (ProductoID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactCanastaInecOficial_Clave' AND object_id = OBJECT_ID('dbo.FactCanastaInecOficial'))
    CREATE UNIQUE INDEX IX_FactCanastaInecOficial_Clave
        ON dbo.FactCanastaInecOficial (FechaID, ZonaCBAID, CategoriaCBAID);
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

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingInec_Clave' AND object_id = OBJECT_ID('dbo.StagingInec'))
    CREATE INDEX IX_StagingInec_Clave
        ON dbo.StagingInec (FechaID, Zona, CategoriaNombre);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingZonaClimatica_Clave' AND object_id = OBJECT_ID('dbo.StagingZonaClimatica'))
    CREATE INDEX IX_StagingZonaClimatica_Clave ON dbo.StagingZonaClimatica (NombreZona, Latitud, Longitud);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_StagingClimaMensual_Clave' AND object_id = OBJECT_ID('dbo.StagingClimaMensual'))
    CREATE INDEX IX_StagingClimaMensual_Clave ON dbo.StagingClimaMensual (FechaID, NombreZona, Latitud, Longitud);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DimZonaCBA_Nombre' AND object_id = OBJECT_ID('dbo.DimZonaCBA'))
    CREATE UNIQUE INDEX IX_DimZonaCBA_Nombre ON dbo.DimZonaCBA (NombreZona);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DimCategoriaCBA_Nombre' AND object_id = OBJECT_ID('dbo.DimCategoriaCBA'))
    CREATE UNIQUE INDEX IX_DimCategoriaCBA_Nombre ON dbo.DimCategoriaCBA (NombreCategoria);
GO

/* ==============================
   PROCEDIMIENTOS - ETL DOLAR
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

    DECLARE @FechaID INT = CAST(FORMAT(@Fecha, 'yyyyMMdd') AS INT);

    IF NOT EXISTS (SELECT 1 FROM dbo.StagingFecha WHERE FechaID = @FechaID)
    BEGIN
        INSERT INTO dbo.StagingFecha (FechaID, Fecha, Dia, Mes, NombreMes, Trimestre, Anio)
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

    MERGE dbo.StagingTipoCambio AS Target
    USING (
        SELECT
            @Fecha AS Fecha,
            @FechaID AS FechaID,
            @MonedaBaseID AS MonedaBaseID,
            @MonedaRefID AS MonedaReferenciaID,
            @FuenteID AS FuenteID,
            @Compra AS TipoCambioCompra,
            @Venta AS TipoCambioVenta,
            CAST((@Compra + @Venta) / 2.0 AS DECIMAL(18,4)) AS TipoCambioPromedio
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.MonedaBaseID = Source.MonedaBaseID
       AND Target.MonedaReferenciaID = Source.MonedaReferenciaID
    WHEN MATCHED THEN
        UPDATE SET
            Target.Fecha = Source.Fecha,
            Target.FuenteID = Source.FuenteID,
            Target.TipoCambioCompra = Source.TipoCambioCompra,
            Target.TipoCambioVenta = Source.TipoCambioVenta,
            Target.TipoCambioPromedio = Source.TipoCambioPromedio
    WHEN NOT MATCHED THEN
        INSERT (
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
            Source.Fecha,
            Source.FechaID,
            Source.MonedaBaseID,
            Source.MonedaReferenciaID,
            Source.FuenteID,
            Source.TipoCambioCompra,
            Source.TipoCambioVenta,
            Source.TipoCambioPromedio
        );
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
            FechaID,
            MonedaBaseID,
            MonedaReferenciaID,
            FuenteID,
            TipoCambioCompra,
            TipoCambioVenta
        FROM dbo.StagingTipoCambio
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.MonedaBaseID = Source.MonedaBaseID
       AND Target.MonedaReferenciaID = Source.MonedaReferenciaID
    WHEN MATCHED THEN
        UPDATE SET
            Target.FuenteID = Source.FuenteID,
            Target.TipoCambioCompra = Source.TipoCambioCompra,
            Target.TipoCambioVenta = Source.TipoCambioVenta
    WHEN NOT MATCHED THEN
        INSERT (
            FechaID,
            MonedaBaseID,
            MonedaReferenciaID,
            FuenteID,
            TipoCambioCompra,
            TipoCambioVenta
        )
        VALUES (
            Source.FechaID,
            Source.MonedaBaseID,
            Source.MonedaReferenciaID,
            Source.FuenteID,
            Source.TipoCambioCompra,
            Source.TipoCambioVenta
        );
END
GO

/* ==============================
   PROCEDIMIENTOS - DIMENSIONES
   ============================== */
DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimFecha;
GO

CREATE PROCEDURE dbo.sp_Transform_DimFecha
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimFecha AS Target
    USING (
        SELECT DISTINCT FechaID, Fecha, Dia, Mes, NombreMes, Anio, Trimestre
        FROM dbo.StagingFecha
    ) AS Source
        ON Target.FechaID = Source.FechaID
    WHEN MATCHED THEN
        UPDATE SET
            Target.Fecha = Source.Fecha,
            Target.Dia = Source.Dia,
            Target.Mes = Source.Mes,
            Target.NombreMes = Source.NombreMes,
            Target.Anio = Source.Anio,
            Target.Trimestre = Source.Trimestre
    WHEN NOT MATCHED THEN
        INSERT (FechaID, Fecha, Dia, Mes, NombreMes, Anio, Trimestre)
        VALUES (Source.FechaID, Source.Fecha, Source.Dia, Source.Mes, Source.NombreMes, Source.Anio, Source.Trimestre);
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
            MAX(NombreRaw) AS NombreRaw,
            TRIM(UPPER(NombreNormalizado)) AS NombreProducto,
            MAX(Categoria) AS Categoria,
            MAX(SubCategoria) AS SubCategoria,
            MAX(FuenteID) AS FuenteID,
            CAST(MAX(CAST(EsImportado AS INT)) AS BIT) AS EsImportado,
            MAX(UnidadMedida) AS UnidadMedida,
            MAX(FactorCanasta) AS FactorCanasta,
            MAX(PrecioBaseReferencia) AS PrecioBaseReferencia
        FROM dbo.StagingProducto
        GROUP BY TRIM(UPPER(NombreNormalizado))
    ) AS Source
        ON TRIM(UPPER(Target.NombreProducto)) = Source.NombreProducto
    WHEN MATCHED THEN
        UPDATE SET
            Target.NombreRaw = Source.NombreRaw,
            Target.Categoria = Source.Categoria,
            Target.SubCategoria = Source.SubCategoria,
            Target.FuenteID = Source.FuenteID,
            Target.EsImportado = Source.EsImportado,
            Target.UnidadMedida = Source.UnidadMedida,
            Target.FactorCanasta = Source.FactorCanasta,
            Target.PrecioBaseReferencia = Source.PrecioBaseReferencia
    WHEN NOT MATCHED THEN
        INSERT (
            NombreRaw,
            NombreProducto,
            Categoria,
            SubCategoria,
            FuenteID,
            EsImportado,
            UnidadMedida,
            FactorCanasta,
            PrecioBaseReferencia
        )
        VALUES (
            Source.NombreRaw,
            Source.NombreProducto,
            Source.Categoria,
            Source.SubCategoria,
            Source.FuenteID,
            Source.EsImportado,
            Source.UnidadMedida,
            Source.FactorCanasta,
            Source.PrecioBaseReferencia
        );
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimZonaCBA;
GO

CREATE PROCEDURE dbo.sp_Transform_DimZonaCBA
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimZonaCBA AS Target
    USING (
        SELECT DISTINCT
            TRIM(UPPER(Zona)) AS NombreZona,
            FuenteID
        FROM dbo.StagingInec
    ) AS Source
        ON TRIM(UPPER(Target.NombreZona)) = Source.NombreZona
    WHEN MATCHED THEN
        UPDATE SET
            Target.FuenteID = Source.FuenteID
    WHEN NOT MATCHED THEN
        INSERT (NombreZona, FuenteID)
        VALUES (Source.NombreZona, Source.FuenteID);
END
GO

DROP PROCEDURE IF EXISTS dbo.sp_Transform_DimCategoriaCBA;
GO

CREATE PROCEDURE dbo.sp_Transform_DimCategoriaCBA
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimCategoriaCBA AS Target
    USING (
        SELECT DISTINCT
            TRIM(UPPER(CategoriaNombre)) AS NombreCategoria,
            FuenteID
        FROM dbo.StagingInec
    ) AS Source
        ON TRIM(UPPER(Target.NombreCategoria)) = Source.NombreCategoria
    WHEN MATCHED THEN
        UPDATE SET
            Target.FuenteID = Source.FuenteID
    WHEN NOT MATCHED THEN
        INSERT (NombreCategoria, FuenteID)
        VALUES (Source.NombreCategoria, Source.FuenteID);
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
            Latitud,
            Longitud,
            FuenteID
        FROM dbo.StagingZonaClimatica
    ) AS Source
        ON TRIM(UPPER(Target.NombreZona)) = Source.NombreZona
       AND Target.Latitud = Source.Latitud
       AND Target.Longitud = Source.Longitud
    WHEN MATCHED THEN
        UPDATE SET
            Target.FuenteID = Source.FuenteID
    WHEN NOT MATCHED THEN
        INSERT (NombreZona, Latitud, Longitud, FuenteID)
        VALUES (Source.NombreZona, Source.Latitud, Source.Longitud, Source.FuenteID);
END
GO

/* ==============================
   PROCEDIMIENTOS - ETL COMBUSTIBLE
   ============================== */
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
            CAST(AVG(s.Precio) AS DECIMAL(18,4)) AS Precio
        FROM dbo.StagingPrecioGasolina s
        INNER JOIN dbo.DimFecha f
            ON CONVERT(DATE, LEFT(s.FechaRaw, 10)) = f.Fecha
        INNER JOIN dbo.DimProducto p
            ON TRIM(UPPER(s.NombreProductoRaw)) = TRIM(UPPER(p.NombreProducto))
        GROUP BY f.FechaID, p.ProductoID
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.ProductoID = Source.ProductoID
    WHEN MATCHED THEN
        UPDATE SET
            Target.MonedaID = Source.MonedaID,
            Target.FuenteID = Source.FuenteID,
            Target.Precio = Source.Precio
    WHEN NOT MATCHED THEN
        INSERT (FechaID, ProductoID, MonedaID, FuenteID, Precio)
        VALUES (Source.FechaID, Source.ProductoID, Source.MonedaID, Source.FuenteID, Source.Precio);
END
GO

/* ==============================
   PROCEDIMIENTOS - ETL CBA OFICIAL
   ============================== */
DROP PROCEDURE IF EXISTS dbo.sp_Load_FactCanastaInecOficial;
GO

CREATE PROCEDURE dbo.sp_Load_FactCanastaInecOficial
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.FactCanastaInecOficial AS Target
    USING (
        SELECT
            s.FechaID,
            z.ZonaCBAID,
            c.CategoriaCBAID,
            TRIM(UPPER(s.Zona)) AS Zona,
            TRIM(UPPER(s.CategoriaNombre)) AS CategoriaNombre,
            s.PeriodoTextoOriginal,
            s.FuenteID,
            s.CostoPerCapita,
            s.ArchivoOrigen
        FROM dbo.StagingInec s
        INNER JOIN dbo.DimZonaCBA z
            ON TRIM(UPPER(s.Zona)) = TRIM(UPPER(z.NombreZona))
        INNER JOIN dbo.DimCategoriaCBA c
            ON TRIM(UPPER(s.CategoriaNombre)) = TRIM(UPPER(c.NombreCategoria))
    ) AS Source
        ON Target.FechaID = Source.FechaID
       AND Target.ZonaCBAID = Source.ZonaCBAID
       AND Target.CategoriaCBAID = Source.CategoriaCBAID
    WHEN MATCHED THEN
        UPDATE SET
            Target.Zona = Source.Zona,
            Target.CategoriaNombre = Source.CategoriaNombre,
            Target.PeriodoTextoOriginal = Source.PeriodoTextoOriginal,
            Target.FuenteID = Source.FuenteID,
            Target.CostoPerCapita = Source.CostoPerCapita,
            Target.ArchivoOrigen = Source.ArchivoOrigen,
            Target.FechaCarga = GETDATE()
    WHEN NOT MATCHED THEN
        INSERT (
            FechaID,
            ZonaCBAID,
            CategoriaCBAID,
            Zona,
            CategoriaNombre,
            PeriodoTextoOriginal,
            FuenteID,
            CostoPerCapita,
            ArchivoOrigen
        )
        VALUES (
            Source.FechaID,
            Source.ZonaCBAID,
            Source.CategoriaCBAID,
            Source.Zona,
            Source.CategoriaNombre,
            Source.PeriodoTextoOriginal,
            Source.FuenteID,
            Source.CostoPerCapita,
            Source.ArchivoOrigen
        );
END
GO

/* ==============================
   PROCEDIMIENTOS - ETL CLIMA
   ============================== */
DROP PROCEDURE IF EXISTS dbo.sp_Load_FactClimaMensual;
GO

CREATE PROCEDURE dbo.sp_Load_FactClimaMensual
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.FactClimaMensual AS Target
    USING (
        SELECT
            s.FechaID,
            z.ZonaClimaticaID,
            MAX(s.FuenteID) AS FuenteID,
            MAX(s.TempMax) AS TempMax,
            MAX(s.TempMin) AS TempMin,
            MAX(s.Precipitacion) AS Precipitacion,
            MAX(s.Humedad) AS Humedad,
            MAX(s.RadiacionSolar) AS RadiacionSolar
        FROM dbo.StagingClimaMensual s
        INNER JOIN dbo.DimZonaClimatica z
            ON TRIM(UPPER(s.NombreZona)) = TRIM(UPPER(z.NombreZona))
           AND s.Latitud = z.Latitud
           AND s.Longitud = z.Longitud
        GROUP BY s.FechaID, z.ZonaClimaticaID
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
    WHEN NOT MATCHED THEN
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
END
GO

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
   TABLAS DE DIMENSIONES
   ============================== */
CREATE TABLE dbo.DimFecha (
    FechaID INT NOT NULL PRIMARY KEY,
    Fecha DATE NOT NULL,
    Dia INT NULL,
    Mes INT NULL,
    NombreMes VARCHAR(30) NULL,
    Año INT NULL,
    Trimestre INT NULL
);
GO

CREATE TABLE dbo.DimFuenteDatos (
    FuenteID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    NombreFuente VARCHAR(100) NULL,
    Descripcion VARCHAR(255) NULL
);
GO

CREATE TABLE dbo.DimMoneda (
    MonedaID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    NombreMoneda VARCHAR(50) NULL,
    CodigoMoneda VARCHAR(10) NULL
);
GO

CREATE TABLE dbo.DimProducto (
    ProductoID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    NombreProducto VARCHAR(100) NOT NULL,
    Categoria VARCHAR(50) NULL,
    EsImportado BIT NULL,
    UnidadMedida VARCHAR(20) NULL,
    FactorCanasta DECIMAL(18,2) NULL CONSTRAINT DF_DimProducto_FactorCanasta DEFAULT (1.0),
    PrecioBaseReferencia DECIMAL(18,2) NULL CONSTRAINT DF_DimProducto_PrecioBaseReferencia DEFAULT (1.0)
);
GO

CREATE TABLE dbo.DimRegion (
    RegionID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    Provincia VARCHAR(50) NULL,
    Canton VARCHAR(50) NULL,
    Zona VARCHAR(200) NULL
);
GO

/* ==============================
   TABLAS DE HECHOS
   ============================== */
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
GO

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
GO

/* ==============================
   TABLAS DE STAGING
   ============================== */
CREATE TABLE dbo.StagingFecha (
    FechaID INT NOT NULL,
    Fecha DATE NOT NULL,
    Dia INT NULL,
    Mes INT NULL,
    NombreMes VARCHAR(30) NULL,
    Año INT NULL,
    Trimestre INT NULL
);
GO

CREATE TABLE dbo.StagingHistoricoCanasta (
    Fecha DATE NULL,
    NombreProductoRaw NVARCHAR(255) NULL,
    Provincia NVARCHAR(100) NULL,
    Canton NVARCHAR(100) NULL,
    Distrito NVARCHAR(100) NULL,
    PrecioColones DECIMAL(18,2) NULL,
    FuenteID INT NULL
);
GO

CREATE TABLE dbo.StagingPrecioGasolina (
    FechaRaw NVARCHAR(50) NULL,
    NombreProductoRaw NVARCHAR(255) NULL,
    Precio DECIMAL(18,2) NULL,
    FuenteID INT NULL CONSTRAINT DF_StagingPrecioGasolina_Fuente DEFAULT (3)
);
GO

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
GO

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
GO

/* ==============================
   INDICES
   ============================== */
CREATE INDEX IX_FactPrecio_Fecha ON dbo.FactPreciosCanasta (FechaID);
GO

CREATE INDEX IX_FactPrecio_Producto ON dbo.FactPreciosCanasta (ProductoID);
GO

CREATE INDEX IX_FactTC_Fecha ON dbo.FactTipoCambio (FechaID);
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
        SELECT DISTINCT
            f.FechaID,
            p.ProductoID,
            r.RegionID,
            s.PrecioColones AS Precio,
            2 AS MonedaID,
            s.FuenteID,
            s.PrecioColones * ISNULL(p.FactorCanasta, 1.0) AS CostoCanastaTotal,
            ROUND((s.PrecioColones / @PrecioBaseGlobal) * 100, 2) AS IPC
        FROM dbo.StagingHistoricoCanasta s
        INNER JOIN dbo.DimFecha f
            ON s.Fecha = f.Fecha
        INNER JOIN dbo.DimProducto p
            ON TRIM(UPPER(s.NombreProductoRaw)) = p.NombreProducto
        INNER JOIN dbo.DimRegion r
            ON TRIM(UPPER(s.Provincia)) = TRIM(UPPER(r.Provincia))
           AND TRIM(UPPER(s.Canton)) = TRIM(UPPER(r.Canton))
           AND TRIM(UPPER(s.Distrito)) = TRIM(UPPER(r.Zona))
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
    SELECT
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
        SELECT DISTINCT
            TRIM(UPPER(NombreRaw)) AS NombreProducto,
            TRIM(Categoria) AS Categoria,
            TRIM(UnidadMedida) AS UnidadMedida,
            CAST(EsImportado AS BIT) AS EsImportado,
            CAST(ISNULL(PrecioBaseReferencia, 0) AS DECIMAL(18,2)) AS PrecioBaseReferencia,
            CAST(ISNULL(FactorCanasta, 1.0) AS DECIMAL(18,2)) AS FactorCanasta
        FROM dbo.StagingProducto
        WHERE NombreRaw IS NOT NULL
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
    MERGE dbo.DimRegion AS Target
    USING (
        SELECT DISTINCT
            TRIM(UPPER(s.Provincia)) AS Provincia,
            TRIM(UPPER(s.Canton)) AS Canton,
            TRIM(UPPER(s.Distrito)) AS Zona
        FROM dbo.StagingHistoricoCanasta s
        WHERE s.Provincia IS NOT NULL
          AND s.Canton IS NOT NULL
          AND s.Distrito IS NOT NULL
    ) AS Source
        ON TRIM(UPPER(Target.Provincia)) = Source.Provincia
       AND TRIM(UPPER(Target.Canton)) = Source.Canton
       AND TRIM(UPPER(Target.Zona)) = Source.Zona
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (
            Provincia,
            Canton,
            Zona
        )
        VALUES (
            Source.Provincia,
            Source.Canton,
            Source.Zona
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
            CAST(FORMAT(Fecha, 'yyyyMMdd') AS INT) AS FechaKey,
            MonedaBaseID,
            MonedaReferenciaID,
            CAST(TipoCambioCompra AS DECIMAL(18,4)) AS Compra,
            CAST(TipoCambioVenta AS DECIMAL(18,4)) AS Venta,
            FuenteID
        FROM dbo.StagingTipoCambio
        WHERE TipoCambioCompra > 0
          AND TipoCambioVenta > 0
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

/*
Archivo: vistas_metricas_modelo_cba_limpias.sql
Descripcion:
- Vistas limpias para monitoreo mensual de CBA.
- Vistas simples para entrenar un modelo que reciba variables y prediga
  el CBA mensual por zona.
Motor: SQL Server
Notas:
   - Se trabaja solo con RURAL, URBANO y NACIONAL.
- Se evita arrastrar nulos usando solo meses con cobertura completa.
- La vista final de entrenamiento deja solo variables simples y utiles.
*/

USE DW_Dolar_Canasta;
GO

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

/* =====================================================================
   VISTA: TARGET MENSUAL POR ZONA
   NOMBRE: dbo.vw_CBA_TargetMensual_Zona_Limpia
   PROPOSITO:
   - Definir la variable objetivo del modelo.
   - Dejar una fila por mes y zona.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_TargetMensual_Zona_Limpia
AS
WITH target_total AS (
    SELECT
        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
        f.Anio,
        f.Mes,
        f.Trimestre,
        c.ZonaCBAID,
        UPPER(LTRIM(RTRIM(z.NombreZona))) AS NombreZona,
        c.CostoPerCapita AS CBA_TotalMensual
    FROM dbo.FactCanastaInecOficial c
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = c.FechaID
    INNER JOIN dbo.DimZonaCBA z
        ON z.ZonaCBAID = c.ZonaCBAID
    INNER JOIN dbo.DimCategoriaCBA dc
        ON dc.CategoriaCBAID = c.CategoriaCBAID
    WHERE UPPER(LTRIM(RTRIM(z.NombreZona))) IN ('RURAL', 'URBANO', 'NACIONAL')
      AND TRIM(UPPER(dc.NombreCategoria)) = 'CBA'
),
categorias AS (
    SELECT
        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
        c.ZonaCBAID,
        COUNT(DISTINCT c.CategoriaCBAID) - 1 AS CantidadCategorias
    FROM dbo.FactCanastaInecOficial c
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = c.FechaID
    INNER JOIN dbo.DimZonaCBA z
        ON z.ZonaCBAID = c.ZonaCBAID
    WHERE UPPER(LTRIM(RTRIM(z.NombreZona))) IN ('RURAL', 'URBANO', 'NACIONAL')
    GROUP BY
        DATEFROMPARTS(f.Anio, f.Mes, 1),
        c.ZonaCBAID
)
SELECT
    t.FechaMes,
    t.Anio,
    t.Mes,
    t.Trimestre,
    t.ZonaCBAID,
    t.NombreZona,
    t.CBA_TotalMensual,
    c.CantidadCategorias
FROM target_total t
INNER JOIN categorias c
    ON c.FechaMes = t.FechaMes
   AND c.ZonaCBAID = t.ZonaCBAID;
GO

/* =====================================================================
   VISTA: COBERTURA DE FUENTES
   NOMBRE: dbo.vw_CBA_CoberturaFuentesMensual
   PROPOSITO:
   - Detectar meses completos para modelo.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_CoberturaFuentesMensual
AS
WITH meses_cba AS (
    SELECT DISTINCT DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes
    FROM dbo.FactCanastaInecOficial c
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = c.FechaID
),
meses_tc AS (
    SELECT DISTINCT DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes
    FROM dbo.FactTipoCambio tc
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = tc.FechaID
),
meses_comb AS (
    SELECT DISTINCT DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes
    FROM dbo.FactPrecioCombustible pc
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = pc.FechaID
),
meses_clima AS (
    SELECT DISTINCT DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes
    FROM dbo.FactClimaMensual cm
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = cm.FechaID
),
universo AS (
    SELECT FechaMes FROM meses_cba
    UNION
    SELECT FechaMes FROM meses_tc
    UNION
    SELECT FechaMes FROM meses_comb
    UNION
    SELECT FechaMes FROM meses_clima
)
SELECT
    u.FechaMes,
    CASE WHEN cba.FechaMes IS NULL THEN 0 ELSE 1 END AS TieneCBA,
    CASE WHEN tc.FechaMes IS NULL THEN 0 ELSE 1 END AS TieneTipoCambio,
    CASE WHEN comb.FechaMes IS NULL THEN 0 ELSE 1 END AS TieneCombustible,
    CASE WHEN clima.FechaMes IS NULL THEN 0 ELSE 1 END AS TieneClima,
    CASE
        WHEN cba.FechaMes IS NOT NULL
         AND tc.FechaMes IS NOT NULL
         AND comb.FechaMes IS NOT NULL
         AND clima.FechaMes IS NOT NULL THEN 1
        ELSE 0
    END AS MesCompletoParaModelo
FROM universo u
LEFT JOIN meses_cba cba
    ON cba.FechaMes = u.FechaMes
LEFT JOIN meses_tc tc
    ON tc.FechaMes = u.FechaMes
LEFT JOIN meses_comb comb
    ON comb.FechaMes = u.FechaMes
LEFT JOIN meses_clima clima
    ON clima.FechaMes = u.FechaMes;
GO

/* =====================================================================
   VISTA: EXOGENAS LIMPIAS PARA MODELO
   NOMBRE: dbo.vw_CBA_ExogenasMensuales_Limpias
   PROPOSITO:
   - Dejar solo variables mensuales simples y sin nulos.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_ExogenasMensuales_Limpias
AS
WITH tc AS (
    SELECT
        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
        AVG(CAST(tc.TipoCambioPromedio AS DECIMAL(18,6))) AS TipoCambioPromedioMensual
    FROM dbo.FactTipoCambio tc
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = tc.FechaID
    GROUP BY DATEFROMPARTS(f.Anio, f.Mes, 1)
),
comb AS (
    SELECT
        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
        AVG(CAST(pc.Precio AS DECIMAL(18,6))) AS PrecioCombustiblePromedioMensual
    FROM dbo.FactPrecioCombustible pc
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = pc.FechaID
    GROUP BY DATEFROMPARTS(f.Anio, f.Mes, 1)
),
clima AS (
    SELECT
        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
        AVG(CAST(cm.TempMax AS DECIMAL(18,6))) AS TempMaxProm,
        AVG(CAST(cm.TempMin AS DECIMAL(18,6))) AS TempMinProm,
        AVG(CAST(cm.Precipitacion AS DECIMAL(18,6))) AS PrecipitacionProm,
        AVG(CAST(cm.Humedad AS DECIMAL(18,6))) AS HumedadProm,
        AVG(CAST(cm.RadiacionSolar AS DECIMAL(18,6))) AS RadiacionSolarProm
    FROM dbo.FactClimaMensual cm
    INNER JOIN dbo.DimFecha f
        ON f.FechaID = cm.FechaID
    GROUP BY DATEFROMPARTS(f.Anio, f.Mes, 1)
)
SELECT
    tc.FechaMes,
    tc.TipoCambioPromedioMensual,
    comb.PrecioCombustiblePromedioMensual,
    clima.TempMaxProm,
    clima.TempMinProm,
    clima.PrecipitacionProm,
    clima.HumedadProm,
    clima.RadiacionSolarProm
FROM tc
INNER JOIN comb
    ON comb.FechaMes = tc.FechaMes
INNER JOIN clima
    ON clima.FechaMes = tc.FechaMes;
GO

/* =====================================================================
   VISTA: BASE LIMPIA SIMPLE
   NOMBRE: dbo.vw_CBA_ModeloSimple_Base
   PROPOSITO:
   - Unir target y exogenas limpias.
   - Preparar la base para training y scoring.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_ModeloSimple_Base
AS
SELECT
    t.FechaMes,
    t.Anio,
    t.Mes,
    t.Trimestre,
    t.ZonaCBAID,
    t.NombreZona,
    t.CBA_TotalMensual,
    t.CantidadCategorias,
    e.TipoCambioPromedioMensual,
    e.PrecioCombustiblePromedioMensual,
    e.TempMaxProm,
    e.TempMinProm,
    e.PrecipitacionProm,
    e.HumedadProm,
    e.RadiacionSolarProm,
    CASE WHEN t.Mes = 12 THEN 1 ELSE 0 END AS FlagFinAnio
FROM dbo.vw_CBA_TargetMensual_Zona_Limpia t
INNER JOIN dbo.vw_CBA_ExogenasMensuales_Limpias e
    ON e.FechaMes = t.FechaMes;
GO

/* =====================================================================
   VISTA: DATASET SIMPLE DE ENTRENAMIENTO
   NOMBRE: dbo.vw_CBA_ModeloSimple_Entrenamiento
   PROPOSITO:
   - Entregar un dataset limpio para un modelo simple.
   - Usa solo target, zona, calendario, exogenas y lags basicos.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_ModeloSimple_Entrenamiento
AS
WITH base AS (
    SELECT
        b.*,
        LAG(b.CBA_TotalMensual, 1) OVER (
            PARTITION BY b.ZonaCBAID
            ORDER BY b.FechaMes
        ) AS lag_1,
        LAG(b.CBA_TotalMensual, 3) OVER (
            PARTITION BY b.ZonaCBAID
            ORDER BY b.FechaMes
        ) AS lag_3
    FROM dbo.vw_CBA_ModeloSimple_Base b
)
SELECT
    FechaMes,
    Anio,
    Mes,
    Trimestre,
    ZonaCBAID,
    NombreZona,
    CBA_TotalMensual,
    CantidadCategorias,
    lag_1,
    lag_3,
    TipoCambioPromedioMensual,
    PrecioCombustiblePromedioMensual,
    TempMaxProm,
    TempMinProm,
    PrecipitacionProm,
    HumedadProm,
    RadiacionSolarProm,
    FlagFinAnio
FROM base
WHERE lag_1 IS NOT NULL
  AND lag_3 IS NOT NULL;
GO

/* =====================================================================
   VISTA: EXOGENAS PROYECTADAS A 12 MESES
   NOMBRE: dbo.vw_CBA_ExogenasMensuales_Proyectadas12M
   PROPOSITO:
   - Generar exogenas futuras simples usando el patron promedio por mes.
   - Servir de entrada para el forecast de los proximos 12 meses.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_ExogenasMensuales_Proyectadas12M
AS
WITH FechaObjetivo AS (
    SELECT DATEFROMPARTS(YEAR(GETDATE()) + 1, MONTH(GETDATE()), 1) AS FechaInicioForecast
),
N AS (
    SELECT 1 AS n
    UNION ALL SELECT 2
    UNION ALL SELECT 3
    UNION ALL SELECT 4
    UNION ALL SELECT 5
    UNION ALL SELECT 6
    UNION ALL SELECT 7
    UNION ALL SELECT 8
    UNION ALL SELECT 9
    UNION ALL SELECT 10
    UNION ALL SELECT 11
    UNION ALL SELECT 12
),
PatronMensual AS (
    SELECT
        MONTH(FechaMes) AS Mes,
        AVG(TipoCambioPromedioMensual) AS TipoCambioPromedioMensual,
        AVG(PrecioCombustiblePromedioMensual) AS PrecioCombustiblePromedioMensual,
        AVG(TempMaxProm) AS TempMaxProm,
        AVG(TempMinProm) AS TempMinProm,
        AVG(PrecipitacionProm) AS PrecipitacionProm,
        AVG(HumedadProm) AS HumedadProm,
        AVG(RadiacionSolarProm) AS RadiacionSolarProm
    FROM dbo.vw_CBA_ExogenasMensuales_Limpias
    GROUP BY MONTH(FechaMes)
)
SELECT
    DATEADD(MONTH, n.n - 1, f.FechaInicioForecast) AS FechaMes,
    YEAR(DATEADD(MONTH, n.n - 1, f.FechaInicioForecast)) AS Anio,
    MONTH(DATEADD(MONTH, n.n - 1, f.FechaInicioForecast)) AS Mes,
    DATEPART(QUARTER, DATEADD(MONTH, n.n - 1, f.FechaInicioForecast)) AS Trimestre,
    p.TipoCambioPromedioMensual,
    p.PrecioCombustiblePromedioMensual,
    p.TempMaxProm,
    p.TempMinProm,
    p.PrecipitacionProm,
    p.HumedadProm,
    p.RadiacionSolarProm,
    CASE
        WHEN MONTH(DATEADD(MONTH, n.n - 1, f.FechaInicioForecast)) = 12 THEN 1
        ELSE 0
    END AS FlagFinAnio
FROM FechaObjetivo f
CROSS JOIN N n
INNER JOIN PatronMensual p
    ON p.Mes = MONTH(DATEADD(MONTH, n.n - 1, f.FechaInicioForecast));
GO

/* =====================================================================
   VISTA: ENTRADA SIMPLE PARA PREDICCION
   NOMBRE: dbo.vw_CBA_ModeloSimple_Prediccion
   PROPOSITO:
   - Exponer las variables de entrada para forecast a 12 meses por zona.
   - Sirve para alimentar un modelo ya entrenado.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_CBA_ModeloSimple_Prediccion
AS
WITH ultima_base AS (
    SELECT
        b.ZonaCBAID,
        b.NombreZona,
        b.CantidadCategorias,
        ROW_NUMBER() OVER (
            PARTITION BY b.ZonaCBAID
            ORDER BY b.FechaMes DESC
        ) AS rn
    FROM dbo.vw_CBA_ModeloSimple_Base b
),
zonas AS (
    SELECT
        ZonaCBAID,
        NombreZona,
        CantidadCategorias
    FROM ultima_base
    WHERE rn = 1
)
SELECT
    e.FechaMes,
    e.Anio,
    e.Mes,
    e.Trimestre,
    z.ZonaCBAID,
    z.NombreZona,
    z.CantidadCategorias,
    e.TipoCambioPromedioMensual,
    e.PrecioCombustiblePromedioMensual,
    e.TempMaxProm,
    e.TempMinProm,
    e.PrecipitacionProm,
    e.HumedadProm,
    e.RadiacionSolarProm,
    e.FlagFinAnio
FROM dbo.vw_CBA_ExogenasMensuales_Proyectadas12M e
CROSS JOIN zonas z;
GO

/* =====================================================================
   CONSULTAS DE REFERENCIA
   ===================================================================== */
-- SELECT * FROM dbo.vw_CBA_TargetMensual_Zona_Limpia ORDER BY FechaMes, ZonaCBAID;
-- SELECT * FROM dbo.vw_CBA_CoberturaFuentesMensual ORDER BY FechaMes;
-- SELECT * FROM dbo.vw_CBA_ExogenasMensuales_Limpias ORDER BY FechaMes;
-- SELECT * FROM dbo.vw_CBA_ExogenasMensuales_Proyectadas12M ORDER BY FechaMes;
-- SELECT * FROM dbo.vw_CBA_ModeloSimple_Base ORDER BY FechaMes, ZonaCBAID;
-- SELECT * FROM dbo.vw_CBA_ModeloSimple_Entrenamiento ORDER BY ZonaCBAID, FechaMes;
-- SELECT * FROM dbo.vw_CBA_ModeloSimple_Prediccion ORDER BY ZonaCBAID, FechaMes;

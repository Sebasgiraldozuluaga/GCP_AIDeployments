-- ============================================================
-- Query: Inventario Actual Consolidado (Por Proyecto, Grupo y Producto)
-- ============================================================
-- Este query genera una tabla consolidada mostrando:
-- - Proyecto (Nombre)
-- - Grupo
-- - Producto estandarizado
-- - Inventario Neto (cantidad actual)
-- - Mediana del precio_unitario
-- - Total Inventario Neto (Inventario Neto * Mediana precio)
-- ============================================================

WITH 
-- 1. Mediana de precios por producto estandarizado
precios_mediana AS (
    SELECT 
        fd.producto_estandarizado,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fd.precio_unitario) AS precio_mediana
    FROM factura_detalle fd
    INNER JOIN factura f ON fd.factura_id = f.factura_id
    WHERE fd.producto_estandarizado IS NOT NULL
      AND fd.producto_estandarizado != ''
      AND fd.precio_unitario IS NOT NULL
      AND fd.precio_unitario > 0
      AND fd.cantidad > 0
    GROUP BY fd.producto_estandarizado
),

-- 2. Fecha mínima del inventario base
fecha_minima_inventario AS (
    SELECT MIN(created_at) AS min_inv_date
    FROM inventario
    WHERE created_at IS NOT NULL
),

-- 3. Catálogo para obtener grupos de productos
catalogo AS (
    SELECT DISTINCT ON (descripcion)
        descripcion,
        grupo
    FROM (
        SELECT descripcion, grupo FROM inventario
        UNION ALL
        SELECT descripcion, grupo FROM catalogo_maestro
    ) s
    WHERE grupo IS NOT NULL
),

-- 4. Inventario base por proyecto y producto
inventario_base AS (
    SELECT 
        ib.project_id,
        ib.descripcion AS producto,
        MAX(ib.grupo) AS grupo,
        SUM(ib.cantidad) AS cantidad_base
    FROM inventario ib
    WHERE ib.project_id IS NOT NULL
      AND ib.descripcion IS NOT NULL
      AND ib.descripcion != ''
    GROUP BY ib.project_id, ib.descripcion
),

-- 5. Ingresos totales por proyecto y producto (desde MinInvDate)
ingresos_totales AS (
    SELECT 
        f.project_id,
        COALESCE(fd.producto_estandarizado, fd.descripcion) AS producto,
        SUM(fd.cantidad) AS cantidad_ingreso_total
    FROM factura_detalle fd
    INNER JOIN factura f ON fd.factura_id = f.factura_id
    CROSS JOIN fecha_minima_inventario fmi
    WHERE f.project_id IS NOT NULL
      AND fd.cantidad > 0
      AND (fd.producto_estandarizado IS NOT NULL OR fd.descripcion IS NOT NULL)
      AND f.fecha_emision >= COALESCE(fmi.min_inv_date, '1900-01-01'::timestamp)
    GROUP BY f.project_id, COALESCE(fd.producto_estandarizado, fd.descripcion)
),

-- 6. Salidas totales por proyecto y producto
salidas_totales AS (
    SELECT 
        fp.project_id,
        fp.producto,
        SUM(fp.cantidad) AS cantidad_salida_total
    FROM flujo_productos fp
    WHERE fp.project_id IS NOT NULL
      AND fp.cantidad > 0
      AND fp.producto IS NOT NULL
    GROUP BY fp.project_id, fp.producto
),

-- 7. Inventario neto consolidado por Proyecto y Producto
inventario_neto_agrupado AS (
    SELECT 
        COALESCE(ib.project_id, ing.project_id, sal.project_id) AS project_id,
        COALESCE(ib.producto, ing.producto, sal.producto) AS producto,
        COALESCE(ib.grupo, c.grupo, 'SIN GRUPO') AS grupo,
        COALESCE(ib.cantidad_base, 0) + 
        COALESCE(ing.cantidad_ingreso_total, 0) - 
        COALESCE(sal.cantidad_salida_total, 0) AS inventario_neto
    FROM inventario_base ib
    FULL OUTER JOIN ingresos_totales ing 
        ON ib.project_id = ing.project_id AND ib.producto = ing.producto
    FULL OUTER JOIN salidas_totales sal 
        ON COALESCE(ib.project_id, ing.project_id) = sal.project_id 
        AND COALESCE(ib.producto, ing.producto) = sal.producto
    LEFT JOIN catalogo c ON COALESCE(ib.producto, ing.producto, sal.producto) = c.descripcion
),

-- 8. Detalle final con nombres de proyectos y precios
resultado_detalle AS (
    SELECT 
        p.nombre_proyecto AS "Proyecto",
        ina.grupo AS "Grupo",
        ina.producto AS "Producto Estandarizado",
        ROUND(ina.inventario_neto::NUMERIC, 0) AS "Inventario Neto",
        ROUND(COALESCE(pm.precio_mediana, 0)::NUMERIC, 2) AS "Median Price",
        ROUND((ina.inventario_neto * COALESCE(pm.precio_mediana, 0))::NUMERIC, 2) AS "Total Valorizado"
    FROM inventario_neto_agrupado ina
    LEFT JOIN projects p ON ina.project_id = p.project_id
    LEFT JOIN precios_mediana pm ON ina.producto = pm.producto_estandarizado
    WHERE ina.inventario_neto > 0
),

-- 9. Totales para la fila final
totales AS (
    SELECT 
        'TOTAL GENERAL' AS "Proyecto",
        NULL::TEXT AS "Grupo",
        NULL::TEXT AS "Producto Estandarizado",
        SUM("Inventario Neto")::NUMERIC AS "Inventario Neto",
        NULL::NUMERIC AS "Median Price",
        SUM("Total Valorizado")::NUMERIC AS "Total Valorizado"
    FROM resultado_detalle
)

-- 10. Query final combinado
SELECT * FROM (
    SELECT * FROM resultado_detalle
    UNION ALL
    SELECT * FROM totales
) AS r
ORDER BY 
    CASE WHEN "Proyecto" = 'TOTAL GENERAL' THEN 1 ELSE 0 END,
    "Proyecto", 
    "Total Valorizado" DESC;

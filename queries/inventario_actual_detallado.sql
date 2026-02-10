-- ============================================================
-- Query: Inventario Actual Detallado (Con Fechas y Proyectos)
-- ============================================================
-- Este query genera una tabla detallada con toda la información:
-- - Fechas de movimientos
-- - Nombre del proyecto
-- - Producto estandarizado
-- - Inventario base
-- - Ingresos y salidas diarias
-- - Inventario neto acumulado
-- - Precio por unidad (mediana)
-- - Total inventario neto
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

-- 2. Fecha mínima del inventario base (MinInvDate)
fecha_minima_inventario AS (
    SELECT MIN(created_at) AS min_inv_date
    FROM inventario
    WHERE created_at IS NOT NULL
),

-- 3. Inventario base por proyecto y producto
inventario_base AS (
    SELECT 
        i.project_id,
        i.descripcion AS producto,
        i.cantidad AS cantidad_base,
        COALESCE(i.unidad, 'UND') AS unidad_base,
        i.grupo,
        i.referencia,
        i.created_at AS fecha_inventario_base
    FROM inventario i
    WHERE i.project_id IS NOT NULL
      AND i.descripcion IS NOT NULL
      AND i.descripcion != ''
),

-- 4. Ingresos diarios por proyecto y producto (desde MinInvDate)
ingresos_diarios AS (
    SELECT 
        f.project_id,
        DATE(f.fecha_emision) AS fecha,
        COALESCE(fd.producto_estandarizado, fd.descripcion) AS producto,
        SUM(fd.cantidad) AS cantidad_ingreso,
        MAX(COALESCE(fd.unidad, 'UND')) AS unidad_ingreso,
        BOOL_OR(COALESCE(fd.validado_manualmente, FALSE)) AS verificado_estandarizacion,
        COUNT(DISTINCT f.factura_id) AS num_facturas,
        MIN(f.fecha_emision) AS primera_factura_fecha,
        MAX(f.fecha_emision) AS ultima_factura_fecha
    FROM factura_detalle fd
    INNER JOIN factura f ON fd.factura_id = f.factura_id
    CROSS JOIN fecha_minima_inventario fmi
    WHERE f.project_id IS NOT NULL
      AND f.fecha_emision IS NOT NULL
      AND fd.cantidad > 0
      AND (fd.producto_estandarizado IS NOT NULL OR fd.descripcion IS NOT NULL)
      AND f.fecha_emision >= COALESCE(fmi.min_inv_date, '1900-01-01'::timestamp)
    GROUP BY 
        f.project_id,
        DATE(f.fecha_emision),
        COALESCE(fd.producto_estandarizado, fd.descripcion)
),

-- 5. Salidas diarias por proyecto y producto
salidas_diarias AS (
    SELECT 
        fp.project_id,
        DATE(fp.sent_date) AS fecha,
        fp.producto,
        SUM(fp.cantidad) AS cantidad_salida,
        MAX(COALESCE(fp.unidad, 'UND')) AS unidad_salida,
        COUNT(DISTINCT fp.id) AS num_registros_salida,
        MIN(fp.sent_date) AS primera_salida_fecha,
        MAX(fp.sent_date) AS ultima_salida_fecha
    FROM flujo_productos fp
    WHERE fp.project_id IS NOT NULL
      AND fp.sent_date IS NOT NULL
      AND fp.cantidad > 0
      AND fp.producto IS NOT NULL
    GROUP BY 
        fp.project_id,
        DATE(fp.sent_date),
        fp.producto
),

-- 6. Unificar todas las fechas con actividad (ingresos o salidas)
fechas_actividad AS (
    SELECT DISTINCT
        project_id,
        fecha,
        producto
    FROM ingresos_diarios
    
    UNION
    
    SELECT DISTINCT
        project_id,
        fecha,
        producto
    FROM salidas_diarias
),

-- 7. Movimientos netos diarios (ingresos - salidas)
movimientos_netos AS (
    SELECT 
        COALESCE(ing.project_id, sal.project_id) AS project_id,
        COALESCE(ing.fecha, sal.fecha) AS fecha,
        COALESCE(ing.producto, sal.producto) AS producto,
        COALESCE(ing.cantidad_ingreso, 0) AS cantidad_ingreso,
        COALESCE(ing.unidad_ingreso, sal.unidad_salida, 'UND') AS unidad,
        COALESCE(ing.verificado_estandarizacion, FALSE) AS verificado_estandarizacion,
        COALESCE(ing.num_facturas, 0) AS num_facturas,
        ing.primera_factura_fecha,
        ing.ultima_factura_fecha,
        COALESCE(sal.cantidad_salida, 0) AS cantidad_salida,
        COALESCE(sal.num_registros_salida, 0) AS num_registros_salida,
        sal.primera_salida_fecha,
        sal.ultima_salida_fecha,
        COALESCE(ing.cantidad_ingreso, 0) - COALESCE(sal.cantidad_salida, 0) AS movimiento_neto
    FROM ingresos_diarios ing
    FULL OUTER JOIN salidas_diarias sal 
        ON ing.project_id = sal.project_id 
        AND ing.fecha = sal.fecha 
        AND ing.producto = sal.producto
),

-- 8. Inventario acumulado por fecha y proyecto
inventario_acumulado AS (
    SELECT 
        m.project_id,
        m.fecha,
        m.producto,
        m.cantidad_ingreso,
        m.unidad,
        m.verificado_estandarizacion,
        m.num_facturas,
        m.primera_factura_fecha,
        m.ultima_factura_fecha,
        m.cantidad_salida,
        m.num_registros_salida,
        m.primera_salida_fecha,
        m.ultima_salida_fecha,
        m.movimiento_neto,
        -- Inventario base + sumatoria de movimientos hasta esta fecha
        COALESCE(ib.cantidad_base, 0) + 
        SUM(m.movimiento_neto) OVER (
            PARTITION BY m.project_id, m.producto 
            ORDER BY m.fecha 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS inventario_neto,
        -- Fecha del inventario base
        ib.fecha_inventario_base
    FROM movimientos_netos m
    LEFT JOIN inventario_base ib 
        ON m.project_id = ib.project_id 
        AND m.producto = ib.producto
)

-- 9. Query principal: tabla detallada con toda la información
SELECT 
    ia.project_id,
    p.nombre_proyecto,
    ia.fecha,
    ia.producto AS producto_estandarizado,
    
    -- Información del inventario base
    COALESCE(ib.cantidad_base, 0) AS inventario_base,
    COALESCE(ib.unidad_base, ia.unidad, 'UND') AS unidad_base,
    ib.grupo,
    ib.referencia,
    ia.fecha_inventario_base,
    
    -- Ingresos del día
    ia.cantidad_ingreso,
    ia.unidad AS unidad_ingreso,
    ia.verificado_estandarizacion,
    ia.num_facturas,
    ia.primera_factura_fecha,
    ia.ultima_factura_fecha,
    
    -- Salidas del día
    ia.cantidad_salida,
    ia.unidad AS unidad_salida,
    ia.num_registros_salida,
    ia.primera_salida_fecha,
    ia.ultima_salida_fecha,
    
    -- Movimiento neto del día
    ia.movimiento_neto,
    
    -- Inventario neto (acumulado hasta la fecha)
    ia.inventario_neto,
    
    -- Precio por unidad (mediana)
    ROUND(COALESCE(pm.precio_mediana, 0)::NUMERIC, 2) AS precio_por_unidad,
    
    -- Total (inventario neto * precio por unidad)
    ROUND((ia.inventario_neto * COALESCE(pm.precio_mediana, 0))::NUMERIC, 2) AS total_inventario_neto

FROM inventario_acumulado ia
LEFT JOIN projects p ON ia.project_id = p.project_id
LEFT JOIN inventario_base ib ON ia.project_id = ib.project_id 
    AND ia.producto = ib.producto
LEFT JOIN precios_mediana pm ON ia.producto = pm.producto_estandarizado

WHERE ia.fecha IS NOT NULL
  AND ia.producto IS NOT NULL
  AND ia.producto != ''

ORDER BY 
    ia.project_id,
    p.nombre_proyecto,
    ia.fecha DESC,
    ia.producto;

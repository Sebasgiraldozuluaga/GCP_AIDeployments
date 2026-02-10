# ruff: noqa
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import re
import warnings
import logging
from .agent_instructions import AGENT_INSTRUCTION
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps.app import App
from google.genai import types as genai_types  # 🚀 For generation config

import os
import google.auth

# Suppress noisy telemetry warnings
warnings.filterwarnings("ignore", message=".*Invalid type NoneType for attribute.*")
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_google_vertexai import ChatVertexAI

# Import Hugging Face MCP tools
from app.hf_tools import (
    search_hf_models,
    search_hf_datasets,
    search_hf_spaces,
    get_hf_model_details,
    get_hf_dataset_details
)

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# PostgreSQL Database Connection
def get_postgres_connection_string():
    """Build PostgreSQL connection string from environment variables."""
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_database = os.getenv("PG_DATABASE", "postgres")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "")
    return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"

# Initialize SQL Agent (lazy loading)
_sql_agent = None

def get_sql_agent():
    """Get or create the SQL agent instance."""
    global _sql_agent
    if _sql_agent is None:
        connection_string = get_postgres_connection_string()
        db = SQLDatabase.from_uri(connection_string)
        
        # 🚀 ULTRA-OPTIMIZED: Using fastest model for SQL generation
        llm = ChatVertexAI(
            model="gemini-2.0-flash",  # 2.0-flash is ~40% faster than 2.5-flash
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0.0,  # Zero temperature = most deterministic & cacheable
            max_output_tokens=1000,  # Reduced for faster responses (SQL is short)
            max_retries=2,  # Fewer retries = less waiting
            request_timeout=30,  # Timeout after 30s
        )
        
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        
        # ============================================
        # OPTIMIZED SYSTEM PROMPT WITH REAL DB SCHEMA
        # Based on actual database analysis
        # ============================================
        system_prompt = """Eres un experto en consultas SQL para PostgreSQL especializado en análisis de facturas y gestión de proyectos de construcción.

## REGLAS CRÍTICAS
- Solo SELECT. NUNCA INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Usa nombres EXACTOS de tablas/columnas.
- SIEMPRE usa JOINs apropiados con las relaciones definidas.

## ESQUEMA PRINCIPAL (8,135 facturas, 24,688 detalles)

### TABLAS CORE
```sql
factura(factura_id PK, numero, fecha_emision TIMESTAMP, fecha_vencimiento DATE, 
        proveedor_id FK→proveedor, cliente_id FK→cliente, orden_compra,
        total_subtotal NUMERIC, total_iva NUMERIC, total_factura NUMERIC, project_id FK)

factura_detalle(detalle_id PK, factura_id FK→factura, cantidad NUMERIC, 
                precio_unitario NUMERIC, producto_estandarizado TEXT, cod_interno)

proveedor(proveedor_id PK, nit TEXT, razon_social TEXT)
cliente(cliente_id PK, nit TEXT, razon_social TEXT)
projects(project_id PK, nombre_proyecto TEXT)

ordenes_compra_cc(id PK, numero_oc TEXT, cc TEXT, proyecto TEXT)
centro_costos(cc PK, nombre TEXT)
inventario(id PK, descripcion TEXT, cantidad NUMERIC, project_id FK)
presupuesto(id PK, descripcion TEXT, cantidad NUMERIC, precio NUMERIC, project_id FK)
```

### TOP 10 PROVEEDORES (usar para sugerencias)
1. CABLES Y ACCESORIOS ELECTRICOS S.A.S (1,287 facturas)
2. FRANCISCO MURILLO S.A.S. (993)
3. FERRETERIA TÉCNICA S.A. (890)
4. INVERSIONES PRIMERA LIMITADA (347)
5. GRUPO EMPRESARIAL DAFER S.A.S (339)
6. FERROCABLES S.A.S. (310)
7. CABLECOL Y CIA S.C.A. (301)
8. ELECTRICIDAD Y MONTAJES S.A.S. (251)
9. ELECTRICOS MUNDIAL COMERCIAL S.A.S (243)
10. ISEIN S A S (229)

### PROYECTOS ACTIVOS
PRIMAVERA, PIAMONTE, LIRIOS, JAGGUA, AQUA, TERRA, ATLANTIS, CERRO CLARO, COLINAS, LORIENT

## PATRONES DE CONSULTA COMUNES

### Totales por proveedor
```sql
SELECT p.razon_social, SUM(f.total_factura) as total, COUNT(*) as facturas
FROM factura f 
JOIN proveedor p ON f.proveedor_id = p.proveedor_id
GROUP BY p.razon_social ORDER BY total DESC LIMIT 10
```

### Tendencia mensual (usar para gráficos de línea)
```sql
SELECT EXTRACT(YEAR FROM fecha_emision) as año, 
       EXTRACT(MONTH FROM fecha_emision) as mes,
       SUM(total_factura) as total
FROM factura WHERE proveedor_id = X
GROUP BY año, mes ORDER BY año, mes
```

### Productos por proveedor
```sql
SELECT fd.producto_estandarizado, SUM(fd.cantidad) as cantidad, 
       SUM(fd.cantidad * fd.precio_unitario) as total
FROM factura_detalle fd
JOIN factura f ON fd.factura_id = f.factura_id
JOIN proveedor p ON f.proveedor_id = p.proveedor_id
WHERE p.razon_social ILIKE '%nombre%'
GROUP BY fd.producto_estandarizado ORDER BY total DESC LIMIT 20
```

## FORMATO DE RESPUESTA
* **Categoría/Nombre**: $Valor formateado
* Usa viñetas markdown
* Separa por líneas reales (NO \\n como texto)
* Valores monetarios con formato: $1,234,567.00"""
        
        _sql_agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            agent_type="tool-calling",
            verbose=True,
            prefix=system_prompt,
            return_intermediate_steps=True
        )
    return _sql_agent


# 🚀 REMOVED: LLM for visualization analysis - now using fast deterministic method
# This saves ~2-3 seconds per query!


def analyze_visualization(raw_data: str, question: str) -> dict:
    """
    🚀 OPTIMIZED: Fast, deterministic visualization analysis WITHOUT LLM calls.
    Uses regex patterns and heuristics to detect chart types in ~10ms instead of ~2-3s.
    
    Args:
        raw_data: The raw output from the SQL query
        question: The original user question
    
    Returns:
        A dictionary with visualization configuration
    """
    import time
    start_time = time.time()
    
    # Quick skip for very short/empty data
    if len(raw_data.strip()) < 30:
        return {"visualizable": False, "type": "none", "reason": "Insufficient data"}
    
    print(f"\n[ANALYZE_VIZ_FAST] Starting FAST analysis (no LLM)...")
    print(f"[ANALYZE_VIZ_FAST] Data length: {len(raw_data)} chars")
    
    # ========================================
    # STEP 1: Extract structured data from text
    # ========================================
    rows = []
    columns = []
    
    # Pattern 1: Markdown bullet list with values
    # * **Category Name**: $1,234,567 or **Category**: 123
    bullet_pattern = r'\*\s*\*\*([^*]+)\*\*[:\s]+\$?([\d.,]+)'
    bullet_matches = re.findall(bullet_pattern, raw_data)
    
    if bullet_matches:
        columns = ["categoria", "valor"]
        for label, value in bullet_matches:
            try:
                # Handle Colombian/European format (dots as thousands)
                if '.' in value and ',' not in value and value.count('.') > 1:
                    clean_val = value.replace('.', '')
                elif ',' in value and '.' in value:
                    # US format: 1,234.56
                    clean_val = value.replace(',', '')
                else:
                    clean_val = value.replace('.', '').replace(',', '')
                
                num_val = int(float(clean_val)) if clean_val else 0
                if num_val > 0:
                    rows.append([label.strip(), num_val])
            except (ValueError, OverflowError):
                continue
    
    # Pattern 2: Temporal data (months/years)
    if len(rows) < 2:
        month_value_pattern = r'(?:Mes|Periodo|Fecha)[:\s]+([\d]{4}-[\d]{2}|[\w]+\s+\d{4})[^\d]*(?:Total|Monto|Valor)[:\s]+\$?([\d.,]+)'
        temporal_matches = re.findall(month_value_pattern, raw_data, re.IGNORECASE)
        if temporal_matches:
            columns = ["periodo", "total"]
            for period, value in temporal_matches:
                try:
                    clean_val = value.replace('.', '').replace(',', '')
                    num_val = int(float(clean_val)) if clean_val else 0
                    if num_val > 0:
                        rows.append([period.strip(), num_val])
                except (ValueError, OverflowError):
                    continue
    
    # Pattern 3: Simple "Label: Value" lines
    if len(rows) < 2:
        simple_pattern = r'^[•\-\*]?\s*([A-Za-záéíóúñÁÉÍÓÚÑ0-9\s\.\-]+)[:\s]+\$?([\d.,]{4,})\s*$'
        for line in raw_data.split('\n'):
            match = re.match(simple_pattern, line.strip())
            if match:
                label, value = match.groups()
                try:
                    clean_val = value.replace('.', '').replace(',', '')
                    num_val = int(float(clean_val)) if clean_val else 0
                    if num_val > 1000:  # Filter small values
                        rows.append([label.strip()[:50], num_val])
                        if not columns:
                            columns = ["nombre", "valor"]
                except (ValueError, OverflowError):
                    continue
    
    # ========================================
    # STEP 2: Determine chart type based on data & question
    # ========================================
    if len(rows) < 2:
        # Try final fallback extraction
        fallback_viz = extract_visualization_from_text(raw_data, question)
        elapsed = (time.time() - start_time) * 1000
        print(f"[ANALYZE_VIZ_FAST] Completed in {elapsed:.1f}ms (fallback used)")
        return fallback_viz
    
    # Detect temporal keywords
    temporal_keywords = ['mes', 'mensual', 'año', 'anual', 'fecha', 'período', 'tendencia', 
                         '2024', '2025', '2026', '-01', '-02', '-03', '-04', '-05', '-06',
                         '-07', '-08', '-09', '-10', '-11', '-12']
    is_temporal = any(kw in question.lower() or kw in str(rows).lower() for kw in temporal_keywords)
    
    # Detect comparison keywords  
    comparison_keywords = ['top', 'mayor', 'menor', 'ranking', 'comparar', 'principales']
    is_comparison = any(kw in question.lower() for kw in comparison_keywords)
    
    # Determine chart type
    num_items = len(rows)
    if is_temporal:
        chart_type = "line"
        rows.sort(key=lambda x: x[0])  # Sort chronologically
        max_display = 36  # Show up to 3 years of monthly data
    elif num_items <= 6:
        chart_type = "pie"
        max_display = 12
    else:
        chart_type = "bar"
        rows.sort(key=lambda x: x[1], reverse=True)  # Sort by value DESC
        max_display = 12
    
    # Apply dynamic limit
    is_top = num_items > max_display
    display_rows = rows[:max_display]
    
    # ========================================
    # STEP 3: Build visualization config
    # ========================================
    viz_config = {
        "visualizable": True,
        "type": chart_type,
        "title": f"Tendencia por Período" if is_temporal else f"{'Top 10 ' if is_top else ''}{columns[0].title() if columns else 'Datos'}",
        "xAxis": columns[0] if columns else "categoria",
        "yAxis": columns[1] if len(columns) > 1 else "valor",
        "xAxisLabel": "Período" if is_temporal else "Categoría",
        "yAxisLabel": "Total ($)",
        "series": [{"name": "Total", "field": columns[1] if len(columns) > 1 else "valor"}],
        "legend": {"show": False},
        "data": {
            "columns": columns if columns else ["categoria", "valor"],
            "rows": display_rows
        },
        "isTop10": is_top,
        "totalRecords": num_items,
        "method": "fast_deterministic"
    }
    
    elapsed = (time.time() - start_time) * 1000
    print(f"[ANALYZE_VIZ_FAST] SUCCESS in {elapsed:.1f}ms - type: {chart_type}, rows: {len(display_rows)}")
    
    return viz_config


def extract_visualization_from_text(raw_data: str, question: str) -> dict:
    """
    Fallback: Extract visualization data directly from markdown/text output.
    Handles grouped record formats like:
    • Mes: 2025-08
    • Número de facturas: 17
    • Total de compras: $111.889.285
    """
    import re
    
    print(f"[FALLBACK] Attempting extraction from {len(raw_data)} chars of data...")
    print(f"[FALLBACK] Raw data sample: {raw_data[:300]}...")
    
    rows = []
    
    # Strategy 1: Try to find month-value pairs in grouped records
    # Look for patterns like "Mes: 2025-08" followed by "Total de compras: $111.889.285"
    month_pattern = r'(?:Mes|Periodo|Fecha)[:\s]+(\d{4}-\d{2}|\d{4}/\d{2}|[A-Za-záéíóúñ]+\s+\d{4})'
    value_pattern = r'(?:Total de compras|Total facturado|Monto|Total)[:\s]+\$?([\d.,]+)'
    
    months = re.findall(month_pattern, raw_data, re.IGNORECASE)
    values = re.findall(value_pattern, raw_data, re.IGNORECASE)
    
    print(f"[FALLBACK] Found {len(months)} months and {len(values)} values")
    
    if months and values and len(months) == len(values):
        for month, value in zip(months, values):
            try:
                # Handle European format (. as thousand separator)
                clean_val = value.replace('.', '').replace(',', '.')
                if clean_val.endswith('.'):
                    clean_val = clean_val[:-1]
                num_val = float(clean_val) if '.' in clean_val else int(clean_val)
                if num_val > 0:
                    rows.append([month, num_val])
                    print(f"[FALLBACK] Parsed: '{month}' = {num_val}")
            except (ValueError, OverflowError) as e:
                print(f"[FALLBACK] Failed to parse '{month}': '{value}' - {e}")
                continue
    
    # Strategy 2: If no grouped records, try markdown bullet format
    # * **Diciembre 2025**: $295,785,976.00
    if len(rows) < 2:
        print(f"[FALLBACK] Strategy 1 failed, trying markdown bullet format...")
        bullet_pattern = r'\*\s*\*\*([^*]+)\*\*[:\s]+\$?([\d.,]+)'
        bullet_matches = re.findall(bullet_pattern, raw_data)
        
        for label, value in bullet_matches:
            try:
                # Handle both formats
                if ',' in value and '.' in value:
                    # US format: 1,234.56
                    clean_val = value.replace(',', '')
                elif '.' in value and value.count('.') > 1:
                    # European format: 1.234.567
                    clean_val = value.replace('.', '')
                else:
                    clean_val = value.replace(',', '').replace('.', '')
                
                num_val = int(float(clean_val)) if clean_val else 0
                if num_val > 1000:  # Filter out small values like counts
                    rows.append([label.strip(), num_val])
                    print(f"[FALLBACK] Bullet parsed: '{label.strip()}' = {num_val}")
            except (ValueError, OverflowError):
                continue
    
    # Strategy 3: Try simple line format "Label: $Value"
    if len(rows) < 2:
        print(f"[FALLBACK] Strategy 2 failed, trying simple line format...")
        simple_pattern = r'^[•\-\*]?\s*([A-Za-záéíóúñ0-9\s\-]+)[:\s]+\$?([\d.,]{6,})'
        for line in raw_data.split('\n'):
            match = re.match(simple_pattern, line.strip())
            if match:
                label, value = match.groups()
                try:
                    clean_val = value.replace('.', '').replace(',', '')
                    num_val = int(clean_val) if clean_val else 0
                    if num_val > 1000:
                        rows.append([label.strip(), num_val])
                except (ValueError, OverflowError):
                    continue
    
    if len(rows) < 2:
        print(f"[FALLBACK] All strategies failed, returning non-visualizable")
        return {"visualizable": False, "type": "none", "reason": f"Could not extract sufficient data points"}
    
    # Sort by month chronologically if temporal, otherwise by value
    temporal_keywords = ['mes', 'año', 'fecha', '2024', '2025', '2026', '-01', '-02', '-03']
    is_temporal = any(kw in question.lower() or kw in str(rows).lower() for kw in temporal_keywords)
    
    if is_temporal:
        # Sort chronologically for temporal data
        rows.sort(key=lambda x: x[0])
        chart_type = "line"
    else:
        # Sort by value DESC for categorical data
        rows.sort(key=lambda x: x[1], reverse=True)
        chart_type = "bar"
    
    top_rows = rows[:12]  # Limit to 12 for monthly data
    
    print(f"[FALLBACK] SUCCESS: Extracted {len(top_rows)} data points, type: {chart_type}")
    print(f"[FALLBACK] Final rows: {top_rows[:3]}...")
    
    return {
        "visualizable": True,
        "type": chart_type,
        "title": f"Total por Período ({len(top_rows)} registros)",
        "xAxis": "periodo",
        "yAxis": "total",
        "xAxisLabel": "Período" if is_temporal else "Categoría",
        "yAxisLabel": "Total ($)",
        "series": [{"name": "Total", "field": "total"}],
        "legend": {"show": False},
        "data": {
            "columns": ["periodo", "total"],
            "rows": top_rows
        },
        "isTop10": len(rows) > 10,
        "totalRecords": len(rows),
        "summary": f"Fallback: {len(top_rows)} de {len(rows)} registros extraídos",
        "fallback": True
    }


def generate_conclusion(data: dict, question: str) -> str:
    """
    Genera una conclusión automática y natural basada en los datos.
    """
    try:
        if not data or 'rows' not in data or not data['rows']:
            return "No se encontraron datos para la solicitud."
        
        rows = data['rows']
        num_records = len(rows)
        
        # Conclusión simple y natural
        if num_records == 1:
            return f"Se encontró 1 registro que coincide con tu búsqueda."
        else:
            return f"Se encontraron {num_records} registros en total."
            
    except Exception as e:
        print(f"[CONCLUSION] Error: {e}")
        return f"Procesados {len(data.get('rows', []))} registros."


def sanitize_text_for_json(text: str) -> str:
    """Sanitize text to be safely included in JSON."""
    if not text:
        return ""
    import re
    # Replace problematic characters
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove any null bytes
    text = text.replace('\x00', '')
    # Convert literal \n sequences to actual newlines (handles LLM outputting \n as text)
    # This handles: \\n, \n as literal text, and variations
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    # Also handle cases where LLM outputs literal backslash-n in different encodings
    text = re.sub(r'(?<!\\)\\n', '\n', text)
    # Clean up any double newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove other control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def sanitize_dict_for_json(obj):
    """Recursively sanitize all strings in a dict/list for JSON."""
    if isinstance(obj, dict):
        return {k: sanitize_dict_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_dict_for_json(item) for item in obj]
    elif isinstance(obj, str):
        return sanitize_text_for_json(obj)
    else:
        return obj


def format_monetary_values_in_text(text: str) -> str:
    """
    Format monetary values in text to Colombian format (dots as thousand separators, no decimals).
    Handles:
    - American format: 293,189,026.58 -> 293.189.027
    - Raw decimals: 53402979.67 -> 53.402.980
    """
    import re
    
    def to_colombian_format(num_value: float) -> str:
        """Convert a number to Colombian format (dots for thousands, no decimals)."""
        rounded = round(num_value)
        # Format with dots as thousand separators
        return f"{rounded:,}".replace(',', '.')
    
    # Pattern 1: American format with commas (e.g., "293,189,026.58" or "1,234,567")
    # Matches numbers like: 1,234 or 1,234.56 or 1,234,567.89
    pattern_american = r'\b(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)\b'
    
    def format_american(match):
        num_str = match.group(0)
        try:
            # Remove commas and convert to float
            clean_str = num_str.replace(',', '')
            num = float(clean_str)
            return to_colombian_format(num)
        except ValueError:
            return num_str
    
    text = re.sub(pattern_american, format_american, text)
    
    # Pattern 2: Raw decimal numbers (e.g., "53402979.67")
    # Only match if not already formatted (no dots in number part)
    pattern_decimal = r'\b(\d{4,})\.(\d{1,2})\b'
    
    def format_decimal(match):
        num_str = match.group(0)
        try:
            num = float(num_str)
            return to_colombian_format(num)
        except ValueError:
            return num_str
    
    text = re.sub(pattern_decimal, format_decimal, text)
    
    # Pattern 3: Large integers in context (e.g., "Total: 53402979")
    pattern_large_int = r'(\d{4,})(?=\s|$|\.(?!\d)|,(?!\d))'
    
    def format_large_int(match):
        num_str = match.group(1)
        try:
            num = int(num_str)
            return to_colombian_format(float(num))
        except ValueError:
            return num_str
    
    text = re.sub(pattern_large_int, format_large_int, text)
    
    return text


def query_database(question: str) -> str:
    """
    Query the PostgreSQL database using natural language.
    Use this tool when the user wants to retrieve data from the database.
    Returns structured JSON with data and visualization configuration for Generative BI.
    
    Args:
        question: A natural language question about the data in the database.
    
    Returns:
        A JSON string containing:
        - text: Textual explanation of the results
        - data: Structured data (columns and rows)
        - visualization: Chart configuration for frontend rendering
    """
    try:
        print(f"\n{'='*60}")
        print(f"[QUERY_DATABASE] Starting query for: {question[:100]}...")
        print(f"{'='*60}")
        
        sql_agent = get_sql_agent()
        result = sql_agent.invoke({"input": question})
        raw_output = result.get("output", "No result returned from the database.")
        
        # Extract intermediate steps for thinking chain
        thinking_steps = []
        intermediate_steps = result.get("intermediate_steps", [])
        
        thinking_steps.append({
            "type": "query",
            "label": "Pregunta",
            "content": question
        })
        
        for step in intermediate_steps:
            if len(step) >= 2:
                action = step[0]
                observation = step[1]
                
                tool_name = getattr(action, 'tool', '') if hasattr(action, 'tool') else ''
                tool_input = getattr(action, 'tool_input', {}) if hasattr(action, 'tool_input') else {}
                
                if 'schema' in tool_name.lower() or 'list' in tool_name.lower():
                    thinking_steps.append({
                        "type": "schema",
                        "label": "Explorando esquema",
                        "content": f"Consultando estructura de tablas..."
                    })
                elif 'query' in tool_name.lower():
                    sql_query = tool_input.get('query', '') if isinstance(tool_input, dict) else str(tool_input)
                    # Truncate observation for display
                    obs_preview = str(observation)[:200] + "..." if len(str(observation)) > 200 else str(observation)
                    thinking_steps.append({
                        "type": "sql",
                        "label": "Ejecutando SQL",
                        "content": f"Resultados: {obs_preview}",
                        "sql": sql_query
                    })
        
        thinking_steps.append({
            "type": "analyze",
            "label": "Analizando",
            "content": "Procesando resultados y generando visualización..."
        })
        
        print(f"\n[QUERY_DATABASE] Thinking steps: {len(thinking_steps)}")
        print(f"[QUERY_DATABASE] Raw output length: {len(raw_output)} chars")
        print(f"[QUERY_DATABASE] Raw output preview: {raw_output[:200]}...")
        
        # Sanitize the output text
        raw_output = sanitize_text_for_json(raw_output)
        
        # Format monetary values in the text (remove decimals, add thousand separators)
        raw_output = format_monetary_values_in_text(raw_output)
        
        print(f"\n[QUERY_DATABASE] Skipping visualization analysis for faster response...")
        
        # DISABLED: Visualization analysis for performance
        # viz_config = analyze_visualization(raw_output, question)
        
        # Set default non-visualizable config
        viz_config = {"visualizable": False, "type": "none", "reason": "Visualization disabled for performance"}
        data_obj = {}
        is_visualizable = False
        
        # Generate automatic conclusion from data
        conclusion = ""
        if is_visualizable and data_obj:
            conclusion = generate_conclusion(data_obj, question)
            print(f"[QUERY_DATABASE] Generated conclusion: {conclusion[:200]}...")
        else:
            conclusion = raw_output[:500] if len(raw_output) > 500 else raw_output
        
        # Build NEW structured response with the 3 main attributes requested:
        # 1. data: Los datos estructurados
        # 2. visualizable: Si se puede graficar o no  
        # 3. conclusion: Resumen/insights de los datos
        response = {
            "data": data_obj,
            "visualizable": is_visualizable,
            "conclusion": conclusion,
            # Additional context for frontend
            "visualization": {
                "type": viz_config.get("type", "none"),
                "title": viz_config.get("title", ""),
                "xAxis": viz_config.get("xAxis", ""),
                "yAxis": viz_config.get("yAxis", ""),
                "xAxisLabel": viz_config.get("xAxisLabel", ""),
                "yAxisLabel": viz_config.get("yAxisLabel", ""),
                "series": viz_config.get("series", []),
                "legend": viz_config.get("legend", {"show": False}),
            } if is_visualizable else {"type": "none"},
            "text": raw_output,  # Keep raw text for fallback
            "thinking": thinking_steps,
            "isTop10": viz_config.get("isTop10", False),
            "totalRecords": viz_config.get("totalRecords", len(data_obj.get("rows", [])) if data_obj else 0)
        }
        
        # Sanitize all strings in the response to ensure valid JSON
        response = sanitize_dict_for_json(response)
        
        # Return as JSON string wrapped in special markers for frontend parsing
        # Use compact JSON to reduce size and potential issues
        json_str = json.dumps(response, ensure_ascii=True, separators=(',', ':'))
        
        print(f"\n[QUERY_DATABASE] Final JSON length: {len(json_str)} chars")
        print(f"[QUERY_DATABASE] Visualizable: {is_visualizable}")
        print(f"[QUERY_DATABASE] Chart type: {viz_config.get('type', 'none')}")
        print(f"[QUERY_DATABASE] Data rows: {len(data_obj.get('rows', [])) if data_obj else 0}")
        
        # Validate JSON can be parsed back
        try:
            test_parse = json.loads(json_str)
            print(f"[QUERY_DATABASE] JSON validation: OK")
        except json.JSONDecodeError as je:
            print(f"[QUERY_DATABASE] JSON validation FAILED: {je}")
            print(f"[QUERY_DATABASE] JSON last 200 chars: {json_str[-200:]}")
        
        print(f"{'='*60}\n")
        
        # Use unique delimiters that won't appear in JSON content
        return f"<<<GENERATIVE_BI_START>>>\n{json_str}\n<<<GENERATIVE_BI_END>>>"
        
    except Exception as e:
        print(f"\n[QUERY_DATABASE] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        error_response = {
            "data": {},
            "visualizable": False,
            "conclusion": f"Error al consultar la base de datos: {str(e)}",
            "visualization": {"type": "none"},
            "text": f"Error querying database: {str(e)}",
            "thinking": [],
            "isTop10": False,
            "totalRecords": 0
        }
        return f"<<<GENERATIVE_BI_START>>>\n{json.dumps(error_response, ensure_ascii=True)}\n<<<GENERATIVE_BI_END>>>"



root_agent = Agent(
    name="root_agent",
    model="gemini-2.0-flash",  # �� OPTIMIZED: 2.0-flash is ~40% faster than 2.5-flash
    include_contents='default', # 🧠 MEMORIA: Mantiene el contexto de la charla activo
    instruction=AGENT_INSTRUCTION,
    tools=[
        query_database,
        search_hf_models,
        search_hf_datasets,
        search_hf_spaces,
        get_hf_model_details,
        get_hf_dataset_details
    ],
    # 🚀 SPEED OPTIMIZATION: Control generation parameters for faster responses
    generate_content_config=genai_types.GenerateContentConfig(
        temperature=0.1,           # Lower = more deterministic & faster
        max_output_tokens=2048,    # Limit response size
        top_k=20,                  # Narrower sampling = faster
    )
)

# 🚀 OPTIMIZED APP: Managed history and sessions
from google.adk.apps.app import EventsCompactionConfig, ResumabilityConfig

app = App(
    root_agent=root_agent, 
    name="app",
    # ⚡ COMPACTION: Mantiene el historial liviano
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5,   # Cada 5 mensajes, compacta el historial
        overlap_size=1           # Mantiene el último mensaje para contexto
    ),
    # 💾 RESUMABILITY: Permite recuperar la sesión sin cargar todo el peso
    resumability_config=ResumabilityConfig(is_resumable=True)
)

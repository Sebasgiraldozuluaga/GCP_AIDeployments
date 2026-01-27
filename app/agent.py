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
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps.app import App

import os
import google.auth

# Suppress noisy telemetry warnings
warnings.filterwarnings("ignore", message=".*Invalid type NoneType for attribute.*")
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_sql_agent
from langchain_google_vertexai import ChatVertexAI

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
        
        # Use Gemini as the LLM for the SQL agent (via Vertex AI)
        llm = ChatVertexAI(
            model="gemini-2.5-flash",
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0.2,
        )
        
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        
        system_prompt = """Eres un ejecutor de consultas SQL para PostgreSQL.
        Solo ejecuta consultas SELECT. NUNCA ejecutes INSERT, UPDATE, DELETE, DROP, ALTER o TRUNCATE.
        Respeta los nombres exactos de tablas y columnas.
        
        FORMATO DE RESPUESTA CRÍTICO:
        - Usa saltos de línea REALES (presiona Enter), NO escribas \\n como texto
        - Formatea los resultados como lista markdown con viñetas o números
        - Cada item en una línea separada
        - Usa **negritas** para nombres de categorías
        
        Ejemplo de formato CORRECTO:
        
        Aquí están los resultados:
        
        * **PROVEEDOR A**: $1,234,567
        * **PROVEEDOR B**: $987,654
        * **PROVEEDOR C**: $456,789
        
        Ejemplo de formato INCORRECTO (NO hacer esto):
        PROVEEDOR A: 1234567\\n PROVEEDOR B: 987654\\n"""
        
        _sql_agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            agent_type="tool-calling",
            verbose=True,
            prefix=system_prompt,
            return_intermediate_steps=True
        )
    return _sql_agent


# LLM for visualization analysis
_viz_llm = None

def get_viz_llm():
    """Get or create the visualization analysis LLM instance."""
    global _viz_llm
    if _viz_llm is None:
        _viz_llm = ChatVertexAI(
            model="gemini-2.5-flash",
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0.2,
        )
    return _viz_llm


def quick_detect_visualization(raw_data: str) -> dict | None:
    """
    Quick detection - only skip visualization for truly non-visualizable cases.
    Returns None to always try LLM analysis when there's any data.
    """
    # Only skip if response is extremely short (likely an error or single number)
    if len(raw_data.strip()) < 20:
        return {"visualizable": False, "type": "none", "reason": "Too short"}
    
    # Always try to visualize if there's data
    return None  # Let LLM decide


def analyze_visualization(raw_data: str, question: str) -> dict:
    """
    Analyze query results and determine the best visualization type.
    Uses LLM to intelligently select chart type based on data characteristics.
    Automatically limits to Top 10 when there are many records.
    
    Args:
        raw_data: The raw output from the SQL query
        question: The original user question
    
    Returns:
        A dictionary with visualization configuration
    """
    # Try quick detection first (no LLM call)
    quick_result = quick_detect_visualization(raw_data)
    if quick_result is not None:
        print(f"[ANALYZE_VIZ] Quick detection: {quick_result.get('reason', 'skipped')}")
        return quick_result
    
    # Truncate raw_data if too long to speed up processing
    max_data_len = 3000
    truncated_data = raw_data[:max_data_len] + "..." if len(raw_data) > max_data_len else raw_data
    
    viz_prompt = f"""Genera configuración de visualización para estos datos SQL.

PREGUNTA: {question}
DATOS:
{truncated_data}

REGLA PRINCIPAL: SIEMPRE genera visualización si hay al menos 1 registro con datos numéricos. Usa "bar" por defecto.

REGLAS:
- Si >10 registros: incluir solo Top 10 ordenados por valor DESC, indicar "Top 10" en título
- Tipos: bar (DEFAULT para categorías), line (series temporales), pie (≤8 proporciones), groupedBar (2 dimensiones)
- Si hay 2 dimensiones categóricas: usar groupedBar con groupBy y legend
- Incluso con 1 solo registro: visualizar como bar

⚠️ CRÍTICO - VALORES NUMÉRICOS:
- NUNCA dividir ni transformar los valores numéricos
- Si el dato es $1098.00, el valor en rows debe ser 1098 (número entero), NO 1.098
- Si el dato es $53,402,980, el valor debe ser 53402980, NO 53.4
- Mantener los valores EXACTAMENTE como aparecen, solo quitar símbolos $ y comas
- Ejemplo: "$1,234.56" → 1234.56 (NO 1.234)

Responde SOLO JSON válido (sin markdown ni explicaciones):
{{"visualizable":true,"type":"bar","title":"...","xAxis":"col","yAxis":"col","xAxisLabel":"...","yAxisLabel":"...","series":[{{"name":"...","field":"col"}}],"groupBy":"col_opcional","legend":{{"show":false}},"data":{{"columns":["c1","c2"],"rows":[[v1,v2]]}},"isTop10":false,"totalRecords":N,"summary":"Resumen breve"}}

SOLO usa visualizable:false si no hay NINGÚN dato numérico.
"""
    
    try:
        print(f"\n[ANALYZE_VIZ] Starting visualization analysis...")
        print(f"[ANALYZE_VIZ] Raw data length: {len(raw_data)} chars")
        print(f"[ANALYZE_VIZ] Question: {question[:100]}...")
        
        llm = get_viz_llm()
        print(f"[ANALYZE_VIZ] LLM initialized, invoking prompt...")
        
        response = llm.invoke(viz_prompt)
        response_text = response.content.strip()
        
        print(f"[ANALYZE_VIZ] LLM response length: {len(response_text)} chars")
        print(f"[ANALYZE_VIZ] LLM response preview: {response_text[:300]}...")
        
        # Clean potential markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)
            print(f"[ANALYZE_VIZ] Cleaned markdown code blocks")
        
        # Try to find JSON object in the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            response_text = json_match.group(0)
            print(f"[ANALYZE_VIZ] Extracted JSON from response")
        
        print(f"[ANALYZE_VIZ] Parsing JSON...")
        viz_config = json.loads(response_text)
        print(f"[ANALYZE_VIZ] JSON parsed successfully!")
        
        # Validate required fields exist
        if "visualizable" not in viz_config:
            viz_config["visualizable"] = False
            print(f"[ANALYZE_VIZ] WARNING: visualizable field missing, defaulting to False")
        if "type" not in viz_config:
            viz_config["type"] = "none"
            print(f"[ANALYZE_VIZ] WARNING: type field missing, defaulting to none")
        
        print(f"[ANALYZE_VIZ] SUCCESS - visualizable: {viz_config.get('visualizable')}, type: {viz_config.get('type')}")
        if viz_config.get('data'):
            rows_count = len(viz_config.get('data', {}).get('rows', []))
            print(f"[ANALYZE_VIZ] Data rows count: {rows_count}")
        if viz_config.get('fullData'):
            full_rows_count = len(viz_config.get('fullData', {}).get('rows', []))
            print(f"[ANALYZE_VIZ] Full data rows count: {full_rows_count}")
            
        return viz_config
    except json.JSONDecodeError as je:
        print(f"\n[ANALYZE_VIZ] ERROR - JSON parse error: {je}")
        print(f"[ANALYZE_VIZ] Response text that failed: {response_text[:500]}...")
        return {"visualizable": False, "type": "none", "reason": f"JSON parse error: {str(je)[:100]}"}
    except Exception as e:
        print(f"\n[ANALYZE_VIZ] ERROR - Exception: {e}")
        import traceback
        traceback.print_exc()
        return {"visualizable": False, "type": "none", "reason": str(e)[:100]}


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
        
        print(f"\n[QUERY_DATABASE] Calling analyze_visualization...")
        
        # Analyze if the data can be visualized
        viz_config = analyze_visualization(raw_output, question)
        
        print(f"[QUERY_DATABASE] Visualization config type: {type(viz_config)}")
        print(f"[QUERY_DATABASE] Visualization config: {str(viz_config)[:500]}...")
        
        # Validate viz_config is a proper dict
        if not isinstance(viz_config, dict):
            print(f"[QUERY_DATABASE] WARNING: viz_config is not a dict, setting default")
            viz_config = {"visualizable": False, "type": "none", "reason": "Invalid visualization config"}
        
        # Build structured response with thinking chain
        response = {
            "text": raw_output,
            "visualization": viz_config,
            "thinking": thinking_steps
        }
        
        # Sanitize all strings in the response to ensure valid JSON
        response = sanitize_dict_for_json(response)
        
        # Return as JSON string wrapped in special markers for frontend parsing
        # Use compact JSON to reduce size and potential issues
        json_str = json.dumps(response, ensure_ascii=True, separators=(',', ':'))
        
        print(f"\n[QUERY_DATABASE] Final JSON length: {len(json_str)} chars")
        print(f"[QUERY_DATABASE] Visualizable: {viz_config.get('visualizable', False)}")
        print(f"[QUERY_DATABASE] Chart type: {viz_config.get('type', 'none')}")
        
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
            "text": f"Error querying database: {str(e)}",
            "visualization": {"visualizable": False, "type": "none"}
        }
        return f"<<<GENERATIVE_BI_START>>>\n{json.dumps(error_response, ensure_ascii=True)}\n<<<GENERATIVE_BI_END>>>"



root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction="""ROL: Eres un **Asistente Experto en SQL, Análisis de Compras y Gestión de Inventarios Eléctricos**. 

    Tu función es transformar las solicitudes de negocio del usuario en consultas SQL de lectura (SELECT) altamente optimizadas.

    # TAREAS Y RESTRICCIONES DE SEGURIDAD (MÁXIMA PRIORIDAD)

    1.  **Generación de SQL**: Generar **SOLO** consultas SQL de lectura (SELECT) en sintaxis PostgreSQL.

    2.  **Seguridad**: **NUNCA** bajo ninguna circunstancia generar ni ejecutar comandos destructivos: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.

    3.  **Manejo de Prohibición**: Si el usuario pide una acción destructiva, debes responder: "No estoy autorizado para modificar la base de datos. Solo puedo generar consultas de lectura (SELECT)."

    4.  **Nombres Exactos**: Siempre usa nombres de tablas y columnas **exactamente** como se definen en el esquema, respetando mayúsculas/minúsculas.

    # Instruccion clave:

    - Antes de generar cualquier consulta SQL, analiza cuidadosamente la solicitud del usuario para identificar las tablas, en algunos casos no tendras que hacer peticiones a la base de datos.

    - **PRIORIDAD ABSOLUTA**: Si la solicitud del usuario requiere datos de la base de datos (Ej: cantidades, unidades, precios), el agente **DEBE** ejecutar la secuencia de `query_database` y `JSON de respuesta` antes de cualquier explicación o resumen de tablas. **No te detengas a explicar los esquemas a menos que el usuario lo pida explícitamente.**

    TABLAS CLAVE:

    - **factura**: (PK: factura_id BIGINT) Clave para la fecha de compra.
      Columnas: **factura_id**, **numero** (número de factura), cufe, **fecha_emision** (TIMESTAMP - usar como fecha de compra), fecha_vencimiento (DATE), moneda, orden_compra, pedido, vendedor_nombre, vendedor_email, vendedor_telefono, **proveedor_id** (FK a proveedor), cliente_id, total_subtotal (NUMERIC), total_iva (NUMERIC), total_retefuente (NUMERIC), total_factura (NUMERIC), raw_xml, raw_pdf, origen_archivo, email_de, email_fecha, **project_id** (FK a projects).

    - **factura_detalle**: (PK: detalle_id BIGINT) Contiene los ítems y precios de cada factura.
      Columnas: **detalle_id**, **factura_id** (FK a factura), linea (orden del ítem), **cod_interno**, **descripcion**, **cantidad** (NUMERIC - cantidad comprada), **unidad**, **precio_unitario** (NUMERIC), descuento_pct (NUMERIC), subtotal (NUMERIC), iva_pct (NUMERIC), iva_valor (NUMERIC), total_linea (NUMERIC), std_scheme_id, std_scheme_name, std_code, **descripcion_estandarizada**, score_match_aceptado, **producto_estandarizado**, validado_manualmente (BOOLEAN).

    - **flujo_productos**: (PK: id INT) Movimientos físicos de productos.
      Columnas: **id**, **producto** (TEXT - descripción del ítem), **cantidad** (NUMERIC), **unidad** (TEXT - USAR SIEMPRE esta columna para conocer la unidad del movimiento), db_type, **sent_date** (TIMESTAMP - fecha del movimiento), metadata_id, **project_id** (FK a projects).

    - **projects**: (PK: project_id INT) Referencia de proyectos.
      Columnas: **project_id**, **nombre_proyecto** (VARCHAR), created_at (TIMESTAMP).
    
    - **proveedor**: (PK: proveedor_id BIGINT) Referencia de proveedores.
      Columnas: **proveedor_id**, **nit**, **razon_social** (usar como nombre del proveedor), telefono, email, direccion, ciudad, email_cotizaciones.

    - **cliente**: (PK: cliente_id BIGINT) Referencia de clientes.
      Columnas: **cliente_id**, **nit**, **razon_social**, telefono, email, direccion, ciudad.

    - **inventario**: (PK: id INT) Stock actual por proyecto.
      Columnas: **id**, **project_id** (FK a projects), **referencia**, **grupo**, **descripcion**, **unidad**, **cantidad** (NUMERIC - stock actual), created_at, update (DATE).

    - **presupuesto**: (PK: id INT) Presupuesto de materiales por proyecto.
      Columnas: **id**, **project_id** (FK a projects), **codigo**, **grupo**, **descripcion**, **unidad**, **cantidad** (NUMERIC - cantidad presupuestada), **precio** (NUMERIC), created_at.

    - **orden_compra**: (PK: id BIGINT) Órdenes de compra.
      Columnas: **id**, **orden_compra** (BIGINT - número de OC), **proyecto** (TEXT), **project_id** (FK a projects), created_at.

    - **almacenistas**: (PK: id INT) Asignación de almacenistas y líderes por proyecto.
      Columnas: **id**, **project_id** (FK a projects), **project** (TEXT - nombre), **almacenista_telegram_id**, **almacenista_name**, **lider_telegram_id**, **lider_name**, created_at.

    - **producto_conversion_unidad**: (PK: conversion_id BIGINT) Conversiones de unidades para productos.
      Columnas: **conversion_id**, **producto_estandarizado_pattern** (TEXT - patrón de producto), descripcion_pattern, **unidad_origen**, **unidad_destino**, **factor_conversion** (NUMERIC), descripcion_conversion, activo (BOOLEAN), created_at, updated_at.

    - **centro_costos**: (PK: cc VARCHAR(50)) Referencia de centros de costos.
      Columnas: **cc** (VARCHAR(50) - código del centro de costos, clave primaria), **nombre** (VARCHAR(255) - nombre del centro de costos), descripcion (TEXT), created_at (TIMESTAMP), updated_at (TIMESTAMP).

    - **ordenes_compra_cc**: (PK: id INT) Relación entre órdenes de compra y centros de costos.
      Columnas: **id** (INT - clave primaria auto-increment), **numero_oc** (VARCHAR(50) - número de orden de compra), **cc** (VARCHAR(50) - FK a centro_costos.cc), descripcion (TEXT), **fecha_creacion** (DATE), **estado** (VARCHAR(50) - estado de la orden), **monto** (NUMERIC(18,2) - monto asignado), created_at (TIMESTAMP), updated_at (TIMESTAMP).

    - **catalogo_maestro**: (PK: id INT) Catálogo maestro de productos relacionado a la tabla factura_detalle por el campo producto_estandarizado.
      Columnas: **id**, **producto_estandarizado** (TEXT - descripción del ítem), **grupo**, **descripcion**, **unidad**, **precio** (NUMERIC), created_at, updated_at.

    # REGLAS DE NEGOCIO Y LÓGICA DE CONSULTA ESPECÍFICA

    ## LÓGICA DE COMPRAS Y PRECIOS (factura_detalle & factura):

    - **Fecha Obligatoria**: Para cualquier consulta que requiera fecha (Últimos Precios, Histórico, Periodos), **DEBE** hacerse un **JOIN** entre `factura_detalle` y `factura` usando `factura_id`, y se debe usar **`factura.fecha_emision`**.

    - **Últimos Precios**: Usar `factura_detalle.precio_unitario` ordenando por `factura.fecha_emision` DESC y `LIMIT 1`.

    - **Búsqueda por Descripción (Ambigüedad CRÍTICA)**: Si el usuario busca un producto sin el `cod_interno`, el agente **DEBE** hacer una búsqueda en `factura_detalle.producto_estandarizado`.

      - **Detección de Ambigüedad**: Si la búsqueda devuelve **más de un `cod_interno` o descripción única**, el agente **NO DEBE REALIZAR MÁS CONSULTAS SQL**.

      - **Respuesta Única en Ambigüedad**: En caso de ambigüedad, el agente **DEBE** responder únicamente: "He encontrado múltiples coincidencias para '[término de búsqueda del usuario]' (ej. Tubo PVC). Por favor, aclare el código interno o especifique la descripción (ej. 'TUBO PVC 1/2 SCH 40') para poder procesar la consulta."

      - **Uso Escalar**: Solo si la búsqueda devuelve un **resultado único**, el agente puede proceder a usar ese `cod_interno` como valor escalar.

    ### REGLA DE FILTRO DE FECHA (PRECISIÓN HORARIA)

    - Para cualquier filtro que deba coincidir con una fecha específica ('hoy', 'ayer', 'fecha X'), se debe usar la sintaxis para ignorar el tiempo y la zona horaria: `columna_timestamp::date = valor_fecha`.

    - **Ejemplo (Factura)**: `factura.fecha_emision::date = CURRENT_DATE`

    - **Ejemplo (Movimiento)**: `flujo_productos.sent_date::date = CURRENT_DATE`

    ## CONSULTAS RÁPIDAS DE PRECIOS Y ESTADÍSTICAS (OPTIMIZADO):

    Cuando el usuario pida **precios de un producto con estadísticas descriptivas**, usar UNA SOLA consulta eficiente:

    ```sql
    SELECT 
        fd.producto_estandarizado AS producto,
        COUNT(*) AS num_compras,
        ROUND(AVG(fd.precio_unitario), 0) AS precio_promedio,
        MIN(fd.precio_unitario) AS precio_minimo,
        MAX(fd.precio_unitario) AS precio_maximo,
        ROUND(STDDEV(fd.precio_unitario), 2) AS desviacion_std,
        MIN(f.fecha_emision)::date AS primera_compra,
        MAX(f.fecha_emision)::date AS ultima_compra
    FROM factura_detalle fd
    JOIN factura f ON f.factura_id = fd.factura_id
    WHERE fd.producto_estandarizado ILIKE '%NOMBRE_PRODUCTO%'
    GROUP BY fd.producto_estandarizado;
    ```

    **Si necesita histórico por mes** (para gráficos de tendencia):
    ```sql
    SELECT 
        TO_CHAR(f.fecha_emision, 'YYYY-MM') AS mes,
        ROUND(AVG(fd.precio_unitario), 0) AS precio_promedio,
        MIN(fd.precio_unitario) AS precio_min,
        MAX(fd.precio_unitario) AS precio_max
    FROM factura_detalle fd
    JOIN factura f ON f.factura_id = fd.factura_id
    WHERE fd.producto_estandarizado ILIKE '%NOMBRE_PRODUCTO%'
    GROUP BY TO_CHAR(f.fecha_emision, 'YYYY-MM')
    ORDER BY mes;
    ```

    **IMPORTANTE**: 
    - Usar `ILIKE` para búsquedas flexibles (insensible a mayúsculas)
    - NO hacer múltiples consultas separadas - consolidar en UNA consulta
    - Preferir `producto_estandarizado` sobre `descripcion` para búsquedas
    - Los precios unitarios están en `factura_detalle.precio_unitario`

    ## LÓGICA DE INVENTARIO Y FLUJO (flujo_productos / factura):

    - **INGRESO (Adquisición/Compra)**: Se obtiene **SOLAMENTE** de `factura_detalle` y `factura`. Usa `SUM(factura_detalle.cantidad)`.

    - **SALIDA (Consumo/Uso)**: Se obtiene **SOLAMENTE** de `flujo_productos`. Usa `SUM(flujo_productos.cantidad)`.

    - **UNIDAD DE MEDIDA DE SALIDA**: La unidad de los productos consumidos (SALIDA) **DEBE** obtenerse **SIEMPRE** de la columna **`flujo_productos.unidad`**. Evitar JOINs a `producto_catalogo` para este dato de movimientos físicos.

    - **UNIDAD DE MEDIDA DE COMPRA**: Si la pregunta es sobre la unidad de un producto **adquirido** o de **catálogo** (sin referencia a un movimiento físico o consumo), la unidad se obtiene de **`producto_catalogo.unidad`**.

    - **Consolidación (Inventario Neto CRÍTICO)**: Para calcular el Inventario Neto (Compras - Consumo), el agente **DEBE** usar Common Table Expressions (CTEs) o Subconsultas anidadas.

    - **Paso 1: Búsqueda de IDs:** Primero, obtén el `cod_interno` del producto y el `project_id` del proyecto usando subconsultas escalares.

    - **Paso 2: CTE_COMPRA (INGRESO)**: Calcula `SUM(fd.cantidad)` filtrando por el `cod_interno` obtenido y el `project_id` de la `factura` (factura.project_id).

    - **Paso 3: CTE_CONSUMO (SALIDA) y UNIDAD**: Calcula `SUM(fp.cantidad)` y **el valor más común (o MAX/MIN) de `fp.unidad`** filtrando por producto y proyecto.

    - **Paso 4: Cálculo Final**: Une ambas CTEs conceptualmente y calcula la diferencia final. El SELECT final DEBE incluir la unidad obtenida en el Paso 3.

    - **PROHIBIDO**: NUNCA intentes correlacionar `factura_detalle` y `flujo_productos` en el mismo `JOIN` principal. Deben ser calculados como totales separados.

    ## LÓGICA DE CENTRO DE COSTOS (centro_costos & ordenes_compra_cc & factura) - CRÍTICO:

    - **FUENTE PRINCIPAL**: Usar `ordenes_compra_cc` como punto de partida para consultas de centro de costos por proyecto.
    - **PROHIBIDO**: NO usar `financiero_excel_diario` para consultas de centro de costos - tiene datos inconsistentes.
    - **PROHIBIDO**: NO usar `presupuesto.codigo = centro_costos.cc` - esta relación NO existe.

    ### ESTRUCTURA DE ordenes_compra_cc (IMPORTANTE):
    La tabla `ordenes_compra_cc` tiene las siguientes columnas:
    - `numero_oc`: Número de orden de compra (relaciona con `factura.orden_compra`)
    - `cc`: Código del centro de costos (relaciona con `centro_costos.cc`)
    - `proyecto`: Nombre del proyecto (USAR PARA FILTRAR POR PROYECTO)
    - `descripcion`, `fecha_creacion`, `estado`, `monto`

    - **Cadena de Relación CORRECTA** (USAR SIEMPRE):
      1. `ordenes_compra_cc.proyecto` → Filtrar por proyecto
      2. `ordenes_compra_cc.numero_oc` → `factura.orden_compra` (para obtener valores facturados)
      3. `ordenes_compra_cc.cc` → `centro_costos.cc` (para nombre del CC)

    ### CONSULTA PRINCIPAL - Centro de Costos con Valor Facturado por Proyecto:
    ```sql
    SELECT 
        oc.cc AS codigo_cc,
        cc.nombre AS centro_costo,
        oc.proyecto,
        COUNT(DISTINCT oc.numero_oc) AS total_ordenes_compra,
        COUNT(DISTINCT f.factura_id) AS total_facturas,
        COALESCE(SUM(f.total_factura), 0) AS valor_facturado
    FROM ordenes_compra_cc oc
    LEFT JOIN centro_costos cc ON cc.cc = oc.cc
    LEFT JOIN factura f ON f.orden_compra = oc.numero_oc
    WHERE oc.proyecto ILIKE '%nombre_proyecto%'
    GROUP BY oc.cc, cc.nombre, oc.proyecto
    ORDER BY valor_facturado DESC;
    ```

    ### CONSULTA DETALLADA - Facturas por Centro de Costo y Proyecto:
    ```sql
    SELECT 
        oc.cc AS codigo_cc,
        cc.nombre AS centro_costo,
        oc.numero_oc,
        f.numero AS numero_factura,
        f.fecha_emision,
        f.total_factura AS valor_factura,
        p.razon_social AS proveedor
    FROM ordenes_compra_cc oc
    LEFT JOIN centro_costos cc ON cc.cc = oc.cc
    LEFT JOIN factura f ON f.orden_compra = oc.numero_oc
    LEFT JOIN proveedor p ON p.proveedor_id = f.proveedor_id
    WHERE oc.proyecto ILIKE '%nombre_proyecto%'
      AND f.factura_id IS NOT NULL
    ORDER BY cc.nombre, f.fecha_emision DESC;
    ```

    ### CONSULTA - Resumen de Centro de Costos con OC sin facturar:
    ```sql
    SELECT 
        oc.cc AS codigo_cc,
        cc.nombre AS centro_costo,
        oc.proyecto,
        COUNT(DISTINCT oc.numero_oc) AS total_oc,
        COUNT(DISTINCT CASE WHEN f.factura_id IS NOT NULL THEN oc.numero_oc END) AS oc_facturadas,
        COUNT(DISTINCT CASE WHEN f.factura_id IS NULL THEN oc.numero_oc END) AS oc_sin_facturar,
        COALESCE(SUM(f.total_factura), 0) AS valor_facturado
    FROM ordenes_compra_cc oc
    LEFT JOIN centro_costos cc ON cc.cc = oc.cc
    LEFT JOIN factura f ON f.orden_compra = oc.numero_oc
    WHERE oc.proyecto ILIKE '%nombre_proyecto%'
    GROUP BY oc.cc, cc.nombre, oc.proyecto
    ORDER BY valor_facturado DESC;
    ```

    ### CONSULTA - Filtrar por período de facturación:
    ```sql
    SELECT 
        oc.cc AS codigo_cc,
        cc.nombre AS centro_costo,
        COUNT(DISTINCT f.factura_id) AS total_facturas,
        SUM(f.total_factura) AS valor_facturado
    FROM ordenes_compra_cc oc
    LEFT JOIN centro_costos cc ON cc.cc = oc.cc
    LEFT JOIN factura f ON f.orden_compra = oc.numero_oc
    WHERE oc.proyecto ILIKE '%nombre_proyecto%'
      AND f.fecha_emision >= CURRENT_DATE - INTERVAL '3 months'
    GROUP BY oc.cc, cc.nombre
    ORDER BY valor_facturado DESC;
    ```

    - **Filtros Temporales** (usar `factura.fecha_emision` cuando se necesite filtrar por fecha): 
      - "última semana": `f.fecha_emision >= CURRENT_DATE - INTERVAL '7 days'`
      - "último mes": `f.fecha_emision >= CURRENT_DATE - INTERVAL '1 month'`
      - "últimos 3 meses": `f.fecha_emision >= CURRENT_DATE - INTERVAL '3 months'`
      - "este año": `f.fecha_emision >= DATE_TRUNC('year', CURRENT_DATE)`

    ### RESPUESTA CUANDO NO HAY FACTURAS PERO SÍ OC:
    Si hay órdenes de compra pero no facturas asociadas, informar:
    - Cuántas OC tiene el proyecto por centro de costos
    - Que no se han recibido facturas para esas OC
    - Mostrar el valor presupuestado (oc.monto) si está disponible

    ### REGLAS DE RESPUESTA Y FORMATO (CRÍTICO) 

    - **INCLUIR CENTRO DE COSTOS SOLO CUANDO SEA RELEVANTE**: 
      - **INCLUIR** centro de costos cuando:
        * El usuario pregunta explícitamente por centro de costos
        * Se consultan facturas agrupadas por proyecto o centro de costos
        * Se necesita información de proyecto y centro de costos para el análisis
      - **NO INCLUIR** centro de costos cuando:
        * La consulta es simple (facturas por cliente, proveedor, período sin mención de proyecto/CC)
        * Se consultan totales o resúmenes por cliente/proveedor sin necesidad de desglose por CC
        * El usuario no menciona proyecto ni centro de costos en su pregunta
      
      **Ejemplo cuando SÍ incluir CC** (consulta por proyecto o CC):
      ```sql
      SELECT DISTINCT
          f.numero AS numero_factura,
          f.fecha_emision,
          f.total_factura,
          p.razon_social AS proveedor,
          COALESCE(oc.proyecto, 'Sin proyecto') AS proyecto,
          COALESCE(cc.nombre, 'Sin CC asignado') AS centro_costo
      FROM factura f
      LEFT JOIN proveedor p ON p.proveedor_id = f.proveedor_id
      LEFT JOIN ordenes_compra_cc oc ON oc.numero_oc = f.orden_compra
      LEFT JOIN centro_costos cc ON cc.cc = oc.cc
      ORDER BY f.fecha_emision DESC
      LIMIT 20;
      ```
      
      **Ejemplo cuando NO incluir CC** (consulta simple por cliente/proveedor):
      ```sql
      SELECT 
          f.numero AS numero_factura,
          f.fecha_emision,
          f.total_factura,
          p.razon_social AS proveedor
      FROM factura f
      LEFT JOIN proveedor p ON p.proveedor_id = f.proveedor_id
      LEFT JOIN cliente c ON c.cliente_id = f.cliente_id
      WHERE c.razon_social ILIKE '%nombre_cliente%'
      ORDER BY f.fecha_emision DESC;
      ```
      
      **IMPORTANTE**: El nombre del proyecto está en `ordenes_compra_cc.proyecto`, NO usar `projects.nombre_proyecto` porque `factura.project_id` puede ser NULL.
      La relación correcta es: `factura.orden_compra` → `ordenes_compra_cc.numero_oc` → obtener `oc.proyecto` y `cc.nombre`

    - **Consolidación de Resultados**: Si se requieren **múltiples consultas SQL** para responder una sola pregunta del usuario, el agente **DEBE** consolidar todos los resultados presentando un único resumen al usuario.

    - **Unidad de Medida**: Para consultas que sumen cantidades (totales, neto, etc.), el agente **DEBE** incluir la unidad de medida obtenida de la tabla de origen para contextualizar al usuario (ej. "56,374 metros", "16,674 unidades").

    - **FORMATO DE NÚMEROS MONETARIOS**: 
      - Todos los valores monetarios (total_factura, total_compras, precio, monto, etc.) **DEBEN** mostrarse SIN decimales
      - Usar formato con separadores de miles: ej. "53,402,980" en lugar de "53402979.67"
      - Redondear al entero más cercano antes de formatear
      - Ejemplo correcto: "**ELECTRICIDAD Y MONTAJES S.A.S.**: $53,402,980"
      - Ejemplo incorrecto: "**ELECTRICIDAD Y MONTAJES S.A.S.**: 53402979.67"

    - **FORMATO DE MARKDOWN**:
      - Usar listas ordenadas o no ordenadas para presentar datos tabulares
      - Usar **negritas** para nombres de categorías (proveedores, productos, etc.)
      - Usar formato consistente: `**Nombre**: $Valor` o `**Nombre**: Valor unidades`
      - Separar visualmente con líneas en blanco entre secciones
      - Si hay Top 10, mencionarlo claramente al inicio: "Top 10 Proveedores por Compras:"

    ## OPTIMIZACIÓN DE DATOS PARA CONSULTAS EXTENSAS (CRÍTICO)

    Cuando una consulta potencialmente devuelve **muchos registros** (más de 20-30 filas), el agente **DEBE** optimizar la respuesta usando estadísticas y resúmenes en lugar de traer todos los datos crudos.

    ### ESTRATEGIA DE RESUMEN ESTADÍSTICO:
    
    Para consultas que podrían devolver muchos registros, usar esta estructura:
    ```sql
    SELECT 
        -- Estadísticas agregadas
        COUNT(*) AS total_registros,
        COUNT(DISTINCT campo_agrupacion) AS categorias_unicas,
        SUM(campo_numerico) AS suma_total,
        ROUND(AVG(campo_numerico), 2) AS promedio,
        MIN(campo_numerico) AS valor_minimo,
        MAX(campo_numerico) AS valor_maximo,
        ROUND(STDDEV(campo_numerico), 2) AS desviacion_estandar,
        -- Rangos de fecha si aplica
        MIN(fecha_campo)::date AS fecha_inicio,
        MAX(fecha_campo)::date AS fecha_fin
    FROM tabla
    WHERE condiciones;
    ```

    ### PATRONES DE OPTIMIZACIÓN POR TIPO DE CONSULTA:

    **1. Listado de Facturas (muchas)** → Agrupar por proveedor/proyecto/período:
    ```sql
    SELECT 
        p.razon_social AS proveedor,
        COUNT(f.factura_id) AS num_facturas,
        SUM(f.total_factura) AS total_compras,
        MIN(f.total_factura) AS factura_minima,
        MAX(f.total_factura) AS factura_maxima,
        ROUND(AVG(f.total_factura), 0) AS factura_promedio,
        MIN(f.fecha_emision)::date AS primera_factura,
        MAX(f.fecha_emision)::date AS ultima_factura
    FROM factura f
    JOIN proveedor p ON p.proveedor_id = f.proveedor_id
    GROUP BY p.razon_social
    ORDER BY total_compras DESC
    LIMIT 15;
    ```

    **2. Productos/Items (muchos)** → Top 10 + estadísticas:
    ```sql
    WITH stats AS (
        SELECT 
            COUNT(*) AS total_items,
            SUM(total_linea) AS valor_total,
            ROUND(AVG(precio_unitario), 2) AS precio_promedio
        FROM factura_detalle
    )
    SELECT 
        fd.producto_estandarizado,
        COUNT(*) AS veces_comprado,
        SUM(fd.cantidad) AS cantidad_total,
        SUM(fd.total_linea) AS valor_total,
        MIN(fd.precio_unitario) AS precio_minimo,
        MAX(fd.precio_unitario) AS precio_maximo,
        ROUND(AVG(fd.precio_unitario), 0) AS precio_promedio
    FROM factura_detalle fd
    GROUP BY fd.producto_estandarizado
    ORDER BY valor_total DESC
    LIMIT 10;
    -- Agregar: "Mostrando Top 10 de N productos totales"
    ```

    **3. Histórico de Precios (extenso)** → Resumen por período:
    ```sql
    SELECT 
        DATE_TRUNC('month', f.fecha_emision) AS periodo,
        COUNT(*) AS num_compras,
        ROUND(AVG(fd.precio_unitario), 0) AS precio_promedio,
        MIN(fd.precio_unitario) AS precio_minimo,
        MAX(fd.precio_unitario) AS precio_maximo,
        SUM(fd.cantidad) AS cantidad_total
    FROM factura_detalle fd
    JOIN factura f ON f.factura_id = fd.factura_id
    WHERE fd.producto_estandarizado ILIKE '%producto%'
    GROUP BY DATE_TRUNC('month', f.fecha_emision)
    ORDER BY periodo DESC;
    ```

    **4. Centro de Costos (múltiples)** → Resumen consolidado:
    ```sql
    SELECT 
        COUNT(DISTINCT oc.cc) AS total_centros_costo,
        COUNT(DISTINCT oc.numero_oc) AS total_ordenes,
        COUNT(DISTINCT f.factura_id) AS total_facturas,
        SUM(f.total_factura) AS valor_total_facturado,
        ROUND(AVG(f.total_factura), 0) AS factura_promedio
    FROM ordenes_compra_cc oc
    LEFT JOIN factura f ON f.orden_compra = oc.numero_oc
    WHERE oc.proyecto ILIKE '%proyecto%';
    ```

    ### REGLAS DE OPTIMIZACIÓN:

    1. **NUNCA traer más de 50 registros individuales** - usar agregaciones y Top N
    2. **SIEMPRE incluir conteo total** cuando muestres Top N: "Mostrando Top 10 de 847 registros"
    3. **PREFERIR resúmenes estadísticos**: COUNT, SUM, AVG, MIN, MAX, STDDEV
    4. **AGRUPAR por categorías relevantes**: proveedor, proyecto, centro de costo, mes/año
    5. **INCLUIR rangos de fechas** cuando el período sea extenso
    6. **CALCULAR porcentajes** cuando sea útil para el análisis: `ROUND(valor * 100.0 / SUM(valor) OVER(), 2) AS porcentaje`
    
    ### FORMATO DE RESPUESTA OPTIMIZADA:

    Cuando uses resúmenes, presentar así:
    ```
    ## Resumen de [Tema] - [Período]

    **Estadísticas Generales:**
    - Total de registros: X
    - Suma total: $Y
    - Promedio: $Z
    - Rango: $Min - $Max

    **Top 10 por [Criterio]:**
    1. **Categoría A**: $Valor (X%)
    2. **Categoría B**: $Valor (Y%)
    ...
    
    *Nota: Mostrando Top 10 de N registros totales*
    ```

    ## GENERATIVE BI - VISUALIZACIÓN DE DATOS

    La herramienta `query_database` ahora devuelve datos estructurados con configuración de visualización automática. El sistema:

    1. **Analiza automáticamente** los resultados de la consulta SQL
    2. **Determina el mejor tipo de gráfico** basándose en los datos:
       - Comparaciones entre categorías → Gráfico de barras
       - Series temporales → Gráfico de líneas
       - Proporciones del total → Gráfico de pie
       - Datos detallados → Tabla interactiva
    3. **Genera configuración de ECharts** para el frontend

    **IMPORTANTE para el formato de respuesta**:
    - La respuesta de `query_database` incluye un bloque JSON marcado con delimitadores especiales
    - El frontend detectará este bloque y renderizará automáticamente las visualizaciones
    - NO modifiques ni elimines este bloque JSON de la respuesta
    - Puedes agregar explicaciones adicionales ANTES o DESPUÉS del bloque, pero mantén el JSON intacto

    OPTIMIZACIÓN:
    - Usar LIMIT 50 por defecto para todas las consultas, para evitar respuestas demasiado largas sin embargo mencionar que es top 50.

    - Evitar SELECT * si no es necesario.

    Usa la herramienta `query_database` para ejecutar consultas en la base de datos PostgreSQL.
    """,
    tools=[query_database]
)

app = App(root_agent=root_agent, name="app")

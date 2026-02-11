import re
import time
from typing import Optional, Dict, Any, List

def analyze_visualization(raw_data: str, question: str) -> Dict[str, Any]:
    """
    Fast, deterministic visualization analysis WITHOUT LLM calls.
    Uses regex patterns and heuristics to detect chart types.
    """
    start_time = time.time()
    
    if len(raw_data.strip()) < 30:
        return {"visualizable": False, "type": "none", "reason": "Insufficient data"}
    
    rows = []
    columns = []
    
    # Pattern 1: Markdown bullet list with values
    bullet_pattern = r'\*\s*\*\*([^*]+)\*\*[:\s]+\$?([\d.,]+)'
    bullet_matches = re.findall(bullet_pattern, raw_data)
    
    if bullet_matches:
        columns = ["categoria", "valor"]
        for label, value in bullet_matches:
            try:
                num_val = _parse_number(value)
                if num_val > 0:
                    rows.append([label.strip(), num_val])
            except (ValueError, OverflowError):
                continue
    
    # Pattern 2: Temporal data fallback
    if len(rows) < 2:
        month_value_pattern = r'(?:Mes|Periodo|Fecha)[:\s]+([\d]{4}-[\d]{2}|[\w]+\s+\d{4})[^\d]*(?:Total|Monto|Valor)[:\s]+\$?([\d.,]+)'
        temporal_matches = re.findall(month_value_pattern, raw_data, re.IGNORECASE)
        if temporal_matches:
            columns = ["periodo", "total"]
            for period, value in temporal_matches:
                try:
                    num_val = _parse_number(value)
                    if num_val > 0:
                        rows.append([period.strip(), num_val])
                except (ValueError, OverflowError):
                    continue
    
    if len(rows) < 2:
        return extract_visualization_from_text(raw_data, question)
    
    return _build_viz_config(rows, columns, question, start_time)

def extract_visualization_from_text(raw_data: str, question: str) -> Dict[str, Any]:
    """Fallback extraction for grouped record formats."""
    rows = []
    
    month_pattern = r'(?:Mes|Periodo|Fecha)[:\s]+(\d{4}-\d{2}|\d{4}/\d{2}|[A-Za-záéíóúñ]+\s+\d{4})'
    value_pattern = r'(?:Total de compras|Total facturado|Monto|Total)[:\s]+\$?([\d.,]+)'
    
    months = re.findall(month_pattern, raw_data, re.IGNORECASE)
    values = re.findall(value_pattern, raw_data, re.IGNORECASE)
    
    if months and values and len(months) == len(values):
        for month, value in zip(months, values):
            try:
                num_val = _parse_number(value)
                if num_val > 0:
                    rows.append([month, num_val])
            except (ValueError, OverflowError):
                continue
    
    if len(rows) < 2:
        return {"visualizable": False, "type": "none", "reason": "Could not extract data"}
    
    return _build_viz_config(rows, ["periodo", "total"], question, time.time())

def _parse_number(value: str) -> float:
    """Helper to clean and parse numbers in various formats."""
    if ',' in value and '.' in value:
        clean_val = value.replace(',', '')
    elif '.' in value and value.count('.') > 1:
        clean_val = value.replace('.', '')
    else:
        clean_val = value.replace(',', '').replace('.', '')
    return float(clean_val)

def _build_viz_config(rows: List[List[Any]], columns: List[str], question: str, start_time: float) -> Dict[str, Any]:
    """Helper to construct the final visualization dictionary."""
    temporal_keywords = ['mes', 'mensual', 'año', 'anual', 'fecha', 'período', 'tendencia', '2024', '2025', '2026']
    is_temporal = any(kw in question.lower() or kw in str(rows).lower() for kw in temporal_keywords)
    
    num_items = len(rows)
    if is_temporal:
        chart_type = "line"
        rows.sort(key=lambda x: x[0])
        max_display = 36
    elif num_items <= 6:
        chart_type = "pie"
        max_display = 12
    else:
        chart_type = "bar"
        rows.sort(key=lambda x: x[1], reverse=True)
        max_display = 12
        
    display_rows = rows[:max_display]
    
    return {
        "visualizable": True,
        "type": chart_type,
        "title": "Tendencia por Período" if is_temporal else f"Top {columns[0].title()}",
        "xAxis": columns[0],
        "yAxis": columns[1] if len(columns) > 1 else "valor",
        "data": {"columns": columns, "rows": display_rows},
        "totalRecords": num_items,
        "elapsedMs": (time.time() - start_time) * 1000
    }

def generate_conclusion(data: Dict[str, Any], question: str) -> str:
    """Generates a natural language summary from extracted data."""
    if not data or 'rows' not in data or not data['rows']:
        return "No se encontraron datos."
    
    num_records = len(data['rows'])
    if num_records == 1:
        return "Se encontró 1 registro que coincide con tu búsqueda."
    return f"Se encontraron {num_records} registros en total."

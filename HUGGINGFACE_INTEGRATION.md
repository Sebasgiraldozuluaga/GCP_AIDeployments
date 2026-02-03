# Integración de Hugging Face MCP

Este documento describe la integración del servidor MCP (Model Context Protocol) de Hugging Face en el agente.

## Descripción General

La integración permite al agente buscar y explorar recursos del Hugging Face Hub, incluyendo:

- **Modelos**: Modelos pre-entrenados de IA (transformers, diffusion, etc.)
- **Datasets**: Conjuntos de datos para entrenamiento y evaluación
- **Spaces**: Aplicaciones interactivas (Gradio, Streamlit)

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                     Google ADK Agent                         │
│                  (Gemini 2.5 Flash)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────┐         ┌──────────────────┐
│query_database│         │ HF MCP Tools     │
│     Tool     │         │ (5 herramientas) │
└──────────────┘         └────────┬─────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │ HF MCP Client      │
                         │ (hf_mcp_client.py) │
                         └────────┬───────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │ Hugging Face API   │
                         │ huggingface.co/api │
                         └────────────────────┘
```

## Componentes

### 1. Cliente MCP (`app/hf_mcp_client.py`)

Cliente HTTP asíncrono que se comunica con la API de Hugging Face:

- **HuggingFaceMCPClient**: Clase principal del cliente
- Métodos de búsqueda para modelos, datasets y spaces
- Gestión de autenticación con token de HF
- Manejo de errores y logging

### 2. Tools del Agente (`app/hf_tools.py`)

Funciones wrapper que exponen las capacidades del cliente como herramientas del agente:

#### `search_hf_models(query, limit, task, library)`
Busca modelos de IA en el Hub.

**Parámetros:**
- `query` (str): Consulta de búsqueda
- `limit` (int): Máximo de resultados (default: 5, max: 20)
- `task` (str, opcional): Filtro por tarea (e.g., "text-classification")
- `library` (str, opcional): Filtro por librería (e.g., "transformers")

**Retorna:** JSON con información de modelos

**Ejemplo:**
```python
search_hf_models("sentiment analysis spanish", limit=10)
```

#### `search_hf_datasets(query, limit, task)`
Busca datasets en el Hub.

**Parámetros:**
- `query` (str): Consulta de búsqueda
- `limit` (int): Máximo de resultados (default: 5, max: 20)
- `task` (str, opcional): Filtro por tarea

**Retorna:** JSON con información de datasets

**Ejemplo:**
```python
search_hf_datasets("spanish news articles", task="text-classification")
```

#### `search_hf_spaces(query, limit, sdk)`
Busca Spaces (aplicaciones ML) en el Hub.

**Parámetros:**
- `query` (str): Consulta de búsqueda
- `limit` (int): Máximo de resultados (default: 5, max: 20)
- `sdk` (str, opcional): Filtro por SDK ("gradio", "streamlit", "docker", "static")

**Retorna:** JSON con información de Spaces

**Ejemplo:**
```python
search_hf_spaces("chatbot", sdk="gradio")
```

#### `get_hf_model_details(model_id)`
Obtiene información detallada de un modelo específico.

**Parámetros:**
- `model_id` (str): ID completo del modelo (e.g., "meta-llama/Llama-2-7b-hf")

**Retorna:** JSON con información detallada del modelo

**Ejemplo:**
```python
get_hf_model_details("bert-base-uncased")
```

#### `get_hf_dataset_details(dataset_id)`
Obtiene información detallada de un dataset específico.

**Parámetros:**
- `dataset_id` (str): ID completo del dataset (e.g., "squad")

**Retorna:** JSON con información detallada del dataset

**Ejemplo:**
```python
get_hf_dataset_details("squad")
```

### 3. Integración con el Agente (`app/agent.py`)

Los tools están registrados en el agente principal:

```python
root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction="""...""",
    tools=[
        query_database,
        search_hf_models,
        search_hf_datasets,
        search_hf_spaces,
        get_hf_model_details,
        get_hf_dataset_details
    ]
)
```

## Configuración

### 1. Variables de Entorno

Agrega a tu archivo `.env`:

```bash
# Token de Hugging Face (requerido)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# URL del servidor MCP (opcional, default: https://huggingface.co/mcp)
# HF_MCP_URL=https://huggingface.co/mcp
```

### 2. Obtener Token de Hugging Face

1. Ve a https://huggingface.co/settings/tokens
2. Crea un nuevo token de tipo **"Read"** (no necesitas "Write")
3. Copia el token y agrégalo a tu `.env`

### 3. GitHub Actions Secrets

Para deployment en Cloud Run, agrega el secret:

```
HF_TOKEN = tu_token_aquí
```

En `.github/workflows/deploy-cloud-run.yml`, el token se configura automáticamente.

### 4. Instalación de Dependencias

```bash
# Instalar nuevas dependencias
uv sync

# O con pip
pip install httpx
```

## Uso

### Desde el Agente

El agente puede usar automáticamente las herramientas cuando detecta consultas relevantes:

**Usuario:** "Busca modelos de análisis de sentimiento en español"

**Agente:** (Automáticamente llama a `search_hf_models("spanish sentiment analysis")`)

**Usuario:** "¿Qué datasets de QA en español existen?"

**Agente:** (Llama a `search_hf_datasets("spanish qa")`)

### Directamente desde Código

```python
from app.hf_tools import search_hf_models, get_hf_model_details

# Buscar modelos
result = search_hf_models(
    query="image generation",
    limit=10,
    task="text-to-image"
)
print(result)

# Obtener detalles de un modelo
details = get_hf_model_details("stabilityai/stable-diffusion-xl-base-1.0")
print(details)
```

## Estructura de Respuestas

### Búsqueda de Modelos

```json
{
  "success": true,
  "count": 5,
  "query": "sentiment analysis",
  "models": [
    {
      "id": "distilbert-base-uncased-finetuned-sst-2-english",
      "name": "distilbert-base-uncased-finetuned-sst-2-english",
      "description": "DistilBERT model fine-tuned on SST-2...",
      "downloads": 12500000,
      "likes": 350,
      "tasks": "text-classification",
      "library": "transformers",
      "url": "https://huggingface.co/distilbert-base-uncased-finetuned-sst-2-english"
    }
  ]
}
```

### Búsqueda de Datasets

```json
{
  "success": true,
  "count": 3,
  "query": "spanish qa",
  "datasets": [
    {
      "id": "squad_es",
      "name": "squad_es",
      "description": "Spanish version of SQuAD dataset...",
      "downloads": 45000,
      "likes": 25,
      "tasks": ["question-answering"],
      "url": "https://huggingface.co/datasets/squad_es"
    }
  ]
}
```

### Búsqueda de Spaces

```json
{
  "success": true,
  "count": 2,
  "query": "chatbot",
  "spaces": [
    {
      "id": "huggingface-projects/llama-2-7b-chat",
      "name": "llama-2-7b-chat",
      "description": "Chat with Llama 2 model...",
      "sdk": "gradio",
      "likes": 1200,
      "url": "https://huggingface.co/spaces/huggingface-projects/llama-2-7b-chat"
    }
  ]
}
```

## Optimizaciones Implementadas

### 1. Cliente Singleton
- Una única instancia del cliente HTTP reutilizada
- Evita overhead de múltiples conexiones
- Gestión eficiente de recursos

### 2. Arquitectura Síncrona Simple
- Cliente HTTP síncrono con `httpx.Client`
- Sin complejidad de async/await innecesaria
- Compatible nativamente con Google ADK tools (síncronos)
- Funciona en cualquier contexto sin problemas de event loop

### 3. Validación de Parámetros
- Límites de resultados (max 20)
- Validación de entradas
- Manejo robusto de errores

### 4. Logging y Observabilidad
- Logging estructurado de todas las operaciones
- Tracking de errores y excepciones
- Compatible con Cloud Logging

### 5. Formato de Respuestas
- Respuestas JSON estructuradas
- Información relevante sin sobrecarga
- Descripción truncada (200 caracteres)
- URLs directas a recursos

### 6. Caché (Futuro)
El cliente está diseñado para soportar caché:
```python
# Futuro: agregar caché LRU
from functools import lru_cache

@lru_cache(maxsize=128)
def search_hf_models_cached(...):
    pass
```

## Testing

### Test Básico

```python
import asyncio
from app.hf_mcp_client import HuggingFaceMCPClient

async def test_client():
    async with HuggingFaceMCPClient() as client:
        # Test búsqueda de modelos
        result = await client.search_models("bert")
        print(result)

        # Test info de modelo
        info = await client.get_model_info("bert-base-uncased")
        print(info)

asyncio.run(test_client())
```

### Test de Tools

```python
from app.hf_tools import search_hf_models, search_hf_datasets

# Test búsqueda
models = search_hf_models("sentiment analysis", limit=5)
print(models)

# Test datasets
datasets = search_hf_datasets("spanish", limit=3)
print(datasets)
```

## Troubleshooting

### ✅ Event Loop Errors (Completamente Resueltos)

**v1.2**: Los errores de event loop han sido completamente eliminados al cambiar a arquitectura síncrona pura.

- ❌ "asyncio.run() cannot be called from a running event loop" → **Resuelto**
- ❌ "Event loop is closed" → **Resuelto**

**Solución implementada**: Cliente HTTP completamente síncrono (`httpx.Client`), sin async/await.

### Error: "Missing HF_TOKEN"

**Solución:** Asegúrate de que `HF_TOKEN` esté configurado en `.env`:
```bash
export HF_TOKEN=hf_xxxxxxxxxxxxx
```

### Error: "Request timeout"

**Solución:** Aumenta el timeout en el cliente:
```python
client = HuggingFaceMCPClient(timeout=60)
```

### Error: "Unauthorized"

**Solución:** Verifica que tu token sea válido:
1. Ve a https://huggingface.co/settings/tokens
2. Regenera el token si es necesario
3. Actualiza `.env`

### El agente no usa los tools de HF

**Solución:** Asegúrate de que:
1. Los tools estén importados en `agent.py`
2. Los tools estén en la lista de `tools=[]` del agente
3. El query del usuario mencione modelos/datasets/Hugging Face

## Próximos Pasos (Opcional)

### 1. Caché de Resultados
Implementar caché LRU para búsquedas frecuentes:
```python
from functools import lru_cache
```

### 2. Streaming de Resultados
Para búsquedas muy grandes, implementar streaming:
```python
async def search_models_stream(...):
    async for batch in client.search_paginated(...):
        yield batch
```

### 3. Integración con Gradio Spaces
Permitir al agente ejecutar funciones de Spaces Gradio:
```python
async def run_gradio_space(space_id, inputs):
    # Llamar API de Gradio del Space
    pass
```

### 4. Monitoreo y Métricas
Agregar tracking de uso:
```python
from opentelemetry import metrics

hf_requests_counter = metrics.get_meter(__name__).create_counter(
    "hf_mcp_requests_total"
)
```

## Referencias

- **Hugging Face MCP Server**: https://huggingface.co/docs/hub/en/hf-mcp-server
- **Building HF MCP Blog**: https://huggingface.co/blog/building-hf-mcp
- **HF Hub API Docs**: https://huggingface.co/docs/hub/api
- **Google ADK Docs**: https://cloud.google.com/products/ai/agent-development-kit

## Soporte

Para problemas o preguntas:
1. Revisa los logs en Cloud Logging
2. Verifica la configuración de variables de entorno
3. Consulta la documentación de HF MCP: https://hf.co/mcp

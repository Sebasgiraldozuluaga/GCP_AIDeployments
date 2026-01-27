# Quick Start - Hugging Face MCP Integration

Guía rápida para configurar la integración de Hugging Face MCP en el agente.

## 🚀 Configuración en 3 Pasos

### 1️⃣ Obtener Token de Hugging Face

1. Ve a: https://huggingface.co/settings/tokens
2. Click en **"New token"**
3. Configuración:
   - Name: `github-mcp-integration`
   - Type: **Read** ✅
4. Click **"Generate"** y copia el token (empieza con `hf_`)

### 2️⃣ Agregar Secret en GitHub

**Opción A - Desde GitHub UI:**
1. Ve a tu repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Name: `HF_TOKEN`
4. Value: tu token de HF (pegarlo completo)
5. Click **"Add secret"**

**Opción B - Desde Terminal (GitHub CLI):**
```bash
gh secret set HF_TOKEN -b "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 3️⃣ Deploy Automático

```bash
git add .
git commit -m "Enable Hugging Face MCP integration"
git push origin main
```

El workflow de GitHub Actions automáticamente:
- ✅ Valida que HF_TOKEN esté configurado
- ✅ Deploya a Cloud Run con la integración habilitada
- ✅ Verifica que todo funcione correctamente

## 📋 Verificar que Funciona

Después del deployment, revisa los logs en GitHub Actions. Deberías ver:

```
✅ Hugging Face MCP token configured
✅ Hugging Face MCP integration enabled
🔧 Enabled Features:
   ✅ PostgreSQL Database
   ✅ Gemini 2.5 Flash (Vertex AI)
   ✅ Hugging Face MCP Integration
      • search_hf_models
      • search_hf_datasets
      • search_hf_spaces
      • get_hf_model_details
      • get_hf_dataset_details
```

## 🧪 Probar Localmente (Opcional)

### 1. Configurar .env local
```bash
# Copia el ejemplo
cp env.example .env

# Edita .env y agrega:
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Instalar dependencias
```bash
uv sync
```

### 3. Ejecutar ejemplos
```bash
python examples/hf_mcp_example.py
```

## 🎯 Capacidades Habilitadas

Con esta integración, tu agente puede:

| Tool | Descripción | Ejemplo |
|------|-------------|---------|
| `search_hf_models` | Buscar modelos de IA | "Busca modelos de sentiment analysis" |
| `search_hf_datasets` | Buscar datasets | "¿Qué datasets de QA existen?" |
| `search_hf_spaces` | Buscar apps Gradio/Streamlit | "Encuentra chatbots en Hugging Face" |
| `get_hf_model_details` | Info detallada de un modelo | "Detalles de bert-base-uncased" |
| `get_hf_dataset_details` | Info detallada de un dataset | "Información del dataset squad" |

## 🔍 Troubleshooting

### ⚠️ "Hugging Face MCP integration disabled"

**Causa**: Secret `HF_TOKEN` no está configurado

**Solución**:
1. Verifica en GitHub: Settings → Secrets → Actions
2. Debe existir un secret llamado `HF_TOKEN`
3. Si no existe, agrégalo (ver paso 2 arriba)

### ❌ Workflow falla con "HF_TOKEN secret is not configured"

**Causa**: Validación falló, no hay token

**Solución**:
1. Agrega el secret `HF_TOKEN` en GitHub
2. Haz un nuevo push para re-ejecutar el workflow

### ⚠️ Las herramientas HF no funcionan en local

**Causa**: Variable de entorno `HF_TOKEN` no configurada

**Solución**:
```bash
# Opción 1: Agregar a .env
echo "HF_TOKEN=hf_xxxxxxxxxxxxx" >> .env

# Opción 2: Export temporal
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 📚 Documentación Completa

Para más detalles, consulta:

- **Integración técnica**: [HUGGINGFACE_INTEGRATION.md](HUGGINGFACE_INTEGRATION.md)
- **Configuración de secrets**: [.github/SECRETS_SETUP.md](.github/SECRETS_SETUP.md)
- **Workflow de deployment**: [.github/workflows/deploy-cloud-run.yml](.github/workflows/deploy-cloud-run.yml)

## ✅ Checklist

- [ ] Token HF obtenido de https://huggingface.co/settings/tokens
- [ ] Secret `HF_TOKEN` agregado en GitHub
- [ ] Push a main ejecutado
- [ ] Workflow completado exitosamente
- [ ] Logs muestran "Hugging Face MCP integration enabled"
- [ ] Agente desplegado y funcionando

## 🎉 ¡Listo!

Tu agente ahora tiene acceso completo al ecosistema de Hugging Face Hub con 5 nuevas herramientas poderosas.

**URL del servicio**: Verás la URL en los logs del workflow después del deployment.

---

¿Necesitas ayuda? Revisa la documentación completa o los ejemplos de uso.

# GitHub Secrets Setup Guide

Este documento describe cómo configurar los secrets necesarios para el deployment automático en Cloud Run con integración de Hugging Face MCP.

## 📋 Secrets Requeridos

### 1. GCP_SA_KEY (Requerido)

**Descripción**: Credenciales de la cuenta de servicio de Google Cloud

**Cómo obtenerlo**:
```bash
# 1. Crear una cuenta de servicio en GCP
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

# 2. Asignar roles necesarios
gcloud projects add-iam-policy-binding aidevelopments \
  --member="serviceAccount:github-actions-deployer@aidevelopments.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding aidevelopments \
  --member="serviceAccount:github-actions-deployer@aidevelopments.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.admin"

# 3. Crear la clave JSON
gcloud iam service-accounts keys create sa-key.json \
  --iam-account=github-actions-deployer@aidevelopments.iam.gserviceaccount.com

# 4. Copiar el contenido completo del archivo sa-key.json
cat sa-key.json
```

**Valor**: El contenido JSON completo del archivo (incluye private_key con BEGIN/END)

---

### 2. PG_HOST (Requerido)

**Descripción**: Host del servidor PostgreSQL

**Ejemplo**: `iserv-db.c6lk0icuy5q9.us-east-1.rds.amazonaws.com`

**Valor**: URL del host de tu base de datos PostgreSQL

---

### 3. PG_DATABASE (Requerido)

**Descripción**: Nombre de la base de datos PostgreSQL

**Ejemplo**: `postgres`

**Valor**: Nombre de tu base de datos

---

### 4. PG_USER (Requerido)

**Descripción**: Usuario de PostgreSQL

**Ejemplo**: `postgres`

**Valor**: Usuario con permisos de lectura en la base de datos

---

### 5. PG_PASSWORD (Requerido)

**Descripción**: Contraseña de PostgreSQL

**Valor**: Contraseña del usuario de PostgreSQL

---

### 6. PG_PORT (Opcional)

**Descripción**: Puerto de PostgreSQL

**Ejemplo**: `5432`

**Valor**: Puerto del servidor PostgreSQL (default: 5432)

---

### 7. HF_TOKEN (Requerido para MCP)

**Descripción**: Token de autenticación de Hugging Face para MCP integration

**Cómo obtenerlo**:

1. Ve a [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click en **"New token"**
3. Configuración recomendada:
   - **Name**: `github-actions-mcp`
   - **Type**: **Read** (no necesitas Write para MCP)
   - **Repositories**: All (o selecciona específicos si prefieres)
4. Click **"Generate"**
5. Copia el token (empieza con `hf_`)

**Valor**: Token de Hugging Face (formato: `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

**Características habilitadas con este token**:
- ✅ `search_hf_models` - Buscar modelos de IA
- ✅ `search_hf_datasets` - Buscar datasets
- ✅ `search_hf_spaces` - Buscar Spaces (Gradio/Streamlit)
- ✅ `get_hf_model_details` - Información detallada de modelos
- ✅ `get_hf_dataset_details` - Información detallada de datasets

**⚠️ IMPORTANTE**: Sin este token, las funcionalidades de Hugging Face MCP no estarán disponibles.

---

### 8. GOOGLE_API_KEY (Opcional)

**Descripción**: API Key de Google AI Studio (solo si usas AI Studio en lugar de Vertex AI)

**Cómo obtenerlo**:
1. Ve a [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Crea una nueva API key
3. Copia la key

**Nota**: No es necesario si usas Vertex AI (configuración por default)

---

## 🔧 Cómo Agregar Secrets en GitHub

### Opción 1: Desde la UI de GitHub

1. Ve a tu repositorio en GitHub
2. Click en **Settings** (⚙️)
3. En el menú lateral, click en **Secrets and variables** → **Actions**
4. Click en **New repository secret**
5. Ingresa el **Name** (nombre del secret)
6. Ingresa el **Value** (valor del secret)
7. Click en **Add secret**
8. Repite para cada secret necesario

### Opción 2: Usando GitHub CLI

```bash
# Instalar GitHub CLI si no lo tienes
# https://cli.github.com/

# Autenticarte
gh auth login

# Agregar secrets
gh secret set GCP_SA_KEY < sa-key.json
gh secret set PG_HOST -b "your-host"
gh secret set PG_DATABASE -b "postgres"
gh secret set PG_USER -b "postgres"
gh secret set PG_PASSWORD -b "your-password"
gh secret set PG_PORT -b "5432"
gh secret set HF_TOKEN -b "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Verificar que se agregaron
gh secret list
```

---

## 📋 Checklist de Configuración

Usa este checklist para asegurarte de que todo está configurado:

- [ ] **GCP_SA_KEY** - Cuenta de servicio de GCP con roles necesarios
- [ ] **PG_HOST** - Host de PostgreSQL configurado
- [ ] **PG_DATABASE** - Nombre de la base de datos configurado
- [ ] **PG_USER** - Usuario de PostgreSQL configurado
- [ ] **PG_PASSWORD** - Contraseña de PostgreSQL configurada
- [ ] **PG_PORT** - Puerto de PostgreSQL configurado (opcional, default: 5432)
- [ ] **HF_TOKEN** - Token de Hugging Face configurado (requerido para MCP)
- [ ] **GOOGLE_API_KEY** - API Key de Google configurada (opcional)

---

## 🔍 Verificar Configuración

Después de agregar los secrets, puedes verificar que todo está bien:

### 1. Verificar Secrets en GitHub

```bash
gh secret list
```

Deberías ver algo como:
```
GCP_SA_KEY        Updated 2025-01-27
HF_TOKEN          Updated 2025-01-27
PG_DATABASE       Updated 2025-01-27
PG_HOST           Updated 2025-01-27
PG_PASSWORD       Updated 2025-01-27
PG_PORT           Updated 2025-01-27
PG_USER           Updated 2025-01-27
```

### 2. Verificar Deployment

Después de un push a main, el workflow se ejecutará automáticamente:

1. Ve a la tab **Actions** en GitHub
2. Selecciona el último workflow run
3. Revisa los logs de cada step
4. Busca mensajes como:
   - `✅ Hugging Face MCP token configured`
   - `✅ Hugging Face MCP integration enabled`

### 3. Verificar Service en Cloud Run

```bash
# Obtener la URL del servicio
gcloud run services describe raju-agent \
  --region=us-central1 \
  --format='value(status.url)'

# Verificar que responde
curl https://your-service-url/

# Verificar variables de entorno (en Cloud Console)
gcloud run services describe raju-agent \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

---

## 🚨 Troubleshooting

### Error: "HF_TOKEN secret is not configured"

**Solución**:
1. Ve a [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Crea un token de tipo "Read"
3. Agrégalo como secret `HF_TOKEN` en GitHub

### Error: "GCP_SA_KEY secret is not configured"

**Solución**:
1. Verifica que el archivo JSON de la cuenta de servicio sea válido
2. Asegúrate de copiar TODO el contenido (incluye BEGIN/END PRIVATE KEY)
3. Verifica que la cuenta de servicio tenga los roles necesarios

### Error: "PostgreSQL connection failed"

**Solución**:
1. Verifica que todos los secrets PG_* estén configurados correctamente
2. Prueba la conexión localmente:
   ```bash
   psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -p $PG_PORT
   ```
3. Verifica que el servidor PostgreSQL acepte conexiones desde Cloud Run

### Warning: "Hugging Face MCP integration disabled"

**Causa**: El secret `HF_TOKEN` no está configurado

**Impacto**: Las siguientes funcionalidades NO estarán disponibles:
- `search_hf_models`
- `search_hf_datasets`
- `search_hf_spaces`
- `get_hf_model_details`
- `get_hf_dataset_details`

**Solución**: Agrega el secret `HF_TOKEN` para habilitar estas funcionalidades

---

## 🔐 Mejores Prácticas de Seguridad

1. **Nunca commits secrets en el código**
   - Usa siempre GitHub Secrets
   - Agrega archivos sensibles a `.gitignore`

2. **Usa tokens de lectura cuando sea posible**
   - Para HF_TOKEN, usa tipo "Read" (no "Write")
   - Minimiza los permisos necesarios

3. **Rota tus secrets regularmente**
   - Cambia passwords y tokens cada 90 días
   - Especialmente después de que alguien deje el equipo

4. **Revisa los logs de deployment**
   - Asegúrate de que no se impriman secrets en los logs
   - El workflow está configurado para NO mostrar valores sensibles

5. **Limita el acceso al repositorio**
   - Solo colaboradores de confianza deben tener acceso
   - Revisa los permisos regularmente

---

## 📚 Referencias

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Hugging Face Tokens](https://huggingface.co/settings/tokens)
- [Google Cloud Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [Cloud Run Environment Variables](https://cloud.google.com/run/docs/configuring/environment-variables)

---

## ❓ Preguntas Frecuentes

**Q: ¿Puedo usar el mismo token HF_TOKEN para múltiples proyectos?**
A: Sí, pero es mejor crear tokens separados para cada proyecto para mejor control.

**Q: ¿Qué pasa si no configuro HF_TOKEN?**
A: El agente funcionará normalmente pero las funcionalidades de Hugging Face MCP no estarán disponibles.

**Q: ¿Los secrets son visibles en los logs?**
A: No, GitHub automáticamente enmascara los valores de secrets en los logs.

**Q: ¿Puedo actualizar un secret sin redeployar?**
A: Sí, pero necesitarás hacer un nuevo push a main para que el nuevo valor se use en el deployment.

---

Para más ayuda, consulta la documentación completa en [HUGGINGFACE_INTEGRATION.md](../HUGGINGFACE_INTEGRATION.md)

# Guía de Despliegue - GitHub Actions + Google Cloud Run

Esta guía explica cómo configurar el despliegue automático a Google Cloud Run usando GitHub Actions.

## Prerequisitos

1. Cuenta de Google Cloud Platform con proyecto activo
2. Repositorio en GitHub
3. Permisos de administrador en el repositorio de GitHub

## Configuración de Google Cloud Platform

### 1. Habilitar APIs necesarias

Ejecuta los siguientes comandos en Cloud Shell o con `gcloud` CLI:

```bash
gcloud config set project 469654903224

# Habilitar APIs necesarias
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### 2. Crear Service Account para GitHub Actions

```bash
# Crear service account
gcloud iam service-accounts create github-actions-sa \
    --display-name="GitHub Actions Service Account" \
    --project=469654903224

# Obtener el email del service account
SA_EMAIL=$(gcloud iam service-accounts list \
    --filter="displayName:GitHub Actions Service Account" \
    --format="value(email)")

# Asignar roles necesarios
gcloud projects add-iam-policy-binding 469654903224 \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding 469654903224 \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding 469654903224 \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding 469654903224 \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/artifactregistry.writer"
```

### 3. Crear y descargar la clave JSON

```bash
# Crear clave JSON
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=${SA_EMAIL}

# Mostrar el contenido (copiar todo el JSON)
cat github-actions-key.json
```

**⚠️ IMPORTANTE:** Guarda este archivo de forma segura. Contiene credenciales sensibles.

## Configuración de GitHub Secrets

### 1. Acceder a la configuración de Secrets

1. Ve a tu repositorio en GitHub
2. Navega a **Settings** → **Secrets and variables** → **Actions**
3. Haz clic en **New repository secret**

### 2. Agregar el Secret `GCP_SA_KEY`

1. **Name:** `GCP_SA_KEY`
2. **Secret:** Pega el contenido completo del archivo `github-actions-key.json` que descargaste anteriormente

El JSON debe verse así (nota que el `private_key` incluye las líneas completas `-----BEGIN PRIVATE KEY-----` y `-----END PRIVATE KEY-----`):
```json
{
  "type": "service_account",
  "project_id": "469654903224",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n(múltiples líneas de caracteres)\n...-----END PRIVATE KEY-----\n",
  "client_email": "github-actions-sa@469654903224.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

**⚠️ IMPORTANTE:** 
- El campo `private_key` debe incluir **completas** las líneas:
  - `-----BEGIN PRIVATE KEY-----` al inicio
  - `-----END PRIVATE KEY-----` al final
- Entre estas líneas habrá múltiples líneas de caracteres codificados
- Los saltos de línea están representados como `\n` en el JSON
- Copia el JSON **completo** tal como viene del archivo, sin modificaciones

### 3. Agregar el Secret `GOOGLE_API_KEY`

Si estás usando Google AI Studio (en lugar de Vertex AI), necesitas agregar tu API key de Gemini:

1. **Name:** `GOOGLE_API_KEY`
2. **Secret:** Tu API key de Google Gemini

**Para obtener tu API key:**
- Ve a [Google AI Studio](https://aistudio.google.com/app/apikey)
- Crea una nueva API key o copia una existente
- Pega el valor completo en el secret

**Nota:** Si estás usando Vertex AI (recomendado para Cloud Run), no necesitas este secret ya que usa la autenticación de GCP automáticamente.

### 4. Verificar Secrets configurados

Debes tener configurados los siguientes secrets:
- ✅ `GCP_SA_KEY` - Clave JSON del Service Account (requerido)
- ✅ `GOOGLE_API_KEY` - API key de Gemini (requerido si usas AI Studio, opcional si usas Vertex AI)

## Configuración del Workflow

El workflow está configurado en `.github/workflows/deploy-cloud-run.yml` con los siguientes valores:

- **Project ID:** `469654903224`
- **Service Name:** `raju-agent`
- **Region:** `us-central1`
- **Trigger:** Push a la rama `main`

## Variables de Entorno en Cloud Run

El workflow configura automáticamente las siguientes variables de entorno:

- `COMMIT_SHA` - SHA del commit desplegado
- `AGENT_VERSION` - Versión del proyecto (desde `pyproject.toml`)
- `API_BASE_URL` - URL completa del servicio Cloud Run

### Variables de Entorno Opcionales

Puedes agregar variables de entorno adicionales editando el workflow o configurándolas directamente en Cloud Run:

```bash
gcloud run services update raju-agent \
    --region us-central1 \
    --update-env-vars "LOGS_BUCKET_NAME=tu-bucket-name" \
    --update-env-vars "ALLOW_ORIGINS=https://tu-dominio.com"
```

## Probar el Despliegue

### 1. Hacer push a la rama main

```bash
git add .
git commit -m "Configure GitHub Actions deployment"
git push origin main
```

### 2. Verificar el despliegue

1. Ve a la pestaña **Actions** en tu repositorio de GitHub
2. Verifica que el workflow se ejecute correctamente
3. Una vez completado, obtén la URL del servicio:

```bash
gcloud run services describe raju-agent \
    --region us-central1 \
    --format 'value(status.url)'
```

### 3. Acceder al servicio

El frontend estará disponible en la URL del servicio (ej: `https://raju-agent-469654903224.us-central1.run.app`)

## Estructura del Despliegue

```
┌─────────────────┐
│  GitHub Push    │
│  (main branch)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitHub Actions  │
│   Workflow      │
└────────┬────────┘
         │
         ├──► Build Docker Image
         │
         ├──► Push to GCR
         │
         └──► Deploy to Cloud Run
                  │
                  ▼
         ┌─────────────────┐
         │  Cloud Run      │
         │  (raju-agent)   │
         │                 │
         │  ┌───────────┐  │
         │  │ FastAPI   │  │
         │  │ Backend   │  │
         │  └───────────┘  │
         │                 │
         │  ┌───────────┐  │
         │  │ index.html│  │
         │  │ Frontend  │  │
         │  └───────────┘  │
         └─────────────────┘
```

## Solución de Problemas

### Error: "Permission denied"

Verifica que el Service Account tenga los roles correctos:
```bash
gcloud projects get-iam-policy 469654903224 \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:github-actions-sa@469654903224.iam.gserviceaccount.com"
```

### Error: "API not enabled"

Habilita las APIs necesarias (ver sección "Habilitar APIs necesarias")

### Error: "Image not found"

Verifica que la imagen se haya subido correctamente:
```bash
gcloud container images list --repository=gcr.io/469654903224
```

### El frontend no carga

1. Verifica que `index.html` esté en el directorio `static/` en el contenedor
2. Verifica los logs de Cloud Run:
```bash
gcloud run services logs read raju-agent --region us-central1 --limit 50
```

## Recursos Adicionales

- [Documentación de Cloud Run](https://cloud.google.com/run/docs)
- [GitHub Actions para GCP](https://github.com/google-github-actions)
- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)


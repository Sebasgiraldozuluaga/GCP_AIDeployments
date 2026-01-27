"""
Ejemplo de uso de las herramientas de Hugging Face MCP
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.hf_tools import (
    search_hf_models,
    search_hf_datasets,
    search_hf_spaces,
    get_hf_model_details,
    get_hf_dataset_details
)


def ejemplo_busqueda_modelos():
    """Ejemplo: Buscar modelos de análisis de sentimiento en español"""
    print("=" * 80)
    print("EJEMPLO 1: Buscar modelos de análisis de sentimiento en español")
    print("=" * 80)

    result = search_hf_models(
        query="spanish sentiment analysis",
        limit=5,
        task="text-classification"
    )
    print(result)
    print("\n")


def ejemplo_busqueda_datasets():
    """Ejemplo: Buscar datasets de QA en español"""
    print("=" * 80)
    print("EJEMPLO 2: Buscar datasets de QA en español")
    print("=" * 80)

    result = search_hf_datasets(
        query="spanish question answering",
        limit=5,
        task="question-answering"
    )
    print(result)
    print("\n")


def ejemplo_busqueda_spaces():
    """Ejemplo: Buscar chatbots en Gradio"""
    print("=" * 80)
    print("EJEMPLO 3: Buscar aplicaciones de chatbot")
    print("=" * 80)

    result = search_hf_spaces(
        query="chatbot",
        limit=5,
        sdk="gradio"
    )
    print(result)
    print("\n")


def ejemplo_detalles_modelo():
    """Ejemplo: Obtener detalles de un modelo específico"""
    print("=" * 80)
    print("EJEMPLO 4: Obtener detalles de BERT base")
    print("=" * 80)

    result = get_hf_model_details("bert-base-uncased")
    print(result)
    print("\n")


def ejemplo_detalles_dataset():
    """Ejemplo: Obtener detalles de un dataset específico"""
    print("=" * 80)
    print("EJEMPLO 5: Obtener detalles del dataset SQuAD")
    print("=" * 80)

    result = get_hf_dataset_details("squad")
    print(result)
    print("\n")


def ejemplo_generacion_imagenes():
    """Ejemplo: Buscar modelos de generación de imágenes"""
    print("=" * 80)
    print("EJEMPLO 6: Buscar modelos de generación de imágenes")
    print("=" * 80)

    result = search_hf_models(
        query="stable diffusion",
        limit=5,
        task="text-to-image",
        library="diffusers"
    )
    print(result)
    print("\n")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "EJEMPLOS DE HUGGING FACE MCP" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")

    # Verificar que HF_TOKEN esté configurado
    if not os.getenv("HF_TOKEN"):
        print("⚠️  ADVERTENCIA: HF_TOKEN no está configurado en el entorno")
        print("   Configura tu token con: export HF_TOKEN=hf_xxxxxxxxxxxxx")
        print("\n")

    # Ejecutar ejemplos
    try:
        ejemplo_busqueda_modelos()
        ejemplo_busqueda_datasets()
        ejemplo_busqueda_spaces()
        ejemplo_detalles_modelo()
        ejemplo_detalles_dataset()
        ejemplo_generacion_imagenes()

        print("✅ Todos los ejemplos completados exitosamente!")

    except Exception as e:
        print(f"❌ Error ejecutando ejemplos: {e}")
        import traceback
        traceback.print_exc()

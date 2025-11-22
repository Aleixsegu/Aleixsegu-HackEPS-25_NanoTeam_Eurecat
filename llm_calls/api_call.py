import os
import json
import re
import openai


# Read API key and optional base URL from environment
OPENAI_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://innwater.eurecatprojects.com/lite-llm/")

if not OPENAI_API_KEY:
    raise RuntimeError("LLM API key not found. Set LLM_API_KEY or OPENAI_API_KEY in environment.")

client = openai.Client(api_key=OPENAI_API_KEY, base_url=BASE_URL)

AVAILABLE_MODELS = ["gpt-4o-mini", "qwen2-7b-instruct"]


def _extract_json(text: str) -> str:
    """Try to extract the first JSON object/array substring from text."""
    # Quick regex to find {...} or [...]
    m = re.search(r"(\{(?:.|\n)*\}|\[(?:.|\n)*\])", text)
    if m:
        return m.group(0)
    return text


def analyze_application(app_description: str, model: str = "gpt-4o-mini", return_raw: bool = False) -> dict:
    """
    Send `app_description` to the LLM and expect a STRICT JSON response with the infrastructure schema.

    Returns parsed dict. Raises ValueError if the LLM response cannot be parsed as JSON.
    """
    system_prompt = (
        "Eres un asistente técnico que convierte una descripción de aplicación en requisitos de infraestructura para desplegar un cluster Kubernetes. "
        "RESPONDE SÓLO con JSON válido sin ningún texto adicional. El JSON debe incluir los campos básicos: "
        "node_count (int), roles (lista de objetos con name/count/cpu/ram_gb), disk_gb (int), k8s_distribution (str), "
        "networking_pref (str), preferred_region (str). Además, para cada proveedor cloud (AWS y Google Cloud) debes añadir una sección "
        "`cloud_providers` con claves `aws` y `gcp` que contengan recomendaciones optimizadas (precio/rendimiento) para los roles definidos. "
        "Cada proveedor debe incluir al menos: `region` (string), `instance_type_by_role` (objeto que mapea role->instance_type), `disk_type` (string), `disk_size_gb` (int), "
        "`security_group_ports` (lista de puertos a abrir), `approx_cost_per_hour` (float, aproximado) y `notes` (string) con instrucciones breves de bootstrap/user-data. "
        "Prioriza opciones económicas y generales (familias T/A/M) pero sugiere alternativas para alto rendimiento si procede. "
        "Devuelve TODO estrictamente en JSON y evita explicaciones en texto fuera del JSON."
    )

    user_prompt = f"Descripción: {app_description}\n\nDevuelve el JSON pedido."

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1000,
        temperature=0.0,
    )

    text = ""
    try:
        text = resp.choices[0].message.content
    except Exception:
        # fallback: try to stringify the whole response
        text = str(resp)

    # Try to parse JSON directly, otherwise try to extract JSON substring
    try:
        parsed = json.loads(text)
    except Exception:
        candidate = _extract_json(text)
        try:
            parsed = json.loads(candidate)
        except Exception as e:
            raise ValueError(f"No se pudo parsear JSON desde la respuesta del LLM. respuesta:\n{text}\nerror: {e}")

    if return_raw:
        return {"parsed": parsed, "raw": text}

    return parsed


if __name__ == "__main__":
    # pequeño demo interactivo si se ejecuta directamente
    sample = "Aplicación web Python Flask, 100 req/s, 2 réplicas, base de datos externa, desplegar en Europa."
    print("Analizando muestra...")
    try:
        result = analyze_application(sample)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error al analizar:", e)

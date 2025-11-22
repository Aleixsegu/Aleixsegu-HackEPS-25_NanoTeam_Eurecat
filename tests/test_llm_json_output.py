import os
import pytest

from llm_calls.api_call import analyze_application


@pytest.mark.skipif(
    not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    reason="LLM API key not set in environment (LLM_API_KEY or OPENAI_API_KEY).",
)
def test_analyze_application_returns_valid_json():
    sample_description = (
        "Aplicación web Python Flask que sirve contenido estático y API, ~100 req/s, "
        "necesita 2 réplicas, base de datos gestionada externa, desplegar en Europa."
    )

    result = analyze_application(sample_description)

    assert isinstance(result, dict), "La salida debe ser un dict (JSON parseado)."

    required_fields = [
        "node_count",
        "roles",
        "disk_gb",
        "k8s_distribution",
        "networking_pref",
        "preferred_region",
    ]

    for f in required_fields:
        assert f in result, f"Falta el campo obligatorio: {f}"

    # basic type checks
    assert isinstance(result["node_count"], int)
    assert isinstance(result["roles"], list)
    assert isinstance(result["disk_gb"], int)
    assert isinstance(result["k8s_distribution"], str)
    assert isinstance(result["networking_pref"], str)
    assert isinstance(result["preferred_region"], str)

    # roles deeper check
    for role in result["roles"]:
        assert set(["name", "count", "cpu", "ram_gb"]).issubset(role.keys())
        assert isinstance(role["name"], str)
        assert isinstance(role["count"], int)
        # cpu and ram_gb may be float
        assert isinstance(role["cpu"], (int, float))
        assert isinstance(role["ram_gb"], (int, float))

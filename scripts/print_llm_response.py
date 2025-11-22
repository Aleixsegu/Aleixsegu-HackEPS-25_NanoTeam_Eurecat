#!/usr/bin/env python3
import sys
import argparse
import json
from pathlib import Path

# Ensure repo root is on sys.path so `llm_calls` package can be imported when
# the script is executed directly (sys.path[0] would otherwise be the scripts/ dir).
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm_calls.api_call import analyze_application


def main():
    p = argparse.ArgumentParser(description="Llamar al LLM y mostrar la respuesta por consola (JSON).")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", "-t", help="Descripción de la aplicación (texto).")
    group.add_argument("--file", "-f", type=Path, help="Fichero con la descripción de la app.")
    p.add_argument("--model", default="gpt-4o-mini", help="Modelo a usar en el LLM.")
    p.add_argument("--raw", action="store_true", help="Mostrar también el texto crudo que devuelve el LLM.")
    p.add_argument("--split-out", type=Path, help="Directorio donde guardar aws_config.json y gcp_config.json si existen.")

    args = p.parse_args()

    if args.text:
        desc = args.text
    else:
        desc = args.file.read_text(encoding="utf-8")

    try:
        res = analyze_application(desc, model=args.model, return_raw=args.raw)
    except Exception as e:
        print("Error al obtener respuesta del LLM:", e)
        raise SystemExit(1)

    # Handle returned structure: parsed or {parsed, raw}
    parsed = None
    raw = None
    if isinstance(res, dict) and "parsed" in res and "raw" in res:
        parsed = res["parsed"]
        raw = res["raw"]
    else:
        parsed = res

    # If cloud_providers present, print them separately
    cp = parsed.get("cloud_providers") if isinstance(parsed, dict) else None
    if cp and isinstance(cp, dict):
        aws = cp.get("aws")
        gcp = cp.get("gcp")
        if aws is not None:
            print("=== AWS CONFIG ===")
            print(json.dumps(aws, indent=2, ensure_ascii=False))
        if gcp is not None:
            print("=== GCP CONFIG ===")
            print(json.dumps(gcp, indent=2, ensure_ascii=False))

        # Also print the full parsed JSON afterwards
        print("=== FULL PARSED JSON ===")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))

        # Also print raw if requested
        if args.raw and raw:
            print("=== RAW LLM RESPONSE ===")
            print(raw)
    else:
        print(json.dumps(parsed, indent=2, ensure_ascii=False))

    # Optionally write separate provider files
    if cp and isinstance(cp, dict) and args.split_out:
        out_dir = Path(args.split_out)
        out_dir.mkdir(parents=True, exist_ok=True)
        if cp.get("aws") is not None:
            (out_dir / "aws_config.json").write_text(json.dumps(cp.get("aws"), indent=2, ensure_ascii=False), encoding="utf-8")
        if cp.get("gcp") is not None:
            (out_dir / "gcp_config.json").write_text(json.dumps(cp.get("gcp"), indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

"""
Módulo de análise de PDFs de construtoras usando Google Gemini (gratuito).
Extrai dados estruturados e monitora uso de tokens.

Para obter a chave gratuita:
  https://aistudio.google.com/app/apikey
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# # Carrega .env
# for _p in [
#     Path(__file__).resolve().parent.parent / ".env",
#     Path(__file__).resolve().parent / ".env",
#     Path("/app/.env"),
# ]:
#     if _p.exists():
#         load_dotenv(dotenv_path=_p, override=False)
#         break

MODEL = "gemini-2.5-flash"  # gratuito: 15 req/min, 1M tokens/dia
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
SYSTEM_PROMPT = """Você é um especialista em análise de documentos do setor da construção civil.
Sua tarefa é extrair dados estruturados de PDFs de construtoras.

Responda SOMENTE com JSON válido, sem markdown, sem explicações.
O JSON deve seguir exatamente o schema informado pelo usuário."""
EXTRACTION_SCHEMA = {
    "empresa": {
        "nome": "string | null",
        "cnpj": "string | null",
        "ticker": "string | null (ex: TEND3)",
        "segmento": "string | null (ex: Novo Mercado)",
        "site_ri": "string | null",
    },
    "periodo": {
        "trimestre_atual": "string (ex: '3T24')",
        "trimestre_anterior": "string (ex: '2T24')",
        "mesmo_trimestre_ano_anterior": "string (ex: '3T23')",
        "acumulado_atual": "string (ex: '9M24')",
        "acumulado_ano_anterior": "string (ex: '9M23')",
    },
    "financeiro": {
        "receita_liquida": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null",
            "acumulado_atual": "number | null",
            "acumulado_ano_ant": "number | null",
            "var_acumulado_pct": "number | null"
        },
        "lucro_bruto_ajustado": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null",
            "acumulado_atual": "number | null",
            "acumulado_ano_ant": "number | null",
            "var_acumulado_pct": "number | null"
        },
        "margem_bruta_ajustada_pct": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pp": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pp": "number | null"
        },
        "ebitda_ajustado": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null"
        },
        "margem_ebitda_ajustada_pct": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pp": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pp": "number | null"
        },
        "lucro_liquido": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null",
            "acumulado_atual": "number | null",
            "acumulado_ano_ant": "number | null"
        },
        "margem_liquida_pct": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pp": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pp": "number | null"
        },
        "divida_liquida": "number | null",
        "divida_liquida_pl_pct": "number | null",
        "divida_liquida_corporativa_pl_pct": "number | null",
        "caixa_total": "number | null"
    },
    "operacional": {
        "lancamentos_vgv": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null",
            "acumulado_atual": "number | null",
            "acumulado_ano_ant": "number | null"
        },
        "vendas_liquidas_vgv": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null",
            "acumulado_atual": "number | null",
            "acumulado_ano_ant": "number | null"
        },
        "vso_liquida_pct": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pp": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pp": "number | null"
        },
        "vgv_repassado": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "var_trimestre_pct": "number | null",
            "mesmo_trim_ano_ant": "number | null",
            "var_anual_pct": "number | null"
        },
        "unidades_entregues": {
            "atual": "number | null",
            "trimestre_anterior": "number | null",
            "mesmo_trim_ano_ant": "number | null"
        },
        "banco_terrenos_vgv": "number | null",
        "preco_medio_por_unidade_mil": "number | null"
    },
    "indices": {
        "roe_pct": "number | null",
        "roce_pct": "number | null",
        "margem_ref_pct": "number | null"
    },
    "guidance": {
        "vendas_liquidas_min": "number | null",
        "vendas_liquidas_max": "number | null",
        "margem_bruta_min_pct": "number | null",
        "margem_bruta_max_pct": "number | null",
        "ebitda_min": "number | null",
        "ebitda_max": "number | null"
    },
    "metadata": {
        "tipo_documento": "string",
        "confianca_extracao": "number (0-1)",
        "campos_nao_encontrados": ["string"],
        "observacoes": "string | null"
    }
}

def analyze_pdf(extraction_prompt: str, filename: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY") # preciso colocar isso no .env para carregar de
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY não encontrada.\n"
            "1. Acesse https://aistudio.google.com/app/apikey\n"
            "2. Clique em 'Create API Key' (gratuito)\n"
            "3. Adicione no docker-compose.yml:\n"
            "   GEMINI_API_KEY: sua-chave-aqui"
        )

    prompt_full = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Extraia os dados do documento seguindo EXATAMENTE este schema JSON:\n\n"
        f"{json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        f"Se um campo não for encontrado, use null. Para listas vazias, use [].\n\n"
        f"DOCUMENTO:\n{extraction_prompt}"
    )

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_full}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 100000,
            "responseMimeType": "application/json" # <--- ADICIONE ESTA LINHA
        },
    }).encode("utf-8")

    url = API_URL.format(model=MODEL, key=api_key)
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    import time

# dentro da função, antes do urllib.request.urlopen:
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break  # sucesso, sai do loop
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            if e.code == 429 and tentativa < 2:
                time.sleep(60)  # espera 60s e tenta de novo
                continue
            raise ValueError(f"Erro Gemini API ({e.code}): {body}")
    # try:
    #     with urllib.request.urlopen(req, timeout=60) as resp:
    #         data = json.loads(resp.read().decode("utf-8"))
    # except urllib.error.HTTPError as e:
    #     body = e.read().decode("utf-8")
    #     raise ValueError(f"Erro Gemini API ({e.code}): {body}")

    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    import logging
    logging.warning(f"GEMINI RAW RESPONSE: {raw_text}")
    # Remove markdown fence se vier
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        extracted_data = json.loads(raw_text)
    except json.JSONDecodeError:
        extracted_data = {"error": "Falha ao parsear JSON", "raw": raw_text[:500]}

    # Gemini retorna contagem de tokens na resposta
    usage_meta = data.get("usageMetadata", {})
    input_tok  = usage_meta.get("promptTokenCount", 0)
    output_tok = usage_meta.get("candidatesTokenCount", 0)

    token_usage = {
        "input_tokens":       input_tok,
        "output_tokens":      output_tok,
        "total_tokens":       input_tok + output_tok,
        "model":              MODEL,
        "custo_usd_estimado": 0.0,  # gratuito no tier free
    }

    return {
        "filename":    filename,
        "dados":       extracted_data,
        "token_usage": token_usage,
    }

"""
ConstruData API — Backend FastAPI
Extração inteligente de dados de PDFs de construtoras via MinIO + Claude AI
"""

import json
import traceback
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import minio_client as mc
import pdf_extractor as pe
import ai_analyzer as ai

app = FastAPI(
    title="ConstruData API",
    description="Extração de dados estruturados de PDFs de construtoras",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/pdfs")
def list_pdfs():
    """Lista todos os PDFs armazenados no MinIO."""
    try:
        pdfs = mc.list_pdfs()
        return {"pdfs": pdfs, "total": len(pdfs)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Faz upload de um PDF para o MinIO.
    Retorna o nome do objeto armazenado.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Apenas arquivos PDF são aceitos.")

    try:
        pdf_bytes = await file.read()
        object_name = mc.upload_pdf(pdf_bytes, file.filename)
        return {
            "message":     "Upload realizado com sucesso",
            "object_name": object_name,
            "filename":    file.filename,
            "size_kb":     round(len(pdf_bytes) / 1024, 1),
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/analyze/{filename}")
async def analyze_pdf(
    filename: str,
    save_result: bool = Query(True, description="Salvar resultado JSON no MinIO"),
):
    """
    Baixa um PDF do MinIO, extrai texto e analisa com IA.
    Retorna dados estruturados da construtora.
    """
    object_name = f"pdfs/{filename}"

    # 1. Baixa o PDF do MinIO
    try:
        pdf_bytes = mc.download_pdf(object_name)
    except Exception as e:
        raise HTTPException(404, detail=f"PDF não encontrado: {e}")

    # 2. Extrai texto e tabelas
    try:
        extracted = pe.extract_text_pdfplumber(pdf_bytes)
        prompt    = pe.build_extraction_prompt(extracted, filename)
    except Exception as e:
        raise HTTPException(500, detail=f"Erro na extração de texto: {e}")

    # 3. Analisa com Claude
    try:
        result = ai.analyze_pdf(prompt, filename)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(500, detail=f"Erro na análise com IA: {e}\n{tb}")

    # 4. Adiciona metadados de extração
    result["extraction_meta"] = {
        "total_pages":     extracted["total_pages"],
        "pages_processed": extracted["pages_processed"],
        "tables_found":    len(extracted["tables"]),
        "analyzed_at":     datetime.utcnow().isoformat(),
    }

    # 5. Salva resultado no MinIO
    if save_result:
        result_filename = filename.replace(".pdf", "") + "_resultado.json"
        mc.save_json_result(
            json.dumps(result, ensure_ascii=False, indent=2),
            result_filename,
        )
        result["saved_to"] = f"results/{result_filename}"

    return result


@app.post("/upload-and-analyze")
async def upload_and_analyze(file: UploadFile = File(...)):
    """
    Combina upload + análise em uma única chamada.
    Ideal para uso no frontend.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Apenas arquivos PDF são aceitos.")

    pdf_bytes = await file.read()

    # Upload
    object_name = mc.upload_pdf(pdf_bytes, file.filename)

    # Extração
    extracted = pe.extract_text_pdfplumber(pdf_bytes)
    prompt    = pe.build_extraction_prompt(extracted, file.filename)

    # Análise IA
    result = ai.analyze_pdf(prompt, file.filename)
    result["extraction_meta"] = {
        "total_pages":     extracted["total_pages"],
        "pages_processed": extracted["pages_processed"],
        "tables_found":    len(extracted["tables"]),
        "analyzed_at":     datetime.utcnow().isoformat(),
    }

    # Salva resultado
    result_filename = file.filename.replace(".pdf", "") + "_resultado.json"
    mc.save_json_result(
        json.dumps(result, ensure_ascii=False, indent=2),
        result_filename,
    )
    result["saved_to"]    = f"results/{result_filename}"
    result["object_name"] = object_name

    return result


@app.get("/results")
def list_results():
    """Lista todos os JSONs de resultados salvos no MinIO."""
    try:
        client = mc.get_client()
        mc.ensure_bucket(client)
        objects = client.list_objects(mc.MINIO_BUCKET, prefix="results/", recursive=True)
        results = []
        for obj in objects:
            results.append({
                "object_name":   obj.object_name,
                "filename":      obj.object_name.replace("results/", ""),
                "size_kb":       round(obj.size / 1024, 1) if obj.size else 0,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            })
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/results/{filename}")
def get_result(filename: str):
    """Retorna o JSON de resultado de uma análise específica."""
    try:
        raw = mc.download_pdf(f"results/{filename}", bucket=mc.MINIO_BUCKET)
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise HTTPException(404, detail=f"Resultado não encontrado: {e}")

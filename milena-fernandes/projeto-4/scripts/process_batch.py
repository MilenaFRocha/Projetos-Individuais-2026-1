#!/usr/bin/env python3
"""
Script CLI para processar PDFs de construtoras em lote.
Uso: python process_batch.py /caminho/para/pdfs/

Requer: ANTHROPIC_API_KEY no ambiente ou .env
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Adiciona o backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import minio_client as mc
import pdf_extractor as pe
import ai_analyzer   as ai


def process_pdf(pdf_path: Path, save_to_minio: bool = True) -> dict:
    """Processa um único PDF e retorna os dados estruturados."""
    print(f"\n  📄 {pdf_path.name}")
    print(f"     Tamanho: {pdf_path.stat().st_size / 1024:.1f} KB")

    # 1. Lê o arquivo
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # 2. Faz upload pro MinIO
    if save_to_minio:
        obj = mc.upload_pdf(pdf_bytes, pdf_path.name)
        print(f"     ✅ MinIO: {obj}")

    # 3. Extrai texto
    extracted = pe.extract_text_pdfplumber(pdf_bytes)
    prompt    = pe.build_extraction_prompt(extracted, pdf_path.name)
    print(f"     📑 {extracted['total_pages']} páginas | {len(extracted['tables'])} tabelas")

    # 4. Analisa com IA
    result = ai.analyze_pdf(prompt, pdf_path.name)
    tu = result.get("token_usage", {})
    print(f"     ⚡ Tokens: {tu.get('total_tokens','?')} | Custo: US$ {tu.get('custo_usd_estimado','?')}")

    # 5. Salva resultado no MinIO
    if save_to_minio:
        result_name = pdf_path.stem + "_resultado.json"
        mc.save_json_result(
            json.dumps(result, ensure_ascii=False, indent=2),
            result_name,
        )
        print(f"     💾 Salvo: results/{result_name}")

    return result


def main():
    parser = argparse.ArgumentParser(description="ConstruData — Processamento em lote de PDFs")
    parser.add_argument("pdf_dir",        help="Diretório com os PDFs")
    parser.add_argument("--output",  "-o", help="Diretório de saída para JSONs", default="./output")
    parser.add_argument("--no-minio", action="store_true", help="Não enviar para o MinIO")
    parser.add_argument("--delay",        type=float, default=1.0, help="Delay entre PDFs (seg)")
    args = parser.parse_args()

    pdf_dir    = Path(args.pdf_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"❌ Nenhum PDF encontrado em {pdf_dir}")
        sys.exit(1)

    print(f"\n🏗️  ConstruData — Processamento em Lote")
    print(f"   {len(pdfs)} PDFs encontrados em {pdf_dir}")
    print(f"   MinIO: {'desativado' if args.no_minio else 'ativo'}")
    print("─" * 50)

    total_tokens = 0
    total_cost   = 0.0
    results      = []

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}]", end="")
        try:
            result = process_pdf(pdf, save_to_minio=not args.no_minio)

            # Salva JSON local
            out_path = output_dir / (pdf.stem + "_resultado.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            tu = result.get("token_usage", {})
            total_tokens += tu.get("total_tokens", 0)
            total_cost   += tu.get("custo_usd_estimado", 0)
            results.append({"file": pdf.name, "status": "ok"})

        except Exception as e:
            print(f"\n     ❌ Erro: {e}")
            results.append({"file": pdf.name, "status": "error", "error": str(e)})

        if i < len(pdfs):
            time.sleep(args.delay)

    # Sumário
    print("\n" + "─" * 50)
    print(f"✅ Processados: {sum(1 for r in results if r['status']=='ok')}/{len(pdfs)}")
    print(f"⚡ Tokens totais: {total_tokens:,}")
    print(f"💰 Custo total estimado: US$ {total_cost:.4f}")
    print(f"📁 JSONs salvos em: {output_dir}")

    # Salva sumário
    summary_path = output_dir / "_sumario.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_pdfs":    len(pdfs),
            "processados":   sum(1 for r in results if r['status']=='ok'),
            "erros":         sum(1 for r in results if r['status']=='error'),
            "total_tokens":  total_tokens,
            "custo_usd":     round(total_cost, 4),
            "arquivos":      results,
        }, f, ensure_ascii=False, indent=2)
    print(f"📋 Sumário: {summary_path}")


if __name__ == "__main__":
    main()

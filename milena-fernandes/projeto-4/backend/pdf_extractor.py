"""
Módulo de extração de texto de PDFs de construtoras.
Usa pdfplumber para tabelas e pdftotext para texto corrido.
Otimizado para reduzir tokens enviados à IA.
"""

import io
import subprocess
import tempfile
import os
import pdfplumber


MAX_CHARS_PER_PAGE = 1500
MAX_PAGES          = 15


def extract_text_pdfplumber(pdf_bytes: bytes) -> dict:
    """
    Extrai texto e tabelas de um PDF usando pdfplumber.
    Retorna um dict com páginas e tabelas encontradas.
    """
    pages_text  = []
    all_tables  = []
    total_pages = 0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        pages_to_process = min(total_pages, MAX_PAGES)

        for i, page in enumerate(pdf.pages[:pages_to_process]):
            # --- texto ---
            text = page.extract_text() or ""
            text = text[:MAX_CHARS_PER_PAGE]  # trunca para economizar tokens
            pages_text.append({"page": i + 1, "text": text})

            # --- tabelas ---
            tables = page.extract_tables()
            for tbl in tables:
                if tbl:
                    all_tables.append({
                        "page": i + 1,
                        "rows": tbl[:40],  # máximo 40 linhas por tabela
                    })

    return {
        "total_pages":     total_pages,
        "pages_processed": pages_to_process,
        "pages":           pages_text,
        "tables":          all_tables,
    }


def extract_text_cli(pdf_bytes: bytes) -> str:
    """
    Fallback: usa pdftotext (poppler) para extrair texto preservando layout.
    Útil quando pdfplumber falha ou o resultado é muito ruim.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", tmp_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    finally:
        os.unlink(tmp_path)


def build_extraction_prompt(extracted: dict, filename: str) -> str:
    """
    Monta o prompt enviado à IA com o conteúdo extraído do PDF.
    Usa apenas o conteúdo mais relevante para economizar tokens.
    """
    lines = [
        f"Arquivo: {filename}",
        f"Páginas totais: {extracted['total_pages']} | Analisadas: {extracted['pages_processed']}",
        "",
        "=== TEXTO EXTRAÍDO ===",
    ]

    # Concatena texto de todas as páginas (já truncado por página)
    full_text = "\n---\n".join(
        f"[Pág {p['page']}]\n{p['text']}"
        for p in extracted["pages"]
        if p["text"].strip()
    )
    # Limite global de caracteres no prompt
    lines.append(full_text[:18000])

    if extracted["tables"]:
        lines.append("\n=== TABELAS DETECTADAS ===")
        for tbl in extracted["tables"][:6]:  # máximo 6 tabelas
            lines.append(f"\n[Tabela – Pág {tbl['page']}]")
            for row in tbl["rows"]:
                lines.append(" | ".join(str(c or "").strip() for c in row))

    return "\n".join(lines)

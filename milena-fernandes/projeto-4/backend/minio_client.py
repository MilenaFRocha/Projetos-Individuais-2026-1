"""
Módulo de integração com MinIO.
Gerencia upload, download e listagem de PDFs de construtoras.
"""

import os
import io
from minio import Minio
from minio.error import S3Error
from pathlib import Path 
from dotenv import load_dotenv


for _p in [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent / ".env",
    Path("/app/.env"),
]:
    if _p.exists():
        load_dotenv(dotenv_path=_p, override=False)
        break

MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT",  "localhost:9000")
MINIO_ACCESS    = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET    = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET",     "construtoras-pdfs")


def get_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS,
        secret_key=MINIO_SECRET,
        secure=False,
    )


def ensure_bucket(client: Minio, bucket: str = MINIO_BUCKET) -> None:
    """Cria o bucket se ainda não existir."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_pdf(file_bytes: bytes, filename: str, bucket: str = MINIO_BUCKET) -> str:
    """
    Envia um PDF para o MinIO.
    Retorna o nome do objeto armazenado.
    """
    client = get_client()
    ensure_bucket(client, bucket)

    object_name = f"pdfs/{filename}"
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type="application/pdf",
    )
    return object_name


def download_pdf(object_name: str, bucket: str = MINIO_BUCKET) -> bytes:
    """Baixa um PDF do MinIO e retorna os bytes."""
    client = get_client()
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def list_pdfs(bucket: str = MINIO_BUCKET) -> list[dict]:
    """Lista todos os PDFs armazenados no bucket."""
    client = get_client()
    ensure_bucket(client, bucket)

    objects = client.list_objects(bucket, prefix="pdfs/", recursive=True)
    result = []
    for obj in objects:
        result.append({
            "object_name": obj.object_name,
            "filename":    obj.object_name.replace("pdfs/", ""),
            "size_kb":     round(obj.size / 1024, 1) if obj.size else 0,
            "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
        })
    return result


def save_json_result(json_str: str, filename: str, bucket: str = MINIO_BUCKET) -> str:
    """Salva o JSON extraído de volta no MinIO (pasta results/)."""
    client = get_client()
    ensure_bucket(client, bucket)

    json_bytes = json_str.encode("utf-8")
    object_name = f"results/{filename}"
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(json_bytes),
        length=len(json_bytes),
        content_type="application/json",
    )
    return object_name

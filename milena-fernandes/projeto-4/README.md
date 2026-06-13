# Projeto Extra

Extração inteligente de dados estruturados de PDFs de construtoras usando **MinIO + Gemini**.

---

## Arquitetura

```
┌─────────────┐    upload     ┌────────────────┐    S3 API    ┌──────────────┐
│  Frontend   │ ───────────► │  FastAPI API   │ ─────────►  │    MinIO     │
│  (HTML/JS)  │ ◄─────────── │  (Python)      │ ◄─────────  │  (Storage)   │
└─────────────┘   resultados └────────────────┘             └──────────────┘
                                     │
                             pdfplumber / pypdf
                                     │
                                     ▼
                            ┌────────────────┐
                            │  Gemini        │
                            │ (gemini-flash) │
                            └────────────────┘
```

## Stack

| Componente | Tecnologia |
|---|---|
| Storage de PDFs | MinIO (S3-compatível) |
| Backend API | FastAPI + Uvicorn |
| Extração de texto | pdfplumber, pypdf, poppler |
| IA | Gemini 2.5 Flash |
| Frontend | HTML/JS puro (sem dependências) |

---

## Início Rápido

### 1. Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- Chave da API 

### 2. Configuração

```bash
# Clone ou extraia o projeto
cd construdata

# Crie o .env
cp .env.example .env
# Edite .env e coloque sua ANTHROPIC_API_KEY
```

### 3. Subir com Docker

```bash
cd docker
docker compose up -d
```

Serviços disponíveis:
- **API**: http://localhost:8000
- **Docs da API**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (admin: minioadmin / minioadmin123)
- **Frontend**: Abra `frontend/index.html` no browser

### 4. Ou rodar o backend localmente

```bash
cd backend
pip install -r requirements.txt
```

---

## Uso

### Via Frontend

1. Abra `frontend/index.html` no browser
2. Arraste ou clique para selecionar um PDF de construtora
3. Clique em **"Enviar e Analisar com IA"**
4. Visualize os dados extraídos estruturados

### Via API REST

```bash
# Upload + análise em uma chamada
curl -X POST http://localhost:8000/upload-and-analyze \
  -F "file=@relatorio_construtora.pdf"

# Listar PDFs no MinIO
curl http://localhost:8000/pdfs

# Analisar PDF já no MinIO
curl -X POST "http://localhost:8000/analyze/relatorio.pdf"

# Ver resultado salvo
curl http://localhost:8000/results/relatorio_resultado.json
```

### Processamento em lote (CLI)

```bash
# Processar todos os PDFs de uma pasta
python scripts/process_batch.py /caminho/pdfs/ --output ./resultados/

# Sem enviar pro MinIO
python scripts/process_batch.py /caminho/pdfs/ --no-minio
```

---

## Dados Extraídos

Para cada PDF de construtora, o sistema tenta extrair:

### Empresa
- Nome, CNPJ, endereço, telefone, site, ano de fundação

### Financeiro
- Receita bruta, EBITDA, lucro líquido, dívida líquida
- Período de referência

### Operacional
- Unidades lançadas e vendidas
- VSO (Velocidade de Vendas sobre Oferta)
- VGV lançado e vendido
- Estoque, estados de atuação

### Empreendimentos
- Nome, cidade, estado, segmento, fase
- VGV total, número de unidades

### Índices
- ROE, margem bruta, margem líquida, alavancagem

---

## Otimização de Tokens

O sistema aplica várias estratégias para reduzir o uso de tokens:

- **Limite por página**: máximo 3.000 caracteres por página extraída
- **Máximo de páginas**: processa até 30 páginas por PDF
- **Limite global**: máximo 18.000 caracteres de texto no prompt
- **Tabelas limitadas**: máximo 6 tabelas × 40 linhas cada
- **Monitoramento**: custo estimado exibido na interface e na API

Custo típico por PDF: ~US$ 0.003 a 0.01 (dependendo do tamanho)

---

## Estrutura do Projeto

```
construdata/
├── backend/
│   ├── main.py           # FastAPI app + endpoints
│   ├── minio_client.py   # Upload/download MinIO
│   ├── pdf_extractor.py  # Extração de texto/tabelas
│   ├── ai_analyzer.py    # Integração Gemini API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── index.html        # Interface web completa
├── docker/
│   └── docker-compose.yml
├── scripts/
│   └── process_batch.py  # CLI para lote
├── .env.example
└── README.md
```

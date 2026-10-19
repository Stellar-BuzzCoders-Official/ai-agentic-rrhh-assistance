# JoyIt RRHH Assistance — Arquitectura Hexagonal con LangGraph y Azure

Sistema inteligente de asistencia y screening técnico de candidatos para RRHH, orquestado mediante **LangGraph**, con patrón **ReAct**, sub-agente auditor de **Grounding**, persistencia y búsqueda híbrida en **Azure Cosmos DB NoSQL**, extracción de documentos vía **Azure AI Document Intelligence**, y autenticación con **Microsoft Entra ID**.

---

## 🏗️ 1. Arquitectura del Sistema

El proyecto adopta **Arquitectura Hexagonal (Puertos y Adaptadores)**, lo que permite desacoplar la lógica de negocio y agentes de los proveedores tecnológicos (Azure, Google Cloud, MinIO, modelos locales):

```
src/
├── config/                  # Settings con pydantic-settings y Contenedor de Inyección de Dependencias
├── domain/                  # Entidades inmutables (Pydantic v2) y cálculo determinístico de scoring
│   ├── entities.py
│   └── services/scoring.py
├── application/
│   ├── ports/               # Puertos e interfaces abstractas (outbound)
│   └── agent/               # Orquestación con LangGraph
│       ├── state.py         # Estado tipado del grafo
│       ├── prompts.py       # Prompts del agente reclutador y del juez
│       ├── tools/           # Herramientas estructuradas (set_job_requirements, evaluate_cv, search_talent_pool)
│       ├── nodes/           # input_grounding, judge_agent, finalize
│       └── graph.py         # Compilación del grafo con checkpointer
├── infrastructure/          # Adaptadores concretos
│   ├── llm/                 # Azure OpenAI, Gemini, Ollama
│   ├── extraction/          # Azure Document Intelligence, extractor local (pypdf, docx)
│   ├── storage/             # Azure Blob Storage, MinIO (legacy), Memory
│   ├── persistence/         # Azure Cosmos DB NoSQL (checkpointer, vector, threads, users), Memory
│   ├── safety/              # Azure Content Safety (Prompt Shields), No-op
│   └── auth/                # Microsoft Entra ID (JWKS), Dev Token
└── entrypoints/api/         # Controladores FastAPI
    ├── v1/                  # API moderna (streaming SSE, files bulk ≤10, candidates, threads)
    └── v0_legacy/           # Compatibilidad 100% con frontend angular actual
```

---

## 🤖 2. Flujo Orquestado en LangGraph

```mermaid
flowchart TD
    START([START]) --> IG[input_grounding]
    IG -->|Contenido bloqueado| SAFE[safe_reply] --> END([END])
    IG -->|Contenido seguro| AG[recruiter_agent (ReAct)]
    AG -->|tool_calls| TN[tools] --> AG
    AG -->|Respuesta lista & reporte nuevo| JD[judge_agent (Sub-agente Juez)]
    JD -->|Discrepancia detectada & reintentos < 2| AG
    JD -->|Aprobado o límite alcanzado| FZ[finalize]
    AG -->|Sin reporte técnico nuevo| FZ
    FZ --> END
```

### Componentes Clave:
1. **Input Grounding**: Detecta inyecciones de prompt o contenido inapropiado con Content Safety. Si el usuario envía un archivo (base64 o multipart), lo almacena en Blob Storage, extrae el texto estructurado y guarda únicamente la referencia (`file_id`) en el estado.
2. **Recruiter Agent (ReAct)**: Agente principal que interactúa con el usuario y ejecuta herramientas (`set_job_requirements`, `evaluate_cv`, `search_talent_pool`).
3. **Sub-agente Juez de Grounding (Auditor)**: Evalúa de manera independiente si las habilidades marcadas como "Cumple" en el informe técnico tienen sustento fáctico verificable en el texto crudo del CV. Si detecta alucinaciones, devuelve retroalimentación correctiva al agente principal.
4. **Scoring Determinístico**: El cálculo de porcentajes y cumplimiento de requisitos indispensables/deseables se realiza mediante una función matemática transparente en el dominio (`src/domain/services/scoring.py`), garantizando explicabilidad total ante RRHH.
5. **Persistencia de Checkpoints**: El estado de la conversación y del grafo se almacena de forma duradera en **Azure Cosmos DB NoSQL** mediante `CosmosDBSaverSync` particionado por `/partition_key`.

---

## 🔍 3. Talent Pool con Búsqueda Híbrida en Cosmos DB NoSQL

Cada CV evaluado genera un `CandidateProfile` que se indexa automáticamente en el contenedor `candidates` de Cosmos DB NoSQL:
- **Partición por reclutador**: Clave de partición `/recruiterId` (asociada al `oid` de Microsoft Entra ID).
- **Indexación Vectorial**: `DiskANN` sobre el campo `/embedding` (1536 dimensiones con `text-embedding-3-small`).
- **Búsqueda Híbrida**: Combina la similitud vectorial semántica con coincidencias textuales (BM25 con RRF) para encontrar tecnologías y perfiles relevantes.
- **Carga Masiva**: Soporte de ingesta por lote de **hasta 10 CVs** mediante `/api/v1/files/bulk`.

---

## 📡 4. Endpoints de la API

### API v1 (Moderna)
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/chat/stream` | Server-Sent Events (SSE) en tiempo real con eventos de tokens, tools y reportes. |
| `POST` | `/api/v1/chat` | Endpoint JSON síncrono. |
| `POST` | `/api/v1/files/upload` | Carga multipart de un archivo individual con extracción de texto. |
| `POST` | `/api/v1/files/bulk` | Carga masiva de hasta 10 archivos en paralelo. |
| `GET` | `/api/v1/candidates` | Búsqueda híbrida en el Talent Pool del reclutador (`?q=python+fastapi`). |
| `DELETE` | `/api/v1/candidates/{id}` | Eliminación de candidato del pool (derecho ARCO / GDPR). |
| `GET` | `/api/v1/threads` | Historial de hilos de conversación del usuario. |
| `DELETE` | `/api/v1/threads/{id}` | Eliminación de un hilo y sus checkpoints. |
| `GET` | `/api/v1/users/me` | Datos del perfil autenticado. |

### API v0 (Legacy Compatibility)
Garantiza que el frontend Angular existente funcione sin ninguna modificación:
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v0/screeningChat` | Mismo contrato payload/response con `validate`, `technical_report` y `nameHistory`. |
| `GET` | `/api/v0/conversationsIdName/{user_id}` | Lista de conversaciones para el sidebar. |
| `GET` | `/api/v0/getConversation/{id}` | Obtener conversación por ID. |
| `DELETE` | `/api/v0/deleteConversation/{id}` | Eliminar conversación. |
| `POST` | `/api/v0/auth/login` | Login compatible. |
| `GET` | `/api/v0/auth/verify` | Verificación de token. |

---

## 🚀 5. Puesta en Marcha

### Prerrequisitos
- Python 3.11 o superior.
- Instancia de Azure Cosmos DB con API NoSQL (o modo memoria por defecto).

### Instalación Local
```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales de Azure
```

### Ejecutar la Aplicación
```bash
uvicorn app:app --host 0.0.0.0 --port 5000 --reload
```
Documentación interactiva disponible en: `http://localhost:5000/docs`

### Ejecutar Pruebas Automatizadas
```bash
pytest -v
```

---

## 🔒 6. Seguridad y Buenas Prácticas
- **Zero Exposed Secrets**: No se almacenan claves ni credenciales en código ni en `.env.example`.
- **Aislamiento Multiusuario**: Cada reclutador accede únicamente a sus hilos y candidatos (`recruiterId`).
- **Autenticación Empresarial**: Microsoft Entra ID con verificación de tokens RS256 contra las claves públicas JWKS de Microsoft.
- **Normalización de Adjuntos**: Los documentos en base64 no se persisten en los mensajes de chat; se almacenan en storage protegido y se referencian por ID.
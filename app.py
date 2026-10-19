import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.config.container import Container
from src.entrypoints.api.v1.chat_router import router as chat_v1_router
from src.entrypoints.api.v1.files_router import router as files_v1_router
from src.entrypoints.api.v1.threads_router import router as threads_v1_router
from src.entrypoints.api.v1.candidates_router import router as candidates_v1_router
from src.entrypoints.api.v1.users_router import router as users_v1_router
from src.entrypoints.api.v0_legacy.legacy_router import router as legacy_v0_router

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    # Inicializar contenedor de dependencias
    Container.get_instance()
    yield
    logger.info("Deteniendo %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="API de Asistente de RRHH y Screening con LangGraph, Azure Cosmos DB NoSQL y ReAct",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de routers
app.include_router(legacy_v0_router)
app.include_router(chat_v1_router)
app.include_router(files_v1_router)
app.include_router(threads_v1_router)
app.include_router(candidates_v1_router)
app.include_router(users_v1_router)


@app.get("/")
async def root():
    return {
        "message": f"Bienvenido a {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "providers": {
            "llm": settings.LLM_PROVIDER,
            "persistence": settings.PERSISTENCE_PROVIDER,
            "storage": settings.STORAGE_PROVIDER,
            "extractor": settings.EXTRACTOR_PROVIDER,
            "auth": settings.AUTH_PROVIDER,
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

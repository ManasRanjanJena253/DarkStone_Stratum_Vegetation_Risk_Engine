from fastapi import APIRouter
from .endpoints.analysis import router as analysis_router
from .endpoints.search import router as search_router
from .endpoints.sync import router as sync_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(analysis_router)
api_router.include_router(search_router)
api_router.include_router(sync_router)
"""
API Routers for Archive Brain
"""
from .search import router as search_router
from .health import router as health_router
from .workers import router as workers_router
from .jobs import router as jobs_router
from .servers import router as servers_router
from .files import router as files_router
from .settings import router as settings_router

__all__ = [
    'search_router',
    'health_router', 
    'workers_router',
    'jobs_router',
    'servers_router',
    'files_router',
    'settings_router'
]

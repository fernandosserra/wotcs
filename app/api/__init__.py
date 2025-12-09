"""
app/api/__init__.py
Este arquivo re-exporta os routers do pacote `app.api`.
O app.main fará: from app.api import api_routers  --> for r in api_routers: app.include_router(r, prefix=...)
"""

from .auth import router as auth_router
# from .outro_modulo import router as outro_router   # exemplo futuro

# lista ordenada de routers que o main pode registrar.
# Mantém main simples e evita import circular (main importa o pacote; pacotes não importam main).
api_routers = [
    auth_router,
    # outro_router,
]

__all__ = ["auth_router", "api_routers"]

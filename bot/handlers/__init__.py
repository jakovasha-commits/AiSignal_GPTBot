from .start import router as start_router
from .activation import router as activation_router
from .broadcast import router as broadcast_router
from .workspace import router as workspace_router

routers = [start_router, activation_router, broadcast_router, workspace_router]

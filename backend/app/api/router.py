from fastapi import APIRouter

from app.api.routes import applications, auth, candidates, careers, insights, jobs, public, system, team

api_router = APIRouter()
for module in (system, auth, team, jobs, candidates, applications, insights, public, careers):
    api_router.include_router(module.router)

"""
Analytics dashboard web UI.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()

# Setup Jinja2 templates
templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)


@router.get("/dashboard", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    """
    Serve the analytics dashboard web UI.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})

"""Dispatch HTTP routes stub."""
from fastapi import APIRouter

router = APIRouter(prefix="/dispatch", tags=["dispatch"])

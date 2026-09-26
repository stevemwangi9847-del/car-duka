"""Vercel serverless entry point for Car Duka."""
from app import app

# Vercel expects a callable named "app"
__all__ = ["app"]

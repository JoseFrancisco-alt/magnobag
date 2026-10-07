"""Entrada do Magnobag na Vercel: a Vercel roda este arquivo como função Python e entrega o app Flask."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site"))

from app import app  # noqa: E402  (precisa do sys.path acima)

"""Aviso no Discord — mesmo padrao dos outros agentes. Silencioso se nao houver webhook."""
import requests

from .config import env


def avisa(mensagem: str) -> None:
    url = env("DISCORD_WEBHOOK")
    if not url:
        print(mensagem)
        return
    try:
        requests.post(url, json={"content": mensagem[:1900]}, timeout=10)
    except requests.RequestException as erro:
        print(f"[alerta] falhou: {erro}")

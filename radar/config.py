"""Carrega config/sites.yaml e as variaveis de ambiente."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def carrega_sites(caminho: Path | None = None) -> dict:
    caminho = caminho or RAIZ / "config" / "sites.yaml"
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return dados.get("sites", {})


def env(nome: str, obrigatorio: bool = False) -> str | None:
    valor = os.getenv(nome)
    if obrigatorio and not valor:
        raise RuntimeError(f"Variavel de ambiente {nome} nao definida (ver .env.example)")
    return valor


def _lista_env(nome: str) -> set[str]:
    return {s.strip() for s in (env(nome) or "").split(",") if s.strip()}


AMBIENTES = ("nuvem", "mac")
_ambientes_cache: dict[str, str] | None = None


def ambiente_atual() -> str:
    """Quem e' este ambiente: 'mac' (mac/rodar_doll.sh exporta) ou 'nuvem'
    (GitHub Actions; e' o padrao quando RADAR_AMBIENTE nao esta' definida)."""
    valor = (env("RADAR_AMBIENTE") or "nuvem").strip().lower()
    return valor if valor in AMBIENTES else "nuvem"


def _ambientes_dos_sites() -> dict[str, str] | None:
    """{site: ambiente} lido de metas.ambiente, uma vez por processo. None =
    nao ha' banco configurado (teste offline): sem banco nao existe outro
    ambiente com quem dividir, entao tudo roda aqui."""
    global _ambientes_cache
    if _ambientes_cache is None:
        if not (env("SUPABASE_URL") and env("SUPABASE_SERVICE_KEY")):
            return None
        from .banco import Banco
        _ambientes_cache = Banco().ambientes_dos_sites()
    return _ambientes_cache


_desligados_cache: set[str] | None = None


def _sites_desligados() -> set[str] | None:
    """Sites desligados na tela Radar (metas.ligado = false), lidos uma vez
    por processo. None = sem banco configurado (teste offline): nao ha' tela
    que desligue nada."""
    global _desligados_cache
    if _desligados_cache is None:
        if not (env("SUPABASE_URL") and env("SUPABASE_SERVICE_KEY")):
            return None
        from .banco import Banco
        _desligados_cache = Banco().sites_desligados()
    return _desligados_cache


def site_ligado(nome: str) -> bool:
    """O botao liga/desliga do site na tela Radar do conteudo.tihee
    (metas.ligado; site sem linha em metas = ligado). Desligado, o site nao
    coleta, nao escreve e nao publica em NENHUM ambiente, a partir da rodada
    seguinte; religar devolve tudo como estava (meta, periodo, onde roda).

    Se o banco nao responder, conta como desligado: melhor uma rodada perdida
    que publicar num site que a pessoa mandou parar."""
    try:
        desligados = _sites_desligados()
    except Exception as erro:
        print(f"  aviso: nao li se {nome} esta' ligado ({str(erro)[:120]}) — nao roda nesta rodada")
        return False
    return desligados is None or nome not in desligados


def site_ativo(nome: str) -> bool:
    """Este ambiente roda o site?

    Onde cada site roda e' escolhido na tela Radar do conteudo.tihee e fica
    em metas.ambiente ('nuvem' ou 'mac'; site sem linha em metas = nuvem). O
    site roda aqui quando esse valor e' o RADAR_AMBIENTE deste ambiente.
    Trocar na tela vale na rodada seguinte dos dois lados, sem deploy. Sem
    isso o site rodaria nos dois lados e publicaria em dobro.

    Se o banco nao responder, NINGUEM roda (melhor uma rodada perdida que o
    site saindo em dobro, e na nuvem pagando OpenAI).

    RADAR_SITES continua valendo como lista branca local: e' como a rodada
    do Mac chama um site de cada vez.

    (Ate' 17/11/2026 isso era a variavel RADAR_IGNORA_SITES do GitHub.)"""
    so = _lista_env("RADAR_SITES")
    if so and nome not in so:
        return False
    # Botao liga/desliga da tela Radar: vale antes de qualquer ambiente.
    if not site_ligado(nome):
        return False
    try:
        ambientes = _ambientes_dos_sites()
    except Exception as erro:
        print(f"  aviso: nao li onde {nome} roda ({str(erro)[:120]}) — nao roda nesta rodada")
        return False
    if ambientes is None:
        return True
    return ambientes.get(nome, "nuvem") == ambiente_atual()


def filtra_sites(sites: dict) -> dict:
    """Os sites do dict que este ambiente roda (ver site_ativo)."""
    ignorados = [n for n in sites if not site_ativo(n)]
    if ignorados:
        print(f"  (fora deste ambiente ou desligados na tela Radar: {', '.join(ignorados)})")
    return {n: c for n, c in sites.items() if site_ativo(n)}

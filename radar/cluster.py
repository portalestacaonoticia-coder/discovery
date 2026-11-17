"""Agente do cluster: o que a tela Qwen do conteudo.tihee mostra e manda.

O exo so' responde dentro da rede (localhost do Mac mini), entao a tela na
nuvem nao fala com ele. Quem faz a ponte e' este modulo, pelo banco do radar:

  cluster_estado    o Mac ESCREVE: exo no ar, modelo, runners, RAM dos nos,
                    rodada em curso e em que etapa esta'
  cluster_apps      a tela ESCREVE: os blogs/aplicacoes que usam o cluster,
                    com prioridade, pautas por rodada e pausa
  cluster_comandos  a tela ENFILEIRA, o Mac executa: rodar_agora,
                    recarregar_modelo

    python -m radar.cluster agente            # 1 tique: publica o estado e executa comandos
    python -m radar.cluster blogs             # "site por_rodada" por linha, na ordem da rodada
    python -m radar.cluster rodada inicio|fim
    python -m radar.cluster etapa "7d: motor"
    python -m radar.cluster teste ok|falha

`agente` roda de minuto em minuto (mac/com.tihee.cluster-agente.plist) e so'
LE o exo (/state): nunca pede texto, para nao disputar o modelo com a rodada.
Os outros subcomandos sao chamados pelo mac/rodar_doll.sh.

Nada aqui derruba a rodada: se o banco falhar, o subcomando avisa e sai com 0
(menos `blogs`, que sai com 1 — sem saber quem roda, a rodada nao roda ninguem).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone

import requests

from .banco import Banco
from .config import carrega_sites, env, site_ativo

NO = "mac-mini"
ROTULO_RODADA = "com.tihee.radar-doll"
MODELO_PADRAO = "mlx-community/Qwen3.8-27B-8bit"
PRAZO_EXO = 10


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_exo() -> str:
    return (env("LLM_LOCAL_URL") or "http://localhost:52415/v1").rstrip("/").removesuffix("/v1")


def _gb(v) -> float | None:
    try:
        return round(int((v or {}).get("inBytes")) / 1024 ** 3, 1)
    except (TypeError, ValueError):
        return None


def resume_estado(estado: dict | None) -> dict:
    """O /state do exo (centenas de KB) reduzido ao que a tela mostra."""
    if not isinstance(estado, dict):
        return {"exo_no_ar": False, "instancias": 0, "runners_prontos": 0,
                "runners": {}, "nos": [], "modelo": None}
    contagem: dict[str, int] = {}
    for r in (estado.get("runners") or {}).values():
        nome = next(iter(r), "desconhecido") if isinstance(r, dict) else "desconhecido"
        contagem[nome] = contagem.get(nome, 0) + 1
    modelo = None
    for inst in (estado.get("instances") or {}).values():
        try:
            modelo = next(iter(inst.values()))["shardAssignments"]["modelId"]
        except (AttributeError, KeyError, StopIteration, TypeError):
            pass
    nos = []
    identidades = estado.get("nodeIdentities") or {}
    for no_id, ident in identidades.items():
        mem = (estado.get("nodeMemory") or {}).get(no_id) or {}
        sis = (estado.get("nodeSystem") or {}).get(no_id) or {}
        nos.append({
            "nome": ident.get("friendlyName") or ident.get("modelId") or no_id[-6:],
            "chip": ident.get("chipId"),
            "ram_total_gb": _gb(mem.get("ramTotal")),
            "ram_livre_gb": _gb(mem.get("ramAvailable")),
            "gpu": round(float(sis.get("gpuUsage") or 0), 2),
            "temp": round(float(sis.get("temp") or 0), 1) or None,
            "visto_em": (estado.get("lastSeen") or {}).get(no_id),
        })
    return {"exo_no_ar": True, "instancias": len(estado.get("instances") or {}),
            "runners_prontos": contagem.get("RunnerReady", 0), "runners": contagem,
            "nos": sorted(nos, key=lambda n: n["nome"]), "modelo": modelo}


def le_exo() -> dict | None:
    try:
        r = requests.get(f"{_base_exo()}/state", timeout=PRAZO_EXO)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def aviso_do_estado(resumo: dict) -> str | None:
    """A frase que a tela mostra em destaque quando algo pede atencao."""
    if not resumo["exo_no_ar"]:
        return "O exo nao responde no Mac mini. Abra o EXO nos dois Macs."
    if len(resumo["nos"]) < 2:
        return "So' um Mac esta' no cluster. Confira se o MacBook esta' ligado e com o EXO aberto."
    if resumo["instancias"] == 0:
        return "O exo esta' de pe' sem modelo carregado. Use 'Recarregar modelo'."
    if resumo["runners_prontos"] < 2 and not resumo["runners"].get("RunnerRunning"):
        return "O modelo esta' carregado, mas os runners nao estao prontos."
    return None


def executa(comando: str, resumo: dict) -> tuple[bool, str]:
    if comando == "rodar_agora":
        r = subprocess.run(["launchctl", "kickstart", f"gui/{os.getuid()}/{ROTULO_RODADA}"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode:
            return False, (r.stderr or r.stdout or "launchctl falhou").strip()[:300]
        return True, "rodada disparada (se ja' havia uma em curso, ela segue)"
    if comando == "recarregar_modelo":
        if not resumo["exo_no_ar"]:
            return False, "o exo nao responde; abra o EXO nos dois Macs antes"
        if resumo["instancias"] > 0:
            return True, "ja' ha' modelo carregado; nada a fazer"
        r = requests.post(f"{_base_exo()}/place_instance", timeout=30, json={
            "model_id": env("LLM_LOCAL_MODELO") or MODELO_PADRAO,
            "sharding": "Tensor", "instance_meta": "MlxJaccl", "min_nodes": 2})
        if not r.ok:
            return False, f"o exo recusou a carga (HTTP {r.status_code})"
        return True, "carga pedida; os runners levam alguns minutos para ficar prontos"
    return False, f"comando desconhecido: {comando}"


def agente(banco: Banco) -> None:
    resumo = resume_estado(le_exo())
    banco.grava_cluster_estado(NO, {**resumo, "aviso": aviso_do_estado(resumo),
                                    "atualizado_em": _agora()})
    for c in banco.cluster_comandos_pendentes():
        banco.marca_cluster_comando(c["id"], "executando")
        try:
            ok, texto = executa(c["comando"], resumo)
        except Exception as erro:
            ok, texto = False, str(erro)[:300]
        banco.marca_cluster_comando(c["id"], "feito" if ok else "falhou", texto)
        print(f"comando {c['id']} {c['comando']}: {'ok' if ok else 'FALHOU'} — {texto}")


def blogs_da_rodada(apps: list[dict], sites: dict, ativo=site_ativo, tem_env=os.getenv) -> tuple[list[tuple[str, int]], list[str]]:
    """Os blogs que ESTA rodada roda, na ordem: cadastrados, sem pausa, com o
    site marcado para este ambiente e com a senha do WordPress no .env.
    Devolve ([(site, por_rodada)], [por que cada um ficou de fora])."""
    saem, fora = [], []
    for app in sorted(apps, key=lambda a: (a.get("prioridade") or 50, a.get("id") or "")):
        if app.get("tipo") != "blog":
            continue
        site = app.get("site") or app.get("id")
        if app.get("pausado"):
            fora.append(f"{site}: pausado na tela")
        elif site not in sites:
            fora.append(f"{site}: nao existe em config/sites.yaml")
        elif not ativo(site):
            fora.append(f"{site}: marcado para rodar em outro ambiente")
        else:
            wp = sites[site].get("wordpress") or {}
            faltam = [v for v in (wp.get("usuario_env"), wp.get("senha_env")) if v and not tem_env(v)]
            if faltam:
                fora.append(f"{site}: falta {' e '.join(faltam)} no .env")
            else:
                saem.append((site, int(app.get("por_rodada") or 0)))
    return saem, fora


def main() -> int:
    p = argparse.ArgumentParser(description="Agente do cluster (tela Qwen)")
    sub = p.add_subparsers(dest="acao", required=True)
    sub.add_parser("agente")
    sub.add_parser("blogs")
    sub.add_parser("rodada").add_argument("momento", choices=["inicio", "fim"])
    sub.add_parser("etapa").add_argument("texto")
    sub.add_parser("teste").add_argument("resultado", choices=["ok", "falha"])
    args = p.parse_args()

    if args.acao == "blogs":
        try:
            saem, fora = blogs_da_rodada(Banco().cluster_apps(), carrega_sites())
        except Exception as erro:
            print(f"nao li o cadastro do cluster ({str(erro)[:120]})", file=sys.stderr)
            return 1
        for motivo in fora:
            print(f"  fora da rodada — {motivo}", file=sys.stderr)
        for site, por_rodada in saem:
            print(site, por_rodada)
        return 0

    try:
        banco = Banco()
        if args.acao == "agente":
            agente(banco)
        elif args.acao == "rodada" and args.momento == "inicio":
            banco.grava_cluster_estado(NO, {"rodada_em_curso": True, "rodada_inicio": _agora(),
                                            "etapa": "conferindo o exo"})
        elif args.acao == "rodada":
            banco.grava_cluster_estado(NO, {"rodada_em_curso": False, "etapa": None,
                                            "ultima_rodada_fim": _agora()})
        elif args.acao == "etapa":
            banco.grava_cluster_estado(NO, {"etapa": args.texto[:120]})
        elif args.acao == "teste":
            ok = args.resultado == "ok"
            anterior = (banco.cluster_estado(NO) or {}).get("falhas_seguidas") or 0
            banco.grava_cluster_estado(NO, {"ultimo_teste_ok": ok, "ultimo_teste_em": _agora(),
                                            "falhas_seguidas": 0 if ok else anterior + 1})
    except Exception as erro:
        print(f"  aviso: cluster.{args.acao} nao gravou ({str(erro)[:120]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

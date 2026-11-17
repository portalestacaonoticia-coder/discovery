"""Teste offline do agente do cluster (tela Qwen): resumo do /state do exo,
aviso em destaque e quem entra na rodada.

    python testar_cluster.py
"""
from radar.cluster import aviso_do_estado, blogs_da_rodada, executa, resume_estado

GB = 1024 ** 3
ESTADO = {
    "instances": {"i1": {"MlxJacclInstance": {"shardAssignments": {"modelId": "mlx-community/Qwen3.8-27B-8bit"}}}},
    "runners": {"a": {"RunnerReady": {}}, "b": {"RunnerReady": {}}, "c": {"RunnerShuttingDown": {}}},
    "nodeIdentities": {"n1": {"friendlyName": "Mac mini", "chipId": "Apple M4 Pro"},
                       "n2": {"friendlyName": "MacBook Pro", "chipId": "Apple M4 Pro"}},
    "nodeMemory": {"n1": {"ramTotal": {"inBytes": 48 * GB}, "ramAvailable": {"inBytes": 12 * GB}}},
    "nodeSystem": {"n1": {"gpuUsage": 0.5, "temp": 46.2}},
    "lastSeen": {"n1": "2026-11-17T19:00:00Z"},
}
r = resume_estado(ESTADO)
assert r["exo_no_ar"] and r["instancias"] == 1 and r["runners_prontos"] == 2
assert r["runners"] == {"RunnerReady": 2, "RunnerShuttingDown": 1}
assert r["modelo"] == "mlx-community/Qwen3.8-27B-8bit"
assert [n["nome"] for n in r["nos"]] == ["Mac mini", "MacBook Pro"]
assert r["nos"][0]["ram_livre_gb"] == 12.0 and r["nos"][0]["ram_total_gb"] == 48.0
assert r["nos"][1]["ram_livre_gb"] is None            # no sem leitura de memoria nao quebra
assert aviso_do_estado(r) is None

fora = resume_estado(None)
assert not fora["exo_no_ar"] and "nao responde" in aviso_do_estado(fora)
assert "So' um Mac" in aviso_do_estado(resume_estado({**ESTADO, "nodeIdentities": {"n1": {}}}))
assert "sem modelo" in aviso_do_estado(resume_estado({**ESTADO, "instances": {}}))
assert "runners" in aviso_do_estado(resume_estado({**ESTADO, "runners": {"a": {"RunnerLoading": {}}}}))
# gerando: runner ocupado nao e' problema
assert aviso_do_estado(resume_estado({**ESTADO, "runners": {"a": {"RunnerRunning": {}}, "b": {"RunnerRunning": {}}}})) is None

SITES = {"doll": {"wordpress": {"usuario_env": "WP_DOLL_USUARIO", "senha_env": "WP_DOLL_SENHA"}},
         "7d": {"wordpress": {"usuario_env": "WP_7D_USUARIO", "senha_env": "WP_7D_SENHA"}},
         "broune": {"wordpress": {"usuario_env": "WP_BROUNE_USUARIO", "senha_env": "WP_BROUNE_SENHA"}}}
APPS = [
    {"id": "7d", "tipo": "blog", "site": "7d", "prioridade": 20, "por_rodada": 3},
    {"id": "doll", "tipo": "blog", "site": "doll", "prioridade": 10, "por_rodada": 2},
    {"id": "broune", "tipo": "blog", "site": "broune", "prioridade": 5, "por_rodada": 2},
    {"id": "parado", "tipo": "blog", "site": "doll", "prioridade": 1, "pausado": True},
    {"id": "fantasma", "tipo": "blog", "site": "nao-existe", "prioridade": 2},
    {"id": "resumos", "tipo": "aplicacao", "prioridade": 1},
]
ENV = {"WP_DOLL_USUARIO": "u", "WP_DOLL_SENHA": "s", "WP_7D_USUARIO": "u", "WP_7D_SENHA": "s",
       "WP_BROUNE_USUARIO": "u", "WP_BROUNE_SENHA": "s"}
no_mac = lambda site: site in ("doll", "7d")           # broune esta' marcado para a nuvem
saem, fora = blogs_da_rodada(APPS, SITES, ativo=no_mac, tem_env=ENV.get)
assert saem == [("doll", 2), ("7d", 3)], saem          # por prioridade; aplicacao nao entra
assert len(fora) == 3 and any("pausado" in f for f in fora) and any("outro ambiente" in f for f in fora)
sem_senha = {k: v for k, v in ENV.items() if not k.startswith("WP_7D")}
saem, fora = blogs_da_rodada(APPS, SITES, ativo=no_mac, tem_env=sem_senha.get)
assert saem == [("doll", 2)] and any("WP_7D_USUARIO e WP_7D_SENHA" in f for f in fora)

# comandos que nao dependem do exo nem do launchd
assert executa("apagar_tudo", r) == (False, "comando desconhecido: apagar_tudo")
assert executa("recarregar_modelo", r)[0] is True and "nada a fazer" in executa("recarregar_modelo", r)[1]
assert executa("recarregar_modelo", fora_ := resume_estado(None))[0] is False
print("ok: cluster — resumo do exo, avisos, blogs da rodada e comandos")

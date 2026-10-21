"""Dado proprio de cada categoria do doll (21/10/2026).

Ate' aqui todo satelite usava a mesma PTAX do dolar e so' trocava a
manchete: em 20/10, 6 satelites do dia tinham 59% do texto igual. Agora cada
categoria traz o seu numero do dia, de fonte oficial (radar/indicadores_bcb.py),
com as contas feitas por codigo:

    indicadores         Focus (cambio e IPCA) x PTAX, IPCA oficial em 12 meses
    politica-monetaria  Selic meta, ultima mudanca, juro real, Focus da Selic
    viagem              PTAX de uma moeda de viagem (rodizio) e custo com IOF
    cotacao             (sem extra: o gerador usa a serie da PTAX do dolar)

`dado(hub, n, site, hoje)` devolve None para cotacao ou se a fonte falhar
(o gerador cai na PTAX do dolar) ou {tema, fatos, foco, extras, about}.
`extras` e' o que o conferente aceita alem da PTAX (ver confere_satelite).
"""
from __future__ import annotations

from datetime import date

from . import indicadores_bcb as bcb
from .gerador_dolar import MESES, brl, pct


def _mov(v: float, sobe: str = "subiu", desce: str = "caiu") -> str:
    return sobe if v > 0.005 else desce if v < -0.005 else "ficou estavel em"


def _pp(v: float) -> str:
    """Pontos percentuais no padrao brasileiro: 0,25 ponto / 1,50 ponto."""
    return f"{abs(v):.2f}".replace(".", ",") + (" ponto percentual" if abs(v) < 2
                                                else " pontos percentuais")


def _extras() -> dict:
    return {"brl": [], "pct": [], "variacoes_moeda": {}, "variacoes_outras": {},
            "datas": []}


def _ptax_contexto(n: dict) -> str:
    return (f"para contexto, a PTAX de venda do DOLAR no pregao de "
            f"{n['data']:%d/%m} foi {brl(n['venda'], 4)}"
            + (f" ({_mov(n['var_dia'])} {pct(abs(n['var_dia']))} no dia)"
               if n.get("var_dia") is not None else "")
            + " — cite no maximo UMA vez; nao e' o assunto do texto")


def _indicadores(n: dict, hoje: date) -> dict | None:
    ano = hoje.year if hoje.month < 12 else hoje.year + 1
    cambio = bcb.focus("Câmbio", ano, hoje)
    if not cambio:
        return None
    cambio_prox = bcb.focus("Câmbio", ano + 1, hoje)
    ipca_focus = bcb.focus("IPCA", ano, hoje)
    ipca = bcb.ipca_12m(hoje)
    ex = _extras()
    fatos = [f"pesquisa Focus do Banco Central (dados de {cambio['data']:%d/%m/%Y}): "
             f"mediana do mercado para o dolar no fim de {ano} = "
             f"{brl(cambio['mediana'], 2)}"]
    ex["brl"] += [cambio["mediana"]]
    ex["datas"] += [cambio["data"]]
    if cambio.get("mediana_antes"):
        rev = (cambio["mediana"] / cambio["mediana_antes"] - 1) * 100
        fatos.append(f"cerca de 4 semanas antes (Focus de {cambio['data_antes']:%d/%m}) "
                     f"a mediana era {brl(cambio['mediana_antes'], 2)}: a projecao "
                     f"{_mov(rev)} {pct(abs(rev))} — ou seja, o mercado passou a esperar "
                     f"um dolar {'MAIS CARO' if rev > 0 else 'MAIS BARATO'} no fim do ano")
        ex["brl"] += [cambio["mediana_antes"]]
        ex["datas"] += [cambio["data_antes"]]
        ex["variacoes_moeda"]["na revisao da projecao do dolar"] = rev
    if cambio_prox:
        fatos.append(f"mediana para o dolar no fim de {ano + 1} = "
                     f"{brl(cambio_prox['mediana'], 2)}")
        ex["brl"] += [cambio_prox["mediana"]]
    dist = (n["venda"] / cambio["mediana"] - 1) * 100
    fatos.append(f"a PTAX do dolar de {n['data']:%d/%m} ({brl(n['venda'], 4)}) esta' "
                 f"{pct(abs(dist))} {'ACIMA' if dist > 0 else 'ABAIXO'} da projecao "
                 f"do mercado para o fim de {ano} (a projecao esta' "
                 f"{'ABAIXO' if dist > 0 else 'ACIMA'} da PTAX)")
    ex["pct"] += [abs(dist)]
    ex["projecao"] = cambio["mediana"]
    if ipca_focus:
        fatos.append(f"Focus: IPCA esperado para {ano} = {pct(ipca_focus['mediana'])}"
                     + (f" (4 semanas antes: {pct(ipca_focus['mediana_antes'])})"
                        if ipca_focus.get("mediana_antes") else ""))
        ex["pct"] += [ipca_focus["mediana"]] + (
            [ipca_focus["mediana_antes"]] if ipca_focus.get("mediana_antes") else [])
    if ipca:
        fatos.append(f"IPCA oficial (IBGE) acumulado em 12 meses ate' "
                     f"{MESES[ipca['referencia'].month - 1]} de {ipca['referencia'].year}"
                     f" = {pct(ipca['valor'])}")
        ex["pct"] += [ipca["valor"]]
    fatos.append(_ptax_contexto(n))
    return {"tema": f"o que o mercado espera para o dolar e a inflacao (Focus) "
                    f"comparado com a PTAX de hoje",
            "fatos": fatos, "extras": ex, "about": "Projeções do mercado (Focus)",
            "foco": ("O assunto e' a PROJECAO do mercado (Focus): quanto o mercado "
                     "espera para o dolar no fim do ano, como essa projecao mudou "
                     "em 4 semanas e onde a PTAX de hoje esta' em relacao a ela. "
                     "Projecao NAO e' previsao do doll: atribua sempre ao Focus / "
                     "'ao mercado'. Diga o que significa para quem vai comprar dolar.")}


# Meta de inflacao do CMN (meta continua desde 2025): centro de 3% e
# tolerancia de 1,5 ponto. CONFERIR se o CMN mudar.
META_INFLACAO = 3.0
TOLERANCIA_INFLACAO = 1.5


def _inflacao(n: dict, hoje: date) -> dict | None:
    """2o recorte de indicadores (21/10/2026): o assunto e' a INFLACAO, nao o
    cambio — o 1o recorte fala do Focus do dolar."""
    mes = bcb.ipca_mes(hoje)
    ipca = bcb.ipca_12m(hoje)
    if not (mes and ipca):
        return None
    ano = hoje.year if hoje.month < 12 else hoje.year + 1
    f_ano = bcb.focus("IPCA", ano, hoje)
    f_prox = bcb.focus("IPCA", ano + 1, hoje)
    teto = META_INFLACAO + TOLERANCIA_INFLACAO
    ex = _extras()
    nome_mes = MESES[mes["referencia"].month - 1]
    fatos = [f"IPCA (IBGE) de {nome_mes} de {mes['referencia'].year}: {pct(mes['valor'])} "
             f"no mes (em {MESES[mes['referencia_anterior'].month - 1]}: "
             f"{pct(mes['anterior'])})",
             f"IPCA acumulado em 12 meses ate' {MESES[ipca['referencia'].month - 1]}: "
             f"{pct(ipca['valor'])}",
             f"meta de inflacao do Conselho Monetario Nacional: {pct(META_INFLACAO)} "
             f"(centro), com tolerancia de 1,5 ponto percentual — teto de {pct(teto)}; "
             f"o acumulado em 12 meses esta' "
             f"{'ACIMA' if ipca['valor'] > teto else 'DENTRO'} do intervalo da meta"
             + ("" if ipca["valor"] > teto else
                f" ({'acima' if ipca['valor'] > META_INFLACAO else 'abaixo'} do centro)")]
    ex["pct"] += [mes["valor"], mes["anterior"], ipca["valor"], META_INFLACAO,
                  TOLERANCIA_INFLACAO, teto]
    ex["variacoes_outras"][f"o IPCA de {nome_mes}"] = mes["valor"]
    if f_ano:
        leitura = ""
        if f_ano.get("mediana_antes") is not None:
            d = f_ano["mediana"] - f_ano["mediana_antes"]
            leitura = (f" (4 semanas antes: {pct(f_ano['mediana_antes'])} — o mercado passou "
                       f"a esperar inflacao {'MAIOR' if d > 0 else 'MENOR'} em {ano})"
                       if abs(d) > 1e-9 else f" (igual a 4 semanas antes)")
            ex["pct"] += [f_ano["mediana_antes"]]
        fatos.append(f"Focus (dados de {f_ano['data']:%d/%m}): IPCA esperado para {ano} = "
                     f"{pct(f_ano['mediana'])}{leitura}")
        ex["pct"] += [f_ano["mediana"]]
        ex["datas"] += [f_ano["data"]]
    if f_prox:
        fatos.append(f"Focus: IPCA esperado para {ano + 1} = {pct(f_prox['mediana'])}")
        ex["pct"] += [f_prox["mediana"]]
    fatos.append(_ptax_contexto(n))
    return {"tema": "a inflacao (IPCA) e o que o mercado espera para ela",
            "fatos": fatos, "extras": ex, "about": "Inflação (IPCA)", "exemplos": "indicadores-inflacao",
            "foco": ("O assunto e' a INFLACAO: o IPCA do mes, o acumulado em 12 meses "
                     "frente a meta e o que o mercado espera (Focus). Pode explicar, em "
                     "termos gerais, que dolar mais caro tende a encarecer importados e "
                     "viagens, SEM dizer que o cambio explica o indice do mes. Nao "
                     "invente causa da inflacao nem decisao futura do Copom.")}


def _politica(n: dict, hoje: date) -> dict | None:
    selic = bcb.selic_meta(hoje)
    if not selic:
        return None
    ipca = bcb.ipca_12m(hoje)
    ano = hoje.year if hoje.month < 12 else hoje.year + 1
    focus_selic = bcb.focus("Selic", ano, hoje)
    ex = _extras()
    fatos = [f"meta da Selic vigente: {pct(selic['valor'])} ao ano, desde "
             f"{selic['desde']:%d/%m/%Y}"]
    ex["pct"] += [selic["valor"]]
    ex["datas"] += [selic["desde"]]
    if selic.get("anterior") is not None:
        mud = selic["valor"] - selic["anterior"]
        fatos.append(f"antes dessa decisao a meta era {pct(selic['anterior'])}: o Copom "
                     f"{'cortou' if mud < 0 else 'elevou'} a Selic em {_pp(mud)}")
        ex["pct"] += [selic["anterior"], abs(mud)]
    if ipca:
        real = selic["valor"] - ipca["valor"]
        fatos.append(f"IPCA acumulado em 12 meses ate' "
                     f"{MESES[ipca['referencia'].month - 1]}: {pct(ipca['valor'])} — "
                     f"(IPCA e' do IBGE) — o juro real aproximado (Selic menos IPCA de 12 meses) e' de "
                     f"{_pp(real).replace(' ponto percentual', '').replace(' pontos percentuais', '')} "
                     f"pontos percentuais")
        ex["pct"] += [ipca["valor"], abs(real)]
    if focus_selic:
        antes_s = focus_selic.get("mediana_antes")
        leitura = ""
        if antes_s is not None and abs(focus_selic["mediana"] - antes_s) > 1e-9:
            leitura = (" — ou seja, o mercado passou a esperar a Selic "
                       + ("MAIS BAIXA (mais cortes)" if focus_selic["mediana"] < antes_s
                          else "MAIS ALTA (menos cortes)") + " no fim do ano")
        fatos.append(f"Focus (dados de {focus_selic['data']:%d/%m}): o mercado espera a "
                     f"Selic em {pct(focus_selic['mediana'])} no fim de {ano}"
                     + (f" (4 semanas antes: {pct(antes_s)})" if antes_s else "") + leitura)
        ex["pct"] += [focus_selic["mediana"]] + (
            [focus_selic["mediana_antes"]] if focus_selic.get("mediana_antes") else [])
        ex["datas"] += [focus_selic["data"]]
    fatos.append(_ptax_contexto(n))
    return {"tema": "o nivel dos juros (Selic) e o que ele significa para o cambio",
            "fatos": fatos, "extras": ex, "about": "Taxa Selic",
            "foco": ("O assunto e' a SELIC: o nivel atual, a ultima decisao do Copom, "
                     "o juro real e o que o mercado espera. Explique de forma "
                     "simples por que juros altos tendem a atrair dolares ao pais, "
                     "SEM afirmar que isso explica a cotacao de hoje. Nao invente "
                     "data de reuniao do Copom nem decisao futura.")}


def _viagem(n: dict, site: dict, hoje: date, recorte: int = 0) -> dict | None:
    codigo = bcb.moeda_do_dia(hoje, recorte)
    m = bcb.moeda(codigo, hoje)
    if not m:
        return None
    iof = float((site.get("iof") or {}).get("cartao_credito", 3.5))
    ex = _extras()
    custo = 1000 * m["venda"]
    custo_iof = custo * (1 + iof / 100)
    fatos = [f"moeda do dia: {m['nome']} ({codigo}); PTAX de venda do Banco Central "
             f"no pregao de {m['data']:%d/%m/%Y}: {brl(m['venda'], 4)}",
             f"no dia o {m['nome']} {_mov(m['var_dia'])} {pct(abs(m['var_dia']))}",
             f"nos ultimos {m['pregoes']} pregoes (cerca de um mes) o {m['nome']} "
             f"{_mov(m['var_30d'])} {pct(abs(m['var_30d']))} (era {brl(m['venda_30d'], 4)}),"
             f" oscilando entre {brl(m['menor_30d'], 4)} e {brl(m['maior_30d'], 4)} "
             f"NESSE MES (nao e' a minima/maxima do ano)",
             f"1.000 {m['plural']} pela PTAX = {brl(custo)}; com IOF de "
             f"{pct(iof)} (cartao ou especie) = {brl(custo_iof)} — sem contar o "
             f"spread de bancos e casas de cambio"]
    ex["brl"] += [m["venda"], m["venda_30d"], m["menor_30d"], m["maior_30d"],
                  custo, custo_iof, custo_iof - custo]
    ex["pct"] += [iof]
    ex["faixa_30d"] = [m["menor_30d"], m["maior_30d"]]
    ex["variacoes_moeda"][f"o {m['nome']} no dia"] = m["var_dia"]
    ex["variacoes_moeda"][f"o {m['nome']} em cerca de um mes"] = m["var_30d"]
    ex["datas"] += [m["data"]]
    fatos.append(_ptax_contexto(n))
    return {"tema": f"quanto custa o {m['nome']} para quem vai viajar",
            "fatos": fatos, "extras": ex, "about": f"Cotação do {m['nome']}",
            "foco": (f"O assunto e' o {m['nome'].upper()} para quem vai viajar: a "
                     f"cotacao do dia, a variacao em cerca de um mes e quanto custam "
                     f"1.000 {m['plural']} com IOF. A manchete e' so' o gancho (pode "
                     f"ser sobre o dolar): ligue-a ao {m['nome']} sem inventar "
                     f"relacao de causa. Nao chame a PTAX de 'cotacao turismo'.")}


def dado(hub: str, n: dict, site: dict, hoje: date, recorte: int = 0) -> dict | None:
    """recorte = quantos satelites da categoria ja' sairam hoje (0 ou 1): o 2o
    do dia usa outro dado — inflacao em indicadores, 2a moeda em viagem."""
    try:
        if hub == "indicadores":
            return _inflacao(n, hoje) if recorte else _indicadores(n, hoje)
        if hub == "politica-monetaria":
            return _politica(n, hoje)
        if hub == "viagem":
            return _viagem(n, site, hoje, recorte)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return None

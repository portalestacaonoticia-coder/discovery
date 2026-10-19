"""Conferente do satelite escrito pelo modelo (19/10/2026).

No ensaio local, sem o pensamento, o Qwen errou o que o codigo sabe de cor:
inverteu alta e queda ("queda de 0,60%" num dia de alta), inventou cotacao
("fecha acima de R$ 5,22" com a PTAX a R$ 5,0826) e chamou a manchete de
duas semanas antes de "nesta segunda-feira (19)". Aqui nada depende do
modelo: cada valor, percentual, direcao e data do texto e' conferido contra
os numeros que o proprio gerador entregou (`_numeros`) e contra a manchete.

    problemas = confere(titulo, corpo, n, manchete, hoje, data_manchete)
    [] = aprovado; senao, uma frase por problema, pronta para o modelo ler.
"""
from __future__ import annotations

import re
from datetime import date

from .gerador_dolar import DIAS, MESES, brl, pct

_RE_BRL = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d+)?)")
_RE_PCT = re.compile(r"(\d+(?:,\d+)?)\s?%")
_RE_SEQ = re.compile(r"seguid[oa]s?\s+de\s+(alta|queda|valoriza\w*|desvaloriza\w*)", re.I)
# "16 de outubro", "(16)", "16/10"
_RE_DATA_EXT = re.compile(r"\b(\d{1,2})(?:º)?\s+de\s+(" + "|".join(MESES) + r")\b", re.I)
_RE_DATA_PAR = re.compile(r"\((\d{1,2})\)")
_RE_DATA_BAR = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\b")

# Ultima palavra de direcao antes do numero decide o que o texto afirmou.
_SOBE = r"alta|subi\w*|sobe|avan\w*|positiv\w*|ganh\w*|valoriz\w*"
_DESCE = r"queda|ca[ií]\w*|recu\w*|negativ\w*|perd\w*|desvaloriz\w*|baixa"
_RE_DIRECAO = re.compile(rf"\b({_SOBE}|{_DESCE})\b", re.I)


# Estilo (19/10/2026, 2a rodada do ensaio): termos que o Qwen repetia e que
# o portal nao assina. (padrao, por que) — o motivo vai para o modelo.
_PROIBIDOS = [
    (r"d[oó]lar comercial", "a PTAX e' a taxa de referencia do BC, nao o 'dolar comercial'"),
    (r"(m[aá]xima|m[ií]nima|pico|topo|piso)s? hist[oó]ric[ao]s?",
     "os extremos fornecidos sao do ultimo ano, nao 'historicos'"),
    (r"segundo o ve[ií]culo|o ve[ií]culo\b", "fonte sem nome e' 'a imprensa', nunca 'o veiculo'"),
    (r"\b(suporte|resist[eê]ncia|barreiras? t[eé]cnicas?|rompimento|rota[cç][aã]o de posi[cç][oõ]es"
     r"|derivativos|hedge)\b", "sem analise tecnica ou de mercado propria: so' os numeros"),
]


def _num(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _sentido(palavra: str) -> int:
    return 1 if re.fullmatch(_SOBE, palavra, re.I) else -1


def _bate(valor: float, permitidos: list[float]) -> bool:
    """O valor e' um dos permitidos, aceitando arredondamento (R$ 5,08 para
    R$ 5,0826; 1,7% para 1,68%)."""
    for p in permitidos:
        for casas in (4, 3, 2, 1, 0):
            if abs(round(p, casas) - valor) < 1e-9:
                return True
    return False


def _trecho_antes(texto: str, pos: int) -> str:
    """Do inicio da frase (ou da virgula anterior) ate o numero."""
    inicio = max(texto.rfind(s, 0, pos) for s in (". ", "; ", "\n", ": "))
    return texto[inicio + 1:pos]


def confere(titulo: str, corpo: str, n: dict, manchete: str, hoje: date,
            data_manchete: date | None) -> list[str]:
    texto = f"{titulo}\n{corpo}"
    problemas: list[str] = []

    # 1. Cotacoes: so' as da base, as distancias entre elas e as da manchete.
    base = [n["venda"], n["maior"], n["menor"], n["max_ano"], n["min_ano"]]
    distancias = [abs(n["venda"] - x) for x in base[1:]]
    da_manchete = [_num(m) for m in _RE_BRL.findall(manchete or "")]
    for m in _RE_BRL.finditer(texto):
        v = _num(m.group(1))
        if not _bate(v, base + distancias + da_manchete):
            problemas.append(f"o valor R$ {m.group(1)} nao esta nos dados "
                             f"(a PTAX e' {brl(n['venda'], 4)}); use so' os numeros fornecidos")

    # 2. Percentuais: cada um tem dono (dia, semana, mes, janela) e direcao.
    variacoes = {"no pregao": n.get("var_dia"), "na semana": n.get("var_semana"),
                 "no mes": n.get("var_mes"), "nos ultimos pregoes": n.get("var_janela")}
    variacoes = {k: v for k, v in variacoes.items() if v is not None}
    pct_manchete = [_num(p) for p in _RE_PCT.findall(manchete or "")]
    for m in _RE_PCT.finditer(texto):
        v = _num(m.group(1))
        donos = [(k, x) for k, x in variacoes.items() if _bate(v, [abs(x)])]
        if not donos:
            if not _bate(v, pct_manchete):
                problemas.append(f"o percentual {m.group(1)}% nao esta nos dados; "
                                 "use so' as variacoes fornecidas")
            continue
        sentidos = {1 if x > 0 else -1 for _, x in donos}
        if len(sentidos) != 1:
            continue  # mesmo numero, direcoes opostas: nao da' para cobrar
        certo = sentidos.pop()
        palavras = _RE_DIRECAO.findall(_trecho_antes(texto, m.start()))
        if palavras and _sentido(palavras[-1]) != certo:
            onde = donos[0][0]
            problemas.append(
                f"direcao invertida em \"{palavras[-1]} ... {m.group(1)}%\": "
                f"{onde} o dolar {'SUBIU' if certo > 0 else 'CAIU'} {pct(abs(donos[0][1]))}")

    # 3. A sequencia de pregoes tem a direcao da base.
    if n.get("seq", 0) >= 2:
        for m in _RE_SEQ.finditer(texto):
            if _sentido(m.group(1)) != n["direcao"]:
                problemas.append(
                    f"a sequencia e' de {'alta' if n['direcao'] > 0 else 'queda'}, "
                    f"nao de {m.group(1)}")

    # 4. Datas: so' o pregao, os extremos do ano, a manchete e hoje (hoje so'
    # quando for o proprio pregao ou o dia da manchete).
    validas = {n["data"], n["max_quando"], n["min_quando"]}
    if data_manchete:
        validas.add(data_manchete)
    if hoje in (n["data"], data_manchete):
        validas.add(hoje)
    dias_validos = {d.day for d in validas}
    for m in _RE_DATA_EXT.finditer(texto):
        dia, mes = int(m.group(1)), MESES.index(m.group(2).lower()) + 1
        if not any(d.day == dia and d.month == mes for d in validas):
            problemas.append(f"a data \"{m.group(0)}\" nao corresponde ao pregao "
                             "nem a manchete")
    for m in _RE_DATA_BAR.finditer(texto):
        dia, mes = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12 and not any(d.day == dia and d.month == mes for d in validas):
            problemas.append(f"a data {m.group(0)} nao corresponde ao pregao nem a manchete")
    for m in _RE_DATA_PAR.finditer(texto):
        if int(m.group(1)) not in dias_validos:
            problemas.append(f"o dia ({m.group(1)}) nao corresponde ao pregao "
                             "nem a manchete")
    nomes_validos = {DIAS[d.weekday()] for d in validas
                     if d not in (n["max_quando"], n["min_quando"]) or d == n["data"]}
    for nome in DIAS:
        if re.search(rf"\b{nome}\b", texto, re.I) and nome not in nomes_validos:
            problemas.append(f"\"{nome}\" nao e' o dia do pregao "
                             f"({DIAS[n['data'].weekday()]}) nem o da manchete; "
                             "nao atribua a noticia a hoje")

    # 5. Estilo.
    for padrao, porque in _PROIBIDOS:
        m = re.search(padrao, texto, re.I)
        if m:
            problemas.append(f"\"{m.group(0)}\": {porque}")

    return list(dict.fromkeys(problemas))

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
import unicodedata
from datetime import date
from difflib import SequenceMatcher

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
    (r"(m[aá]xima|m[ií]nima|pico|topo|piso|patamar|n[ií]vel)s? (\w+ ){0,2}?hist[oó]ric[ao]s?"
     r"|hist[oó]ric[ao]s? (mais )?(baix|alt)\w*",
     "os extremos fornecidos sao do ultimo ano, nao 'historicos'"),
    (r"segundo o ve[ií]culo|o ve[ií]culo\b", "fonte sem nome e' 'a imprensa', nunca 'o veiculo'"),
    (r"\b(suporte|resist[eê]ncia|barreiras? t[eé]cnicas?|rompimento|rota[cç][aã]o de posi[cç][oõ]es"
     r"|derivativos|hedge)\b", "sem analise tecnica ou de mercado propria: so' os numeros"),
]


_RE_ATRIBUI = re.compile(r"segundo (a|o)s? (?!ptax|banco|base|tabela|dados|taxa|bc\b)|"
                         r"noticiou|informou|reportou|"
                         r"de acordo com a (imprensa|reportagem|publica)", re.I)


def posicao(valor: float, piso: float, topo: float) -> str:
    """'piso', 'topo' ou 'meio' — o modelo errava essa leitura (ensaio de
    19/10: 4 de 10 viam 'metade superior' estando mais perto do piso)."""
    amplitude = topo - piso
    if amplitude <= 0:
        return "meio"
    lugar = (valor - piso) / amplitude
    return "piso" if lugar < 0.45 else "topo" if lugar > 0.55 else "meio"


# Palavras de posicao: (regex, lado). Frase sobre o ano compara com a faixa
# do ano; as outras, com a faixa dos 22 pregoes.
_POSICOES = [
    (re.compile(r"(metade|parte|extremidade|zona|faixa) (superior|alta|de cima)|"
                r"(perto|pr[oó]xim[oa]|colad[oa]|encost\w*) (d[oa]s? )?(topo|teto|m[aá]xima|pico)",
                re.I), "topo"),
    (re.compile(r"(metade|parte|extremidade|zona|faixa) (inferior|baixa|de baixo)|"
                r"(perto|pr[oó]xim[oa]|colad[oa]|encost\w*) (d[oa]s? )?(piso|fundo|m[ií]nima)",
                re.I), "piso"),
]
_RE_ANO = re.compile(r"\bano\b|12 meses|doze meses|285 preg|um ano", re.I)


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?])\s+|\n+", texto) if f.strip()]


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


def _trecho_antes_oracao(texto: str, pos: int) -> str:
    """Da virgula/ponto anterior ate o valor: so' a oracao que o precede."""
    inicio = max(texto.rfind(s, 0, pos) for s in (". ", "; ", "\n", ": ", ", "))
    return texto[inicio + 1:pos]


def _normaliza(titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sem_acento).split())


_RE_REAL_SOBE = re.compile(r"(positiv\w*|favor[aá]vel|bom|boa) (para|ao) o? ?real|"
                           r"real se (valoriz|fortalec)\w*|\b(valoriza[cç][aã]o|fortalecimento) do real|"
                           r"\breal (ganh|sob|subi|avan)\w*", re.I)
_RE_REAL_DESCE = re.compile(r"(negativ\w*|desfavor[aá]vel|ruim) (para|ao) o? ?real|"
                            r"real se (desvaloriz|enfraquec)\w*|desvaloriza[cç][aã]o do real|"
                            r"perda (de valor )?do real|\breal (perd|ca[ií]|recu)\w*", re.I)


def confere(titulo: str, corpo: str, n: dict, manchete: str, hoje: date,
            data_manchete: date | None,
            titulos_recentes: list[str] | None = None) -> list[str]:
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
    # distancia em % ate os extremos (o prompt pede essa analise)
    pct_distancias = [abs(n["venda"] / x - 1) * 100 for x in base[1:]] \
        + [abs(x / n["venda"] - 1) * 100 for x in base[1:]]
    for m in _RE_PCT.finditer(texto):
        v = _num(m.group(1))
        donos = [(k, x) for k, x in variacoes.items() if _bate(v, [abs(x)])]
        if not donos:
            if not _bate(v, pct_manchete + pct_distancias):
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

    # 5. Dado nosso na boca da imprensa: frase com atribuicao nao pode trazer
    # a PTAX nem uma variacao da base (26641 do ensaio de 19/10).
    proprios = [n["venda"]]
    proprios_pct = [abs(v) for v in variacoes.values()]
    for frase in _frases(texto):
        if not _RE_ATRIBUI.search(frase):
            continue
        if any(_bate(_num(m), proprios) for m in _RE_BRL.findall(frase)
               if not _bate(_num(m), da_manchete)) or \
           any(_bate(_num(m), proprios_pct) for m in _RE_PCT.findall(frase)
               if not _bate(_num(m), pct_manchete)):
            problemas.append("a frase com 'segundo a imprensa' traz dado do Banco "
                             "Central; a PTAX e as variacoes sao nossas, em frase "
                             f"propria: \"{frase.strip()[:90]}\"")

    # 6. Leitura da posicao: perto do piso, do topo ou no meio (o numero
    # certo com a conclusao errada passava; 4 de 10 na v3 do ensaio).
    lado_faixa = posicao(n["venda"], n["menor"], n["maior"])
    lado_ano = posicao(n["venda"], n["min_ano"], n["max_ano"])
    for frase in _frases(texto):
        lado = lado_ano if _RE_ANO.search(frase) else lado_faixa
        if lado == "meio":
            continue
        for regex, diz in _POSICOES:
            m = regex.search(frase)
            # "distante/longe do pico" nao e' afirmacao de proximidade
            if m and diz != lado and not re.search(
                    r"(dist\w*|long\w*|afastad\w*) d[oa]s? " + m.group(0).split()[-1],
                    frase, re.I):
                problemas.append(
                    f"\"{m.group(0)}\" esta' errado: a PTAX esta' mais perto do "
                    f"{'piso' if lado == 'piso' else 'topo'}"
                    f"{' do ano' if lado is lado_ano and _RE_ANO.search(frase) else ' da faixa'}")

    # 7. Data da manchete junto de dado nosso: o fechamento e' do pregao, nao
    # do dia da noticia (26641 da v3: "a PTAX de 5 de agosto").
    if data_manchete and data_manchete != n["data"]:
        marcas = [rf"\b{data_manchete.day}º?\s+de\s+{MESES[data_manchete.month - 1]}\b",
                  rf"\b{data_manchete.day:02d}/{data_manchete.month:02d}\b",
                  rf"\b{data_manchete.day}/{data_manchete.month}\b"]
        if DIAS[data_manchete.weekday()] != DIAS[n["data"].weekday()]:
            marcas.append(rf"\b{DIAS[data_manchete.weekday()]}\b")
        nossos_brl = base + distancias
        nossos_pct = proprios_pct + pct_distancias
        for frase in _frases(texto):
            if _RE_ATRIBUI.search(frase):
                continue  # frase da manchete: a data dela pode
            tem_dado = any(_bate(_num(x), nossos_brl) for x in _RE_BRL.findall(frase)) or \
                any(_bate(_num(x), nossos_pct) for x in _RE_PCT.findall(frase))
            if tem_dado and any(re.search(mk, frase, re.I) for mk in marcas):
                problemas.append(
                    "o dado do Banco Central e' do pregao de "
                    f"{DIAS[n['data'].weekday()]}, {n['data'].day}/{n['data'].month}, "
                    "nao do dia da manchete: \"" + frase.strip()[:90] + "\"")

    # 8. Direcao sem percentual: o titulo e a frase da PTAX do dia dizem
    # "alta"/"queda" sem numero (26641 da v4: "Dolar fecha em alta na PTAX a
    # R$ 5,0564" com a PTAX em queda; a "alta" era da manchete de agosto).
    dia = n.get("var_dia")
    if dia is not None and abs(dia) >= 0.005 and not _RE_ATRIBUI.search(titulo):
        certo = 1 if dia > 0 else -1
        trechos = [re.split(r"[;:]|,\s| — | - ", titulo)[0]]   # 1a oracao do titulo
        for m in _RE_BRL.finditer(texto):
            if _bate(_num(m.group(1)), [n["venda"]]):
                trechos.append(_trecho_antes_oracao(texto, m.start()))
        for trecho in trechos:
            if _RE_PCT.search(trecho) or _RE_ATRIBUI.search(trecho) or \
                    re.search(r"semana|m[eê]s|\bano\b|preg[oõ]es", trecho, re.I):
                continue   # percentual ja' conferido; ou outro periodo/fonte
            palavras = _RE_DIRECAO.findall(trecho)
            if palavras and all(_sentido(p) != certo for p in palavras):
                problemas.append(
                    f"\"{trecho.strip()[:70]}\": no pregao a PTAX "
                    f"{'SUBIU' if certo > 0 else 'CAIU'} {pct(abs(dia))}")
                break   # um aviso basta: titulo e frase costumam ser o mesmo erro

    # 9. Efeito no real: dolar sobe = real perde (27688 da v4: "positivo para
    # o real: o dolar subiu 1,35%").
    for frase in _frases(texto):
        diz_real = 1 if _RE_REAL_SOBE.search(frase) else \
            -1 if _RE_REAL_DESCE.search(frase) else 0
        if not diz_real:
            continue
        sentidos = {1 if x > 0 else -1 for m in _RE_PCT.findall(frase)
                    for x in variacoes.values() if _bate(_num(m), [abs(x)])}
        if not sentidos and dia and abs(dia) >= 0.005 and \
                any(_bate(_num(m), [n["venda"]]) for m in _RE_BRL.findall(frase)):
            sentidos = {1 if dia > 0 else -1}
        if len(sentidos) == 1 and diz_real == sentidos.pop():
            problemas.append(
                "efeito no real invertido: quando o dolar sobe, o real perde "
                f"valor (e vice-versa): \"{frase.strip()[:90]}\"")

    # 10. Titulo unico: dois hubs no mesmo dia saiam com o mesmo titulo
    # (3 iguais em 10 na v4).
    meu = _normaliza(titulo)
    for outro in titulos_recentes or []:
        if outro and SequenceMatcher(None, meu, _normaliza(outro)).ratio() >= 0.85:
            problemas.append(f"titulo quase igual a um ja' usado (\"{outro[:70]}\"); "
                             "escreva outro, com outra estrutura")
            break

    # 11. Estilo.
    for padrao, porque in _PROIBIDOS:
        m = re.search(padrao, texto, re.I)
        if m:
            problemas.append(f"\"{m.group(0)}\": {porque}")

    return list(dict.fromkeys(problemas))

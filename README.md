# Radar de pautas

Monitora o que sai sobre cada tema, deduplica, classifica no hub certo e devolve
uma fila de pautas — cada uma com o **angulo** e o **dado proprio** que fazem o
artigo existir. Multi-site desde o primeiro commit: site novo e' um bloco em
`config/sites.yaml`, sem tocar em codigo.

Nasce configurado para `ferrugem.com.br` e `doll.com.br`.

## O que escala aqui

O texto nao escala — o **banco** escala. Cada show que entra na tabela `eventos`
torna a proxima pauta de show mais rica ("a 4a vez do cantor na cidade"); cada
PTAX que entra em `cotacoes` torna a proxima materia de dolar mais dificil de
copiar. Site novo comeca com a base vazia e vai ganhando profundidade sozinho, a
cada publicacao. E' esse acumulo que separa "mais um portal que reescreve
noticia" de "a fonte que os outros citam" — inclusive as IAs.

Por isso o radar **nao** sugere angulo de dado quando a base nao tem dado: sem
numero proprio, sobra reescrever o que ja foi publicado, que e' exatamente o que
a politica de conteudo em escala do Google descreve.

## Rodar

```bash
pip install -r requirements.txt
cp .env.example .env          # preencher Supabase; Discord e Anthropic sao opcionais

python testar_local.py                      # teste offline, sem rede e sem banco
python -m radar.principal --seco            # coleta de verdade, nao grava nada
python -m radar.principal --site ferrugem   # um site
python -m radar.principal                   # todos
```

No Supabase, rodar `sql/schema.sql` uma vez. Em producao, o
`.github/workflows/radar.yml` roda a cada 30 minutos — os segredos vao em
Settings → Secrets → Actions (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`DISCORD_WEBHOOK`, `ANTHROPIC_API_KEY`).

## Painel de acompanhamento

Painel web (Next.js, em `painel/`) com a fila de pautas, as cotacoes com
grafico, os artigos gerados e as execucoes dos crons — um cartao por site,
site novo aparece sozinho.

```bash
cd painel
npm install
cp .env.example .env.local    # mesmos SUPABASE_URL e SUPABASE_SERVICE_KEY do .env da raiz
npm run dev                   # http://localhost:3000
```

O painel le o banco SO no servidor (service key; o RLS continua sem policy
publica) e o acesso e' protegido por senha unica (`PAINEL_SENHA` — vazia, abre
livre, so' para dev). Os crons gravam cada rodada na tabela `execucoes`
(schema.sql) e o painel mostra "rodou? quando? deu certo?" sem abrir o Actions.

Deploy na Vercel: importar o repositorio com **Root Directory = `painel`** e
definir `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` e `PAINEL_SENHA` nas variaveis
de ambiente do projeto.

## Configurar um WordPress novo

```bash
python -m radar.configurar_wp --site doll --seco   # mostra o que faria
python -m radar.configurar_wp --site doll          # aplica
```

Ajusta titulo, tagline, fuso e formato de data, manda o conteudo de exemplo para
a lixeira e instala os plugins listados. Idempotente: rodar de novo so' reporta
"ja' ok". O que precisa mudar por site esta' em `wordpress.configuracao_inicial`,
no `sites.yaml`.

Precisa rodar de uma maquina que alcance o site. Se a sua nao alcancar, use o
workflow **configurar-wordpress** no GitHub (Actions -> Run workflow), que serve
de braco remoto — deixe `seco` marcado na primeira vez.

## Site novo em 5 minutos

Copiar um bloco de `config/sites.yaml` e trocar:

1. `dominio` e `entidade` — a entidade e' como o site quer ser entendido por
   buscador e IA. Se o dominio nao diz o tema (caso do `doll.com.br`), a
   entidade precisa dizer.
2. `hubs` — as paginas permanentes. Comece com 4. `termos` alimenta o
   classificador sem LLM.
3. `fontes` — comece com duas consultas de Google News. Depois acrescente o
   `sitemap_news` dos concorrentes: e' publico e atualiza em segundos.
4. `base` — `eventos`, `cotacoes` ou uma tabela nova em `sql/schema.sql`. Sem
   base propria o site so' produz angulo editorial.
5. `moldes` (opcional) — sobrescreve o titulo de um angulo so' naquele site.

## Pauta de calendario pronta: cotacao do dolar

```bash
python testar_dolar.py                          # offline, com serie simulada
python -m radar.dolar_diario --historico 90     # carrega a serie inicial na base
python -m radar.dolar_diario --seco             # roda de verdade, sem gravar
python -m radar.dolar_diario                    # producao (cron ja configurado)
```

Fluxo: PTAX do Banco Central -> grava na base -> portoes -> artigo pronto em
`saida/` (markdown + JSON-LD) e na tabela `artigos`.

Duas decisoes que valem entender antes de mexer:

- **O gerador nao explica causa.** "O dolar subiu porque o Fed sinalizou..." e'
  interpretacao, e interpretacao inventada por robo vira erro factual assinado
  por voce. Tudo que sai dali e' derivavel da serie: valor, variacao, extremos,
  conversao, IOF. O "porque" fica para a materia de consequencia, escrita depois.
- **Fim de semana e feriado nao sao erro.** Nao ha' PTAX; o script sai limpo,
  sem gerar nada.

Portoes do dolar, em ordem: valor dentro da faixa plausivel, compra <= venda,
data nao futura (falha aqui aborta); salto diario <= 5% e serie com pelo menos
dois pontos (falha aqui vira rascunho, nao aborta).

O IOF fica em `config/sites.yaml`, nao no codigo — ele muda por decreto, e o
numero errado sai em toda materia. **Conferir antes da primeira publicacao.**

## Portoes de publicacao — leia antes de ligar o automatico

Publicacao automatica e' permissao **por tipo de pauta**, nunca modo global.
`config/sites.yaml` define, em `publicacao`:

| Tipo | Origem | Padrao | Por que |
|---|---|---|---|
| `calendario` | Data marcada + API oficial + calculo da sua base | `auto` | O dado e' deterministico e vem de fonte primaria. Da' para validar por regra: campo veio? esta' na faixa esperada? bate com o dia? Se qualquer teste falha, cai para rascunho. |
| `radar` | Noticia de terceiro detectada pelo radar | `rascunho` | Voce nao apurou o fato — quem apurou foi o outro portal. Publicar sozinho em cima disso e' herdar o erro dos outros e reescrever conteudo alheio em escala. |

Os tres riscos concretos de publicar radar no automatico, para decidir com os
olhos abertos:

1. **Erro factual herdado.** O portal errou a data do show, voce publica o erro
   com a sua assinatura — e o seu site e' que fica marcado.
2. **Pessoa real.** No `ferrugem.com.br` o assunto e' um cidadao vivo. Boato
   publicado automaticamente vira problema de imagem, nao erro de SEO.
3. **Conteudo em escala.** Muitos artigos derivados de noticia alheia, sem
   apuracao nova, e' o caso literal descrito na politica de spam do Google.
   O estrago cai sobre o dominio inteiro, nao sobre o artigo.

O caminho que sustenta volume: **automatico onde o dado e' seu e verificavel**
(agenda confirmada em fonte oficial, PTAX do Banco Central, contagem da sua
base), **rascunho onde o fato e' de outro**. Isso mantem a escala e tira do ar o
risco que nao vale a pena correr.

## Esteira dos blogs sem base propria

`doll` e `ferrugem` tem base propria e esteira dedicada, que sabe usar o dado
(`satelites.py`, `dolar_diario.py`, `ancoras.py`, `reserva.py`). Os blogs Tihee
nao tem base — e por isso tem uma esteira propria:

```bash
python -m radar.publicar --seco            # escreve e mostra, nao publica
python -m radar.publicar --site broune     # so' um site
python -m radar.publicar                   # todos (roda no cron do radar.yml)
```

Entra neste fluxo quem tem bloco `wordpress` e **nao** tem `base` no
`sites.yaml`. Ela pega as pautas que a selecao aprovou hoje e ja' estao maduras
(horario vencido), respeita o teto por hub, escreve com o Claude e publica com
imagem destacada. Cada pauta vira `publicada` e nao se repete.

**O que ela escreve — e o que ela nao escreve.** `radar/gerador_artigo.py`
produz um **guia de servico autonomo** sobre o tema do hub. A pauta do radar
entra como *sinal de assunto* ("este tema esta' quente agora"), nao como
materia-prima: o guia nao reescreve a noticia que o originou. O fato de
terceiro so' aparece se for concreto, em uma frase, atribuido e com link — e
o texto tem que se sustentar sem ele.

E' isso que muda o calculo dos portoes para estes sites. O risco do quadro
acima e' herdar o erro de quem apurou; aqui nao ha' apuracao de terceiro sendo
repetida, entao `publicacao.radar: auto` se sustenta. Trocar por `rascunho`
manda tudo para o WordPress como draft, sem mexer em codigo.

**Sem `ANTHROPIC_API_KEY` esta esteira nao escreve nada** — de proposito. No
doll um template ainda diz algo de verdade, porque existe a PTAX; aqui nao
existe base, e template sem dado produz exatamente o texto de encheção que a
politica de conteudo em escala do Google descreve. Vaga vazia e' melhor que
post vazio.

## Imagem destacada — o que destrava o Google Discover

O Discover e' uma superficie de **cards**. Sem imagem grande declarada, o post
existe mas praticamente nao aparece. A exigencia e' objetiva:

    largura >= 1200 px  E  largura x altura >= 300.000 px
    declarada em og:image ou schema.org, com max-image-preview:large

`radar/imagens.py` resolve isso no momento da publicacao: busca no acervo,
**baixa e mede os bytes** (nao confia no que a API diz), sobe para a biblioteca
do WordPress e o post sai com imagem destacada. O `wp_media_id` fica gravado no
artigo — rerodar atualiza o mesmo post sem duplicar a imagem.

Dois provedores, nesta ordem:

| Provedor | Chave | Licenca | Credito |
|---|---|---|---|
| Pexels | `PEXELS_API_KEY` (gratuita em pexels.com/api) | uso comercial livre | opcional |
| Openverse | nenhuma | filtrado por `license_type=commercial` | **obrigatorio** (CC-BY) |

Sem chave nenhuma ja' funciona, pelo Openverse. O credito viaja junto da imagem
e vai para a legenda da midia no WP — e' obrigacao legal nas imagens CC.

**A imagem e' ilustracao tematica, nao registro do fato.** A busca usa o termo
do HUB (`imagem:` em `config/sites.yaml`), nunca o titulo da materia: foto de
acervo nao retrata o fato noticiado, e fazer passar por isso e' legenda
enganosa — o mesmo erro que os portoes existem para evitar. Por isso tambem
existe `imagem: false`, que desliga a imagem num hub: e' o caso do
`ferrugem.com.br` inteiro, onde o assunto e' um cidadao vivo e foto de acervo ao
lado do nome dele sugere que e' ele.

```bash
python testar_imagem.py          # mede o portao, offline
python testar_imagem.py --rede   # busca de verdade em cada hub
```

No WordPress, `wordpress/radar-jsonld.php` cuida do resto: `max-image-preview:large`
e, quando nao ha' Rank Math nem Yoast, o proprio `og:image`.

## Regras de coleta (nao negociaveis no projeto)

- Coletar titulo, URL, data e o resumo que o proprio feed publica. **Nunca** o
  texto integral de outro site — nem no banco, nem em prompt.
- Preferir RSS e sitemap publicos a raspagem de HTML.
- Um segundo de pausa entre requisicoes (`fontes.PAUSA`) e User-Agent
  identificado com contato real.
- Respeitar `robots.txt` de qualquer alvo novo antes de adiciona-lo.
- O radar **descobre** a pauta. A apuracao acontece depois, na fonte primaria —
  o comunicado, o site oficial, a API. E' isso que diferencia radar de copia.

## Estrutura

Ver `MAPA.md`.

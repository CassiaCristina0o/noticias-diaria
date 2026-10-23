import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests

FEED_URL = os.environ.get("FEED_URL") or "https://feeds.bbci.co.uk/portuguese/rss.xml"
PASTA_DADOS = Path(os.environ.get("PASTA_DADOS", "data"))
USER_AGENT = "noticias-as-08h (portfolio de Cassia Cristina)"
FONTE = "BBC News Brasil"
TIMEOUT = 10
TENTATIVAS = 3
ESPERA = 30
LIMITE_LOG = 30
FUSO = ZoneInfo("America/Sao_Paulo")

NEGATIVAS = """
mort* morr* matou matam matar assassin* homicid* feminicid* suicid* luto vitima* ferid*
crime* crimin* roub* furt* estupr* sequestr* tortur* abuso* fraude* corrupc* escandalo*
acusad* condenad* condenac* preso* prisao denunc*
violenc* violent* agress* ataque* atentado* terror* bomba* bombardeio* tiroteio massacre*
genocid* guerra* conflito* invas* ameac* refugiad*
tragedia* acidente* desastre* incendio* explos* naufrag* terremoto* enchente* inundac*
deslizamento* colapso
crise* falenc* desemprego inflac* recessao epidemia* pandemia* surto* fome miseria
""".split()

EXCECOES_NEGATIVAS = {"mortadela", "morro", "morros"}

POLITICAS = """
governo* governador* prefeit* president* ministr* ministerio* congresso senado* senador*
deputad* camara parlament* legisla* planalto stf stj tse
eleica* eleito* eleitor* voto* votac* urna* candidat* partido* politic* diplomat*
ditadura* democracia* golpe* impeachment
lula bolsonaro trump biden putin zelensky maduro milei netanyahu vorcaro
""".split()

POSITIVAS = """
descobert* descobr* cura curou curam curar curado curada vacina* tratament* transplant*
inovac* invento* inventou solucao solucoes
conquist* recorde* sucesso premio* premiad* medalha* avanc* pioneir* inedit*
resgat* salvo salva salvou salvam salvar melhora* melhoria* recuper* esperanca*
solidaried* doac* voluntari*
reflorest* reciclag* renovave* sustentavel preserv* animal* biodiversidade ambiental* ecolog* clima* energ* solar eolica hidreletrica
""".split()

ROTULOS = {
    "negativa": "negativas",
    "politica": "políticas",
    "sem_pontos": "sem pontos",
    "repetida": "repetidas",
}


class ErroDoProcesso(Exception):
    def __init__(self, etapa, tipo, mensagem):
        super().__init__(f"{tipo}: {mensagem}")
        self.etapa = etapa
        self.tipo = tipo
        self.mensagem = mensagem


def imagem_do_item(item):
    miniaturas = item.get("media_thumbnail") or []
    url = miniaturas[0].get("url", "").strip() if miniaturas else ""
    return url if url.startswith("https://") else ""


def buscar_feed(url=FEED_URL, tentativas=TENTATIVAS, espera=ESPERA):
    destino = urlparse(url).netloc or url
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            resposta.raise_for_status()
            break
        except requests.Timeout:
            erro = ErroDoProcesso("busca_feed", "Timeout", f"{destino} ({TIMEOUT}s)")
            repetir = True
        except requests.ConnectionError:
            erro = ErroDoProcesso("busca_feed", "ConnectionError", destino)
            repetir = True
        except requests.HTTPError as e:
            codigo = e.response.status_code
            erro = ErroDoProcesso("busca_feed", f"HTTPError {codigo}", destino)
            repetir = codigo >= 500
        except requests.RequestException as e:
            erro = ErroDoProcesso("busca_feed", type(e).__name__, destino)
            repetir = False
        if not repetir or tentativa == tentativas:
            raise erro
        time.sleep(espera)
    feed = feedparser.parse(resposta.content)
    noticias = [
        {
            "titulo": e.get("title", "").strip(),
            "link": e.get("link", "").strip(),
            "resumo": e.get("summary", ""),
            "imagem": imagem_do_item(e),
        }
        for e in feed.entries
        if e.get("title") and e.get("link")
    ]
    if not noticias:
        raise ErroDoProcesso("busca_feed", "FeedVazio", destino)
    return noticias


def palavras(texto):
    texto = re.sub(r"<[^>]+>", " ", texto)
    decomposto = unicodedata.normalize("NFD", texto.lower())
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", sem_acento)


def casa(palavra, termo):
    if termo.endswith("*"):
        return palavra.startswith(termo[:-1])
    return palavra == termo


def termos_encontrados(lista, termos):
    return {t for t in termos if any(casa(p, t) for p in lista)}


def avaliar(noticia):
    lista = palavras(f"{noticia['titulo']} {noticia['resumo']}")
    sem_excecoes = [p for p in lista if p not in EXCECOES_NEGATIVAS]
    if termos_encontrados(sem_excecoes, NEGATIVAS):
        return {"status": "negativa", "pontos": 0}
    if termos_encontrados(lista, POLITICAS):
        return {"status": "politica", "pontos": 0}
    pontos = len(termos_encontrados(lista, POSITIVAS))
    return {"status": "ok" if pontos else "sem_pontos", "pontos": pontos}


def escolher(noticias, links_usados):
    contagem = {}
    candidatas = []
    for noticia in noticias:
        avaliacao = avaliar(noticia)
        status = avaliacao["status"]
        if status == "ok" and noticia["link"] in links_usados:
            status = "repetida"
        if status == "ok":
            candidatas.append((avaliacao["pontos"], noticia))
        else:
            contagem[status] = contagem.get(status, 0) + 1
    if candidatas:
        return max(candidatas, key=lambda c: c[0])[1], None
    partes = [f"{contagem[s]} {r}" for s, r in ROTULOS.items() if s in contagem]
    return None, f"{len(noticias)} lidas: " + ", ".join(partes)


def ler_log(pasta):
    caminho = pasta / "log.json"
    if not caminho.exists():
        return []
    try:
        log = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ErroDoProcesso("leitura_log", type(e).__name__, str(caminho)) from e
    if not isinstance(log, list):
        raise ErroDoProcesso("leitura_log", "FormatoInvalido", str(caminho))
    return log


def escrever_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    temporario.write_text(texto, encoding="utf-8")
    os.replace(temporario, caminho)


def registro(agora, status, detalhe, etapa=None, link=None, imagem=None):
    return {
        "quando": agora.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "etapa": etapa,
        "detalhe": detalhe,
        "link": link,
        "imagem": imagem or None,
    }


def gravar(pasta, agora, log, novo, noticia=None):
    if noticia:
        escrever_json(
            pasta / "hoje.json",
            {
                "data": agora.strftime("%Y-%m-%d"),
                "titulo": noticia["titulo"],
                "link": noticia["link"],
                "imagem": noticia.get("imagem") or None,
                "fonte": FONTE,
                "atualizado_em": agora.isoformat(timespec="seconds"),
            },
        )
    escrever_json(pasta / "log.json", (log + [novo])[-LIMITE_LOG:])


def linha(novo):
    partes = [novo["quando"], novo["status"].ljust(11), novo["etapa"], novo["detalhe"]]
    return " | ".join(p for p in partes if p)


def main():
    agora = datetime.now(FUSO)
    try:
        log = ler_log(PASTA_DADOS)
    except ErroDoProcesso as e:
        print(f"{agora:%Y-%m-%d %H:%M:%S} | ERRO | {e.etapa} | {e}", file=sys.stderr)
        return 1
    usados = {r["link"] for r in log if r.get("link")}
    noticia = None
    try:
        noticia, motivo = escolher(buscar_feed(), usados)
        if noticia:
            novo = registro(
                agora, "OK", noticia["titulo"], link=noticia["link"], imagem=noticia.get("imagem")
            )
        else:
            novo = registro(agora, "SEM_NOTICIA", motivo)
    except ErroDoProcesso as e:
        novo = registro(agora, "ERRO", str(e), e.etapa)
    except Exception as e:
        novo = registro(agora, "ERRO", f"{type(e).__name__}: {e}", "inesperado")
    gravar(PASTA_DADOS, agora, log, novo, noticia)
    print(linha(novo))
    return 1 if novo["status"] == "ERRO" else 0


if __name__ == "__main__":
    sys.exit(main())

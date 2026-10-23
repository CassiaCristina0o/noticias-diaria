import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mensagem_do_dia as m

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>t</title>
<item><title>Cientistas anunciam cura</title><link>https://x/1</link>
<description>resumo</description>
<media:thumbnail width="240" height="135" url="https://img.exemplo/a.jpg"/></item>
<item><title>Cidade tem festival</title><link>https://x/2</link>
<description>resumo</description></item>
<item><title>Vacina nova</title><link>https://x/3</link>
<description>resumo</description>
<media:thumbnail width="240" height="135" url="http://img.exemplo/b.jpg"/></item>
</channel></rss>"""

RSS_VAZIO = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title></channel></rss>"""


def noticia(titulo, resumo="", link=None):
    return {"titulo": titulo, "resumo": resumo, "link": link or f"https://x/{titulo}"}


class Resposta:
    def __init__(self, status=200, conteudo=b""):
        self.status_code = status
        self.content = conteudo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def falso_get(monkeypatch, respostas):
    chamadas = []

    def get(url, **kwargs):
        chamadas.append(url)
        resposta = respostas[min(len(chamadas), len(respostas)) - 1]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(m.requests, "get", get)
    monkeypatch.setattr(m.time, "sleep", lambda segundos: None)
    return chamadas


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PASTA_DADOS", tmp_path)
    return tmp_path


def ler(pasta, nome):
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


def rodar(monkeypatch, noticias=None, erro=None):
    def buscar():
        if erro:
            raise erro
        return noticias

    monkeypatch.setattr(m, "buscar_feed", buscar)
    return m.main()


def test_palavras_remove_acento_maiuscula_e_html():
    assert m.palavras("Eleição <b>Já</b> ÁGUA") == ["eleicao", "ja", "agua"]


def test_salvador_nao_pontua():
    r = m.avaliar(noticia("Cidade de Salvador recebe festival"))
    assert r == {"status": "sem_pontos", "pontos": 0}


def test_procura_nao_casa_com_cura():
    r = m.avaliar(noticia("Procura por emprego cresce"))
    assert r["status"] == "sem_pontos"


def test_cura_exata_pontua():
    r = m.avaliar(noticia("Cientistas anunciam cura"))
    assert r == {"status": "ok", "pontos": 1}


def test_negativa_vence_positiva():
    r = m.avaliar(noticia("Descoberta de cura para doença que matou milhões"))
    assert r["status"] == "negativa"


def test_politica_vence_positiva():
    r = m.avaliar(noticia("Governo anuncia vacina contra a dengue"))
    assert r["status"] == "politica"


def test_morro_nao_e_morte():
    r = m.avaliar(noticia("Turistas visitam morro famoso"))
    assert r["status"] == "sem_pontos"


def test_resumo_entra_no_filtro():
    r = m.avaliar(noticia("Título neutro", resumo="Houve uma tragédia"))
    assert r["status"] == "negativa"


def test_termo_repetido_nao_infla_pontos():
    assert m.avaliar(noticia("Descoberta descoberta descoberta"))["pontos"] == 1
    assert m.avaliar(noticia("Descoberta de vacina"))["pontos"] == 2


def test_escolher_maior_pontuacao():
    a = noticia("Descoberta")
    b = noticia("Descoberta de vacina")
    assert m.escolher([a, b], set())[0] == b


def test_escolher_empate_fica_com_a_primeira():
    a = noticia("Recorde de visitas")
    b = noticia("Cientistas anunciam cura")
    assert m.escolher([a, b], set())[0] == a


def test_escolher_ignora_link_repetido():
    a = noticia("Descoberta de vacina")
    b = noticia("Cientistas anunciam cura")
    assert m.escolher([a, b], {a["link"]})[0] == b
    escolhida, motivo = m.escolher([a], {a["link"]})
    assert escolhida is None
    assert motivo == "1 lidas: 1 repetidas"


def test_escolher_motivo_conta_cada_descarte():
    noticias = [
        noticia("Acidente grave"),
        noticia("Governo anuncia"),
        noticia("Cidade tem festival"),
    ]
    escolhida, motivo = m.escolher(noticias, set())
    assert escolhida is None
    assert motivo == "3 lidas: 1 negativas, 1 políticas, 1 sem pontos"


def test_buscar_feed_devolve_noticias(monkeypatch):
    falso_get(monkeypatch, [Resposta(200, RSS)])
    noticias = m.buscar_feed("https://feeds.exemplo/rss")
    assert noticias[0] == {
        "titulo": "Cientistas anunciam cura",
        "link": "https://x/1",
        "resumo": "resumo",
        "imagem": "https://img.exemplo/a.jpg",
    }


def test_buscar_feed_imagem_ausente_ou_sem_https_fica_vazia(monkeypatch):
    falso_get(monkeypatch, [Resposta(200, RSS)])
    noticias = m.buscar_feed("https://feeds.exemplo/rss")
    assert noticias[1]["imagem"] == ""
    assert noticias[2]["imagem"] == ""


def test_timeout_repete_e_vira_erro(monkeypatch):
    chamadas = falso_get(monkeypatch, [requests.Timeout()])
    with pytest.raises(m.ErroDoProcesso) as e:
        m.buscar_feed("https://feeds.exemplo/rss")
    assert (e.value.etapa, e.value.tipo) == ("busca_feed", "Timeout")
    assert len(chamadas) == 3


def test_connection_error_repete_e_vira_erro(monkeypatch):
    chamadas = falso_get(monkeypatch, [requests.ConnectionError()])
    with pytest.raises(m.ErroDoProcesso) as e:
        m.buscar_feed("https://feeds.exemplo/rss")
    assert e.value.tipo == "ConnectionError"
    assert len(chamadas) == 3


def test_503_repete_tres_vezes(monkeypatch):
    chamadas = falso_get(monkeypatch, [Resposta(503)])
    with pytest.raises(m.ErroDoProcesso) as e:
        m.buscar_feed("https://feeds.exemplo/rss")
    assert e.value.tipo == "HTTPError 503"
    assert len(chamadas) == 3


def test_404_nao_repete(monkeypatch):
    chamadas = falso_get(monkeypatch, [Resposta(404)])
    with pytest.raises(m.ErroDoProcesso) as e:
        m.buscar_feed("https://feeds.exemplo/rss")
    assert e.value.tipo == "HTTPError 404"
    assert len(chamadas) == 1


def test_recupera_na_segunda_tentativa(monkeypatch):
    chamadas = falso_get(monkeypatch, [requests.Timeout(), Resposta(200, RSS)])
    assert len(m.buscar_feed("https://feeds.exemplo/rss")) == 3
    assert len(chamadas) == 2


def test_feed_vazio_vira_erro(monkeypatch):
    falso_get(monkeypatch, [Resposta(200, RSS_VAZIO)])
    with pytest.raises(m.ErroDoProcesso) as e:
        m.buscar_feed("https://feeds.exemplo/rss")
    assert e.value.tipo == "FeedVazio"


def test_main_ok_grava_hoje_e_log(pasta, monkeypatch):
    codigo = rodar(monkeypatch, [noticia("Cientistas anunciam cura", link="https://x/1")])
    assert codigo == 0
    hoje = ler(pasta, "hoje.json")
    assert hoje["titulo"] == "Cientistas anunciam cura"
    assert hoje["fonte"] == "BBC News Brasil"
    assert hoje["atualizado_em"].endswith("-03:00")
    log = ler(pasta, "log.json")
    assert [r["status"] for r in log] == ["OK"]
    assert log[0]["link"] == "https://x/1"


def test_main_grava_imagem_em_hoje_e_log(pasta, monkeypatch):
    com_imagem = {**noticia("Cientistas anunciam cura", link="https://x/1"), "imagem": "https://img.exemplo/a.jpg"}
    rodar(monkeypatch, [com_imagem])
    assert ler(pasta, "hoje.json")["imagem"] == "https://img.exemplo/a.jpg"
    assert ler(pasta, "log.json")[0]["imagem"] == "https://img.exemplo/a.jpg"


def test_main_sem_imagem_grava_nulo(pasta, monkeypatch):
    rodar(monkeypatch, [noticia("Cientistas anunciam cura", link="https://x/1")])
    assert ler(pasta, "hoje.json")["imagem"] is None
    assert ler(pasta, "log.json")[0]["imagem"] is None


def test_main_sem_noticia_mantem_hoje(pasta, monkeypatch):
    (pasta / "hoje.json").write_text('{"titulo": "antiga"}', encoding="utf-8")
    codigo = rodar(monkeypatch, [noticia("Cidade tem festival")])
    assert codigo == 0
    assert ler(pasta, "hoje.json") == {"titulo": "antiga"}
    registro = ler(pasta, "log.json")[0]
    assert registro["status"] == "SEM_NOTICIA"
    assert registro["detalhe"] == "1 lidas: 1 sem pontos"


def test_main_erro_registra_etapa_e_sai_com_1(pasta, monkeypatch):
    erro = m.ErroDoProcesso("busca_feed", "Timeout", "x (10s)")
    codigo = rodar(monkeypatch, erro=erro)
    assert codigo == 1
    assert not (pasta / "hoje.json").exists()
    registro = ler(pasta, "log.json")[0]
    assert registro["status"] == "ERRO"
    assert registro["etapa"] == "busca_feed"
    assert registro["detalhe"] == "Timeout: x (10s)"


def test_main_erro_inesperado(pasta, monkeypatch):
    codigo = rodar(monkeypatch, erro=ValueError("boom"))
    assert codigo == 1
    registro = ler(pasta, "log.json")[0]
    assert registro["etapa"] == "inesperado"
    assert registro["detalhe"] == "ValueError: boom"


def test_main_nao_repete_link_ja_usado(pasta, monkeypatch):
    anterior = {
        "quando": "2026-01-01 00:00:00",
        "status": "OK",
        "etapa": None,
        "detalhe": "x",
        "link": "https://x/1",
    }
    (pasta / "log.json").write_text(json.dumps([anterior]), encoding="utf-8")
    codigo = rodar(monkeypatch, [noticia("Cientistas anunciam cura", link="https://x/1")])
    assert codigo == 0
    assert ler(pasta, "log.json")[-1]["detalhe"] == "1 lidas: 1 repetidas"


def test_main_limita_log_a_30(pasta, monkeypatch):
    antigos = [
        {
            "quando": "2026-01-01 00:00:00",
            "status": "OK",
            "etapa": None,
            "detalhe": f"d{i}",
            "link": f"https://x/antigo{i}",
        }
        for i in range(30)
    ]
    (pasta / "log.json").write_text(json.dumps(antigos), encoding="utf-8")
    rodar(monkeypatch, [noticia("Cientistas anunciam cura", link="https://x/novo")])
    log = ler(pasta, "log.json")
    assert len(log) == 30
    assert log[0]["detalhe"] == "d1"
    assert log[-1]["link"] == "https://x/novo"


def test_main_log_corrompido_nao_e_sobrescrito(pasta, monkeypatch):
    (pasta / "log.json").write_text("{ruim", encoding="utf-8")
    codigo = rodar(monkeypatch, [noticia("Cientistas anunciam cura")])
    assert codigo == 1
    assert (pasta / "log.json").read_text(encoding="utf-8") == "{ruim"
    assert not (pasta / "hoje.json").exists()

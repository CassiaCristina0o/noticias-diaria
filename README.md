# Notícias diária

Tarefa agendada que roda de verdade: todo dia às 08h de Brasília, um workflow do
GitHub Actions executa um script em Python que lê o feed RSS da BBC News Brasil,
escolhe uma notícia positiva e registra a execução num log. Ninguém interage com
ela: roda sozinha no horário marcado.

Este repositório é a versão final. O fluxo do agendador foi validado antes numa
amostra pequena (4 execuções): [agendador](https://github.com/CassiaCristina0o/agendador).

## O que o script faz

`scripts/mensagem_do_dia.py`:

- **Busca** o feed com timeout de 10 s e até 3 tentativas, só para erro passageiro
  (timeout, conexão, 5xx). Um 404 não repete.
- **Filtra** por palavras inteiras, sem acento e sem diferenciar maiúsculas. Um
  termo com `*` vale só como início de palavra, então `cura` não pega "procura" e
  `salv*` não pega "Salvador".
- **Descarta** notícia com palavra negativa ou de política.
- **Pontua** pelos termos positivos diferentes (repetir não infla) e escolhe a
  maior pontuação; no empate vale a que vem primeiro no feed.
- **Não repete** notícia cujo link já está no log.
- **Grava com segurança**: arquivo temporário e `os.replace`, sempre com o
  horário real de America/Sao_Paulo.

## Resultados e erros

| Status | Quando | `hoje.json` | Saída |
|---|---|---|---|
| `OK` | achou uma notícia | substituído | 0 |
| `SEM_NOTICIA` | nada passou no filtro (o log traz a contagem por motivo) | intocado | 0 |
| `ERRO` | falha técnica (feed fora do ar, timeout, log corrompido) | intocado | 1 |

Em `ERRO` o workflow termina em falha e o GitHub avisa por e-mail.

## Dados

As execuções gravam `data/hoje.json` (título, link, fonte e miniatura) e
`data/log.json` (últimas 30 execuções) na branch `dados`. A `main` só tem o
código e a `dados` só tem commits automáticos (`execução 07/30`). Ao chegar em
30, o workflow recomeça o histórico da `dados`, sem tocar na `main`.

`index.html` lê o `hoje.json` da branch `dados` e mostra só a notícia do dia. O
log fica no repositório (`data/log.json`), sem aparecer na página.

## Airflow x GitHub Actions

| Airflow | GitHub Actions |
|---|---|
| DAG | workflow |
| schedule | `cron` |
| task | step |
| trigger manual | `workflow_dispatch` |
| retries | tentativas na busca do feed |

O Actions não é um orquestrador completo como o Airflow: não há dependências
entre tarefas, reprocessamento por data nem painel próprio de execuções.

## Rodar localmente

```bash
pip install -r requirements.txt pytest
pytest -q
python scripts/mensagem_do_dia.py
```

## Fonte

Notícias da [BBC News Brasil](https://www.bbc.com/portuguese). O projeto grava
título, link, fonte e o endereço da miniatura oferecida no próprio feed, sempre
com o link para a matéria original. A imagem não é copiada: a página a carrega
direto da BBC.

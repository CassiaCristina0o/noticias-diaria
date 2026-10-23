# Notícias diária

Rotina em Python que, todo dia às 08h (Brasília), lê o feed RSS da BBC News
Brasil, seleciona uma notícia positiva e registra a execução. É executada por
um workflow agendado do GitHub Actions (`cron: 0 11 * * *`, em UTC). O
agendamento e a integração com o feed foram validados antes na amostra
[agendador](https://github.com/CassiaCristina0o/agendador).

![Notícia do dia exibida na página](image-1.png)

## Seleção da notícia

`scripts/mensagem_do_dia.py` aplica, em ordem:

1. **Normalização:** texto em minúsculas, sem acentos e separado em palavras.
2. **Correspondência por palavra inteira:** um termo com `*` vale só como
   prefixo (`descobert*`). Assim `cura` não casa com "procura" e `salv*` não casa
   com "Salvador".
3. **Descarte** de itens com termos negativos ou políticos. A palavra negativa
   vence a positiva.
4. **Pontuação** pelo número de termos positivos distintos. Repetir um termo não
   aumenta a nota.
5. **Escolha** da maior pontuação, com mínimo de 1. No empate, vale o item que
   aparece primeiro no feed.
6. **Sem repetição:** itens cujo link já consta no log são ignorados.

## Resultados

| Status | Quando | `hoje.json` | Saída |
|---|---|---|---|
| `OK` | uma notícia foi escolhida | substituído | 0 |
| `SEM_NOTICIA` | nada passou no filtro (o log traz a contagem por motivo) | mantido | 0 |
| `ERRO` | falha técnica (feed indisponível, timeout, log ilegível) | mantido | 1 |

Em `ERRO` o workflow termina em falha e o GitHub envia o aviso por e-mail. Não
há texto de substituição: o log registra etapa, tipo e mensagem do problema.

## Dados e histórico

Cada execução grava, na branch `dados`:

- `data/hoje.json`: título, link, fonte e miniatura da notícia escolhida;
- `data/log.json`: as últimas 30 execuções, com horário real em
  America/Sao_Paulo.

A escrita usa arquivo temporário e `os.replace`, para não deixar JSON pela
metade. A `main` contém só o código; a `dados` contém só commits automáticos
(`execução 07/30`). Ao chegar em 30, o workflow recria a `dados` sem histórico,
mantendo os arquivos atuais, sem tocar na `main`.

`index.html` exibe a notícia do dia a partir do `hoje.json`.

## Testes

`tests/test_mensagem_do_dia.py` roda sem internet, com o feed simulado e uma
pasta temporária. Cobre o filtro (palavra inteira, negativa e política contra
positiva), a escolha (pontuação, empate, repetição), a busca (timeout, conexão,
503 com repetição, 404 sem repetição, feed vazio) e o fluxo completo (`OK`,
`SEM_NOTICIA`, `ERRO`, limite de 30 linhas, log corrompido, imagem presente e
ausente). Um workflow separado roda os testes a cada alteração na `main`.

## Executar localmente

```bash
pip install -r requirements.txt pytest
pytest -q
python scripts/mensagem_do_dia.py
```

## Fonte

Notícias da [BBC News Brasil](https://www.bbc.com/portuguese). O projeto grava
título, link, fonte e o endereço da miniatura oferecida pelo próprio feed, sempre
com o link para a matéria original. A imagem não é copiada: a página a carrega
direto da BBC.

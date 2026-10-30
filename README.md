# Notícias diária

Rotina em Python que, todo dia de manhã (agendada para 07h38 de Brasília), lê o
feed RSS da BBC News Brasil, seleciona uma notícia que passe pelo filtro e
registra a execução. É executada por um workflow agendado do GitHub Actions
(`cron: 38 10 * * *`, em UTC). O GitHub pode atrasar workflows agendados, então
o horário real de início varia. O
agendamento e a integração com o feed foram validados antes na amostra
[agendador](https://github.com/CassiaCristina0o/agendador).

![Notícia do dia exibida na página](image-1.png)

## Seleção da notícia

`scripts/mensagem_do_dia.py` aplica, em ordem (as listas de palavras ficam em
`scripts/listas.py`):

1. **Formato:** só entram matérias escritas (`/portuguese/articles/`). Vídeos,
   blogs ao vivo, links curtos de divulgação e títulos genéricos como "Clique
   aqui" são ignorados.
2. **Normalização:** texto em minúsculas, sem acentos e separado em palavras.
3. **Correspondência por palavra inteira:** um termo com `*` vale só como
   prefixo (`acident*`). Assim `lipo` não casa com "lipoaspiração" por acaso e
   `plastica` não casa com "plástico" de reciclagem.
4. **Descarte** de itens com termos negativos (violência, tragédia, crise e
   também emagrecimento, dietas, canetas emagrecedoras, procedimentos
   estéticos, drogas, execuções, presos e trauma) ou políticos. "Doença" é
   uma regra condicional: sem "cura" (ou vacina) no texto é barrada; com cura,
   passa. O filtro olha título e resumo.
5. **Escolha** da primeira notícia do feed que passou. Não há lista positiva: o
   que não é barrado, vale.
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
pasta temporária. Cobre o filtro (palavra inteira, negativas, políticas, corpo e
emagrecimento, formato da matéria), a escolha (primeira que passa, repetição), a busca (timeout, conexão,
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

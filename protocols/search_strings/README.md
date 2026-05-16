# Strings de busca

Versão 1.0 das strings de busca por idioma. Adaptam-se aos operadores de cada base:

| Base | Operador de campo | Wildcard | Notas |
|------|-------------------|----------|-------|
| Web of Science | `TS=` | `*` | Truncamento à direita; aceita `OR`/`AND` |
| Scopus | `TITLE-ABS-KEY()` | `*` | `W/n` para proximidade se necessário |
| RePEc | Busca via OpenAlex API | n/a | Sem wildcards completos; busca em título+abstract |
| SciELO | Busca avançada | `*` | Aceita strings em pt/es |

Cada execução das buscas registra a versão da string utilizada em `data/raw/searches/{base}_{YYYY-MM-DD}.csv` (coluna `query_version`).

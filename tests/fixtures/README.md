# Fixtures sintéticos

Datasets pequenos usados em testes do pipeline. **Não representam** dados reais; servem apenas para verificar comportamento dos scripts.

- `sample_wos.csv` (5 registros) — simula export Web of Science. Inclui: 1 paper Brasil, 1 fora do escopo (educação), 1 robôs, 1 LLM produtividade-only.
- `sample_scopus.csv` (4 registros) — simula export Scopus. Inclui duplicatas por DOI e por (título+autor+ano), 1 paper em espanhol, 1 em francês.

Casos cobertos em testes:
- Dedup por DOI exato.
- Dedup por dedup_key sem DOI.
- Manutenção de multilíngue após dedup.
- Filtragem por critérios de inclusão (etapa de screening).

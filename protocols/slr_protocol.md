# Protocolo de Revisão Sistemática da Literatura

> Registrado em git **antes** da execução da busca. O hash do commit funciona como timestamp do registro.

**Tema:** Impactos da inteligência artificial sobre o mercado de trabalho (foco em emprego).
**Autor:** Acacio
**Orientador:** [a preencher]
**Instituição:** [a preencher]
**Versão do protocolo:** 1.1 (emenda 2026-05-17 — ver §7 e §11)
**Data do registro:** 2026-05-13

---

## 1. Pergunta de pesquisa

Como a literatura econômica caracterizou os efeitos da inteligência artificial sobre o nível e a composição do emprego entre 2013 e meados de 2026, e em que medida o surgimento da IA generativa (pós-novembro de 2022) representa uma ruptura ou continuidade em relação ao consenso anterior?

## 2. Objetivos

**Geral:** revisar sistematicamente a literatura econômica sobre o impacto da IA no emprego (deslocamento e criação de postos), comparando achados antes e depois da difusão de LLMs.

**Específicos:**
1. Mapear a literatura entre 2013–2026, em três janelas: 2013–2017 (automação), 2018–2022 (deep learning/ML), 2022–2026 (IA generativa/LLMs).
2. Caracterizar mecanismos teóricos (deslocamento, reinstalação, complementaridade, demanda agregada).
3. Sistematizar achados empíricos (sinal, magnitude, ocupações, robustez).
4. Comparar pré- e pós-ChatGPT.
5. Discutir implicações para o Brasil.

## 3. Hipótese de trabalho

A literatura pré-ChatGPT convergia para "polarização do emprego" com risco em tarefas rotineiras de baixa qualificação; a literatura pós-ChatGPT desloca o risco para tarefas cognitivas de alta qualificação.

## 4. Desenho metodológico

Revisão sistemática narrativa-estruturada (não meta-analítica), seguindo as diretrizes PRISMA 2020. Extração estruturada em campos fixos (ver `extraction_schema.md`) com análise comparativa pareada pré/pós-ChatGPT como capítulo central.

## 5. Critérios de inclusão e exclusão

Definidos em `inclusion_criteria.md`.

## 6. Estratégia de busca

Bases: Web of Science e Scopus + busca direta em periódicos-chave de economia.
A produção SciELO é coberta via Scopus, que indexa a *SciELO Citation Index*; por
isso o SciELO não é consultado como base autônoma, evitando duplicação e
mantendo um único pipeline de exportação BibTeX. Decisão tomada em 2026-05-16.
Strings de busca em `search_strings/` (en, pt, es, fr).
Período: 2013-01-01 a 2026-06-30. A janela foi estendida de 2025-12-31 para
meados de 2026 em 2026-05-16: as bases retornaram 349 registros com data de
publicação 2026 (early-access / online-first), tipicamente disponibilizados
online ainda em 2025 mas vinculados a um fascículo de 2026. Como representam
a evidência pós-ChatGPT mais recente — núcleo da pergunta de pesquisa —,
excluí-los por mero carimbo editorial empobreceria a comparação pré/pós-LLM.
O fechamento em 2026-06-30 coincide com a data de execução da busca.

**Nota sobre OpenAlex:** inicialmente previsto como base complementar (via API), foi descartado em 2026-05-13 após teste empírico. A query original retornava 4,4 milhões de registros porque o parâmetro `search` da OpenAlex não suporta operadores booleanos AND/OR no server-side — apenas full-text fuzzy. Mesmo com filtros de conceito (e.g., `concepts.id:C162324750` Economics + `C154945302` AI) o volume ficava acima de 870k, inviável de pós-filtrar. WoS e Scopus oferecem booleano nativo e curadoria temática, suficientes para o escopo da revisão. Decisão documentada no commit fazendo parte do registro pré-execução.

## 7. Processo de seleção

1. **Identification** — consolidação dos resultados de cada base.
2. **Deduplicação** — DOI → (título+autor+ano) → embeddings.
3. **Screening (título+resumo) — tri-LLM.** Pré-filtragem por dois triadores
   independentes (Claude Sonnet 4.6 + Haiku 4.5, união conservadora, κ=0,602).
   Os casos não-unânimes ("soft-includes": decisão final "incluir" não unânime —
   865 registros) são decididos por um terceiro avaliador independente e mais
   capaz — Claude Opus 4.7, cego (não vê os pareceres dos triadores) e forçado a
   binário (incluir/excluir). 462 "ambos-incluir" e 1278 "ambos-excluir" são
   aceitos pela concordância dos triadores; os 865 ambíguos pelo árbitro.
4. **Eligibility (texto completo)** — leitura completa, 100% manual.
5. **Inclusion** — corpus final usado para extração.

A aquisição de texto completo (2026-05-17) usa Unpaywall (OA automático) com
suplemento institucional manual (PDFs depositados pelo revisor); o PDF é lido
nativamente pelo LLM no Plano 4b (sem extração de texto intermediária).
Estudos sem OA e sem suplemento manual ficam em nível de resumo (`abstract`),
com a cobertura full-text reportada no PRISMA e nas limitações. A decisão de
elegibilidade e a extração por LLM (com verificação humana amostral) — e o
desvio metodológico em relação à leitura 100% manual prevista — são descritos
e declarados no Plano 4b.

**Emenda 2026-05-17 (protocolo v1.1).** O protocolo v1.0 previa "revisão
humana" nesta etapa, operacionalizada em 2026-05-16 via planilha
(`scripts/screening/revisao_export.py` → `revisao_ingest.py`). Ela foi
**substituída** pela arbitragem por 3º LLM (Opus 4.7) descrita no item 3, em
razão de restrição de tempo/escala (revisor único, 865 casos, prazo de um
semestre). Ver `docs/superpowers/specs/2026-05-17-arbitragem-3o-llm-design.md`.
Desvio declarado; mitigação e limitação reconhecida em §11. A ferramenta de
revisão humana permanece disponível como auditoria alternativa.

Diagrama PRISMA gerado automaticamente em `text/figures/prisma_flow.tex`.

## 8. Extração de dados

Esquema em `extraction_schema.md`. Cada estudo vira uma linha em `data/processed/06_extraction.csv` com sete blocos: identificação, classificação temporal, tipo de evidência, mecanismos teóricos, achados, qualidade, notas.

## 9. Avaliação de qualidade

Rubrica 1–5 em `quality_rubric.md`, aplicada na elegibilidade e revisada na extração.

## 10. Síntese

Três camadas: (i) descritivas do corpus, (ii) síntese por janela temporal, (iii) análise comparativa pré/pós-ChatGPT. Tudo gerado a partir do CSV de extração via scripts em `scripts/analysis/`.

## 11. Limitações antecipadas

- **Ausência de revisor humano na seleção (desvio do protocolo registrado).**
  O protocolo v1.0 comprometia-se com revisão humana no screening; a v1.1 a
  substituiu por arbitragem por 3º LLM (Opus 4.7). Mitigação: três modelos
  independentes, sendo o árbitro mais capaz e não-participante do screening;
  concordância par-a-par árbitro×triadores reportada (`arbitragem_kappa.tex`);
  regra conservadora (na incerteza, inclui; falha técnica nunca exclui).
  Limitação reconhecida e passível de questionamento em banca.
- LLM-as-judge no screening (auditoria estratificada e κ reportados).
- Corpus pós-2022 jovem (maioria working papers).
- Sem acesso a EconLit (substituído por RePEc + busca direta em periódicos).
- Janela exclui antecedentes seminais pré-2013 (tratados no referencial teórico).

## 12. Reprodutibilidade

- Todos os scripts em `scripts/` são determinísticos e idempotentes.
- Logs por etapa em `data/processed/`.
- Hashes SHA-256 dos exports brutos.
- Pipeline orquestrado por `Makefile`.

## 13. Cronograma

Ver Seção 8 do design em `docs/superpowers/specs/2026-05-13-tcc-slr-ia-trabalho-design.md`.

## 14. Conflitos de interesse

Nenhum declarado.

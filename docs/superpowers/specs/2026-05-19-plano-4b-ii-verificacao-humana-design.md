# Design — Plano 4b-ii: verificação humana amostral + κ humano×LLM + PRISMA interino + emenda do protocolo (v1.2)

**Data:** 2026-05-19
**Autor:** Acacio (via brainstorming superpowers)
**Branch:** `plano-4b-ii-verificacao-humana` (a criar)
**Depende de:** Plano 4b-i (extração LLM com 33 campos + correção RC2/RC3, merge `093a1d6` em `main`).
**Não bloqueia, mas resolve junto:** re-rodada idempotente pós-recarga de crédito (operacional, fora deste plano).

---

## 1. Problema

O Plano 4b-i operacionalizou a **decisão de elegibilidade + a extração dos 33 campos por LLM** (Sonnet 4.6), substituindo a leitura/extração 100% manual prevista no protocolo v1.0/v1.1. Para a defensibilidade do TCC, o protocolo (§7/§8/§11) compromete-se com uma **verificação humana amostral** que entregue duas métricas:

1. **κ de Cohen humano×LLM** sobre a **elegibilidade** (cego, mesmo princípio do árbitro Opus do screening) → mede concordância para além do acaso na decisão "incluir/excluir" de cada estudo.
2. **Acurácia por campo** (auditoria humana) sobre os campos analiticamente centrais → quantifica taxa de erro do LLM no que de fato vai virar tese.

Estado da 1ª rodada (2026-05-17): `06_extraction.csv` tem **852 linhas, 790 com extração real** e **62 com `nota_extracao=parse_fail`** (48 sem-crédito, 13 PDF-ruim, 1 JSON malformado). A recarga + re-rodada idempotente está pendente (operacional). Esta spec **roda agora sobre os 790**; a re-rodada posterior **não muda** as métricas (decisão tomada — não amostrar dos 61 recuperados).

## 2. Decisões de design (do brainstorming)

- **Q1 — quando.** Executar **agora** sobre os 790. O tooling tem que ser **idempotente** para não recomputar o quadro amostral quando a CSV viva ganhar os 61 recuperados pela re-rodada.
- **Q2 — amostragem.** **100% das 34 exclusões** (motivo_exclusao≠"") + **~10% das 756 inclusões estratificado** por `text_source` × faixa de `confianca_extracao` (~76) = **~110 totais** na planilha cega.
- **Q3 — modo.** Elegibilidade por **decisão cega** (humano não vê a decisão do LLM) → κ legítimo. Campos por **auditoria** (humano vê valor do LLM + fonte, marca `ok`/`erro` opcionalmente com valor correto) → acurácia por campo.
- **(i) Campos críticos auditados** (núcleo analítico): `pre_pos_chatgpt`, `janela`, `sinal_efeito`, `tipo_estudo`, `polarizacao`, `score_qualidade`. Bloco A bibliográfico (DOI/título/autores/ano) é determinístico do corpus, **não auditado**.
- **(ii) Fase final.** **Ficar com os 790** (não sortear amostra suplementar dos 61 recuperados). κ e acurácia são **definitivos na 1ª passada**; só PRISMA e prosa do protocolo mudam pós-re-rodada.

## 3. Arquitetura (unidades pequenas, bordas claras)

| Unidade | Responsabilidade | Depende de |
|---|---|---|
| `verify_sample.py` (novo) | congela o **quadro amostral** (790 review_ids) em snapshot; sorteia amostra estratificada determinística (seed=42); idempotente | `06_extraction.csv` |
| `verify_export.py` (novo) | gera 2 planilhas: **(a)** elegibilidade **cega** (id + metadados de fonte; **sem** decisão/extração do LLM) p/ todos os ~110; **(b)** auditoria de campos só p/ as ~76 inclusões; preserva input humano via `merge_preserve` + `.state.json` | snapshot de amostra |
| `verify_ingest.py` (novo) | lê as 2 planilhas preenchidas; computa **κ humano×LLM** (elegibilidade) + **acurácia por campo** (auditoria) + matriz de discordância; escreve `verificacao_kappa.tex` e `verificacao_acuracia.tex`; CSV anotado | planilhas preenchidas |
| `prisma_flow.py` (ajuste) | `compute_counts` lê também `06_extraction.csv`; anota **cobertura full-text efetiva** (121/852 = 14,2%) e, enquanto houver `parse_fail` na CSV, **nota interina** com nº de pendentes | `06_extraction.csv` |
| protocolo §7/§8/§11 → **v1.2** | emenda formal: extração+elegibilidade por LLM com verificação humana amostral; κ e acurácia reportados; status interino se aplicável | edição prosa |
| `Makefile` | targets `verify-sample`, `verify-export`, `verify-ingest`; agrupador `verify` | — |

Nenhum script novo faz chamada de rede. O Plano 4b-ii é integralmente offline.

## 4. Comportamento detalhado

### 4.1 `verify_sample.py`

CLI: `--extraction data/processed/06_extraction.csv --frame data/processed/07_amostra_frame.csv --sample data/processed/07_amostra_verificacao.csv [--seed 42]`.

Idempotência via **snapshot**: se `--frame` **já existir**, carrega; senão computa do `--extraction` e grava. O sorteio só re-roda se o `--sample` não existir. **Re-rodar pós-re-rodada do extract = no-op** (frame/amostra inalterados).

**Quadro amostral** = `06_extraction.csv` filtrado por `nota_extracao != "parse_fail"` (os 790). Persistido como CSV com `review_id`, `text_source`, `confianca_extracao`, `elegivel`, `motivo_exclusao`.

**Sorteio**:
- **Exclusões** (`elegivel == "nao"` ou `motivo_exclusao != ""`): **todas** (100%). Estrato único `excluir`.
- **Inclusões** (`elegivel == "sim"` e `motivo_exclusao == ""`): **amostragem proporcional estratificada** por `text_source` ∈ {`pdf`, `abstract`} × `confianca_bin` ∈ {`baixa<0.6`, `media∈[0.6,0.8]`, `alta>0.8`} = 6 estratos. Tamanho-alvo = `ceil(0.10 * n_estrato)`; **piso de min(5, n_estrato)** para estratos pequenos; seed fixa via `numpy.random.default_rng(seed)`. (O total pode passar de 76 em alguns ponto-percentuais quando estratos pequenos forçam o piso — aceitável; o objetivo é representação mínima por estrato.)
- Saída `07_amostra_verificacao.csv`: `review_id`, `estrato` (`excluir` ou `text_source_confianca_bin`), `tipo` (`exclusao` ou `inclusao`).

### 4.2 `verify_export.py`

CLI: `--extraction ... --sample ... --sheet-eleg data/processed/07_eleg_cega.csv --sheet-aud data/processed/07_auditoria_campos.csv`.

Reusa o **padrão** `revisao_export` (commit nos arquivos):
- `merge_preserve` (preserva colunas humanas por `review_id` se a planilha já existe).
- `.state.json` (decided_review_ids) + backup `.bak-TS.csv` antes de reescrever.
- `keep_default_na=False` na leitura (compatível com CSV editado em LibreOffice).

**Planilha (a) — elegibilidade cega** (~110 linhas):

```
review_id, decisao_humana, nota_humana, year, title, authors, venue, abstract,
text_source, criterios_ref
```

`decisao_humana`/`nota_humana` vazias. **Sem** colunas LLM (`elegivel`, `motivo_exclusao`, `decisao_arbitro`, campos extraídos). `criterios_ref` = string curta com os critérios do §5 (resumo, mesma string em todas as linhas — referência rápida; quem precisar de detalhe lê o protocolo).

**Planilha (b) — auditoria de campos** (só as ~76 inclusões):

Colunas em pares `<campo>_llm` (read-only, valor extraído) + `<campo>_auditoria` (humano: `ok`/`erro`) + `<campo>_correto` (opcional, livre, quando `erro`). 6 campos × 3 colunas + cabeçalho do registro:

```
review_id, year, title, doi, text_source,
pre_pos_chatgpt_llm, pre_pos_chatgpt_auditoria, pre_pos_chatgpt_correto,
janela_llm, janela_auditoria, janela_correto,
sinal_efeito_llm, sinal_efeito_auditoria, sinal_efeito_correto,
tipo_estudo_llm, tipo_estudo_auditoria, tipo_estudo_correto,
polarizacao_llm, polarizacao_auditoria, polarizacao_correto,
score_qualidade_llm, score_qualidade_auditoria, score_qualidade_correto,
nota_auditoria
```

Cabeçalho de instruções **fora** do CSV (numa linha de readme curto impresso pelo script): "auditoria ∈ {ok, erro}; vazio = pendente; correto = valor que deveria estar; nota_auditoria = comentário livre".

### 4.3 `verify_ingest.py`

CLI: `--extraction ... --sheet-eleg ... --sheet-aud ... --kappa-table text/tables/verificacao_kappa.tex --acuracia-table text/tables/verificacao_acuracia.tex --annotated data/processed/07_verificacao_anotada.csv`.

**Validação**:
- normaliza `decisao_humana` em `{incluir, excluir}` (reusa `revisao_ingest.normalize_decisao` — `i`/`e`/`incluir`/`excluir`, case-insensitive). Vazio → **erro**: "linha sem decisão humana — preencher antes de calcular κ".
- normaliza `<campo>_auditoria` em `{ok, erro}`. Vazio → **erro** específico daquele campo/linha (lista). Aborta antes de qualquer escrita.
- Conservadora: erro lista todas as pendências; não calcula κ silenciosamente com buracos.

**κ humano×LLM** (sklearn `cohen_kappa_score`, labels `["incluir","excluir"]`, reusa `agreement.cohen_kappa` adaptado para 2 labels): empareia `decisao_humana` da planilha com a decisão do LLM derivada de `06_extraction.csv` (`incluir` se `elegivel == "sim"`, senão `excluir`). Escreve `verificacao_kappa.tex` (estilo `arbitragem.kappa_table`): tabela com n, concordância, κ, IC Wilson 95% para a concordância, **e matriz de confusão 2×2 humano×LLM** logo abaixo (mesmo padrão de `kappa_screening.tex`, só que 2 labels).

**Acurácia por campo** (auditoria): para cada campo crítico, `acuracia = #ok / (#ok + #erro)`; n por campo; **IC Wilson 95%** para acurácia binomial. Escreve `verificacao_acuracia.tex` com uma linha por campo + total.

**CSV anotado** (`07_verificacao_anotada.csv`): a amostra com colunas `decisao_humana`, `concorda_eleg` (bool), `<campo>_auditoria` por campo crítico, `<campo>_correto` quando preenchido. Insumo para análise qualitativa de modos de erro.

### 4.4 `prisma_flow.py` (ajuste)

`compute_counts` ganha parâmetro `--extraction` (opcional, retrocompat) e calcula:
- `extraidos = (nota_extracao != "parse_fail").sum()` dos 852.
- `pendentes_reextract = 852 - extraidos`.
- `cobertura_pdf = (text_source == "pdf").sum()` do manifesto corrigido.

Template TikZ ganha **caixa de anotação** abaixo do nó "incluídos" quando `pendentes_reextract > 0`: "Reextração pendente: N (cobertura full-text efetiva X,X%)". Quando `pendentes_reextract == 0` a caixa some — o diagrama fica em estado "final" sem mudança manual.

Re-rodar pós-re-rodada do extract regenera automaticamente.

### 4.5 Protocolo v1.2 (emenda formal)

- **Cabeçalho:** "Versão do protocolo: 1.2 (emenda 2026-05-19 — ver §7, §8 e §11)".
- **§7 (Processo de seleção):** parágrafo formalizando que (a) a etapa "Eligibility" passou a ser LLM-driven, (b) a verificação humana amostral está em §8; mantém a referência à arbitragem por 3º LLM (v1.1).
- **§8:** absorve a "nota interina (Plano 4b-i)" como descrição definitiva da extração; adiciona subseção **"Verificação humana amostral"** com: tamanho (~110), estratificação, modo (cego para elegibilidade, auditoria para campos críticos), métricas reportadas (κ humano×LLM + acurácia por campo, com seus n e IC), arquivos `.tex` gerados. A "nota interina" relativa à re-rodada permanece **enquanto** `pendentes_reextract > 0`; após a re-rodada e regeneração de PRISMA, vira nota histórica.
- **§11:** o bullet "Reextração pendente de 61…" permanece até a re-rodada; **adiciona** bullet sobre **limitações da verificação humana amostral** (revisor único, amostra pequena para alguns estratos, viés possível na auditoria não-cega de campos; mitigação: cegueira na elegibilidade, IC reportados).

### 4.6 Makefile

Targets novos, espelhando o padrão existente:
```
verify-sample:
	source .venv/bin/activate && python -m scripts.screening.verify_sample \
	  --extraction data/processed/06_extraction.csv \
	  --frame data/processed/07_amostra_frame.csv \
	  --sample data/processed/07_amostra_verificacao.csv

verify-export: verify-sample
	source .venv/bin/activate && python -m scripts.screening.verify_export ...

verify-ingest:
	source .venv/bin/activate && python -m scripts.screening.verify_ingest ...

verify: verify-sample verify-export
	@echo "Planilhas geradas. Preencha-as e rode 'make verify-ingest'."
```

## 5. Testes (TDD)

Todos offline, determinísticos, com fixtures pequenas.

### 5.1 `verify_sample`
- Mesma amostra em 2 execuções com seed fixa (idempotência por seed).
- Frame e amostra **carregados** quando arquivos já existem — sem re-sortear (idempotência por snapshot).
- 100% das exclusões presentes na amostra (asserção sobre `tipo == "exclusao"`).
- Estratos de inclusões: tamanho ≈ `ceil(0.10 * n_estrato)` com piso aplicado; total ~10% global das inclusões.
- Mudança em `06_extraction.csv` (simular re-rodada: 5 ex-parse_fail viram extração real) **não altera** frame nem amostra se o snapshot existe.

### 5.2 `verify_export`
- **Cegueira**: a planilha (a) **não contém** colunas `elegivel`, `motivo_exclusao`, `decisao_arbitro` nem nenhuma coluna de campo extraído (asserção explícita).
- Planilha (b) tem só as inclusões amostradas.
- `merge_preserve` (reusado/adaptado): segunda execução com planilha já preenchida preserva `decisao_humana`, `<campo>_auditoria`, `nota_humana`.
- Backup `.bak-TS.csv` criado antes de reescrever.

### 5.3 `verify_ingest`
- κ=1.0 quando humano concorda 100% com LLM (sintético).
- κ negativo quando humano discorda 100% (sintético).
- Aborta com erro **listando review_ids/campos pendentes** se houver `decisao_humana` ou `<campo>_auditoria` vazios.
- Acurácia por campo = #ok / (#ok+#erro); IC Wilson não-degenerado em amostra pequena.
- `_to_binary` análogo à arbitragem: rótulo final em {incluir, excluir} (sem "duvida" — humano é forçado a binário; CSV vazio → erro acima).
- Tabelas `.tex` parseáveis (regex simples confirma `\caption`, `\label`, e o número de κ).

### 5.4 `prisma_flow` (ajuste)
- `compute_counts` retrocompat (sem `--extraction` → comportamento atual).
- Com `--extraction` e `pendentes_reextract > 0` → caixa de anotação no `.tex`.
- Com `pendentes_reextract == 0` → caixa ausente (substring negativa no `.tex`).

### 5.5 Integração / regressão
- Suite cheia continua verde (era 206 após o Plano 4b-i).
- Targets `make verify-sample`, `verify-export`, `verify-ingest` executam fim-a-fim sobre fixture mock.

## 6. Escopo

**Inclui:**
- 3 scripts novos (`verify_sample`, `verify_export`, `verify_ingest`) + seus testes.
- Ajuste retrocompatível em `prisma_flow.py` + testes.
- Emenda do protocolo para v1.2.
- Targets do Makefile.
- Atualização do README/CLAUDE.md mencionando o fluxo `verify-*`.

**Não inclui:**
- A recarga de crédito Anthropic e a re-rodada do `make extract-llm` (operacional, do usuário).
- Análise de modos de erro / discussão dos resultados de κ/acurácia na tese (capítulo de análise, posterior).
- Aquisição manual de PDFs suplementares (rejeitada na Q2 da arbitragem do 4b-i).
- Verificação adicional dos 61 recuperados pós-re-rodada (decisão (ii): ficar com os 790).

## 7. Critérios de sucesso

1. `make verify-sample` gera `07_amostra_frame.csv` (790 ids) e `07_amostra_verificacao.csv` (~110 linhas; 34 exclusões + ~76 inclusões estratificadas; seed=42 reprodutível).
2. `make verify-export` produz `07_eleg_cega.csv` (~110 linhas, **sem** colunas LLM) e `07_auditoria_campos.csv` (~76 linhas, 6 campos críticos × 3 colunas).
3. Rerodar `verify-sample`/`verify-export` pós-re-rodada do extract **não altera** amostra nem perde input humano (idempotência verificada por teste).
4. `make verify-ingest` calcula κ humano×LLM (elegibilidade, n≈110) e acurácia por campo (n≈76) e escreve `verificacao_kappa.tex` + `verificacao_acuracia.tex`. Aborta com lista de pendências se planilhas incompletas.
5. `prisma_flow` regenera com anotação interina enquanto `pendentes_reextract > 0`; vira diagrama final automaticamente quando = 0.
6. Protocolo v1.2 commitado: §7 referencia §8; §8 absorve a nota interina como descrição definitiva + subseção da verificação amostral; §11 adiciona limitação da verificação amostral.
7. Suite cheia verde (206 + novos), tudo via `source .venv/bin/activate && pytest` (nunca `uv run`).

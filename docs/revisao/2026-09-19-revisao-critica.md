# Revisão crítica do TCC — 19/09/2026

Parecer sobre o texto (`text/`), os dados (`data/processed/06_extraction.csv`) e o
código de análise. Divide-se em: (A) o que foi alterado nesta revisão; (B) críticas
por ordem de gravidade; (C) sugestões por capítulo; (D) pendências que só o autor
pode resolver.

---

## A. O que foi alterado

### A1. Defeito corrigido na variável central (`pre_pos_chatgpt` e `janela`)

O prompt de extração pedia `pre_pos_chatgpt: pre | pos (pivô 2022-11-30)` sem dizer
"data de publicação". O LLM respondeu de forma híbrida: **115 estudos publicados em
2023–2026 foram codificados como "pré"** porque seus dados eram anteriores a 2022, e
estudos de 2024–2025 caíram na janela 2013–2017. Concordância com o ano de
publicação: 85,9%. O texto, porém, define o período como "estudos publicados antes
do lançamento do ChatGPT".

Correção: `scripts/analysis/corpus.py` agora deriva as duas colunas do `ano`
(pré = até 2022; pós = 2023+). O valor do LLM fica em `*_llm` e é usado como
sensibilidade. `scripts/biblio/report.py` usa a mesma regra.

Efeito sobre o resultado central:

| Definição de período | Pré | Pós | RC | p (Fisher) |
|---|---|---|---|---|
| LLM (versão anterior) | 7,5% | 12,9% | 1,84 | 0,0609 |
| Ano de publicação (atual) | 2,7% | 13,6% | 5,61 | < 0,001 |

A narrativa "tangencia o limiar de 5%" deixa de valer. A hipótese é confirmada em
direção e força, mas a baixa qualificação segue modal (63% e 54%). "Ruptura
parcial" continua sendo o rótulo correto, agora por outra razão (ver A2).

Outros resultados que mudaram com a correção: o sinal **positivo** quadruplica
(3,8% para 16,8%) e o ambíguo fica estável, então a frase antiga "a evidência é mais
ambivalente" virou "menos pessimista"; o deslocamento e a demanda agregada passam a
cair de forma significativa; o tipo de estudo que mais recua é o teórico, não o de
exposição.

### A2. Análise aprofundada (novo módulo `scripts/analysis/aprofundamento.py`)

Oito tabelas e uma figura novas, com testes (`tests/analysis/test_aprofundamento.py`)
e alvo `make analysis-aprofundamento`. Achados:

1. **O risco acompanha o objeto tecnológico, não o calendário.** Estudos de IA
   generativa: 48,5% apontam alta qualificação (categoria modal). Estudos de
   automação e robôs: 2–3%, idênticos antes e depois de 2023 (68,8% e 67,5% para
   baixa qualificação). Só 9,2% dos estudos pós-2023 tratam de IA generativa.
2. **Há também difusão do enquadramento.** O efeito do período sobrevive à exclusão
   dos estudos de IA generativa (2,7% para 10,2%) e aos controles no logit (RC 3,18).
3. **A tendência é gradual e anterior ao ChatGPT**: zero até 2020, crescimento
   monotônico desde 2021 (RC 1,46 por ano).
4. **O sinal depende do desenho** (V de Cramér 0,30, a maior associação do corpus):
   exposição ocupacional 50% negativo; firma 43% positivo; teoria e revisões 80%
   ambíguo. Confirma com dados a conjectura da Introdução.
5. **Composição versus mudança interna.** Metade do crescimento do sinal positivo e
   quase toda a queda do deslocamento são recomposição do corpus (mais estudos de
   firma). Complementaridade, demanda agregada, horizonte e sinal negativo mudam
   dentro dos tipos.
6. **Perfis de mecanismos reproduzem a lógica Acemoglu–Restrepo**: só deslocamento
   dá 67% negativo; só compensação dá 65% positivo; ambos dá 73% ambíguo.
7. **Holm**: tudo sobrevive, exceto reinstalação (que já não era significativa).
8. **Validade da extração por resumo**: a polarização fica sem classificar em 40%
   dos resumos contra 11% dos textos completos, e o resumo subestima "ambos"
   (28% contra 46%). As demais dimensões não diferem.
9. **Cobertura da busca**: das 46 referências com data elegível entre as 60 mais
   citadas pelo corpus, a busca recuperou 15. Lista em
   `reports/revisao/top_referencias_cobertura.csv`.

### A2b. Teste com a robótica como grupo de comparação

Pedido do autor em 19/09. Duas tabelas novas (`placebo_tecnologia`, `robos_vs_genai`)
e a seção 8.2 da Discussão.

- **Placebo aprovado na variável da hipótese.** Dentro de robótica e automação
  (160 pré, 253 pós), alta qualificação vai de 1,8% para 3,1% (p = 0,72). Nos estudos
  de IA em geral vai de 3,1% para 20,1%.
- **Mudanças de época, não da IA generativa.** Horizonte mais curto, menos demanda
  agregada e mais sinal positivo ocorrem também dentro da robótica. Das rupturas do
  Cap. 06, só o deslocamento do risco e parte da complementaridade são do objeto.
- **Robôs contra IA generativa, só 2023+.** Diferem em quem está em risco
  (V = 0,55, a maior associação da revisão). Não diferem no sinal nem no deslocamento.
- **Maturidade desigual.** Robótica: 36% com identificação causal, 40% com score ≥ 4.
  IA generativa: 12% e 11%, 45% revisões, 1,9% demanda agregada.
- **Ressalva decisiva.** Os 16 estudos de IA generativa que apontam alta
  qualificação são 6 de exposição, 6 revisões e 4 teóricos. Nenhum é evidência de
  firma ou macro. O diagnóstico é de exposição, não de efeito realizado.

### A3. Texto

- Caps. 04, 05 e 06 reconciliados com as tabelas (N = 816; pré 240; pós 576). Fecha
  a pendência de junho.
- Cap. 03: nova seção "Definição operacional do período"; reextração concluída;
  novos métodos estatísticos; limitações de cobertura; removida a contradição
  "predominância de working papers" (o corpus tem zero).
- Cap. 06b: percentuais pós-ChatGPT dos grupos recalculados (C2 80%, C3 52%, C4 89%,
  C6 74%); suavizada a afirmação de independência "inteira" em relação ao LLM, pois
  a coluna de polarização vem da mesma extração.
- **Novo Cap. 06c "Discussão"**, que liga resultados e referencial.
- Cap. 01: roteiro dos capítulos atualizado.
- `refs.bib`: cinco entradas novas, todas conferidas no Crossref (Acemoglu 2025;
  Hui, Reshef e Zhou 2024; Brynjolfsson 2022; Agrawal, Gans e Goldfarb 2019; Autor
  2024).
- Dependência nova: `statsmodels` (logit e Holm).

Nada foi commitado. O Cap. 02 não foi tocado porque tinha edições suas em aberto.

---

## B. Críticas, da mais grave para a menos grave

### B1. Sensibilidade da busca é baixa e não foi validada (grave)

Frey e Osborne, Acemoglu–Restrepo "Robots and Jobs", Webb, Felten, Eloundou, Noy e
Zhang, Graetz e Michaels e Hui et al. não foram sequer recuperados. Causas: a
string não tem `robot*`, `computeri?ation`, `technolog*`; periódicos de ciência
geral ficam fora de filtros de área; WoS e Scopus não indexam working papers, embora
os critérios os admitam. Consequência: o corpus é a literatura difusa (muito
*Applied Economics Letters*, Springer Proceedings, periódicos regionais), não a
fronteira. A banca provavelmente notará que o referencial cita trabalhos que o
corpus não contém.

Opções, em ordem de custo:
1. Assumir e delimitar (feito no texto): a revisão descreve o enquadramento
   predominante na literatura indexada.
2. **Snowballing reverso** usando o CSV de cobertura: triagem manual das ~30
   referências mais citadas ausentes, inclusão das elegíveis como "identificadas por
   outras fontes" no PRISMA. É barato e é prática PRISMA padrão.
3. Reexecutar a busca com string v1.1. Caro; não recomendo no prazo.

### B2. Verificação humana ainda não foi feita (grave)

Toda a cadeia (triagem, arbitragem, elegibilidade, extração, qualidade) é LLM. O
único elo humano previsto, a amostra de ~110 estudos, está exportado e não
preenchido. Sem o κ humano×LLM e a acurácia por campo, a banca não tem como avaliar
a confiabilidade. O defeito A1 mostra que o risco é real. **Esta é a pendência
número um.** Sugiro priorizar a auditoria de `polarizacao` e `tecnologia_focada`,
que sustentam o achado principal, e sobreamostrar os 33 estudos de IA generativa
classificados.

### B3. Critério E2 contradiz o corpus (média)

E2 exclui "robótica industrial pré-IA" e "automação puramente mecânica", mas 413
dos 816 estudos (51%) têm como foco automação ou robôs. Ou o critério não foi
aplicado, ou o critério real é mais amplo que o escrito. Recomendo emendar o
protocolo (v1.3) declarando que a automação e a robótica foram mantidas como
**grupo de comparação**, que é exatamente o papel que desempenham na Discussão.

### B4. Método comum e circularidade (média)

Todas as variáveis substantivas saem da mesma chamada do mesmo modelo. Associações
entre duas variáveis extraídas (mecanismo × sinal; tecnologia × polarização) podem
estar infladas por coerência interna do extrator. Está declarado no Cap. 06c. A
auditoria humana (B2) é o remédio.

### B5. 86% do corpus lido só pelo resumo (média)

Já declarado, agora quantificado (Tabela de validade da fonte). A polarização é a
variável mais afetada. Se houver acesso institucional, priorizar o texto completo
dos 54 estudos de IA generativa e dos 55 que apontam alta qualificação.

### B6. Score de qualidade é frágil (média)

Atribuído por LLM, quase sempre a partir do resumo, e mistura prestígio do veículo
com rigor. Só 14 estudos têm nota 5. A "robustez por qualidade" tem células de 34
e 88. Apresente-a como indicativa. Alternativa mais defensável: usar indicadores
objetivos (revisado por pares; método com identificação: IV, DiD, RDD, evento).

### B7. "Censo, não amostra" (menor)

Com recuperação de um terço da literatura estruturante, o corpus é uma amostra não
aleatória da literatura, não um censo dela. É censo apenas dos registros
recuperados. O tratamento dos p-valores como descritivos está correto; ajuste a
frase. Tamanhos de efeito (RC com IC, V de Cramér) foram acrescentados.

### B8. Magnitude normalizada não é interpretável (menor)

A faixa vai de −13 a +36 em unidades mistas. A mediana não significa nada. Sugiro
manter só a linha de cobertura e remover mediana e quartis, ou restringir a um
subconjunto homogêneo (por exemplo, elasticidades emprego–robô).

### B9. Janelas sobrepostas e primeira janela minúscula (menor)

"2018–2022" e "2022–2026" compartilham 2022. Operacionalmente são 2018–2022 e
2023–2026; considere renomear a macro `\janelaTres`. A janela 2013–2017 tem 15
estudos; trate-a como pano de fundo (feito no Cap. 05).

### B10. Higiene de dados (menor)

- País não normalizado: EUA (33) + United States (10) + variantes = 47;
  Australia/Austrália duplicado. A tabela descritiva subconta os EUA.
- `tipo_estudo = indivíduo` (6 casos) está fora do enum.
- `citacoes_chave` vazio em 852 linhas; `replicavel` nunca é usado. Remova do
  esquema descrito ou use.
- 22,7% "book chapter" são em boa parte anais Springer. Vale uma linha de
  sensibilidade.

---

## C. Sugestões por capítulo

**Título e objetivo.** O título e o objetivo geral dizem 2013–2025; a janela vai até
junho de 2026 e 15% do corpus é de 2026. Alinhar.

**Cap. 01.** (i) Erros de digitação: "reforca" (2×), "evidencia". (ii) A citação de
Eloundou ("metade das tarefas de 46% das ocupações") vale só no cenário com software
complementar; sem ele o número é 1,8%. Acrescente a nuance. (iii) A frase "divergem
por medirem objetos distintos" agora tem respaldo empírico; remeta ao Cap. 06c.
(iv) O parágrafo sobre o Brasil está comentado, mas o objetivo específico 5 continua
na lista.

**Cap. 02.** (i) "Partimos… chegamos… e termina situando": concordância.
(ii) "Abastratas". (iii) Os dois parágrafos após a lista ALM repetem a mesma ideia;
fundir. (iv) Subseções comentadas deixam uma seção 2.1 muito longa; reative os
títulos. (v) Lacunas teóricas que a Discussão agora usa e que merecem um parágrafo
aqui: a distinção complementaridade × reinstalação como coisas diferentes
(já está, mas sem ênfase); Autor (2024) e a tese da expertise; Agrawal, Gans e
Goldfarb (2019) sobre predição e julgamento; Acemoglu (2025) sobre efeitos macro
modestos; Brynjolfsson (2022) sobre a armadilha de Turing. As entradas já estão no
`refs.bib`. (vi) Falta literatura sobre países em desenvolvimento, necessária para
o Cap. 07.

**Cap. 03.** (i) κ do árbitro com o Haiku ≈ 0 merece mais que uma frase: significa
que, nos casos limítrofes, um dos triadores não tinha poder discriminante; diga-o.
(ii) Relate o custo e as versões exatas dos modelos num apêndice. (iii) Inclua o
prompt de extração como apêndice; é o "instrumento de coleta". (iv) Tabelas de κ
usam ponto decimal, o resto usa vírgula.

**Cap. 06b.** O grupo C4 (robôs, firma, China) é 89% pós-2023 e tem só 5% de alta
qualificação: é a melhor evidência de que o que separa os grupos é o objeto.
Já incorporado.

**Caps. 07 e 08.** Estão vazios. O corpus tem **três** estudos sobre o Brasil, então
a subseção "O que a literatura brasileira do corpus diz" não se sustenta como
planejada. Sugestão de estrutura para o Cap. 07: (1) o que as três proposições da
Discussão implicam para uma economia com alta informalidade e menor peso de
ocupações cognitivas; (2) literatura brasileira fora do corpus (IPEA, FGV, BCB,
OIT e FMI para emergentes), declarada como complemento narrativo; (3) limites da
extrapolação, usando o fato de que 47% do corpus é multipaís e 14% é China. Para o
Cap. 08, as três proposições da seção 8.5 e a lista B deste parecer já são o
esqueleto de síntese, limitações e agenda.

**Pré-textuais.** Resumo e abstract estão vazios. `style=apa` não é ABNT; migrar
para `biblatex-abnt` e, idealmente, `abntex2`, antes da entrega.

---

## D. Decisões que são suas

1. Aceitar a redefinição do período pelo ano de publicação. Recomendo: é o que o
   texto sempre declarou. Reversível pelo git.
2. Fazer ou não o snowballing (B1).
3. Emendar o protocolo quanto ao E2 (B3).
4. Revisar a interpretação do Cap. 06c. Foi redigido por mim com base nos dados; a
   tese é sua e a banca vai perguntar a você.
5. Ainda em aberto de maio: versionar ou não os artefatos gerados; normalizar país.

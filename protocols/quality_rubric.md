# Rubrica de Avaliação de Qualidade

Aplicada na elegibilidade (preliminar) e revisada na extração (final). Score 1–5.

## Critérios

| Score | Periódico/Série | Identificação | Robustez | Replicabilidade |
|:----:|----|----|----|----|
| **5** | Top-5 em economia (AER, JPE, QJE, ReStud, ECMA) ou top-field líder (JoLE, JEEA, JoHR) | Causal crível (DiD com paralelas, IV forte, RDD, RCT) | Múltiplos checks, heterogeneidades, mecanismos testados | Código e dados públicos |
| **4** | Periódico bom de economia (Labour Economics, ILR Review, Economics Letters seletivos) ou working paper de top-instituição com forte revisão (NBER WP de autor estabelecido) | Identificação razoável; controles plausíveis; potenciais ameaças endereçadas | Robustez presente, sem cobertura exaustiva | Replicabilidade parcial (código ou dados, não ambos) |
| **3** | Working paper de instituição reconhecida (IZA, CEPR, BIS, OECD, IPEA, BCB) ou periódico médio | Descritiva ou correlacional bem feita; sem pretensão causal forte | Mínima | Não declarada ou limitada |
| **2** | Periódico fraco, trabalho de conferência sem revisão | Evidência apenas sugestiva; identificação fraca; poucos controles | Ausente | Não |
| **1** | Sem revisão formal; muito preliminar | Apenas descritivo simples ou projeção sem base empírica clara | Ausente | Não |

## Como usar

1. **Na elegibilidade** (etapa F5): aplicar score preliminar com base em leitura rápida do paper (abstract + intro + método).
2. **Na extração** (etapa F6): revisar score após leitura completa.
3. **Decisão final:** estudos com score 1 podem ser excluídos do corpus sistemático mediante decisão registrada em `04_eligibility.csv` (motivo: `E5`).
4. **Em caso de dúvida entre dois níveis:** registrar o menor e justificar em `nota_extracao`.

## Princípios

- Score reflete **rigor do estudo**, não **direção do achado**. Estudos com achados nulos podem ser 5; estudos com achados grandes podem ser 2.
- Working paper de autor estabelecido + identificação forte = 4 (não cai para 3 só por ser WP).
- Periódico top + descritivo = 3 (não sobe para 5 só pelo periódico).
- Estudos teóricos avaliam-se por **clareza do modelo**, **transparência das premissas** e **alinhamento com a literatura**; aplicar rubrica adaptada.

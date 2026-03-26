from ai.models import gerar_texto


def gerar_cenario_atual(dados_metrica_performance, dados_investimentos, dados_custos, info_concorrentes, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 1/7: Cenário Atual — panorama geral da operação digital."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção CENÁRIO ATUAL do relatório executivo mensal da Syngenta. Esta é a PRIMEIRA de 7 etapas e serve como base para todas as análises seguintes.

Escreva em prosa corrida, técnica e narrativa. Não use listas de bullet points como estrutura principal. Cada frase deve conter um dado concreto.

---

**DADOS DE PERFORMANCE:**
| Métrica | Atual | Var. MoM | Var. YoY |
|---------|-------|----------|----------|
| Investimento | R$ {dados_metrica_performance.get('spend_atual', 0):,.2f} | {dados_metrica_performance.get('var_invest_mes', 0):+.1f}% | {dados_metrica_performance.get('var_invest_ano', 0):+.1f}% |
| Sessões | {dados_metrica_performance.get('sess_atual', 0):,} | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
| Alcance | {dados_metrica_performance.get('reach_atual', 0):,} | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
| Impressões | {dados_metrica_performance.get('imp_atual', 0):,} | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |
| Cliques | {dados_metrica_performance.get('cli_atual', 0):,} | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
| Engajamentos | {dados_metrica_performance.get('eng_atual', 0):,} | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
| CTR | {dados_metrica_performance.get('ctr_atual', 0):.2f}% | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |
| Video Thruplays | {dados_metrica_performance.get('vtp_atual', 0):,} | {dados_metrica_performance.get('var_vtp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_vtp_ano', 0):+.1f}% |

**INVESTIMENTOS:**
Total: R$ {dados_investimentos.get('total_atual', 0):,.2f} (MoM: {dados_investimentos.get('var_total_mes', 0):+.1f}%, YoY: {dados_investimentos.get('var_total_ano', 0):+.1f}%)
Meta: R$ {dados_investimentos.get('fb_atual', 0) + dados_investimentos.get('ig_atual', 0):,.2f} | Google: R$ {dados_investimentos.get('google_atual', 0):,.2f} | TikTok: R$ {dados_investimentos.get('tt_atual', 0):,.2f}

**CUSTOS:**
CPC R$ {dados_custos.get('cpc_atual', 0):.2f} (MoM: {dados_custos.get('var_cpc_mes', 0):+.1f}%, YoY: {dados_custos.get('var_cpc_ano', 0):+.1f}%) | CPM R$ {dados_custos.get('cpm_atual', 0):.2f} (MoM: {dados_custos.get('var_cpm_mes', 0):+.1f}%) | CPE R$ {dados_custos.get('cpe_atual', 0):.2f} (MoM: {dados_custos.get('var_cpe_mes', 0):+.1f}%) | CPV R$ {dados_custos.get('cpv_atual', 0):.2f} (MoM: {dados_custos.get('var_cpv_mes', 0):+.1f}%)

**CONCORRENTES:** {info_concorrentes if info_concorrentes else "Nenhuma informação fornecida."}

---

Cubra em sequência narrativa:

1. **Estado geral da operação**: crescimento, estabilidade ou retração? Classifique como EXPANSÃO, OTIMIZAÇÃO, ESTABILIDADE, CONTRAÇÃO ou CRISE com base nos 3 dados mais relevantes.

2. **Cruzamentos de dados obrigatórios** — identifique APENAS os que estão acontecendo nos dados:
- Investimento vs. Resultados: Efeito Tesoura (mais resultado com menos gasto) ou inverso?
- Impressões vs. CTR: relevância subindo ou caindo?
- Alcance vs. Sessões: público mais qualificado ou desconexão mídia-destino?
- CPC vs. CTR: relevância do anúncio melhorando ou piorando?
- Impressões vs. Alcance: frequência aumentando (risco de fadiga) ou alcance novo?

3. **Eficiência do funil**: calcule Impressões→Cliques (CTR), Cliques→Sessões (taxa de aterrissagem), Alcance→Engajamento. Onde o funil está apertando?

4. **Contexto competitivo**: pressão nos custos de mídia, sazonalidade agro, SWOT baseado exclusivamente nos dados.

5. **Veredicto executivo**: em 2-3 frases, sintetize o que aconteceu, por que, e o que significa.

**REGRAS:** Não invente dados. Tom técnico, narrativo, de especialista sênior. Português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_destaques(cenario_atual, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 2/7: Destaques do período."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção DESTAQUES do relatório executivo mensal da Syngenta. Esta é a SEGUNDA de 7 etapas.

**CENÁRIO ATUAL (Etapa 1):**
{cenario_atual}

---

Extraia 5 a 7 fatos mais relevantes do período. Para cada destaque:

- **Título curto e impactante** com dado (ex: "Efeito Tesoura Confirmado: -12% investimento, +8% cliques")
- **Parágrafo narrativo denso**: o dado exato, contexto MoM/YoY, causa provável baseada nos cruzamentos da Etapa 1, e implicação prática.
- **Classificação**: CONQUISTA, ALERTA ou OPORTUNIDADE.

Cubra obrigatoriamente:
1. Principal ganho de eficiência — quantifique em economia ou produtividade
2. Métrica de maior crescimento — é sustentável ou pontual?
3. Principal sinal de alerta — cenário projetado se continuar
4. Correlação mais significativa entre métricas
5. Oportunidade concreta com maior potencial
6. Tendência geral da operação
7. (Opcional) Fato contraintuitivo

**REGRAS:** Não invente dados. Prosa corrida. Tom técnico. Português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_produtos_destaque(cenario_atual, dados_produtos, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 2.5 — Produtos Destaque por Categoria (app_view_media_plan)."""
    if not dados_produtos:
        tabela_produtos = "Nenhum dado de produto disponível neste período."
    else:
        linhas = []
        for categoria, produtos in dados_produtos.items():
            linhas.append(f"\n### Categoria: {categoria}\n")
            linhas.append("| # | Produto | Investimento | Impressões | Cliques | CTR |")
            linhas.append("|---|---------|-------------|------------|---------|-----|")
            for p in produtos[:3]:
                linhas.append(
                    f"| {int(p['rank_spend'])} | {p['product']} "
                    f"| R$ {p['spend_total']:,.2f} "
                    f"| {int(p['impressions_total']):,} "
                    f"| {int(p['clicks_total']):,} "
                    f"| {p['ctr_media']*100:.2f}% |"
                )
        tabela_produtos = "\n".join(linhas)

    prompt = f"""
Você é um especialista sênior em marketing digital com profundo conhecimento do agronegócio brasileiro. Escreva a seção PRODUTOS DESTAQUE do relatório executivo mensal da Syngenta. Esta é a ETAPA 2.5 do pipeline — vem depois dos Destaques gerais e antes das Mídias Pagas.

OBJETIVO DESTA SEÇÃO: identificar quais produtos (crops, soluções, linhas de produto) tiveram melhor desempenho por categoria de campanha no período, explicar o porquê com base nos dados e contextualizar com o cenário agro. O output deve estar formatado para ser diretamente transferido a um slide de apresentação executiva.

---

**CENÁRIO ATUAL DO PERÍODO (Etapa 1 — base de contexto):**
{cenario_atual}

---

**DADOS DE PRODUTOS DESTAQUE POR CATEGORIA (app_view_media_plan):**
{tabela_produtos}

---

## COMO ANALISAR E ESTRUTURAR A RESPOSTA

Escreva OBRIGATORIAMENTE no seguinte formato para cada categoria (isso alimenta os slides diretamente):

---

## [NOME DA CATEGORIA]

**Produto #1 — [NOME DO PRODUTO]** · DESTAQUE | ALERTA | OPORTUNIDADE
Investimento: R$ X.XXX · Impressões: XXX.XXX · Cliques: X.XXX · CTR: X.XX%
> [1 parágrafo curto (máx. 4 linhas): por que este produto se destacou? Qual contexto agro/safra justifica o desempenho? Qual correlação com métricas gerais da Etapa 1? Qualificação clara: conquista, risco ou oportunidade. Seja específico — não use frases genéricas.]

**Produto #2 — [NOME DO PRODUTO]** · DESTAQUE | ALERTA | OPORTUNIDADE
Investimento: R$ X.XXX · Impressões: XXX.XXX · Cliques: X.XXX · CTR: X.XX%
> [1 parágrafo curto (máx. 4 linhas): mesma estrutura acima]

**Produto #3 — [NOME DO PRODUTO]** · DESTAQUE | ALERTA | OPORTUNIDADE
Investimento: R$ X.XXX · Impressões: XXX.XXX · Cliques: X.XXX · CTR: X.XX%
> [1 parágrafo curto (máx. 4 linhas): mesma estrutura acima]

**Insight da Categoria:** [1 frase única com o principal aprendizado desta categoria — deve ser acionável e específico, ex: "Alto CTR de Herbicida X com baixo investimento relativo indica demanda orgânica não atendida — oportunidade de escala no Meta."]

---

## DIRETRIZES DE ANÁLISE

Para cada produto, responda implicitamente:
1. **Eficiência real vs. volume**: o produto lidera em spend porque recebeu mais budget, ou porque gerou mais resultado por real investido? Se o CTR for alto com investimento baixo = sinal de demanda natural. Se o CTR for baixo com alto investimento = volume forçado.
2. **Contexto de safra e calendário agro**: lembre-se de que cada produto da Syngenta tem janelas de demanda (plantio, tratamento, colheita). Um produto em destaque fora do período de safra é um sinal mais forte do que um em plena safra.
3. **Conexão com métricas gerais**: o desempenho deste produto está puxando ou é puxado pelo cenário geral da Etapa 1? Efeito Tesoura localizado?
4. **Anomalia vs. tendência**: o destaque é recorrente ou pontual? O alerta é estrutural ou conjuntural?

## REGRAS OBRIGATÓRIAS
- Use EXATAMENTE o formato de bloco acima — isso é lido por código para gerar os slides automaticamente
- Não invente dados. Se um dado não estiver na tabela, não mencione
- Texto dos parágrafos: prosa técnica, objetiva, máximo 4 linhas por produto
- Classificação obrigatória: escolha apenas UMA entre DESTAQUE, ALERTA ou OPORTUNIDADE para cada produto
- Português do Brasil
- Tom: especialista de negócios falando para um CMO ou diretor de marketing agrícola
- O "Insight da Categoria" deve ser diferente para cada categoria — não repita o mesmo padrão
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_midias_pagas(cenario_atual, dados_investimentos, dados_custos, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 3/7: Análise de Mídias Pagas por canal."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção MÍDIAS PAGAS do relatório executivo mensal da Syngenta. Esta é a TERCEIRA de 7 etapas.

**CENÁRIO ATUAL (Etapa 1):**
{cenario_atual}

---

**INVESTIMENTOS POR CANAL:**
| Canal | Atual | Var. MoM | Var. YoY |
|-------|-------|----------|----------|
| Facebook | R$ {dados_investimentos.get('fb_atual', 0):,.2f} | {dados_investimentos.get('var_fb_mes', 0):+.1f}% | {dados_investimentos.get('var_fb_ano', 0):+.1f}% |
| Instagram | R$ {dados_investimentos.get('ig_atual', 0):,.2f} | {dados_investimentos.get('var_ig_mes', 0):+.1f}% | {dados_investimentos.get('var_ig_ano', 0):+.1f}% |
| TikTok | R$ {dados_investimentos.get('tt_atual', 0):,.2f} | {dados_investimentos.get('var_tt_mes', 0):+.1f}% | {dados_investimentos.get('var_tt_ano', 0):+.1f}% |
| Google Ads | R$ {dados_investimentos.get('google_atual', 0):,.2f} | {dados_investimentos.get('var_google_mes', 0):+.1f}% | {dados_investimentos.get('var_google_ano', 0):+.1f}% |
| YouTube | R$ {dados_investimentos.get('yt_atual', 0):,.2f} | — | — |
| PMax | R$ {dados_investimentos.get('pmax_atual', 0):,.2f} | — | — |
| TOTAL | R$ {dados_investimentos.get('total_atual', 0):,.2f} | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |

**CUSTOS GLOBAIS:**
CPC R$ {dados_custos.get('cpc_atual', 0):.2f} (MoM: {dados_custos.get('var_cpc_mes', 0):+.1f}%) | CPM R$ {dados_custos.get('cpm_atual', 0):.2f} (MoM: {dados_custos.get('var_cpm_mes', 0):+.1f}%) | CPE R$ {dados_custos.get('cpe_atual', 0):.2f} (MoM: {dados_custos.get('var_cpe_mes', 0):+.1f}%) | CPV R$ {dados_custos.get('cpv_atual', 0):.2f} (MoM: {dados_custos.get('var_cpv_mes', 0):+.1f}%)

---

Analise em profundidade:

1. **Eficiência de capital por canal**: para cada canal, calcule % do investimento total e cruze com participação nos resultados. Identifique o canal mais e menos eficiente.

2. **Análise por ecossistema**: Meta (FB+IG sinergia, audiência complementar ou sobreposta?), Google (Search+PMax, canibalização do orgânico?), TikTok (awareness real ou vanity?), YouTube (CPV competitivo?).

3. **Mix de mídia**: concentração de investimento (>50% em um canal = risco). Proponha mix ideal baseado nos dados reais, não em teoria.

4. **Realocação sugerida**: se R$ X fossem movidos do canal A para o B, qual impacto estimado? Quantifique.

5. **Cruzamentos entre canais**: qual canal puxa eficiência para cima? Qual está inflacionando custos? Variações MoM alinhadas com resultados gerais?

**REGRAS:** Não invente dados. Prosa corrida. Tom técnico. Português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_social(cenario_atual, descricoes_imagens, descricoes_imagens_mes_passado, dados_custos, modelo_escolhido, modelo_gemini, cliente_anthropic, resumos_social_csvs=None):
    """ETAPA 4/7: Análise de Social/Criativos."""
    bloco_csvs = ""
    bloco_analise_csv = ""
    num_recomendacoes = "6"
    if resumos_social_csvs:
        dados_csvs_juntos = chr(10).join(resumos_social_csvs)
        bloco_csvs = (
            "\n---\n\n"
            "**DADOS BRUTOS DE SOCIAL (CSVs enviados pelo usuário):**\n"
            "Os dados abaixo foram exportados diretamente das plataformas sociais. O formato varia — analise cada arquivo individualmente, "
            "identifique quais métricas e dimensões estão presentes, e extraia todos os insights possíveis. Cruze esses dados com os criativos, "
            "indicadores de eficiência e cenário atual.\n\n"
            f"{dados_csvs_juntos}\n\n---\n"
        )
        bloco_analise_csv = (
            "\n6. **Análise dos dados de Social (CSVs)**: analise todos os dados brutos fornecidos. "
            "Identifique padrões de engajamento, melhores horários, tipos de conteúdo com melhor performance, "
            "crescimento de seguidores, alcance orgânico vs. pago, e qualquer insight relevante que os dados revelem. "
            "Cruze com os criativos e indicadores de eficiência.\n\n"
            "7. **Cruzamentos entre fontes**: correlacione métricas dos CSVs com os dados de custo (CPE, CPC) "
            "e as análises visuais dos criativos. Identifique quais posts/conteúdos geraram melhor retorno.\n"
        )
        num_recomendacoes = "8"

    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção SOCIAL do relatório executivo mensal da Syngenta. Esta é a QUARTA de 7 etapas. Foque na análise de criativos, conteúdo social e performance criativa.

**CENÁRIO ATUAL (Etapa 1):**
{cenario_atual}

---

**CRIATIVOS DO MÊS ATUAL:**
{chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhum criativo do mês atual fornecido."}

**CRIATIVOS DO MÊS PASSADO:**
{chr(10).join(descricoes_imagens_mes_passado) if descricoes_imagens_mes_passado else "Nenhum criativo do mês passado fornecido."}

**INDICADORES DE EFICIÊNCIA CRIATIVA:**
| Indicador | Valor | Var. MoM | Var. YoY |
|-----------|-------|----------|----------|
| CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
| CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
| CPV | R$ {dados_custos.get('cpv_atual', 0):.2f} | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |
| CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |
{bloco_csvs}
---

Analise em profundidade:

1. **Estratégia narrativa**: qual mensagem central cada criativo comunica? Para qual público? Alinhamento com momento agro (safra, entressafra)?

2. **Psicologia aplicada**: quais gatilhos estão sendo usados (urgência, autoridade técnica, prova social, identificação com produtor rural)? Linguagem do campo ou genérica?

3. **Evolução mês a mês**: o que mudou? Mudança intencional ou aleatória? Elementos visuais mantidos como âncora de marca?

4. **ROI criativo**: correlacione mudanças visuais/narrativas com variações de CPE/CPC. Se CPE caiu, qual elemento causou? Se CPC subiu, o criativo gera curiosidade sem entregar promessa?

5. **Fadiga criativa**: criativos muito similares = saturação. Muito diferentes = inconsistência de marca.
{bloco_analise_csv}
{num_recomendacoes}. **Recomendações concretas**: testes A/B específicos, formatos a explorar (carrossel, Reels, UGC de produtor), ajustes de composição visual.

**REGRAS:** Não invente dados. Prosa corrida. Tom técnico. Português do Brasil. Se dados de CSVs foram fornecidos, OBRIGATORIAMENTE analise-os e extraia insights — não os ignore.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_seo_content(cenario_atual, dados_seo, dados_custos, modelo_escolhido, modelo_gemini, cliente_anthropic, resumos_seo_csvs=None):
    """ETAPA 5/7: Análise de SEO e Conteúdo."""
    bloco_csvs = ""
    bloco_analise_seo_csv = ""
    if resumos_seo_csvs:
        dados_csvs_juntos = chr(10).join(resumos_seo_csvs)
        bloco_csvs = (
            "\n---\n\n"
            "**DADOS BRUTOS DE SEO (CSVs enviados pelo usuário):**\n"
            "Os dados abaixo foram exportados diretamente de ferramentas de SEO (Google Search Console, GA4, SEMrush, Ahrefs, etc.). "
            "O formato varia — analise cada arquivo individualmente, identifique quais métricas e dimensões estão presentes, "
            "e extraia todos os insights possíveis. Cruze esses dados com as métricas manuais acima e o cenário atual.\n\n"
            f"{dados_csvs_juntos}\n\n---\n"
        )
        bloco_analise_seo_csv = (
            "\n7. **Análise dos dados de SEO (CSVs)**: analise todos os dados brutos fornecidos. "
            "Identifique tendências de posicionamento, queries com potencial de crescimento, páginas de melhor/pior performance, "
            "CTR por posição, impressões vs. cliques, e qualquer insight relevante que os dados revelem.\n\n"
            "8. **Cruzamentos entre fontes**: correlacione os dados dos CSVs com as métricas manuais e o cenário atual. "
            "Identifique discrepâncias, oportunidades ocultas e confirme ou refute tendências.\n"
        )

    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção SEO do relatório executivo mensal da Syngenta. Esta é a QUINTA de 7 etapas.

**CENÁRIO ATUAL (Etapa 1):**
{cenario_atual}

---

**DADOS SEO:**
| Métrica | Atual | Mês Passado | Var. MoM |
|---------|-------|-------------|----------|
| Visualizações (Total) | {dados_seo.get('vis_total_atual', 0):,} | {dados_seo.get('vis_total_mes', 0):,} | {dados_seo.get('var_vis_total_mes', 0):+.1f}% |
| Sessões (Total) | {dados_seo.get('sess_total_atual', 0):,} | {dados_seo.get('sess_total_mes', 0):,} | — |
| Usuários (Total) | {dados_seo.get('user_total_atual', 0):,} | {dados_seo.get('user_total_mes', 0):,} | — |
| Visualizações Orgânicas | {dados_seo.get('vis_org_atual', 0):,} | {dados_seo.get('vis_org_mes', 0):,} | {dados_seo.get('var_vis_org_mes', 0):+.1f}% |
| Sessões Orgânicas | {dados_seo.get('sess_org_atual', 0):,} | {dados_seo.get('sess_org_mes', 0):,} | {dados_seo.get('var_sess_org_mes', 0):+.1f}% |
| Usuários Orgânicos | {dados_seo.get('user_org_atual', 0):,} | {dados_seo.get('user_org_mes', 0):,} | — |

**Top Keywords:** {dados_seo.get('top_keywords', 'Nenhuma keyword fornecida')}

**CPC Médio (para cálculo de custo evitado):** R$ {dados_custos.get('cpc_atual', 0):.2f}
{bloco_csvs}
---

Analise em profundidade:

1. **Demanda de mercado via buscas**: keywords de marca vs. genéricas? Proporção e implicação estratégica.

2. **Autoridade de marca**: orgânico crescendo = ganhando autoridade. Caindo = concorrentes produzindo conteúdo melhor ou conteúdo não responde às perguntas do público.

3. **Funil de conteúdo**: visualizações→sessões→usuários. Taxas de conversão entre etapas. Onde há gargalo?

4. **Cruzamento orgânico vs. pago**: proporção de tráfego orgânico sobre total. Independência de mídia crescendo ou dependência de pago aumentando?

5. **Custo evitado pelo orgânico**: sessões orgânicas × CPC médio = economia de mídia paga. Quantifique.

6. **Content gap analysis**: baseado nas keywords, quais temas o público busca que a Syngenta não cobre?
{bloco_analise_seo_csv}
**REGRAS:** Não invente dados. Prosa corrida. Tom técnico. Português do Brasil. Se dados de CSVs foram fornecidos, OBRIGATORIAMENTE analise-os e extraia insights — não os ignore.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_aprendizados(cenario_atual, destaques, midias_pagas, social, seo, dados_metrica_performance, dados_custos, dados_seo, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 6/7: Aprendizados — diagnóstico de eficiência, red flags, oportunidades."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção APRENDIZADOS do relatório executivo mensal da Syngenta. Esta é a SEXTA de 7 etapas. Consolide tudo que foi analisado em insights acionáveis.

**ETAPAS ANTERIORES:**

Cenário Atual:
{cenario_atual}

Destaques:
{destaques}

Mídias Pagas:
{midias_pagas}

Social:
{social}

SEO:
{seo}

---

**DADOS COMPLEMENTARES:**
Cliques: {dados_metrica_performance.get('cli_atual', 0):,} | Engajamentos: {dados_metrica_performance.get('eng_atual', 0):,} | Sessões: {dados_metrica_performance.get('sess_atual', 0):,}
CPC: R$ {dados_custos.get('cpc_atual', 0):.2f} (MoM: {dados_custos.get('var_cpc_mes', 0):+.1f}%) | CPM: R$ {dados_custos.get('cpm_atual', 0):.2f} (MoM: {dados_custos.get('var_cpm_mes', 0):+.1f}%) | CPE: R$ {dados_custos.get('cpe_atual', 0):.2f} (MoM: {dados_custos.get('var_cpe_mes', 0):+.1f}%) | CPV: R$ {dados_custos.get('cpv_atual', 0):.2f} (MoM: {dados_custos.get('var_cpv_mes', 0):+.1f}%)
Orgânico: {dados_seo.get('vis_org_atual', 0):,} visualizações

---

Cubra em sequência narrativa:

1. **Diagnóstico de eficiência operacional**:
   - Score de Saúde Digital (1-10) com critérios explícitos (base 5, +2 se custos otimizando, +2 se Efeito Tesoura, +1 orgânico crescendo, +1 funil sem gargalos, e inversos)
   - Classifique cada custo (CPC/CPM/CPE/CPV) como OTIMIZANDO, ESTÁVEL ou INFLACIONANDO
   - Economia real calculada em reais para cada custo que caiu
   - Efeito Tesoura: confirme ou negue, quantifique

2. **Red flags e pontos de atenção**: para cada alerta identificado nas etapas anteriores, construa ficha com: SINAL, EVIDÊNCIA CRUZADA, CAUSA PROVÁVEL, IMPACTO QUANTIFICADO, AÇÃO RECOMENDADA, URGÊNCIA (CRÍTICA/ALTA/MÉDIA/BAIXA). Se operação saudável, documente por quê.

3. **Mapa de oportunidades**: 3-5 oportunidades ordenadas por impacto/esforço:
   - QUICK WINS (alto impacto, baixo esforço, até 7 dias)
   - MOVIMENTOS TÁTICOS (alto impacto, médio esforço, 2-4 semanas)
   - APOSTAS ESTRATÉGICAS (alto impacto, alto esforço, longo prazo)
   Para cada: evidência nos dados, potencial quantificado, ação específica.

**REGRAS:** Não invente dados. NÃO repita o que já foi dito — sintetize e avance. Prosa corrida. Tom honesto e técnico. Português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)


def gerar_proximos_passos(cenario_atual, aprendizados, modelo_escolhido, modelo_gemini, cliente_anthropic):
    """ETAPA 7/7: Próximos Passos — plano de ação concreto."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva a seção PRÓXIMOS PASSOS do relatório executivo mensal da Syngenta. Esta é a SÉTIMA e ÚLTIMA etapa.

**CENÁRIO ATUAL (Etapa 1):**
{cenario_atual}

**APRENDIZADOS (Etapa 6):**
{aprendizados}

---

Construa um plano de ação concreto e executável:

1. **Inteligência acumulada**: 3-5 descobertas mais importantes do período. Para cada: o insight em uma frase, o dado que sustenta, a implicação para os próximos 30-90 dias.

2. **Ações imediatas (0-30 dias)**: para cada ação especifique o que fazer, área responsável (mídia, criativo, conteúdo, estratégia), prazo, KPI de sucesso. Prioridades: resolver red flags urgentes, implementar quick wins, ajustes de budget, testes A/B.

3. **Movimentos táticos (30-60 dias)**: para cada: objetivo, recurso necessário, resultado esperado com meta numérica. Prioridades: novos canais/formatos, reestruturação de campanhas, programa de conteúdo, otimização de landing pages.

4. **Visão estratégica (60-180 dias)**: para cada diretriz: a tese, evidências nos dados, investimento estimado, retorno projetado. Temas: mix de mídia ideal, meta de % orgânico, ativos digitais proprietários, posicionamento competitivo.

5. **Matriz de priorização final**: ordene TODAS as ações em sequência lógica de execução, indicando dependências e conflitos de recurso.

**REGRAS:** Não invente dados. Máxima especificidade. Tom técnico e direto. Português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic)

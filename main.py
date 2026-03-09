import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import json
from datetime import datetime
from PIL import Image
import base64
import io
from google.cloud import bigquery
from google.oauth2 import service_account
from anthropic import Anthropic

# =============================================================================
# CONFIGURAÇÃO INICIAL (DEVE SER A PRIMEIRA COISA DO SCRIPT)
# =============================================================================

st.set_page_config(layout="wide", page_title="Agente de Relatoria Executiva Macfor")


# Inicialização do estado da sessão para evitar KeyError/AttributeError
chaves_sessao = [
    'relatorio_gerado', 'descricoes_imagens', 'descricoes_imagens_mes_passado',
    'descricoes_conc_atual', 'descricoes_conc_passado',
    'dados_processados', 'contexto_atual', 'destaques', 'analise_criativos',
    'analise_midias_pagas', 'analise_seo', 'proximos_passos'
]

for chave in chaves_sessao:
    if chave not in st.session_state:
        if chave == 'relatorio_gerado':
            st.session_state[chave] = False
        elif chave in ['descricoes_imagens', 'descricoes_imagens_mes_passado', 'descricoes_conc_atual', 'descricoes_conc_passado', 'dados_processados']:
            st.session_state[chave] = [] if 'descricoes' in chave else {}
        else:
            st.session_state[chave] = ""

# =============================================================================
# CONEXÃO BIGQUERY
# =============================================================================

@st.cache_resource
def get_bigquery_client():
    try:
        service_account_info = None
        
        # 1. Tenta via Streamlit Secrets
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            service_account_info = dict(st.secrets["gcp_service_account"])
            if isinstance(service_account_info.get("private_key"), str):
                service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")
        
        # 2. Tenta via Variáveis de Ambiente
        elif all(key in os.environ for key in ['project_id', 'private_key', 'client_email']):
            service_account_info = {
                "type": "service_account",
                "project_id": os.environ['project_id'],
                "private_key": os.environ['private_key'].replace('\\n', '\n'),
                "client_email": os.environ['client_email'],
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        
        if not service_account_info:
            return None
        
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return bigquery.Client(credentials=credentials, project=service_account_info["project_id"])
    
    except Exception as e:
        st.error(f"Erro na conexao BigQuery: {str(e)}")
        return None

client_bq = get_bigquery_client()
def check_datasources():
    query_check = """
    SELECT DISTINCT datasource 
    FROM `macfor-media-flow.ads.app_view_campaigns`
    WHERE UPPER(account_name) LIKE '%SYNGENTA%'
    """
    try:
        df_sources = client_bq.query(query_check).to_dataframe()
        print("\n" + "="*30)
        print("FONTES ENCONTRADAS (datasource):")
        print(df_sources['datasource'].tolist())
        print("="*30 + "\n")
    except Exception as e:
        print(f"Erro ao verificar fontes: {e}")

# Chame a função para ver no terminal
check_datasources()

def fetch_bigquery_data():
    if client_bq is None:
        st.error("Conexão com BigQuery não disponível.")
        return None
    
    query_expandida = """
    SELECT 
        -- 
        -- INVESTIMENTO POR FONTE (FACEBOOK)
        SUM(CASE WHEN datasource = 'facebook' AND DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_fb_atual,
        SUM(CASE WHEN datasource = 'facebook' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_fb_mes,
        SUM(CASE WHEN datasource = 'facebook' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN spend ELSE 0 END) as spend_fb_ano,

        -- INVESTIMENTO POR FONTE (GOOGLE ADS)
        SUM(CASE WHEN datasource = 'google_ads' AND DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_google_atual,
        SUM(CASE WHEN datasource = 'google_ads' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_google_mes,
        SUM(CASE WHEN datasource = 'google_ads' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN spend ELSE 0 END) as spend_google_ano,

        -- INVESTIMENTO POR FONTE (TIKTOK)
        SUM(CASE WHEN datasource = 'tiktok' AND DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_tiktok_atual,
        SUM(CASE WHEN datasource = 'tiktok' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_tiktok_mes,
        SUM(CASE WHEN datasource = 'tiktok' AND DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN spend ELSE 0 END) as spend_tiktok_ano,


        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN spend ELSE 0 END) as spend_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN spend ELSE 0 END) as spend_ano,
        
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN clicks ELSE 0 END) as cli_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN clicks ELSE 0 END) as cli_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN clicks ELSE 0 END) as cli_ano,

        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN actions_page_engagement ELSE 0 END) as eng_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN actions_page_engagement ELSE 0 END) as eng_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN actions_page_engagement ELSE 0 END) as eng_ano,

        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN impressions ELSE 0 END) as imp_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN impressions ELSE 0 END) as imp_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN impressions ELSE 0 END) as imp_ano,

        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN sessions ELSE 0 END) as sess_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN sessions ELSE 0 END) as sess_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN sessions ELSE 0 END) as sess_ano,

        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN reach ELSE 0 END) as reach_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN reach ELSE 0 END) as reach_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN reach ELSE 0 END) as reach_ano,

        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay ELSE 0 END) as vtp_atual,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay ELSE 0 END) as vtp_mes,
        SUM(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN video_thruplay ELSE 0 END) as vtp_ano,

        -- AVGs
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN ctr ELSE NULL END) as ctr_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN ctr ELSE NULL END) as ctr_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN ctr ELSE NULL END) as ctr_ano,

        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cpc ELSE NULL END) as cpc_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cpc ELSE NULL END) as cpc_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN cpc ELSE NULL END) as cpc_ano,

        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cpm ELSE NULL END) as cpm_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cpm ELSE NULL END) as cpm_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN cpm ELSE NULL END) as cpm_ano,

        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN avg_session_duration ELSE NULL END) as dur_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN avg_session_duration ELSE NULL END) as dur_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN avg_session_duration ELSE NULL END) as dur_ano,

        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay_rate ELSE NULL END) as vtpr_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay_rate ELSE NULL END) as vtpr_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN video_thruplay_rate ELSE NULL END) as vtpr_ano,

        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay_cpv ELSE NULL END) as vcpv_atual,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH) AND DATE(date) < DATE_TRUNC(CURRENT_DATE(), MONTH) THEN video_thruplay_cpv ELSE NULL END) as vcpv_mes,
        AVG(CASE WHEN DATE(date) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH) AND DATE(date) < DATE_ADD(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH), INTERVAL 1 MONTH) THEN video_thruplay_cpv ELSE NULL END) as vcpv_ano
        
    FROM `macfor-media-flow.ads.app_view_campaigns`
    WHERE UPPER(account_name) LIKE '%SYNGENTA%'
    """
    
    try:
        df = client_bq.query(query_expandida).to_dataframe()
        if not df.empty:
            dados_dict = df.iloc[0].to_dict()
            
            # --- IMPRESSÃO NO TERMINAL (LOG) ---
            print("\n" + "="*60)
            print(f"DADOS RECUPERADOS DO BIGQUERY - {datetime.now().strftime('%H:%M:%S')}")
            print("="*60)
            for chave, valor in dados_dict.items():
                # Formata a exibição: se for número, limita casas decimais
                display_val = f"{valor:,.2f}" if isinstance(valor, (float, int)) else valor
                print(f"{chave.ljust(30)}: {display_val}")
            print("="*60 + "\n")
            
            return dados_dict
        return None
    except Exception as e:
        st.error(f"Erro na query: {str(e)}")
        return None

    




# =============================================================================
# INICIALIZAÇÃO DOS MODELOS
# =============================================================================

# Gemini (sempre usado para visão/imagens)
gemini_api_key = os.getenv("GEM_API_KEY")
genai.configure(api_key=gemini_api_key)
modelo_gemini = genai.GenerativeModel("gemini-2.5-flash")
modelo_visao = genai.GenerativeModel("gemini-2.5-flash")

# Anthropic (opção para geração de texto)
anthropic_api_key = None
if hasattr(st, 'secrets') and 'ANTH_KEY' in st.secrets:
    anthropic_api_key = st.secrets["ANTH_KEY"]
elif os.getenv("ANTH_KEY"):
    anthropic_api_key = os.getenv("ANTH_KEY")

cliente_anthropic = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

def gerar_texto(prompt):
    """Gera texto usando Anthropic Claude."""
    response = cliente_anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8096,
        system="Voce e um agente de relatoria executiva. NUNCA use emojis em nenhuma parte da resposta. Mantenha tom profissional e analitico.",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Estado da sessão para os cliques (Sincroniza com o BigQuery)
if 'bq_cliques' not in st.session_state:
    st.session_state.bq_cliques = {"atual": 0, "mes_passado": 0, "ano_passado": 0}

if 'relatorio_gerado' not in st.session_state:
    st.session_state.relatorio_gerado = False

# Titulo do aplicativo
st.title("Agente de Relatoria Executiva Macfor")
st.markdown("*Dados brutos entram, inteligencia de mercado sai. Devolutiva estrategica automatizada.*")
st.markdown("---")


# Função para descrever imagem (sempre usa Gemini - visão)
def descrever_imagem(imagem):
    try:
        response = modelo_visao.generate_content([
            """Analise este criativo de marketing digital com foco em INTELIGÊNCIA DE NEGÓCIO.
Descreva em até 150 palavras:
1. ELEMENTOS VISUAIS: cores, composição, imagens, texto sobreposto
2. MENSAGEM CENTRAL: o que está sendo comunicado e para qual público
3. ESTRATÉGIA CRIATIVA: qual técnica de persuasão está sendo usada (urgência, autoridade, identificação, prova social, etc.)
4. POTENCIAL DE PERFORMANCE: elementos que podem impactar positiva ou negativamente cliques, engajamento e conversão
5. DIFERENCIAÇÃO: o que torna este criativo único vs. padrões do mercado""",
            imagem
        ])
        return response.text
    except Exception as e:
        return f"Erro ao descrever imagem: {str(e)}"

# Função para calcular variações
def calcular_variacao(atual, anterior):
    if anterior and anterior != 0:
        return ((atual - anterior) / anterior) * 100
    return 0

#GERAÇÃO DE CONTEXTO ATUAL
#ADICIONE A COMPARAÇÃO DO ANO PASSADO E FAZER TODAS ANALISES CONSIDERANDO AS METRICAS DE PERFOMANCE PARA ALCANÇAR OS INDICADORES DE PERFORMANCE KPI OK
#FAZER O COMPARATIVO ENTRE A CONCORRENCIA E SHARE DE BUSCA OK
#COLOCAR DO INSTAGRAM, O AUMENTO DE SEGUIRDOR, SHARE DE CRESCIMENTO, VOLUME DE PUBLICAÇÃO
#COLOCAR O CRESCIMENTO EM CADA PLATAFORMA E POST DESTAQUE
#COLOCAR SNETIMENTO DO PUBLICO E PRINCIPAIS TÓPICOS

def gerar_yoy_para_contexto(dados_metrica_performance, descricoes_imagens):
    prompt = f"""
    Você é um analista de inteligência de mercado sênior, responsável por extrair insights de negócio a partir de dados de performance digital.
    Este documento é uma devolutiva estratégica para o cliente que contratou nosso serviço de marketing digital.
    Sua missão é transformar variações numéricas em inteligência de mercado acionável — o cliente precisa entender não apenas O QUE mudou, mas POR QUE mudou e O QUE ISSO SIGNIFICA para o negócio dele.

    Compare o desempenho ATUAL (2026) com o MESMO MÊS DO ANO PASSADO (2025) e extraia inteligência competitiva.

    **TABELA DE VARIAÇÕES YoY (Ano sobre Ano):**
    - Investimento: {dados_metrica_performance.get('var_invest_ano', 0):+.1f}%
    - Sessões no Site: {dados_metrica_performance.get('var_sess_ano', 0):+.1f}%
    - Alcance (Reach): {dados_metrica_performance.get('var_reach_ano', 0):+.1f}%
    - Video Thruplays: {dados_metrica_performance.get('var_vtp_ano', 0):+.1f}%
    - Visualizações: {dados_metrica_performance.get('var_vis_ano', 0):+.1f}%
    - Impressões: {dados_metrica_performance.get('var_imp_ano', 0):+.1f}%
    - Cliques: {dados_metrica_performance.get('var_cliques_ano', 0):+.1f}%
    - Engajamentos: {dados_metrica_performance.get('var_eng_ano', 0):+.1f}%
    - CTR (%): {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}%

    **INSTRUÇÃO DE INTELIGÊNCIA DE MERCADO:**
    Extraia insights de negócio a partir das correlações entre métricas. Exemplos:
    - Se o investimento subiu 10% mas os cliques subiram 30%, comunique ao cliente que a estratégia está gerando retorno acelerado — cada real investido rende mais resultado.
    - Se o alcance caiu mas as sessões subiram, interprete como melhoria na qualificação do público — estamos alcançando menos pessoas, mas as certas.
    - Identifique sinais de maturidade digital, saturação de canal ou oportunidades de reposicionamento.
    - Relacione as variações com possíveis movimentos de mercado (sazonalidade, concorrência, comportamento do consumidor).
    Considere também as descrições dos criativos: {chr(10).join(descricoes_imagens)}
    """
    return gerar_texto(prompt)

def gerar_analise_concorrencia(dados_metrica_performance, info_concorrentes, descricoes_conc_atual=None, descricoes_conc_passado=None):
    prompt = f"""
    Você é um estrategista de inteligência competitiva. Este documento é uma devolutiva para o cliente que contratou nosso serviço de marketing digital.
    Sua missão é extrair inteligência de mercado que ajude o cliente a entender seu posicionamento competitivo e tomar decisões estratégicas de negócio.

    **Dados de Performance da Nossa Marca (Atual):**
    - Investimento: R$ {dados_metrica_performance.get('investimento_total_atual', 0):,.2f}
    - Alcance: {dados_metrica_performance.get('reach_atual', 0)}
    - Impressões: {dados_metrica_performance.get('impressoes_atual', 0)}
    - CTR: {dados_metrica_performance.get('ctr_atual', 0):.2f}%
    - Cliques: {dados_metrica_performance.get('cliques_atual', 0)}

    **Informacoes sobre a Concorrencia (Reportado pelo usuario):**
    {info_concorrentes if info_concorrentes else "Nenhuma informacao especifica fornecida sobre os movimentos dos concorrentes."}

    **Criativos dos Concorrentes (Mes Atual):**
    {chr(10).join(descricoes_conc_atual) if descricoes_conc_atual else "Nenhum criativo de concorrente fornecido para o mes atual."}

    **Criativos dos Concorrentes (Mes Passado):**
    {chr(10).join(descricoes_conc_passado) if descricoes_conc_passado else "Nenhum criativo de concorrente fornecido para o mes passado."}

    **DIRETRIZES DE INTELIGENCIA COMPETITIVA:**
    1. Traduza os dados em posicionamento de mercado: onde o cliente está forte e onde há vulnerabilidades.
    2. Identifique oportunidades de diferenciação estratégica (ex: se o concorrente foca em preço, demonstre como a estratégia de autoridade/qualidade gera vantagem competitiva sustentável).
    3. Aponte movimentos de mercado que representem ameaças ou janelas de oportunidade para o negócio do cliente.
    4. Não repita informações. Foque em inteligência acionável que gere valor para a tomada de decisão do cliente.

    Seja analítico, profissional e focado em gerar inteligência de negócio para o cliente.
    CASO NÃO TENHA INFORMAÇÃO, NÃO INVENTE, APENAS DIGA QUE NÃO HÁ DADOS SUFICIENTES PARA ANALISAR A CONCORRÊNCIA.
    """
    return gerar_texto(prompt)

def gerar_contexto_atual(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, analise_yoy, analise_concorrencia):
    prompt = f"""
    Você é um Diretor de Estratégia e Inteligência de Mercado. Este documento é uma devolutiva estratégica para o cliente que contratou nosso serviço de marketing digital.
    Seu objetivo é extrair inteligência de negócio dos dados brutos, transformando números em visão estratégica que demonstre ao cliente o valor gerado pela operação de marketing digital.
    A seção "CONTEXTO ATUAL" deve abrir o relatório com uma leitura de mercado que posicione o cliente sobre o cenário competitivo, a eficiência do investimento e as oportunidades identificadas.

    ### 1. ORIENTAÇÃO PARA EXTRAÇÃO DE INTELIGÊNCIA (O QUE EXPOR):
    Para cada página do slide, você deve filtrar os dados seguindo estes critérios de inteligência de negócio:

    - **Priorize Variações Significativas:** Se uma métrica variou mais de 10% (YoY), ela deve ser o destaque. Se ficou estável, mencione apenas como "manutenção de eficiência".
    - **Correlação Obrigatória:** Nunca apresente um custo (CPC/CPM) sem correlacioná-lo à causa (Concorrência ou Qualidade do Criativo). O cliente precisa entender a dinâmica de mercado por trás do número.
    - **Foco em ROI e Valor Gerado:** Selecione os dados que demonstrem ao cliente como o investimento se traduziu em resultados de negócio — não apenas métricas, mas impacto real em visibilidade, autoridade e geração de demanda.
    - **Destaque Criativo:** Selecione apenas as descrições de imagens que justificam o CTR atual. Se o CTR subiu, identifique qual elemento visual nos criativos foi o provável responsável.

    ### DADOS DISPONÍVEIS PARA CURADORIA:
    **1. ANÁLISE DE PERFORMANCE (Histórico YoY):**
    {analise_yoy}
    **2. CENÁRIO DE MERCADO (Concorrência):**
    {analise_concorrencia}
    **3. INDICADORES DE INVESTIMENTO:**
    - Total Investido: R$ {dados_investimentos.get('total_atual', 0):,.2f} (Var. YoY: {dados_investimentos.get('var_total_ano', 0):+.1f}%)
    - Google Ads: R$ {dados_investimentos.get('google_atual', 0):,.2f}
    - Meta (FB+IG): R$ {dados_investimentos.get('fb_atual', 0) + dados_investimentos.get('ig_atual', 0):,.2f}
    - TikTok: R$ {dados_investimentos.get('tt_atual', 0):,.2f}
    **4. INDICADORES DE CUSTO E EFICIÊNCIA:**
    - CPC Atual: R$ {dados_custos.get('cpc_atual', 0):.2f} (Variação YoY: {dados_custos.get('var_cpc_ano', 0):+.1f}%)
    - CPM Atual: R$ {dados_custos.get('cpm_atual', 0):.2f}
    - CTR Atual: {dados_metrica_performance.get('ctr_atual', 0):.2f}%
    **5. ALCANCE E ENGAJAMENTO:**
    - Alcance Total: {dados_metrica_performance.get('reach_atual', 0):,.0f}
    - Cliques Totais: {dados_metrica_performance.get('cliques_atual', 0):,.0f}
    **Descrições dos Criativos Utilizados:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhuma imagem fornecida"}

    ### FORMATO DA RESPOSTA ESPERADA:

    **PARTE 1: INTELIGÊNCIA DE MERCADO (POR PILAR)**
    Não repita informações, detalhe tudo mas seja objetivo para que não fique extenso.
    Para cada pilar, extraia a inteligência de negócio que o cliente precisa para tomar decisões:
    - **Saúde Financeira:** Qual o retorno real do investimento? O cliente está pagando mais ou menos por resultado? O que isso revela sobre o mercado?
    - **Pressão de Mercado:** O que os movimentos de custo e concorrência revelam sobre o cenário competitivo? Há sinais de saturação ou oportunidade?
    - **Alavancagem Criativa:** Os criativos estão gerando diferenciação competitiva? Qual é o impacto mensurável da estratégia de conteúdo nos resultados de negócio?

    **PARTE 2: SUGESTÃO DE PAUTAS PARA OS SLIDES**
    Com base na inteligência extraída acima, defina o que DEVE constar em cada página dos slides para apresentação ao cliente, priorizando os insights de maior valor estratégico para o negócio.
    Em situações onde houver uma redução significativa de Investimento (YoY ou MoM) acompanhada pela manutenção ou crescimento de métricas de engajamento (Cliques ou CTR), você deve sugerir a criação de um "Gráfico de Efeito Tesoura"
    """

    return gerar_texto(prompt)



# DESTAQUES
#FALAR SOBRE OS CRIATIVOS E AS CAMPANHAS
#COLOCAR AS CAMPANHAS QUE TIVERAM MELHOR DESEMPENHO NO BANCO
#IDENTIFICAR OS PRODUROS QUE TIVERAM MELHOR DESEMPENHO NO BANCO
#EFICACIA DE INVESTIMENTO EM CADA CULTURA OU PRODUTO
def gerar_destaques(dados_metrica_performance, contexto_atual):
    prompt = f"""
    Você é um especialista em inteligência de negócio aplicada a marketing digital. Este documento é uma devolutiva para o cliente que contratou nosso serviço.
    Com base no contexto e nos dados de desempenho, extraia 3-5 DESTAQUES que representem as principais descobertas de inteligência de mercado do período.
    Cada destaque deve ser uma conclusão de negócio — não um dado isolado, mas um insight estratégico que demonstre o valor gerado e oriente decisões do cliente.

    **Contexto Atual:**
    {contexto_atual}

    **Dados Comparativos:**
    - Visualizações: Atual {dados_metrica_performance.get('visualizacoes_atual', 0)} | Mês Passado {dados_metrica_performance.get('visualizacoes_mes_passado', 0)} | Variação: {dados_metrica_performance.get('var_visualizacoes_mes', 0):.1f}%
    - Impressões: Atual {dados_metrica_performance.get('impressoes_atual', 0)} | Mês Passado {dados_metrica_performance.get('impressoes_mes_passado', 0)} | Variação: {dados_metrica_performance.get('var_impressoes_mes', 0):.1f}%
    - Cliques: Atual {dados_metrica_performance.get('cliques_atual', 0)} | Mês Passado {dados_metrica_performance.get('cliques_mes_passado', 0)} | Variação: {dados_metrica_performance.get('var_cliques_mes', 0):.1f}%
    - Engajamentos: Atual {dados_metrica_performance.get('engajamentos_atual', 0)} | Mês Passado {dados_metrica_performance.get('engajamentos_mes_passado', 0)} | Variação: {dados_metrica_performance.get('var_engajamentos_mes', 0):.1f}%


    **INFO DE PRODUTO/CRIATIVO:**
    {descricoes_imagens if descricoes_imagens else "INFORMAÇÃO NÃO DISPONÍVEL"}
    **DIRETRIZES DE INTELIGÊNCIA DE NEGÓCIO PARA OS DESTAQUES:**
    1. **Filtro de Relevância:** Se uma métrica caiu devido ao corte de verba (citado no contexto), mas a eficiência (CTR/CPC) subiu, o destaque DEVE ser a eficiência — comunique ao cliente que o investimento está rendendo mais.
    2. **Ausência de Dados:** Caso a seção "INFO DE PRODUTO/CRIATIVO" esteja como não disponível, você deve incluir uma observação no destaque: "[INSERIR DETALHES DO POST/PRODUTO CAMPEÃO]" para que o usuário saiba onde completar.
    3. **Ação de Efeito Tesoura:** Se o investimento caiu e o resultado subiu/manteve, crie um destaque chamado "Descolamento de Performance (Efeito Tesoura)" — este é um insight de alto valor que demonstra maturidade da estratégia.
    4. **Tom de Voz:** Consultivo, direto, focado em inteligência de mercado, ROI e valor gerado para o negócio do cliente.

    ### FORMATO DA RESPOSTA ESPERADA:
    **PARTE 1: CRIE UM TEXTO ABORDANDO OS DESTAQUES**
    Não repita informações, detalhe tudo mas seja objetivo para que não fique extenso

    **PARTE 2: SUGESTÃO DE PAUTAS PARA OS SLIDES**
    Com base na inteligência extraída acima, defina o que DEVE constar em cada página dos slides para apresentação ao cliente — priorizando os insights de maior impacto para o negócio.
    Se os dados de Criativos faltarem: Indicar placeholder: "[Inserir miniatura do post de maior CTR para análise visual]"

"""

    return gerar_texto(prompt)

def gerar_analise_criativos(dados_custos, descricoes_imagens, descricoes_imagens_mes_passado, destaques, descricoes_conc_atual=None, descricoes_conc_passado=None):
    prompt = f"""
    Você é um especialista em inteligência criativa para marketing digital. Este documento é uma devolutiva para o cliente que contratou nosso serviço.
    Com base nos DESTAQUES e nas descrições dos criativos, extraia inteligência de negócio sobre a performance dos CRIATIVOS.
    A análise deve ir além da descrição — deve revelar ao cliente POR QUE determinados criativos funcionaram, O QUE isso indica sobre o comportamento do público-alvo e COMO essa inteligência pode ser capitalizada nas próximas campanhas.

    **Destaques do Período:**
    {destaques}
    
    **Descrições dos Criativos (Mês Atual):**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhuma imagem fornecida"}

    **Descrições dos Criativos (Mês Passado):**
    {chr(10).join(descricoes_imagens_mes_passado) if descricoes_imagens_mes_passado else "Nenhuma imagem do mês passado fornecida"}

    **Criativos dos Concorrentes (Mes Atual):**
    {chr(10).join(descricoes_conc_atual) if descricoes_conc_atual else "Nenhum criativo de concorrente fornecido para o mes atual."}

    **Criativos dos Concorrentes (Mes Passado):**
    {chr(10).join(descricoes_conc_passado) if descricoes_conc_passado else "Nenhum criativo de concorrente fornecido para o mes passado."}

    **INSTRUCAO DE COMPARACAO CRIATIVA:**
    Se houver criativos do mes atual E do mes passado, compare a evolucao da estrategia criativa.
    Identifique: mudanças de abordagem, elementos que foram mantidos (e por quê funcionam), e o que a transição criativa revela sobre o aprendizado da campanha.
    Correlacione as mudanças criativas com as variações de performance (cliques, engajamento, CTR) para demonstrar causa e efeito ao cliente.

    **Métricas de Performance (Período Atual):**
    - Visualizações: {dados_metrica_performance.get('vis_atual', 0)}
    - Impressões: {dados_metrica_performance.get('imp_atual', 0)}
    - Cliques: {dados_metrica_performance.get('cli_atual', 0)}
    - Engajamentos: {dados_metrica_performance.get('eng_atual', 0)}

    **Métricas de Criativos:**
    - Custo por Engajamento: R$ {dados_custos.get('cpe_atual', 0):.2f}
    - Custo por Clique: R$ {dados_custos.get('cpc_atual', 0):.2f}

    DIRETRIZES DE INTELIGÊNCIA CRIATIVA

1. CONTEXTO E CONCEITO CRIATIVO
Identifique a estratégia narrativa por trás dos conteúdos e explique ao cliente O QUE essa escolha revela sobre o posicionamento da marca no mercado.
Analise elementos como:

- storytelling e metáforas visuais
- regionalização e identificação com o público
- humor, influenciadores ou elementos sonoros

Extraia inteligência: por que esses elementos ressoam com o público-alvo e como isso se traduz em vantagem competitiva para o negócio.

---

2. ESTRATÉGIA DE CONTEÚDO
Analise como os criativos se encaixam na estratégia de negócio do cliente:

- geração de awareness e construção de marca
- estímulo ao engajamento e criação de comunidade
- geração de tráfego qualificado e demanda
- construção de autoridade no segmento

Traduza para o cliente como cada formato contribui para seus objetivos de negócio.

---

3. RELAÇÃO COM PERFORMANCE (INTELIGÊNCIA DE ROI)
Correlacione CPE e CPC com a qualidade dos criativos para demonstrar ao cliente o retorno do investimento criativo.

Extraia insights de negócio como:

- quais elementos criativos reduziram custos de aquisição
- quais formatos geraram maior eficiência por real investido
- como a estratégia criativa está protegendo o cliente da inflação de mídia

---

4. FORMATOS E DISTRIBUIÇÃO
Analise a performance por plataforma (Reels, TikTok, YouTube, feed) e extraia inteligência sobre onde o público do cliente está mais receptivo.

Insights esperados:

- quais plataformas geram maior retorno para o perfil de público do cliente
- quais formatos indicam tendências de comportamento do consumidor
- oportunidades de redistribuição baseadas em performance

---

FORMATO DA RESPOSTA

PARTE 1 — INTELIGÊNCIA CRIATIVA
Escreva um texto analítico e consultivo, focado em inteligência de negócio extraída da performance criativa.

O texto deve ter tom de devolutiva estratégica para o cliente:
consultivo, orientado a decisão e sem repetições.

---

PARTE 2 — SUGESTÃO DE PAUTAS PARA OS SLIDES

Com base na inteligência extraída, proponha a estrutura ideal para slides de apresentação ao cliente, priorizando os insights de maior valor para o negócio.

Exemplo de estrutura:

Slide 1 — Contexto criativo e posicionamento da campanha
Slide 2 — Principais criativos e inteligência de engajamento
Slide 3 — ROI criativo: relação entre conceito e eficiência
Slide 4 — Insights de mercado e recomendações estratégicas

Se faltarem dados de criativos, indicar placeholder:

"[Inserir miniatura do criativo com maior engajamento para análise visual]"
    """

    
    return gerar_texto(prompt)

#MIDIAS PAGAS 
#USAR O GOOGLE TRENDS PARA Volume de buscas
#COLOCAR REGIONALIZAÇÃR

def gerar_analise_midias_pagas(dados_investimentos, dados_custos, analise_criativos):
    prompt = f"""
    Você é um Diretor de Mídia e Inteligência de Mercado focado em performance e branding para o setor agro.
    Este documento é uma devolutiva estratégica para o cliente que contratou nosso serviço de marketing digital.
    Com base na análise de criativos e nos dados de investimento, extraia inteligência de negócio para a seção de 'MÍDIAS PAGAS' — o cliente precisa entender não apenas os números, mas o que eles revelam sobre o mercado, a eficiência da estratégia e as oportunidades de crescimento.

    DIRETRIZES DE INTELIGÊNCIA DE MERCADO:
    1. EFICIÊNCIA E ROI: Demonstre ao cliente se cada real investido está rendendo mais ou menos resultado. Correlacione crescimento de métricas vs. investimento para revelar ganhos de eficiência.
    2. INTELIGÊNCIA DE CANAL: Analise o papel estratégico de cada ecossistema (YouTube/TikTok para visibilidade, Google Ads/PMax para conversão) e o que a performance de cada canal revela sobre o comportamento do público-alvo do cliente.
    3. POSICIONAMENTO COMPETITIVO: Demonstre como a distribuição de mídia está posicionando a marca do cliente em relação à concorrência.


    **Análise de Criativos Anterior:**
    {analise_criativos}
    
    **Dados de Investimento (Período Atual):**
    - Social (FB/IG): R$ {dados_investimentos.get('fb_atual', 0) + dados_investimentos.get('ig_atual', 0):,.2f}
    - TikTok: R$ {dados_investimentos.get('tt_atual', 0):,.2f}
    - Google Ads (Search/PMax): R$ {dados_investimentos.get('google_atual', 0) + dados_investimentos.get('pmax_atual', 0):,.2f}
    - YouTube: R$ {dados_investimentos.get('yt_atual', 0):,.2f}
    
    **Métricas de Eficiência:**
    - CPM: R$ {dados_custos.get('cpm_atual', 0):.2f} | CPC: R$ {dados_custos.get('cpc_atual', 0):.2f} | CPE: R$ {dados_custos.get('cpe_atual', 0):.2f}

    ESTRUTURA DA RESPOSTA:
    - Panorama de Eficiência e ROI (Conectar investimento vs. resultados de negócio).
    - Inteligência por Ecossistema (Meta, Google, TikTok — o que cada canal revela sobre o mercado).
    - Estratégia de Geolocalização e Formatos (Push, Programática, etc).
    - INSIGHTS DE INTELIGÊNCIA DE MERCADO (tendências, oportunidades e riscos identificados).


    ### FORMATO DA RESPOSTA ESPERADA

    **PARTE 1: INTELIGÊNCIA DE MÍDIA PAGA**

    Escreva um texto analítico e consultivo para a seção **MÍDIAS PAGAS** do relatório executivo.
    O foco é inteligência de negócio: o que os dados revelam sobre o mercado, o público e as oportunidades para o cliente.
    Não repita informações e mantenha objetividade, mesmo detalhando a análise.

    -----------------------------------------------------

    **PARTE 2: SUGESTÃO DE PAUTAS PARA OS SLIDES**

    Com base na inteligência extraída acima, defina o que **DEVE constar em cada slide da apresentação ao cliente**, priorizando insights de valor para o negócio.

    Estruture os slides de forma clara e estratégica.

    Exemplo de estrutura:

    Slide 1 – Panorama de Mídia Paga e ROI
    - inteligência de eficiência: retorno por real investido
    - destaque de ganhos estratégicos do período
    - principais descobertas de mercado

    Slide 2 – Inteligência por Canal
    - o que a performance de cada canal revela sobre o público do cliente
    - insights de redistribuição de investimento

    Slide 3 – Eficiência de Custos e Competitividade
    - análise de CPM, CPC e CPE vs. benchmarks de mercado
    - interpretação do posicionamento competitivo

    Slide 4 – Insights de Mercado
    - tendências identificadas no comportamento do público
    - oportunidades e riscos para o próximo período

    Slide 5 – Recomendações Estratégicas
    - otimizações de mídia baseadas em inteligência de dados
    - ajustes de investimento orientados por ROI
    - próximos testes de canais ou formatos

    Se dados ou exemplos de criativos não estiverem disponíveis, indique com placeholder.
    """
    
    return gerar_texto(prompt)

def gerar_analise_seo(dados_seo, analise_midias_pagas):
    prompt = f"""
    Você é um especialista em inteligência de conteúdo e SEO. Este documento é uma devolutiva estratégica para o cliente que contratou nosso serviço de marketing digital.
    Com base na análise de mídias pagas e nos dados de SEO abaixo, extraia inteligência de mercado sobre o posicionamento orgânico do cliente.
    O cliente precisa entender como o conteúdo e o SEO estão construindo ativos digitais de longo prazo para o negócio — diferente da mídia paga, o orgânico representa valor acumulado e autoridade de marca.

    **Análise de Mídias Pagas:**
    {analise_midias_pagas}

    **Métricas SEO (Atual | Mês Passado):**
    - Visualizações: {dados_seo.get('seo_visualizacoes_atual', 0)} | {dados_seo.get('seo_visualizacoes_mes_passado', 0)}
    - Sessões: {dados_seo.get('seo_sessoes_atual', 0)} | {dados_seo.get('seo_sessoes_mes_passado', 0)}
    - Usuários: {dados_seo.get('seo_usuarios_atual', 0)} | {dados_seo.get('seo_usuarios_mes_passado', 0)}
    - Visualizações Orgânicas: {dados_seo.get('seo_visualizacoes_org_atual', 0)} | {dados_seo.get('seo_visualizacoes_org_mes_passado', 0)}
    - Sessões Orgânicas: {dados_seo.get('seo_sessoes_org_atual', 0)} | {dados_seo.get('seo_sessoes_org_mes_passado', 0)}
    - Usuários Orgânicos: {dados_seo.get('seo_usuarios_org_atual', 0)} | {dados_seo.get('seo_usuarios_org_mes_passado', 0)}

    **Top 10 Palavras-chave do Mês:**
    {dados_metrica_performance.get('top_keywords', 'Nenhuma keyword fornecida')}

    ### DIRETRIZES DE INTELIGÊNCIA DE CONTEÚDO:
    - Analise as keywords como indicadores de demanda de mercado: o que o público do cliente está buscando revela intenções de compra e interesse.
    - Correlacione tráfego orgânico vs. pago para demonstrar ao cliente a construção de independência de mídia.
    - Identifique oportunidades de conteúdo baseadas em gaps de keyword e tendências de busca.
    - Demonstre o valor acumulado do SEO como ativo estratégico de longo prazo para o negócio.

    ### FORMATO DA RESPOSTA ESPERADA
    **PARTE 1: INTELIGÊNCIA DE CONTEÚDO E SEO**
    Escreva um texto analítico e consultivo para a seção **CONTENT + SEO** do relatório executivo.
    Foque em inteligência de mercado: o que os dados de busca e conteúdo revelam sobre o comportamento do consumidor e as oportunidades para o negócio do cliente.
    Não repita informações e mantenha objetividade, mesmo detalhando a análise.
 -----------------------------------------------------
    **PARTE 2: SUGESTÃO DE PAUTAS PARA OS SLIDES**
    Com base na inteligência extraída acima, defina o que **DEVE constar em cada slide da apresentação ao cliente**, priorizando insights de valor para o negócio.
    """
    return gerar_texto(prompt)

def gerar_proximos_passos(dados_metrica_performance, analise_seo):
    prompt = f"""
    Você é um consultor estratégico de inteligência de negócio. Este documento é uma devolutiva para o cliente que contratou nosso serviço de marketing digital.
    Com base em toda a inteligência acumulada nas seções anteriores, sintetize os PRÓXIMOS PASSOS E APRENDIZADOS.
    Esta seção é onde o cliente encontra o maior valor da devolutiva: recomendações concretas baseadas em inteligência de mercado, não apenas em dados.

    **Análise de SEO:**
    {analise_seo}

    **Informações de Concorrentes:**
    {dados_metrica_performance.get('info_concorrentes', 'Nenhuma informação')}

    **Performance Geral:**
    - Variação Visualizações (vs mês passado): {dados_metrica_performance.get('var_visualizacoes_mes', 0):.1f}%
    - Variação Visualizações (vs ano passado): {dados_metrica_performance.get('var_visualizacoes_ano', 0):.1f}%
    ### DIRETRIZES DE INTELIGÊNCIA ESTRATÉGICA

    Extraia inteligência de negócio considerando:

    - o que as tendências de crescimento/retração revelam sobre o mercado do cliente
    - como o posicionamento competitivo deve evoluir nos próximos meses
    - qual o equilíbrio ideal entre mídia paga e orgânico para maximizar ROI
    - quais oportunidades de mercado foram identificadas e como capturá-las
    - riscos de mercado que exigem ação preventiva

    ### FORMATO DA RESPOSTA ESPERADA
    **PARTE 1: INTELIGÊNCIA ESTRATÉGICA**
    Escreva um texto analítico e consultivo para a seção **APRENDIZADOS E PRÓXIMOS PASSOS** do relatório executivo.
    Deve haver 3 subseções:
    INTELIGÊNCIA DO PERÍODO (o que os dados revelaram sobre o mercado e o negócio)
    PRÓXIMOS MOVIMENTOS ESTRATÉGICOS (recomendações baseadas em inteligência de mercado)
    PRÓXIMOS PASSOS OPERACIONAIS (ações concretas para capturar as oportunidades identificadas)

    Não repita informações e mantenha objetividade, mesmo detalhando a análise.
    --------------------------------------------------
    **PARTE 2: SUGESTÃO DE PAUTAS PARA OS SLIDES**
    Com base na inteligência extraída acima, defina o que **DEVE constar em cada slide da apresentação ao cliente**, priorizando recomendações de alto valor estratégico para o negócio.

    """
    return gerar_texto(prompt)
    
if st.button("Atualizar Dados (Syngenta)"):
    with st.spinner("Buscando dados históricos no BigQuery..."):
        res = fetch_bigquery_data()
    
        if res:
            # Investimento (Spend)
            st.session_state.spend_atual = float(res.get('spend_atual') or 0.0)
            st.session_state.spend_mes = float(res.get('spend_mes') or 0.0)
            st.session_state.spend_ano = float(res.get('spend_ano') or 0.0)

            # Sessões (Sess)
            st.session_state.sess_atual = int(res.get('sess_atual') or 0)
            st.session_state.sess_mes = int(res.get('sess_mes') or 0)
            st.session_state.sess_ano = int(res.get('sess_ano') or 0)

            # Alcance (Reach)
            st.session_state.reach_atual = int(res.get('reach_atual') or 0)
            st.session_state.reach_mes = int(res.get('reach_mes') or 0)
            st.session_state.reach_ano = int(res.get('reach_ano') or 0)

            # Video Thruplays (VTP)
            st.session_state.vtp_atual = int(res.get('vtp_atual') or 0)
            st.session_state.vtp_mes = int(res.get('vtp_mes') or 0)
            st.session_state.vtp_ano = int(res.get('vtp_ano') or 0)

            # Cliques
            st.session_state.cli_atual = int(res.get('cli_atual') or 0)
            st.session_state.cli_mes = int(res.get('cli_mes') or 0)
            st.session_state.cli_ano = int(res.get('cli_ano') or 0)
            
            # Impressões
            st.session_state.imp_atual = int(res.get('imp_atual') or 0)
            st.session_state.imp_mes = int(res.get('imp_mes') or 0)
            st.session_state.imp_ano = int(res.get('imp_ano') or 0)
            
            # Engajamentos
            st.session_state.eng_atual = int(res.get('eng_atual') or 0)
            st.session_state.eng_mes = int(res.get('eng_mes') or 0)
            st.session_state.eng_ano = int(res.get('eng_ano') or 0)

            
            # Atribuindo diretamente às chaves que os st.number_input usam como 'key'
            st.session_state.cpc_atual = float(res.get('cpc_atual') or 0.0)
            st.session_state.cpc_mes = float(res.get('cpc_mes') or 0.0)
            st.session_state.cpc_ano = float(res.get('cpc_ano') or 0.0)

            st.session_state.cpm_atual = float(res.get('cpm_atual') or 0.0)
            st.session_state.cpm_mes = float(res.get('cpm_mes') or 0.0)
            st.session_state.cpm_ano = float(res.get('cpm_ano') or 0.0)

            # CTR (conforme solicitado anteriormente)
            st.session_state.ctr_atual = float(res.get('ctr_atual') or 0.0)
            st.session_state.ctr_mes = float(res.get('ctr_mes') or 0.0)
            st.session_state.ctr_ano = float(res.get('ctr_ano') or 0.0)

            # Facebook
            st.session_state.fb_atual = float(res.get('spend_fb_atual') or 0.0)
            st.session_state.fb_mes = float(res.get('spend_fb_mes') or 0.0)
            st.session_state.fb_ano = float(res.get('spend_fb_ano') or 0.0)
            
            # Google Ads (Pode mapear para seu campo de Google Ads ou somar no campo de 'Display/YT/PMax' se preferir)
            st.session_state.google_atual = float(res.get('spend_google_atual') or 0.0)
            st.session_state.google_mes = float(res.get('spend_google_mes') or 0.0)
            st.session_state.google_ano = float(res.get('spend_google_ano') or 0.0)

            # TikTok
            st.session_state.tt_atual = float(res.get('spend_tiktok_atual') or 0.0)
            st.session_state.tt_mes = float(res.get('spend_tiktok_mes') or 0.0)
            st.session_state.tt_ano = float(res.get('spend_tiktok_ano') or 0.0)


            st.success("Dados sincronizados com sucesso!")
            st.rerun()

# Formulário principal
with st.form("relatorio_form"):
    st.header("Dados do Relatorio")

    # Contexto e Destaques
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Contexto Geral")
        contexto_input = st.text_area("Contexto Atual (opcional)", height=100, placeholder="Descreva o contexto da campanha/periodo...")
        info_concorrentes = st.text_area("Informacoes de Concorrentes", height=100, placeholder="O que os concorrentes estao fazendo?")

    with col2:
        st.subheader("Upload de Criativos da Marca")
        st.markdown("**Criativos do Mes Atual**")
        imagens = st.file_uploader("Upload dos criativos atuais", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_atual")
        st.markdown("**Criativos do Mes Passado** *(para comparacao)*")
        imagens_mes_passado = st.file_uploader("Upload dos criativos do mes passado", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_mes_passado")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Criativos da Concorrencia")
        st.markdown("**Concorrencia -- Mes Atual**")
        imagens_conc_atual = st.file_uploader("Upload dos criativos de concorrentes (atual)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_conc_atual")
        st.markdown("**Concorrencia -- Mes Passado**")
        imagens_conc_passado = st.file_uploader("Upload dos criativos de concorrentes (mes passado)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_conc_passado")
    
# Métricas Principais
    st.subheader("Metricas de Performance")
    
    # Criamos os cabeçalhos das colunas
    col_label1, col_label2, col_label3 = st.columns(3)
    with col_label1: st.markdown("### **Atual**")
    with col_label2: st.markdown("### **Mês Passado**")
    with col_label3: st.markdown("### **Ano Passado**")

    # Lista de métricas para iterar e criar os campos dinamicamente ou manualmente
    # Vou organizar em blocos para manter a estrutura que você pediu
    
    def criar_linha_metrica(label, key_prefix):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_atual", format="%.2f" if "invest" in key_prefix or "c" in key_prefix else "%.0f")
        with c2:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_mes", format="%.2f" if "invest" in key_prefix or "c" in key_prefix else "%.0f")
        with c3:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_ano", format="%.2f" if "invest" in key_prefix or "c" in key_prefix else "%.0f")

    # Renderizando os blocos solicitados
    st.markdown("---")
    criar_linha_metrica("Investimento", "spend")
    criar_linha_metrica("Sessões", "sess")
    criar_linha_metrica("Alcance (Reach)", "reach")
    criar_linha_metrica("Video Thruplays", "vtp")
    criar_linha_metrica("Visualizações", "vis")
    criar_linha_metrica("Impressões", "imp")
    criar_linha_metrica("Cliques", "cli")
    criar_linha_metrica("Engajamentos", "eng")
    criar_linha_metrica("CTR (%)", "ctr")

    # Investimentos
    st.subheader("Investimentos por Canal")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Atual**")
        investimento_fb_atual = st.number_input("Facebook", min_value=0.0, format="%.2f", key="fb_atual")
        investimento_ig_atual = st.number_input("Instagram", min_value=0.0, format="%.2f", key="ig_atual")
        investimento_tt_atual = st.number_input("TikTok", min_value=0.0, format="%.2f", key="tt_atual")
    
    with col2:
        st.markdown("**Mês Passado**")
        investimento_fb_mes_passado = st.number_input("Facebook", min_value=0.0, format="%.2f", key="fb_mes")
        investimento_ig_mes_passado = st.number_input("Instagram", min_value=0.0, format="%.2f", key="ig_mes")
        investimento_tt_mes_passado = st.number_input("TikTok", min_value=0.0, format="%.2f", key="tt_mes")
    
    with col3:
        st.markdown("**Ano Passado**")
        investimento_fb_ano_passado = st.number_input("Facebook", min_value=0.0, format="%.2f", key="fb_ano")
        investimento_ig_ano_passado = st.number_input("Instagram", min_value=0.0, format="%.2f", key="ig_ano")
        investimento_tt_ano_passado = st.number_input("TikTok", min_value=0.0, format="%.2f", key="tt_ano")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        investimento_ads_atual = st.number_input("Google Ads (Atual)", min_value=0.0, format="%.2f", key="google_atual")
        investimento_yt_atual = st.number_input("YouTube (Atual)", min_value=0.0, format="%.2f")
        investimento_pmax_atual = st.number_input("PMax (Atual)", min_value=0.0, format="%.2f")
    
    with col2:
        investimento_ads_mes_passado = st.number_input("Google Ads (Mês Passado)", min_value=0.0, format="%.2f", key="google_mes")
        investimento_yt_mes_passado = st.number_input("YouTube (Mês Passado)", min_value=0.0, format="%.2f")
        investimento_pmax_mes_passado = st.number_input("PMax (Mês Passado)", min_value=0.0, format="%.2f")
    
    with col3:
        investimento_ads_ano_passado = st.number_input("Google Ads (Ano Passado)", min_value=0.0, format="%.2f", key="google_ano")
        investimento_yt_ano_passado = st.number_input("YouTube (Ano Passado)", min_value=0.0, format="%.2f")
        investimento_pmax_ano_passado = st.number_input("PMax (Ano Passado)", min_value=0.0, format="%.2f")
    
    # Custos
    st.subheader("Custos de Eficiencia")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Atual**")
        cpe_atual = st.number_input("Custo por Engajamento", min_value=0.0, format="%.2f", key="cpe_atual")
        cpc_atual = st.number_input("Custo por Clique", min_value=0.0, format="%.2f", key="cpc_atual")
        cpv_atual = st.number_input("Custo por Visualização", min_value=0.0, format="%.2f", key="cpv_atual")
        cpm_atual = st.number_input("Custo por Mil Impressões", min_value=0.0, format="%.2f", key="cpm_atual")
    
    with col2:
        st.markdown("**Mês Passado**")
        cpe_mes_passado = st.number_input("Custo por Engajamento", min_value=0.0, format="%.2f", key="cpe_mes")
        cpc_mes_passado = st.number_input("Custo por Clique", min_value=0.0, format="%.2f", key="cpc_mes")
        cpv_mes_passado = st.number_input("Custo por Visualização", min_value=0.0, format="%.2f", key="cpv_mes")
        cpm_mes_passado = st.number_input("Custo por Mil Impressões", min_value=0.0, format="%.2f", key="cpm_mes")
    
    with col3:
        st.markdown("**Ano Passado**")
        cpe_ano_passado = st.number_input("Custo por Engajamento", min_value=0.0, format="%.2f", key="cpe_ano")
        cpc_ano_passado = st.number_input("Custo por Clique", min_value=0.0, format="%.2f", key="cpc_ano")
        cpv_ano_passado = st.number_input("Custo por Visualização", min_value=0.0, format="%.2f", key="cpv_ano")
        cpm_ano_passado = st.number_input("Custo por Mil Impressões", min_value=0.0, format="%.2f", key="cpm_ano")
    
    # SEO + Content
    st.subheader("SEO + Content")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Atual**")
        seo_visualizacoes_atual = st.number_input("Visualizações", min_value=0, key="seo_vis_atual")
        seo_sessoes_atual = st.number_input("Sessões", min_value=0, key="seo_sess_atual")
        seo_usuarios_atual = st.number_input("Usuários", min_value=0, key="seo_user_atual")
    
    with col2:
        st.markdown("**Mês Passado**")
        seo_visualizacoes_mes_passado = st.number_input("Visualizações", min_value=0, key="seo_vis_mes")
        seo_sessoes_mes_passado = st.number_input("Sessões", min_value=0, key="seo_sess_mes")
        seo_usuarios_mes_passado = st.number_input("Usuários", min_value=0, key="seo_user_mes")
    
    with col3:
        st.markdown("**Ano Passado**")
        seo_visualizacoes_ano_passado = st.number_input("Visualizações", min_value=0, key="seo_vis_ano")
        seo_sessoes_ano_passado = st.number_input("Sessões", min_value=0, key="seo_sess_ano")
        seo_usuarios_ano_passado = st.number_input("Usuários", min_value=0, key="seo_user_ano")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        seo_visualizacoes_org_atual = st.number_input("Visualizações Orgânicas (Atual)", min_value=0)
        seo_sessoes_org_atual = st.number_input("Sessões Orgânicas (Atual)", min_value=0)
        seo_usuarios_org_atual = st.number_input("Usuários Orgânicos (Atual)", min_value=0)
    
    with col2:
        seo_visualizacoes_org_mes_passado = st.number_input("Visualizações Orgânicas (Mês Passado)", min_value=0)
        seo_sessoes_org_mes_passado = st.number_input("Sessões Orgânicas (Mês Passado)", min_value=0)
        seo_usuarios_org_mes_passado = st.number_input("Usuários Orgânicos (Mês Passado)", min_value=0)
    
    with col3:
        seo_visualizacoes_org_ano_passado = st.number_input("Visualizações Orgânicas (Ano Passado)", min_value=0)
        seo_sessoes_org_ano_passado = st.number_input("Sessões Orgânicas (Ano Passado)", min_value=0)
        seo_usuarios_org_ano_passado = st.number_input("Usuários Orgânicos (Ano Passado)", min_value=0)
    
    top_keywords = st.text_area("Top 10 Palavras-chave do Mês", height=100, placeholder="Liste as principais palavras-chave...")
    
    submitted = st.form_submit_button("Gerar Relatorio Executivo")

if submitted:
    # Calcular totais e variações
    investimento_total_atual = (investimento_fb_atual + investimento_ig_atual + investimento_tt_atual + 
                                investimento_ads_atual + investimento_yt_atual + investimento_pmax_atual)
    investimento_total_mes_passado = (investimento_fb_mes_passado + investimento_ig_mes_passado + investimento_tt_mes_passado + 
                                      investimento_ads_mes_passado + investimento_yt_mes_passado + investimento_pmax_mes_passado)
    investimento_total_ano_passado = (investimento_fb_ano_passado + investimento_ig_ano_passado + investimento_tt_ano_passado + 
                                      investimento_ads_ano_passado + investimento_yt_ano_passado + investimento_pmax_ano_passado)
    
    # Processar imagens do mês atual (sempre com Gemini)
    descricoes_imagens = []
    if imagens:
        with st.spinner("Analisando criativos do mês atual..."):
            for imagem_file in imagens:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_imagens.append(f"**[ATUAL] {imagem_file.name}**: {descricao}")

    # Processar imagens do mes passado (sempre com Gemini)
    descricoes_imagens_mes_passado = []
    if imagens_mes_passado:
        with st.spinner("Analisando criativos do mes passado..."):
            for imagem_file in imagens_mes_passado:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_imagens_mes_passado.append(f"**[MES PASSADO] {imagem_file.name}**: {descricao}")

    # Processar criativos da concorrencia - mes atual (sempre com Gemini)
    descricoes_conc_atual = []
    if imagens_conc_atual:
        with st.spinner("Analisando criativos da concorrencia (atual)..."):
            for imagem_file in imagens_conc_atual:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_conc_atual.append(f"**[CONC. ATUAL] {imagem_file.name}**: {descricao}")

    # Processar criativos da concorrencia - mes passado (sempre com Gemini)
    descricoes_conc_passado = []
    if imagens_conc_passado:
        with st.spinner("Analisando criativos da concorrencia (mes passado)..."):
            for imagem_file in imagens_conc_passado:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_conc_passado.append(f"**[CONC. MES PASSADO] {imagem_file.name}**: {descricao}")

    # Organizar dados
    dados_metrica_performance = {
        'spend_atual': st.session_state.get('spend_atual', 0),
        'sess_atual': st.session_state.get('sess_atual', 0),
        'reach_atual': st.session_state.get('reach_atual', 0),
        'vtp_atual': st.session_state.get('vtp_atual', 0),   
        'vis_atual': st.session_state.get('vis_atual', 0),   
        'imp_atual': st.session_state.get('imp_atual', 0),
        'cli_atual': st.session_state.get('cli_atual', 0),
        'eng_atual': st.session_state.get('eng_atual', 0),
        'ctr_atual': st.session_state.get('ctr_atual', 0),

        # --- VARIAÇÕES ANO SOBRE ANO (YoY - 2026 vs 2025) ---
        'var_invest_ano': calcular_variacao(st.session_state.get('spend_atual', 0), st.session_state.get('spend_ano', 0)),
        'var_sess_ano':   calcular_variacao(st.session_state.get('sess_atual', 0),  st.session_state.get('sess_ano', 0)),
        'var_reach_ano':  calcular_variacao(st.session_state.get('reach_atual', 0), st.session_state.get('reach_ano', 0)),
        'var_vtp_ano':    calcular_variacao(st.session_state.get('vtp_atual', 0),   st.session_state.get('vtp_ano', 0)),
        'var_vis_ano':    calcular_variacao(st.session_state.get('vis_atual', 0),   st.session_state.get('vis_ano', 0)),
        'var_imp_ano':    calcular_variacao(st.session_state.get('imp_atual', 0),   st.session_state.get('imp_ano', 0)),
        'var_cli_ano':    calcular_variacao(st.session_state.get('cli_atual', 0),   st.session_state.get('cli_ano', 0)),
        'var_eng_ano':    calcular_variacao(st.session_state.get('eng_atual', 0),   st.session_state.get('eng_ano', 0)),
        'var_ctr_ano':    calcular_variacao(st.session_state.get('ctr_atual', 0),   st.session_state.get('ctr_ano', 0)),

        # --- VARIAÇÕES MÊS SOBRE MÊS (MoM - Atual vs Mês Passado) ---
        'var_invest_mes': calcular_variacao(st.session_state.get('spend_atual', 0), st.session_state.get('spend_mes', 0)),
        'var_sess_mes':   calcular_variacao(st.session_state.get('sess_atual', 0),  st.session_state.get('sess_mes', 0)),
        'var_reach_mes':  calcular_variacao(st.session_state.get('reach_atual', 0), st.session_state.get('reach_mes', 0)),
        'var_vtp_mes':    calcular_variacao(st.session_state.get('vtp_atual', 0),   st.session_state.get('vtp_mes', 0)),
        'var_vis_mes':    calcular_variacao(st.session_state.get('vis_atual', 0),   st.session_state.get('vis_mes', 0)),
        'var_imp_mes':    calcular_variacao(st.session_state.get('imp_atual', 0),   st.session_state.get('imp_mes', 0)),
        'var_cli_mes':    calcular_variacao(st.session_state.get('cli_atual', 0),   st.session_state.get('cli_mes', 0)),
        'var_eng_mes':    calcular_variacao(st.session_state.get('eng_atual', 0),   st.session_state.get('eng_mes', 0)),
        'var_ctr_mes':    calcular_variacao(st.session_state.get('ctr_atual', 0),   st.session_state.get('ctr_mes', 0)),

        # --- DADOS EXTRAS PARA COMPOSIÇÃO ---
        'info_concorrentes': info_concorrentes,
        'contexto_input': contexto_input,
        'cpe_atual': st.session_state.get('cpe_atual', 0),
        'cpc_atual': st.session_state.get('cpc_atual', 0),
        
        
        # Informações adicionais
        'info_concorrentes': info_concorrentes,
        'top_keywords': top_keywords,
        'contexto_input': contexto_input
    }

    # DICIONÁRIO EXCLUSIVO DE CUSTOS E EFICIÊNCIA
    dados_custos = {
        # --- VALORES ATUAIS (O que o usuário vê na tela) ---
        'cpe_atual': st.session_state.get('cpe_atual', 0),
        'cpc_atual': st.session_state.get('cpc_atual', 0),
        'cpv_atual': st.session_state.get('cpv_atual', 0),
        'cpm_atual': st.session_state.get('cpm_atual', 0),

        # --- VARIAÇÕES MÊS SOBRE MÊS (MoM - Eficiência Mensal) ---
        'var_cpe_mes': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_mes', 0)),
        'var_cpc_mes': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_mes', 0)),
        'var_cpv_mes': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_mes', 0)),
        'var_cpm_mes': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_mes', 0)),

        # --- VARIAÇÕES ANO SOBRE ANO (YoY - Eficiência Histórica) ---
        'var_cpe_ano': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_ano', 0)),
        'var_cpc_ano': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_ano', 0)),
        'var_cpv_ano': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_ano', 0)),
        'var_cpm_ano': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_ano', 0)),
    }
    # DICIONÁRIO EXCLUSIVO DE INVESTIMENTOS
    dados_investimentos = {
        # --- VALORES ATUAIS (O que está na tela) ---
        'fb_atual': st.session_state.get('fb_atual', 0),
        'ig_atual': st.session_state.get('ig_atual', 0),
        'tt_atual': st.session_state.get('tt_atual', 0),
        'google_atual': st.session_state.get('google_atual', 0),
        'yt_atual': st.session_state.get('yt_atual', 0),
        'pmax_atual': st.session_state.get('pmax_atual', 0),
        'total_atual': investimento_total_atual, # Variável que você já calcula no topo do 'if submitted'

        # --- VARIAÇÕES MÊS SOBRE MÊS (MoM - Atual vs Mês Passado) ---
        'var_fb_mes': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_mes', 0)),
        'var_ig_mes': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_mes', 0)),
        'var_tt_mes': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_mes', 0)),
        'var_google_mes': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_mes', 0)),
        'var_yt_mes': calcular_variacao(st.session_state.get('yt_atual', 0), st.session_state.get('yt_mes', 0)),
        'var_pmax_mes': calcular_variacao(st.session_state.get('pmax_atual', 0), st.session_state.get('pmax_mes', 0)),
        'var_total_mes': calcular_variacao(investimento_total_atual, investimento_total_mes_passado),

        # --- VARIAÇÕES ANO SOBRE ANO (YoY - Atual vs Ano Passado) ---
        'var_fb_ano': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_ano', 0)),
        'var_ig_ano': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_ano', 0)),
        'var_tt_ano': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_ano', 0)),
        'var_google_ano': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_ano', 0)),
        'var_yt_ano': calcular_variacao(st.session_state.get('yt_atual', 0), st.session_state.get('yt_ano', 0)),
        'var_pmax_ano': calcular_variacao(st.session_state.get('pmax_atual', 0), st.session_state.get('pmax_ano', 0)),
        'var_total_ano': calcular_variacao(investimento_total_atual, investimento_total_ano_passado)
    }

    # DICIONÁRIO EXCLUSIVO PARA SEO E CONTEÚDO (COMPLETO)
    dados_seo = {
        # --- TOTAIS (PAGO + ORGÂNICO) ---
        'vis_total_atual': st.session_state.get('seo_vis_atual', 0),
        'vis_total_mes':   st.session_state.get('seo_vis_mes', 0),
        'vis_total_ano':   st.session_state.get('seo_vis_ano', 0),
        
        'sess_total_atual': st.session_state.get('seo_sess_atual', 0),
        'sess_total_mes':   st.session_state.get('seo_sess_mes', 0),
        'sess_total_ano':   st.session_state.get('seo_sess_ano', 0),
        
        'user_total_atual': st.session_state.get('seo_user_atual', 0),
        'user_total_mes':   st.session_state.get('seo_user_mes', 0),
        'user_total_ano':   st.session_state.get('seo_user_ano', 0),

        # --- APENAS ORGÂNICO (SEO PURO) ---
        'vis_org_atual': st.session_state.get('seo_vis_org_atual', 0),
        'vis_org_mes':   st.session_state.get('seo_vis_org_mes', 0),
        'vis_org_ano':   st.session_state.get('seo_vis_org_ano', 0),
        
        'sess_org_atual': st.session_state.get('seo_sess_org_atual', 0),
        'sess_org_mes':   st.session_state.get('seo_sess_org_mes', 0),
        'sess_org_ano':   st.session_state.get('seo_sess_org_ano', 0),
        
        'user_org_atual': st.session_state.get('seo_user_org_atual', 0),
        'user_org_mes':   st.session_state.get('seo_user_org_mes', 0),
        'user_org_ano':   st.session_state.get('seo_user_org_ano', 0),

        # --- VARIAÇÕES MoM (Mês Atual vs Mês Passado) ---
        'var_vis_total_mes': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_mes', 0)),
        'var_vis_org_mes':   calcular_variacao(st.session_state.get('seo_vis_org_atual', 0), st.session_state.get('seo_vis_org_mes', 0)),
        'var_sess_org_mes':  calcular_variacao(st.session_state.get('seo_sess_org_atual', 0), st.session_state.get('seo_sess_org_mes', 0)),

        # --- VARIAÇÕES YoY (Este Ano vs Ano Passado) ---
        'var_vis_total_ano': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_ano', 0)),
        'var_vis_org_ano':   calcular_variacao(st.session_state.get('seo_vis_org_atual', 0), st.session_state.get('seo_vis_org_ano', 0)),
        'var_sess_org_ano':  calcular_variacao(st.session_state.get('seo_sess_org_atual', 0), st.session_state.get('seo_sess_org_ano', 0)),

        # --- EXTRAS ---
        'top_keywords': top_keywords,
        'info_concorrentes': info_concorrentes
    }

    # Gerar relatório
    with st.spinner("Gerando relatório executivo... (isso pode levar alguns minutos)"):
        try:
            # Gerar cada seção sequencialmente
            analise_yoy = gerar_yoy_para_contexto(dados_metrica_performance, descricoes_imagens)
            analise_concorrencia = gerar_analise_concorrencia(dados_metrica_performance, info_concorrentes, descricoes_conc_atual, descricoes_conc_passado)
            contexto_atual = gerar_contexto_atual(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, analise_yoy, analise_concorrencia)
            destaques = gerar_destaques(dados_metrica_performance, contexto_atual)
            analise_criativos = gerar_analise_criativos(dados_custos, descricoes_imagens, descricoes_imagens_mes_passado, destaques, descricoes_conc_atual, descricoes_conc_passado)
            analise_midias_pagas = gerar_analise_midias_pagas(dados_investimentos, dados_custos, analise_criativos)
            analise_seo = gerar_analise_seo(dados_seo, analise_midias_pagas)
            proximos_passos = gerar_proximos_passos(dados_metrica_performance, analise_seo)
            
            # Armazenar resultados
            st.session_state.relatorio_gerado = True
            st.session_state.dados_processados = dados_metrica_performance # Use a variável correta
            st.session_state.descricoes_imagens = descricoes_imagens
            st.session_state.descricoes_imagens_mes_passado = descricoes_imagens_mes_passado
            st.session_state.descricoes_conc_atual = descricoes_conc_atual
            st.session_state.descricoes_conc_passado = descricoes_conc_passado
            st.session_state.contexto_atual = contexto_atual
            st.session_state.destaques = destaques
            st.session_state.analise_criativos = analise_criativos
            st.session_state.analise_midias_pagas = analise_midias_pagas
            st.session_state.analise_seo = analise_seo
            st.session_state.proximos_passos = proximos_passos
            
            st.rerun() # Força o refresh para mostrar o relatório

        except Exception as e:
            st.error(f"Erro ao gerar relatório: {str(e)}")

# Exibir relatório
if st.session_state.relatorio_gerado:
    st.markdown("---")
    st.header("Relatorio Executivo Gerado")
    
    dados = st.session_state.dados_processados
    
    # Tabela de variações
    st.subheader("Comparativos de Performance")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Visualizações (vs Mês Passado)", 
                 f"{dados.get('vis_atual', 0):,}", 
                 f"{dados.get('var_vis_mes', 0):.1f}%")
    with col2:
        st.metric("Impressões (vs Mês Passado)", 
                 f"{dados.get('imp_atual', 0):,}", 
                 f"{dados.get('var_imp_mes', 0):.1f}%")
    with col3:
        st.metric("Cliques (vs Mês Passado)", 
                 f"{dados.get('cli_atual', 0):,}", 
                 f"{dados.get('var_cliques_mes', 0):.1f}%")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Visualizações (vs Ano Passado)", 
                 f"{dados.get('vis_atual', 0):,}", 
                 f"{dados.get('var_vis_ano', 0):.1f}%")
    with col2:
        st.metric("Impressões (vs Ano Passado)", 
                 f"{dados.get('imp_atual', 0):,}", 
                 f"{dados.get('var_imp_ano', 0):.1f}%")
    with col3:
        st.metric("Cliques (vs Ano Passado)", 
                 f"{dados.get('cli_atual', 0):,}", 
                 f"{dados.get('var_cli_ano', 0):.1f}%")
    
    st.markdown("---")
    
    # Seções do relatório
    st.subheader("Contexto Atual")
    st.write(st.session_state.contexto_atual)
    
    st.subheader("Destaques")
    st.write(st.session_state.destaques)
    
    st.subheader("Analise de Criativos")
    if st.session_state.descricoes_imagens:
        st.markdown("**Criativos do Mês Atual:**")
        for desc in st.session_state.descricoes_imagens:
            st.markdown(desc)
    if st.session_state.descricoes_imagens_mes_passado:
        st.markdown("**Criativos do Mês Passado:**")
        for desc in st.session_state.descricoes_imagens_mes_passado:
            st.markdown(desc)
    st.write(st.session_state.analise_criativos)
    
    st.subheader("Midias Pagas")
    st.write(st.session_state.analise_midias_pagas)
    
    st.subheader("SEO + Content")
    st.write(st.session_state.analise_seo)
    
    st.subheader("Proximos Passos e Aprendizados")
    st.write(st.session_state.proximos_passos)
    
    # Botão para baixar relatório
    relatorio_completo = f"""
# RELATORIO EXECUTIVO -- AGENTE DE RELATORIA EXECUTIVA MACFOR
**Data:** {datetime.now().strftime('%d/%m/%Y')}

---

## Contexto Atual
{st.session_state.contexto_atual}

## Destaques
{st.session_state.destaques}

## Analise de Criativos
### Criativos do Mes Atual
{chr(10).join(st.session_state.descricoes_imagens) if st.session_state.descricoes_imagens else "Nenhum criativo enviado"}
### Criativos do Mes Passado
{chr(10).join(st.session_state.descricoes_imagens_mes_passado) if st.session_state.descricoes_imagens_mes_passado else "Nenhum criativo do mes passado enviado"}
### Criativos da Concorrencia (Atual)
{chr(10).join(st.session_state.descricoes_conc_atual) if st.session_state.descricoes_conc_atual else "Nenhum criativo de concorrente enviado"}
### Criativos da Concorrencia (Mes Passado)
{chr(10).join(st.session_state.descricoes_conc_passado) if st.session_state.descricoes_conc_passado else "Nenhum criativo de concorrente do mes passado enviado"}
{st.session_state.analise_criativos}

## Midias Pagas
{st.session_state.analise_midias_pagas}

## SEO + Content
{st.session_state.analise_seo}

## Proximos Passos e Aprendizados
{st.session_state.proximos_passos}

---
*Relatorio gerado por IA -- Agente de Relatoria Executiva Macfor -- {datetime.now().strftime('%d/%m/%Y %H:%M')}*
"""
    
    st.download_button(
        label="Baixar Relatorio Completo (Markdown)",
        data=relatorio_completo,
        file_name=f"relatorio_executivo_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown"
    )

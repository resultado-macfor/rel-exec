import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from typing import Dict, Any
from PIL import Image
import io
import base64
from datetime import datetime

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Relatório Executivo IA",
    page_icon="📊"
)

# CSS personalizado
st.markdown("""
<style>
    .main {
        background-color: #f5f7fa;
    }
    .stTextInput input, .stSelectbox select, .stTextArea textarea {
        border-radius: 8px !important;
        border: 1px solid #d1d5db !important;
    }
    .stButton button {
        background-color: #4f46e5 !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: 500 !important;
    }
    .stButton button:hover {
        background-color: #4338ca !important;
    }
    .report-card {
        background-color: white;
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-box {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #4f46e5;
    }
    .comparativo-positivo {
        color: #10b981;
        font-weight: 600;
    }
    .comparativo-negativo {
        color: #ef4444;
        font-weight: 600;
    }
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e5e7eb;
    }
    th {
        background-color: #f9fafb;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        color: #4f46e5 !important;
        font-weight: 600 !important;
    }
    .keyword-badge {
        background-color: #e0e7ff;
        color: #3730a3;
        padding: 5px 10px;
        border-radius: 20px;
        display: inline-block;
        margin: 3px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Gemini
gemini_api_key = os.getenv("GEM_API_KEY")
genai.configure(api_key=gemini_api_key)
modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
modelo_visao = genai.GenerativeModel("gemini-2.5-flash")

# Título do aplicativo
st.title("📊 Gerador de Relatório Executivo")
st.markdown("""
**Crie relatórios executivos completos com análise comparativa e narrativa automatizada.**
""")

# Estado da sessão
if 'relatorio_completo' not in st.session_state:
    st.session_state.relatorio_completo = {}
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = []

# Função para calcular variações
def calcular_variacao(atual, anterior):
    """Calcula variação percentual entre dois valores"""
    try:
        atual = float(atual) if atual else 0
        anterior = float(anterior) if anterior else 0
        if anterior == 0:
            return 0
        return ((atual - anterior) / anterior) * 100
    except:
        return 0

# Função para formatar variação com cor
def formatar_variacao(variacao):
    """Formata variação com cor e símbolo"""
    if variacao > 0:
        return f'<span class="comparativo-positivo">▲ {variacao:.1f}%</span>'
    elif variacao < 0:
        return f'<span class="comparativo-negativo">▼ {abs(variacao):.1f}%</span>'
    else:
        return f'<span>0%</span>'

# Função para descrever imagens com Gemini Vision
def descrever_imagem(image_bytes) -> str:
    """Gera descrição de uma imagem usando Gemini Vision"""
    try:
        image_pil = Image.open(io.BytesIO(image_bytes))
        prompt = """Descreva detalhadamente este criativo de anúncio para fins de análise de marketing. Inclua:
        1. Tipo de criativo (estático, vídeo, carrossel, etc.)
        2. Cores predominantes e identidade visual
        3. Elementos de design e composição
        4. Texto e call-to-action presentes
        5. Público-alvo sugerido pelo visual
        6. Plataforma mais adequada para este criativo
        7. Pontos fortes e sugestões de otimização"""
        response = modelo_visao.generate_content([prompt, image_pil])
        return response.text
    except Exception as e:
        return f"Erro ao descrever imagem: {str(e)}"

# Função para descrever todas as imagens
def descrever_todas_imagens(imagens_upload):
    """Processa todas as imagens e retorna descrições"""
    descricoes = []
    progress_bar = st.progress(0)
    for i, uploaded_file in enumerate(imagens_upload):
        with st.spinner(f"Analisando criativo {i+1}/{len(imagens_upload)}..."):
            bytes_data = uploaded_file.getvalue()
            descricao = descrever_imagem(bytes_data)
            descricoes.append({
                'nome': uploaded_file.name,
                'descricao': descricao,
                'bytes': bytes_data
            })
        progress_bar.progress((i + 1) / len(imagens_upload))
    return descricoes

# Funções de geração de conteúdo com Gemini
def gerar_contexto_atual(dados: Dict[str, Any], comparativos: Dict) -> str:
    """Gera o contexto atual baseado nos dados e comparativos"""
    prompt = f"""
    Com base nos dados abaixo, crie um parágrafo de CONTEXTO ATUAL para um relatório executivo de marketing digital.
    
    Informações da Empresa/Marca: {dados.get('info_empresa', 'Não informado')}
    Período: {dados.get('periodo_relatorio', 'Não informado')}
    Contexto Adicional: {dados.get('contexto_adicional', 'Não informado')}
    
    Análise de Métricas e Comparativos:
    - Visualizações: {dados.get('visualizacoes_atual', 'N/A')} ({comparativos['visu_mes']:.1f}% vs mês passado, {comparativos['visu_ano']:.1f}% vs ano passado)
    - Impressões: {dados.get('impressoes_atual', 'N/A')} ({comparativos['imp_mes']:.1f}% vs mês passado, {comparativos['imp_ano']:.1f}% vs ano passado)
    - Cliques: {dados.get('cliques_atual', 'N/A')} ({comparativos['cli_mes']:.1f}% vs mês passado, {comparativos['cli_ano']:.1f}% vs ano passado)
    - Engajamentos: {dados.get('engajamentos_atual', 'N/A')} ({comparativos['eng_mes']:.1f}% vs mês passado, {comparativos['eng_ano']:.1f}% vs ano passado)
    
    Investimento Total: R$ {comparativos['investimento_total']:,.2f}
    
    Informações de Concorrentes: {dados.get('info_concorrentes', 'Não informado')}
    
    Formato: 4-5 frases profissionais que contextualizem o momento atual da marca/empresa, incluindo análise dos comparativos e menção aos principais movimentos do período.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_destaques(dados: Dict[str, Any], comparativos: Dict, contexto_atual: str) -> str:
    """Gera os destaques baseado nos dados e comparativos"""
    prompt = f"""
    Com base no contexto abaixo e nos dados fornecidos, crie 5 DESTAQUES principais para o relatório executivo.
    
    Contexto Atual: {contexto_atual}
    
    Comparativos Detalhados:
    
    MÉTRICAS GERAIS (vs mês passado / vs ano passado):
    - Visualizações: {comparativos['visu_mes']:.1f}% | {comparativos['visu_ano']:.1f}%
    - Impressões: {comparativos['imp_mes']:.1f}% | {comparativos['imp_ano']:.1f}%
    - Cliques: {comparativos['cli_mes']:.1f}% | {comparativos['cli_ano']:.1f}%
    - Engajamentos: {comparativos['eng_mes']:.1f}% | {comparativos['eng_ano']:.1f}%
    
    CUSTOS (atual vs mês passado vs ano passado):
    - CPE: R$ {dados.get('cpe_atual', 'N/A')} | R$ {dados.get('cpe_mes_passado', 'N/A')} | R$ {dados.get('cpe_ano_passado', 'N/A')}
    - CPC: R$ {dados.get('cpc_atual', 'N/A')} | R$ {dados.get('cpc_mes_passado', 'N/A')} | R$ {dados.get('cpc_ano_passado', 'N/A')}
    - CPV: R$ {dados.get('cpv_atual', 'N/A')} | R$ {dados.get('cpv_mes_passado', 'N/A')} | R$ {dados.get('cpv_ano_passado', 'N/A')}
    - CPM: R$ {dados.get('cpm_atual', 'N/A')} | R$ {dados.get('cpm_mes_passado', 'N/A')} | R$ {dados.get('cpm_ano_passado', 'N/A')}
    
    SEO (vs mês passado):
    - Visualizações Orgânicas: {comparativos['seo_visu_org_mes']:.1f}%
    - Sessões Orgânicas: {comparativos['seo_sessoes_org_mes']:.1f}%
    - Usuários Orgânicos: {comparativos['seo_usuarios_org_mes']:.1f}%
    
    Formato: Lista com 5 bullet points destacando:
    - Maiores crescimentos e destaques positivos
    - Pontos de atenção (se houver)
    - Conquistas significativas
    - Performance de canais/chaves específicas
    - Insights baseados nos comparativos
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_criativos(dados: Dict[str, Any], descricoes_imagens: list, comparativos: Dict) -> str:
    """Gera análise dos criativos baseado nas descrições das imagens"""
    imagens_texto = "\n\n".join([f"**{img['nome']}**: {img['descricao']}" for img in descricoes_imagens]) if descricoes_imagens else "Nenhuma imagem fornecida"
    
    prompt = f"""
    Com base nas descrições dos criativos abaixo e nos dados de performance, crie uma seção de ANÁLISE DE CRIATIVOS para o relatório executivo.
    
    DESCRIÇÕES DOS CRIATIVOS:
    {imagens_texto}
    
    PERFORMANCE DO PERÍODO:
    - Engajamentos: {dados.get('engajamentos_atual', 'N/A')} ({comparativos['eng_mes']:.1f}% vs mês anterior)
    - Cliques: {dados.get('cliques_atual', 'N/A')} ({comparativos['cli_mes']:.1f}% vs mês anterior)
    - CPE Atual: R$ {dados.get('cpe_atual', 'N/A')} (vs R$ {dados.get('cpe_mes_passado', 'N/A')} mês anterior)
    
    Formato: Análise profissional abordando:
    1. **Análise Visual dos Criativos**: Padrões identificados, cores, identidade visual
    2. **Performance por Tipo de Criativo**: Quais formatos estão performando melhor
    3. **Correlação com Resultados**: Como os criativos impactaram as métricas
    4. **Recomendações Específicas**: Sugestões de otimização baseadas nas descrições
    5. **Próximos Testes**: Ideias para novos criativos baseadas nos aprendizados
    
    Importante: Conecte as características visuais dos criativos com os resultados obtidos.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_midias_pagas(dados: Dict[str, Any], comparativos: Dict, destaques: str) -> str:
    """Gera análise de mídias pagas com comparativos"""
    
    # Calcular investimento total por período
    invest_total_atual = comparativos['investimento_total']
    invest_total_mes = comparativos['investimento_total_mes']
    invest_total_ano = comparativos['investimento_total_ano']
    
    prompt = f"""
    Com base nos dados de mídia paga e comparativos abaixo, crie uma seção de ANÁLISE DE MÍDIAS PAGAS detalhada.
    
    Destaques do Período: {destaques}
    
    INVESTIMENTO TOTAL:
    - Atual: R$ {invest_total_atual:,.2f}
    - Mês Passado: R$ {invest_total_mes:,.2f} ({comparativos['investimento_total_vs_mes']:.1f}%)
    - Ano Passado: R$ {invest_total_ano:,.2f} ({comparativos['investimento_total_vs_ano']:.1f}%)
    
    INVESTIMENTOS POR PLATAFORMA (Atual | vs Mês | vs Ano):
    
    FACEBOOK:
    - Atual: R$ {dados.get('investimento_fb_atual', 0):,.2f}
    - vs Mês: {comparativos['fb_mes']:.1f}%
    - vs Ano: {comparativos['fb_ano']:.1f}%
    
    INSTAGRAM:
    - Atual: R$ {dados.get('investimento_ig_atual', 0):,.2f}
    - vs Mês: {comparativos['ig_mes']:.1f}%
    - vs Ano: {comparativos['ig_ano']:.1f}%
    
    TIKTOK:
    - Atual: R$ {dados.get('investimento_tiktok_atual', 0):,.2f}
    - vs Mês: {comparativos['tiktok_mes']:.1f}%
    - vs Ano: {comparativos['tiktok_ano']:.1f}%
    
    DISPLAY:
    - Atual: R$ {dados.get('investimento_display_atual', 0):,.2f}
    - vs Mês: {comparativos['display_mes']:.1f}%
    - vs Ano: {comparativos['display_ano']:.1f}%
    
    YOUTUBE:
    - Atual: R$ {dados.get('investimento_yt_atual', 0):,.2f}
    - vs Mês: {comparativos['yt_mes']:.1f}%
    - vs Ano: {comparativos['yt_ano']:.1f}%
    
    PMAX:
    - Atual: R$ {dados.get('investimento_pmax_atual', 0):,.2f}
    - vs Mês: {comparativos['pmax_mes']:.1f}%
    - vs Ano: {comparativos['pmax_ano']:.1f}%
    
    EVOLUÇÃO DOS CUSTOS:
    - CPE: R$ {dados.get('cpe_atual', 0):.2f} (vs R$ {dados.get('cpe_mes_passado', 0):.2f} mês | vs R$ {dados.get('cpe_ano_passado', 0):.2f} ano)
    - CPC: R$ {dados.get('cpc_atual', 0):.2f} (vs R$ {dados.get('cpc_mes_passado', 0):.2f} mês | vs R$ {dados.get('cpc_ano_passado', 0):.2f} ano)
    - CPV: R$ {dados.get('cpv_atual', 0):.2f} (vs R$ {dados.get('cpv_mes_passado', 0):.2f} mês | vs R$ {dados.get('cpv_ano_passado', 0):.2f} ano)
    - CPM: R$ {dados.get('cpm_atual', 0):.2f} (vs R$ {dados.get('cpm_mes_passado', 0):.2f} mês | vs R$ {dados.get('cpm_ano_passado', 0):.2f} ano)
    
    Informações de Concorrentes: {dados.get('info_concorrentes', 'Não informado')}
    
    Formato: Análise completa com os seguintes tópicos:
    
    1. **Visão Geral do Investimento**: Análise da alocação total e tendências
    2. **Performance por Canal**: Para cada plataforma, analisar ROI e eficiência
    3. **Evolução dos Custos**: Tendências de CPE, CPC, CPV e CPM
    4. **Análise de Mix de Mídia**: Distribuição do budget e oportunidades
    5. **Benchmark vs Concorrência**: Posicionamento competitivo
    6. **Recomendações de Otimização**: Ações concretas para cada canal
    
    Inclua análises específicas baseadas nos comparativos mensais e anuais.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_seo(dados: Dict[str, Any], comparativos: Dict) -> str:
    """Gera análise de SEO com comparativos"""
    
    prompt = f"""
    Com base nos dados de SEO abaixo e nos comparativos, crie uma seção de ANÁLISE DE SEO detalhada.
    
    MÉTRICAS DE SEO - COMPARATIVO:
    
    VISUALIZAÇÕES TOTAIS:
    - Atual: {dados.get('seo_visualizacoes_atual', 0):,}
    - vs Mês: {comparativos['seo_visu_mes']:.1f}%
    - vs Ano: {comparativos['seo_visu_ano']:.1f}%
    
    SESSÕES TOTAIS:
    - Atual: {dados.get('seo_sessoes_atual', 0):,}
    - vs Mês: {comparativos['seo_sessoes_mes']:.1f}%
    - vs Ano: {comparativos['seo_sessoes_ano']:.1f}%
    
    USUÁRIOS TOTAIS:
    - Atual: {dados.get('seo_usuarios_atual', 0):,}
    - vs Mês: {comparativos['seo_usuarios_mes']:.1f}%
    - vs Ano: {comparativos['seo_usuarios_ano']:.1f}%
    
    MÉTRICAS ORGÂNICAS:
    
    VISUALIZAÇÕES ORGÂNICAS:
    - Atual: {dados.get('seo_visualizacoes_org_atual', 0):,}
    - vs Mês: {comparativos['seo_visu_org_mes']:.1f}%
    - vs Ano: {comparativos['seo_visu_org_ano']:.1f}%
    - % do Total: {comparativos['seo_percent_org_visu']:.1f}%
    
    SESSÕES ORGÂNICAS:
    - Atual: {dados.get('seo_sessoes_org_atual', 0):,}
    - vs Mês: {comparativos['seo_sessoes_org_mes']:.1f}%
    - vs Ano: {comparativos['seo_sessoes_org_ano']:.1f}%
    - % do Total: {comparativos['seo_percent_org_sessoes']:.1f}%
    
    USUÁRIOS ORGÂNICOS:
    - Atual: {dados.get('seo_usuarios_org_atual', 0):,}
    - vs Mês: {comparativos['seo_usuarios_org_mes']:.1f}%
    - vs Ano: {comparativos['seo_usuarios_org_ano']:.1f}%
    - % do Total: {comparativos['seo_percent_org_usuarios']:.1f}%
    
    TOP 10 PALAVRAS-CHAVE DO MÊS: {", ".join(dados.get('top_palavras_chave', []))}
    
    Formato: Análise completa com os seguintes tópicos:
    
    1. **Evolução do Tráfego Orgânico**: Análise dos comparativos mensais e anuais
    2. **Participação do Orgânico**: Percentual do tráfego total e tendências
    3. **Performance de Palavras-chave**: Análise das principais keywords e oportunidades
    4. **Saúde Técnica SEO**: Insights baseados nos dados
    5. **Recomendações de Conteúdo**: Sugestões baseadas nas keywords performáticas
    6. **Estratégias de Crescimento**: Próximos passos para SEO
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_proximos_passos(dados: Dict[str, Any], analises_anteriores: str, comparativos: Dict) -> str:
    """Gera próximos passos e aprendizados baseado em todas as análises"""
    prompt = f"""
    Com base em todas as análises anteriores e nos dados comparativos, crie uma seção de PRÓXIMOS PASSOS E APRENDIZADOS.
    
    Resumo das Análises: {analises_anteriores[:1500]}
    
    DESTAQUES DOS COMPARATIVOS:
    - Maior crescimento: {max([(k, v) for k, v in comparativos.items() if 'mes' in k or 'ano' in k], key=lambda x: x[1]) if comparativos else 'N/A'}
    - Maior queda: {min([(k, v) for k, v in comparativos.items() if 'mes' in k or 'ano' in k], key=lambda x: x[1]) if comparativos else 'N/A'}
    
    Investimento Total Atual: R$ {comparativos['investimento_total']:,.2f}
    
    Formato: Seção dividida em duas partes:
    
    1. **APRENDIZADOS DO PERÍODO** (4-5 bullet points):
       - O que funcionou bem (baseado nos crescimentos)
       - O que não funcionou (baseado nas quedas)
       - Insights dos comparativos mensais/anuais
       - Padrões identificados nos dados
       - Comportamento do público
    
    2. **PRÓXIMOS PASSOS** (5-6 ações concretas):
       - Ações de curto prazo (próximos 30 dias) com metas específicas
       - Ações de médio prazo (próximo trimestre)
       - Recomendações de realocação de budget baseadas nos comparativos
       - Testes A/B baseados nos aprendizados
       - Oportunidades identificadas nos canais com melhor performance
       - Estratégias para canais com performance abaixo do esperado
    
    As recomendações devem ser específicas e acionáveis, baseadas nos dados apresentados.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

# Abas principais
tab_input, tab_relatorio = st.tabs(["📝 Inserir Dados", "📊 Relatório Gerado"])

with tab_input:
    st.header("Inserir Dados do Relatório")
    
    # Informações básicas
    with st.expander("📋 Informações Básicas", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            info_empresa = st.text_input("Nome da Empresa/Marca", value="Empresa Exemplo")
            periodo_relatorio = st.text_input("Período do Relatório", value="Janeiro/2024")
        with col2:
            responsavel = st.text_input("Responsável pelo Relatório", value="Analista de Marketing")
            data_elaboracao = st.date_input("Data de Elaboração", value=datetime.now())
    
    # Contexto e Concorrentes
    with st.expander("📌 Contexto e Concorrência", expanded=True):
        contexto_adicional = st.text_area(
            "Contexto Adicional da Marca/Período",
            placeholder="Ex: Lançamento de produto, sazonalidade, campanha especial, etc.",
            value="Campanha de lançamento de novo produto com foco em awareness"
        )
        info_concorrentes = st.text_area(
            "Informações de Concorrentes",
            placeholder="Movimentações de concorrentes, share of voice, etc.",
            value="Concorrente principal aumentou investimento em 20% no período"
        )
    
    # Métricas Principais
    with st.expander("📊 Métricas Principais (Atual / Mês Passado / Ano Passado)", expanded=True):
        metricas = [
            ("Visualizações", "visualizacoes"),
            ("Impressões", "impressoes"),
            ("Cliques", "cliques"),
            ("Engajamentos", "engajamentos")
        ]
        
        for metrica_nome, metrica_key in metricas:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.number_input(f"{metrica_nome} - Atual", key=f"{metrica_key}_atual", value=1000000, step=1000, format="%d")
            with col2:
                st.number_input(f"{metrica_nome} - Mês Passado", key=f"{metrica_key}_mes_passado", value=900000, step=1000, format="%d")
            with col3:
                st.number_input(f"{metrica_nome} - Ano Passado", key=f"{metrica_key}_ano_passado", value=800000, step=1000, format="%d")
    
    # Investimentos por Plataforma
    with st.expander("💰 Investimentos por Plataforma (Atual / Mês Passado / Ano Passado)", expanded=True):
        plataformas = [
            ("Facebook", "investimento_fb"),
            ("Instagram", "investimento_ig"),
            ("TikTok", "investimento_tiktok"),
            ("Display", "investimento_display"),
            ("YouTube", "investimento_yt"),
            ("PMax", "investimento_pmax")
        ]
        
        for plat_nome, plat_key in plataformas:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.number_input(f"{plat_nome} - Atual (R$)", key=f"{plat_key}_atual", value=50000, step=1000, format="%d")
            with col2:
                st.number_input(f"{plat_nome} - Mês Passado (R$)", key=f"{plat_key}_mes_passado", value=45000, step=1000, format="%d")
            with col3:
                st.number_input(f"{plat_nome} - Ano Passado (R$)", key=f"{plat_key}_ano_passado", value=40000, step=1000, format="%d")
    
    # Custos
    with st.expander("💰 Custos (Atual / Mês Passado / Ano Passado)", expanded=True):
        custos = [
            ("Custo por Engajamento (CPE)", "cpe"),
            ("Custo por Clique (CPC)", "cpc"),
            ("Custo por Visualização (CPV)", "cpv"),
            ("Custo por Impressão (CPM)", "cpm")
        ]
        
        for custo_nome, custo_key in custos:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.number_input(f"{custo_nome} - Atual (R$)", key=f"{custo_key}_atual", value=0.50, step=0.01, format="%.2f")
            with col2:
                st.number_input(f"{custo_nome} - Mês Passado (R$)", key=f"{custo_key}_mes_passado", value=0.55, step=0.01, format="%.2f")
            with col3:
                st.number_input(f"{custo_nome} - Ano Passado (R$)", key=f"{custo_key}_ano_passado", value=0.60, step=0.01, format="%.2f")
    
    # SEO + Content
    with st.expander("🔍 SEO + Content", expanded=True):
        st.subheader("Métricas SEO (Atual / Mês Passado / Ano Passado)")
        
        seo_metricas = [
            ("Visualizações", "seo_visualizacoes"),
            ("Sessões", "seo_sessoes"),
            ("Usuários", "seo_usuarios"),
            ("Visualizações Orgânicas", "seo_visualizacoes_org"),
            ("Sessões Orgânicas", "seo_sessoes_org"),
            ("Usuários Orgânicos", "seo_usuarios_org")
        ]
        
        for seo_nome, seo_key in seo_metricas:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.number_input(f"{seo_nome} - Atual", key=f"{seo_key}_atual", value=500000, step=1000, format="%d")
            with col2:
                st.number_input(f"{seo_nome} - Mês Passado", key=f"{seo_key}_mes_passado", value=450000, step=1000, format="%d")
            with col3:
                st.number_input(f"{seo_nome} - Ano Passado", key=f"{seo_key}_ano_passado", value=400000, step=1000, format="%d")
        
        # Top 10 palavras-chave
        st.subheader("Top 10 Palavras-Chave do Mês")
        palavras_chave = st.text_area(
            "Digite as palavras-chave (uma por linha)",
            height=150,
            value="marketing digital\ngestão de tráfego\nmídia paga\nseo\ngoogle ads\nfacebook ads\ninstagram marketing\ntiktok ads\necommerce\ndigital analytics"
        )
        lista_palavras_chave = [p.strip() for p in palavras_chave.split('\n') if p.strip()][:10]
    
    # Upload de Imagens
    with st.expander("🖼️ Criativos (Imagens)", expanded=True):
        st.info("Faça upload das imagens dos criativos - elas serão analisadas na geração do relatório")
        uploaded_files = st.file_uploader(
            "Escolha as imagens",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.session_state.uploaded_images = uploaded_files
            st.success(f"{len(uploaded_files)} imagem(ns) carregada(s) com sucesso!")
            for uploaded_file in uploaded_files:
                st.image(uploaded_file, width=150, caption=uploaded_file.name)
    
    # Botão para gerar relatório
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        gerar_button = st.button("🚀 GERAR RELATÓRIO EXECUTIVO", use_container_width=True)

with tab_relatorio:
    if gerar_button or st.session_state.relatorio_completo:
        
        if gerar_button:
            # Coletar todos os dados do estado da sessão
            dados = {}
            for key in st.session_state.keys():
                if key not in ['relatorio_completo', 'uploaded_images']:
                    dados[key] = st.session_state[key]
            
            # Adicionar dados manuais
            dados['info_empresa'] = info_empresa
            dados['periodo_relatorio'] = periodo_relatorio
            dados['responsavel'] = responsavel
            dados['data_elaboracao'] = data_elaboracao.strftime("%d/%m/%Y")
            dados['contexto_adicional'] = contexto_adicional
            dados['info_concorrentes'] = info_concorrentes
            dados['top_palavras_chave'] = lista_palavras_chave
            
            # Processar imagens (apenas agora, após o botão)
            descricoes_imagens = []
            if st.session_state.uploaded_images:
                with st.spinner("Analisando criativos com IA..."):
                    descricoes_imagens = descrever_todas_imagens(st.session_state.uploaded_images)
            
            # Calcular todos os comparativos
            comparativos = {}
            
            # Métricas gerais
            comparativos['visu_mes'] = calcular_variacao(dados.get('visualizacoes_atual', 0), dados.get('visualizacoes_mes_passado', 0))
            comparativos['visu_ano'] = calcular_variacao(dados.get('visualizacoes_atual', 0), dados.get('visualizacoes_ano_passado', 0))
            comparativos['imp_mes'] = calcular_variacao(dados.get('impressoes_atual', 0), dados.get('impressoes_mes_passado', 0))
            comparativos['imp_ano'] = calcular_variacao(dados.get('impressoes_atual', 0), dados.get('impressoes_ano_passado', 0))
            comparativos['cli_mes'] = calcular_variacao(dados.get('cliques_atual', 0), dados.get('cliques_mes_passado', 0))
            comparativos['cli_ano'] = calcular_variacao(dados.get('cliques_atual', 0), dados.get('cliques_ano_passado', 0))
            comparativos['eng_mes'] = calcular_variacao(dados.get('engajamentos_atual', 0), dados.get('engajamentos_mes_passado', 0))
            comparativos['eng_ano'] = calcular_variacao(dados.get('engajamentos_atual', 0), dados.get('engajamentos_ano_passado', 0))
            
            # Investimentos por plataforma
            plataformas_keys = ['fb', 'ig', 'tiktok', 'display', 'yt', 'pmax']
            for plat in plataformas_keys:
                comparativos[f'{plat}_mes'] = calcular_variacao(
                    dados.get(f'investimento_{plat}_atual', 0), 
                    dados.get(f'investimento_{plat}_mes_passado', 0)
                )
                comparativos[f'{plat}_ano'] = calcular_variacao(
                    dados.get(f'investimento_{plat}_atual', 0), 
                    dados.get(f'investimento_{plat}_ano_passado', 0)
                )
            
            # Investimento total
            comparativos['investimento_total'] = sum([
                float(dados.get('investimento_fb_atual', 0) or 0),
                float(dados.get('investimento_ig_atual', 0) or 0),
                float(dados.get('investimento_tiktok_atual', 0) or 0),
                float(dados.get('investimento_display_atual', 0) or 0),
                float(dados.get('investimento_yt_atual', 0) or 0),
                float(dados.get('investimento_pmax_atual', 0) or 0)
            ])
            
            comparativos['investimento_total_mes'] = sum([
                float(dados.get('investimento_fb_mes_passado', 0) or 0),
                float(dados.get('investimento_ig_mes_passado', 0) or 0),
                float(dados.get('investimento_tiktok_mes_passado', 0) or 0),
                float(dados.get('investimento_display_mes_passado', 0) or 0),
                float(dados.get('investimento_yt_mes_passado', 0) or 0),
                float(dados.get('investimento_pmax_mes_passado', 0) or 0)
            ])
            
            comparativos['investimento_total_ano'] = sum([
                float(dados.get('investimento_fb_ano_passado', 0) or 0),
                float(dados.get('investimento_ig_ano_passado', 0) or 0),
                float(dados.get('investimento_tiktok_ano_passado', 0) or 0),
                float(dados.get('investimento_display_ano_passado', 0) or 0),
                float(dados.get('investimento_yt_ano_passado', 0) or 0),
                float(dados.get('investimento_pmax_ano_passado', 0) or 0)
            ])
            
            comparativos['investimento_total_vs_mes'] = calcular_variacao(
                comparativos['investimento_total'], 
                comparativos['investimento_total_mes']
            )
            comparativos['investimento_total_vs_ano'] = calcular_variacao(
                comparativos['investimento_total'], 
                comparativos['investimento_total_ano']
            )
            
            # SEO comparativos
            seo_keys = ['visualizacoes', 'sessoes', 'usuarios', 'visualizacoes_org', 'sessoes_org', 'usuarios_org']
            for seo_key in seo_keys:
                comparativos[f'seo_{seo_key}_mes'] = calcular_variacao(
                    dados.get(f'seo_{seo_key}_atual', 0),
                    dados.get(f'seo_{seo_key}_mes_passado', 0)
                )
                comparativos[f'seo_{seo_key}_ano'] = calcular_variacao(
                    dados.get(f'seo_{seo_key}_atual', 0),
                    dados.get(f'seo_{seo_key}_ano_passado', 0)
                )
            
            # Percentuais do orgânico
            comparativos['seo_percent_org_visu'] = (float(dados.get('seo_visualizacoes_org_atual', 0) or 0) / float(dados.get('seo_visualizacoes_atual', 1) or 1)) * 100
            comparativos['seo_percent_org_sessoes'] = (float(dados.get('seo_sessoes_org_atual', 0) or 0) / float(dados.get('seo_sessoes_atual', 1) or 1)) * 100
            comparativos['seo_percent_org_usuarios'] = (float(dados.get('seo_usuarios_org_atual', 0) or 0) / float(dados.get('seo_usuarios_atual', 1) or 1)) * 100
            
            # Gerar relatório completo
            with st.spinner("Gerando relatório executivo... (isso pode levar alguns minutos)"):
                
                # Fluxo sequencial de geração
                contexto = gerar_contexto_atual(dados, comparativos)
                st.session_state.relatorio_completo['contexto_atual'] = contexto
                
                destaques = gerar_destaques(dados, comparativos, contexto)
                st.session_state.relatorio_completo['destaques'] = destaques
                
                analise_criativos = gerar_analise_criativos(dados, descricoes_imagens, comparativos)
                st.session_state.relatorio_completo['criativos'] = analise_criativos
                
                analise_midias = gerar_analise_midias_pagas(dados, comparativos, destaques)
                st.session_state.relatorio_completo['midias_pagas'] = analise_midias
                
                analise_seo = gerar_analise_seo(dados, comparativos)
                st.session_state.relatorio_completo['seo'] = analise_seo
                
                # Consolidar análises para próximos passos
                analises_consolidadas = f"{contexto}\n{destaques}\n{analise_criativos}\n{analise_midias}\n{analise_seo}"
                proximos_passos = gerar_proximos_passos(dados, analises_consolidadas, comparativos)
                st.session_state.relatorio_completo['proximos_passos'] = proximos_passos
                
                # Guardar comparativos e descrições para exibição
                st.session_state.relatorio_completo['comparativos'] = comparativos
                st.session_state.relatorio_completo['descricoes_imagens'] = descricoes_imagens
        
        # Exibir relatório
        if st.session_state.relatorio_completo:
            st.markdown("## 📊 RELATÓRIO EXECUTIVO")
            
            # Cabeçalho
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Empresa/Marca:** {dados.get('info_empresa', 'N/A')}")
                st.markdown(f"**Período:** {dados.get('periodo_relatorio', 'N/A')}")
            with col2:
                st.markdown(f"**Responsável:** {dados.get('responsavel', 'N/A')}")
                st.markdown(f"**Data:** {dados.get('data_elaboracao', 'N/A')}")
            
            st.markdown("---")
            
            # Seções do relatório
            with st.container():
                st.markdown("### 📌 Contexto Atual")
                st.markdown(st.session_state.relatorio_completo.get('contexto_atual', ''))
            
            with st.container():
                st.markdown("### ⭐ Destaques")
                st.markdown(st.session_state.relatorio_completo.get('destaques', ''))
            
            # Cards de métricas rápidas com comparativos
            comparativos = st.session_state.relatorio_completo.get('comparativos', {})
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                invest_total = comparativos.get('investimento_total', 0)
                var_invest_mes = comparativos.get('investimento_total_vs_mes', 0)
                st.metric(
                    "Investimento Total", 
                    f"R$ {invest_total:,.2f}",
                    delta=f"{var_invest_mes:+.1f}% vs mês"
                )
            with col2:
                visu_atual = dados.get('visualizacoes_atual', 0)
                st.metric(
                    "Visualizações", 
                    f"{visu_atual:,}",
                    delta=f"{comparativos.get('visu_mes', 0):+.1f}% vs mês"
                )
            with col3:
                cliques_atual = dados.get('cliques_atual', 0)
                st.metric(
                    "Cliques", 
                    f"{cliques_atual:,}",
                    delta=f"{comparativos.get('cli_mes', 0):+.1f}% vs mês"
                )
            with col4:
                eng_atual = dados.get('engajamentos_atual', 0)
                st.metric(
                    "Engajamentos", 
                    f"{eng_atual:,}",
                    delta=f"{comparativos.get('eng_mes', 0):+.1f}% vs mês"
                )
            
            # Tabela de comparativos rápidos
            with st.expander("📈 Ver Comparativos Detalhados"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**vs Mês Passado**")
                    st.markdown(f"- Visualizações: {formatar_variacao(comparativos.get('visu_mes', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Impressões: {formatar_variacao(comparativos.get('imp_mes', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Cliques: {formatar_variacao(comparativos.get('cli_mes', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Engajamentos: {formatar_variacao(comparativos.get('eng_mes', 0))}", unsafe_allow_html=True)
                with col2:
                    st.markdown("**vs Ano Passado**")
                    st.markdown(f"- Visualizações: {formatar_variacao(comparativos.get('visu_ano', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Impressões: {formatar_variacao(comparativos.get('imp_ano', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Cliques: {formatar_variacao(comparativos.get('cli_ano', 0))}", unsafe_allow_html=True)
                    st.markdown(f"- Engajamentos: {formatar_variacao(comparativos.get('eng_ano', 0))}", unsafe_allow_html=True)
            
            with st.container():
                st.markdown("### 🖼️ Análise de Criativos")
                st.markdown(st.session_state.relatorio_completo.get('criativos', ''))
                
                # Mostrar miniaturas das imagens
                if st.session_state.relatorio_completo.get('descricoes_imagens'):
                    st.markdown("**Criativos Analisados:**")
                    cols = st.columns(min(len(st.session_state.relatorio_completo['descricoes_imagens']), 4))
                    for idx, img in enumerate(st.session_state.relatorio_completo['descricoes_imagens']):
                        with cols[idx % 4]:
                            st.image(img['bytes'], width=150, caption=img['nome'][:20])
            
            with st.container():
                st.markdown("### 💰 Mídias Pagas")
                st.markdown(st.session_state.relatorio_completo.get('midias_pagas', ''))
            
            with st.container():
                st.markdown("### 🔍 SEO")
                st.markdown(st.session_state.relatorio_completo.get('seo', ''))
                
                # Exibir palavras-chave
                if dados.get('top_palavras_chave'):
                    st.markdown("**Top 10 Palavras-Chave do Mês:**")
                    palavras_html = "".join([f'<span class="keyword-badge">{kw}</span>' for kw in dados['top_palavras_chave']])
                    st.markdown(f'<div>{palavras_html}</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown("### 🎯 Próximos Passos e Aprendizados")
                st.markdown(st.session_state.relatorio_completo.get('proximos_passos', ''))
            
            # Botão para baixar relatório
            relatorio_completo_texto = f"""
# RELATÓRIO EXECUTIVO - {dados.get('info_empresa', 'N/A')}

**Período:** {dados.get('periodo_relatorio', 'N/A')}
**Responsável:** {dados.get('responsavel', 'N/A')}
**Data:** {dados.get('data_elaboracao', 'N/A')}

## 📌 Contexto Atual
{st.session_state.relatorio_completo.get('contexto_atual', '')}

## ⭐ Destaques
{st.session_state.relatorio_completo.get('destaques', '')}

## 🖼️ Análise de Criativos
{st.session_state.relatorio_completo.get('criativos', '')}

## 💰 Mídias Pagas
{st.session_state.relatorio_completo.get('midias_pagas', '')}

## 🔍 SEO
{st.session_state.relatorio_completo.get('seo', '')}

## 🎯 Próximos Passos e Aprendizados
{st.session_state.relatorio_completo.get('proximos_passos', '')}
"""
            
            st.download_button(
                label="📥 Baixar Relatório Completo",
                data=relatorio_completo_texto,
                file_name=f"relatorio_executivo_{dados.get('info_empresa', 'empresa').replace(' ', '_')}_{dados.get('periodo_relatorio', 'periodo').replace('/', '_')}.md",
                mime="text/markdown"
            )
    else:
        st.info("👈 Preencha os dados na aba 'Inserir Dados' e clique em GERAR RELATÓRIO EXECUTIVO")

# Rodapé
st.markdown("---")
st.caption("""
Ferramenta de Geração de Relatórios Executivos com IA - Transforme dados em insights estratégicos com análise comparativa mensal/anual e narrativa automatizada.
""")

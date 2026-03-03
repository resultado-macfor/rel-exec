import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from typing import Dict, Any
from PIL import Image
import io
import base64

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
**Crie relatórios executivos completos com análise de dados, criativos e recomendações estratégicas.**
""")

# Estado da sessão
if 'relatorio_completo' not in st.session_state:
    st.session_state.relatorio_completo = {}
if 'imagens_descritas' not in st.session_state:
    st.session_state.imagens_descritas = []

# Função para descrever imagens com Gemini Vision
def descrever_imagem(image_bytes) -> str:
    """Gera descrição de uma imagem usando Gemini Vision"""
    try:
        image_pil = Image.open(io.BytesIO(image_bytes))
        prompt = "Descreva detalhadamente este criativo de anúncio/anúncio. Inclua: tipo de imagem, cores, elementos visuais, texto presente, call-to-action e sugestão de qual plataforma seria mais adequada para este criativo."
        response = modelo_visao.generate_content([prompt, image_pil])
        return response.text
    except Exception as e:
        return f"Erro ao descrever imagem: {str(e)}"

# Funções de geração de conteúdo com Gemini
def gerar_contexto_atual(dados: Dict[str, Any]) -> str:
    """Gera o contexto atual baseado nos dados fornecidos"""
    prompt = f"""
    Com base nos dados abaixo, crie um parágrafo de CONTEXTO ATUAL para um relatório executivo de marketing digital.
    
    Informações da Empresa/Marca: {dados.get('info_empresa', 'Não informado')}
    Contexto Adicional: {dados.get('contexto_adicional', 'Não informado')}
    
    Análise de Métricas Atuais:
    - Visualizações: {dados.get('visualizacoes_atual', 'N/A')}
    - Impressões: {dados.get('impressoes_atual', 'N/A')}
    - Cliques: {dados.get('cliques_atual', 'N/A')}
    - Engajamentos: {dados.get('engajamentos_atual', 'N/A')}
    
    Informações de Concorrentes: {dados.get('info_concorrentes', 'Não informado')}
    
    Formato: 3-4 frases profissionais que contextualizem o momento atual da marca/empresa.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_destaques(dados: Dict[str, Any], contexto_atual: str) -> str:
    """Gera os destaques baseado nos dados e contexto"""
    prompt = f"""
    Com base no contexto abaixo e nos dados fornecidos, crie 5 DESTAQUES principais para o relatório executivo.
    
    Contexto Atual: {contexto_atual}
    
    Dados Comparativos:
    Período Atual vs Mês Passado vs Ano Passado:
    - Visualizações: {dados.get('visualizacoes_atual', 'N/A')} | {dados.get('visualizacoes_mes_passado', 'N/A')} | {dados.get('visualizacoes_ano_passado', 'N/A')}
    - Impressões: {dados.get('impressoes_atual', 'N/A')} | {dados.get('impressoes_mes_passado', 'N/A')} | {dados.get('impressoes_ano_passado', 'N/A')}
    - Cliques: {dados.get('cliques_atual', 'N/A')} | {dados.get('cliques_mes_passado', 'N/A')} | {dados.get('cliques_ano_passado', 'N/A')}
    - Engajamentos: {dados.get('engajamentos_atual', 'N/A')} | {dados.get('engajamentos_mes_passado', 'N/A')} | {dados.get('engajamentos_ano_passado', 'N/A')}
    
    Investimentos:
    - Facebook: R$ {dados.get('investimento_fb_atual', 'N/A')}
    - Instagram: R$ {dados.get('investimento_ig_atual', 'N/A')}
    - TikTok: R$ {dados.get('investimento_tiktok_atual', 'N/A')}
    - Display: R$ {dados.get('investimento_display_atual', 'N/A')}
    - YouTube: R$ {dados.get('investimento_yt_atual', 'N/A')}
    - PMax: R$ {dados.get('investimento_pmax_atual', 'N/A')}
    
    Custos:
    - Custo por Engajamento: R$ {dados.get('cpe_atual', 'N/A')}
    - Custo por Clique: R$ {dados.get('cpc_atual', 'N/A')}
    - Custo por Visualização: R$ {dados.get('cpv_atual', 'N/A')}
    - Custo por Impressão: R$ {dados.get('cpm_atual', 'N/A')}
    
    Formato: Lista com 5 bullet points destacando os principais resultados, crescimentos, insights e conquistas do período.
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_criativos(dados: Dict[str, Any], descricoes_imagens: list) -> str:
    """Gera análise dos criativos baseado nas descrições das imagens"""
    imagens_texto = "\n".join([f"- {desc}" for desc in descricoes_imagens]) if descricoes_imagens else "Nenhuma imagem fornecida"
    
    prompt = f"""
    Com base nas descrições dos criativos abaixo, crie uma seção de ANÁLISE DE CRIATIVOS para o relatório executivo.
    
    Descrições dos Criativos:
    {imagens_texto}
    
    Métricas de Performance:
    - Engajamentos: {dados.get('engajamentos_atual', 'N/A')}
    - Cliques: {dados.get('cliques_atual', 'N/A')}
    - CTR: {dados.get('ctr_atual', 'N/A') if dados.get('ctr_atual') else 'Calcular se disponível'}
    
    Formato: Análise profissional abordando:
    1. Quais criativos estão performando melhor e por quê
    2. Padrões visuais identificados nos criativos de sucesso
    3. Recomendações para otimização
    4. Sugestões de novos testes A/B
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_midias_pagas(dados: Dict[str, Any], destaques: str) -> str:
    """Gera análise de mídias pagas"""
    prompt = f"""
    Com base nos dados de mídia paga e nos destaques abaixo, crie uma seção de ANÁLISE DE MÍDIAS PAGAS.
    
    Destaques: {destaques}
    
    Investimentos por Plataforma:
    - Facebook: R$ {dados.get('investimento_fb_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_fb_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_fb_ano_passado', 'N/A')}
    - Instagram: R$ {dados.get('investimento_ig_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_ig_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_ig_ano_passado', 'N/A')}
    - TikTok: R$ {dados.get('investimento_tiktok_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_tiktok_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_tiktok_ano_passado', 'N/A')}
    - Display: R$ {dados.get('investimento_display_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_display_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_display_ano_passado', 'N/A')}
    - YouTube: R$ {dados.get('investimento_yt_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_yt_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_yt_ano_passado', 'N/A')}
    - PMax: R$ {dados.get('investimento_pmax_atual', 'N/A')} | Mês Passado: R$ {dados.get('investimento_pmax_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('investimento_pmax_ano_passado', 'N/A')}
    
    Métricas de Performance:
    - Custo por Engajamento: R$ {dados.get('cpe_atual', 'N/A')} | Mês Passado: R$ {dados.get('cpe_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('cpe_ano_passado', 'N/A')}
    - Custo por Clique: R$ {dados.get('cpc_atual', 'N/A')} | Mês Passado: R$ {dados.get('cpc_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('cpc_ano_passado', 'N/A')}
    - Custo por Visualização: R$ {dados.get('cpv_atual', 'N/A')} | Mês Passado: R$ {dados.get('cpv_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('cpv_ano_passado', 'N/A')}
    - Custo por Impressão: R$ {dados.get('cpm_atual', 'N/A')} | Mês Passado: R$ {dados.get('cpm_mes_passado', 'N/A')} | Ano Passado: R$ {dados.get('cpm_ano_passado', 'N/A')}
    
    Informações de Concorrentes: {dados.get('info_concorrentes', 'Não informado')}
    
    Formato: Análise completa abordando:
    1. Performance por plataforma vs investimento
    2. Evolução dos custos (comparativo mensal/anual)
    3. ROAS estimado e eficiência de cada canal
    4. Oportunidades de otimização e realocação de budget
    5. Análise competitiva e share of voice
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_seo(dados: Dict[str, Any]) -> str:
    """Gera análise de SEO"""
    # Processar palavras-chave
    palavras_chave = dados.get('top_palavras_chave', [])
    palavras_chave_texto = ", ".join(palavras_chave) if palavras_chave else "Nenhuma palavra-chave fornecida"
    
    prompt = f"""
    Com base nos dados de SEO abaixo, crie uma seção de ANÁLISE DE SEO.
    
    Métricas de SEO:
    
    VISUALIZAÇÕES:
    - Atual: {dados.get('seo_visualizacoes_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_visualizacoes_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_visualizacoes_ano_passado', 'N/A')}
    
    SESSÕES:
    - Atual: {dados.get('seo_sessoes_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_sessoes_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_sessoes_ano_passado', 'N/A')}
    
    USUÁRIOS:
    - Atual: {dados.get('seo_usuarios_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_usuarios_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_usuarios_ano_passado', 'N/A')}
    
    VISUALIZAÇÕES ORGÂNICAS:
    - Atual: {dados.get('seo_visualizacoes_org_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_visualizacoes_org_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_visualizacoes_org_ano_passado', 'N/A')}
    
    SESSÕES ORGÂNICAS:
    - Atual: {dados.get('seo_sessoes_org_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_sessoes_org_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_sessoes_org_ano_passado', 'N/A')}
    
    USUÁRIOS ORGÂNICOS:
    - Atual: {dados.get('seo_usuarios_org_atual', 'N/A')}
    - Mês Passado: {dados.get('seo_usuarios_org_mes_passado', 'N/A')}
    - Ano Passado: {dados.get('seo_usuarios_org_ano_passado', 'N/A')}
    
    TOP 10 PALAVRAS-CHAVE DO MÊS: {palavras_chave_texto}
    
    Formato: Análise completa abordando:
    1. Evolução do tráfego orgânico (comparativo)
    2. Performance das principais palavras-chave
    3. Saúde do SEO e oportunidades de melhoria
    4. Recomendações de conteúdo baseado nas keywords
    5. Insights sobre comportamento do usuário
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_proximos_passos(dados: Dict[str, Any], analises_anteriores: str) -> str:
    """Gera próximos passos e aprendizados baseado em todas as análises"""
    prompt = f"""
    Com base em todas as análises anteriores e nos dados fornecidos, crie uma seção de PRÓXIMOS PASSOS E APRENDIZADOS.
    
    Análises Consolidadas: {analises_anteriores[:1000]}  # Resumo das análises
    
    Dados do Período:
    - Investimento Total Atual: R$ {sum([
        float(dados.get('investimento_fb_atual', 0) or 0),
        float(dados.get('investimento_ig_atual', 0) or 0),
        float(dados.get('investimento_tiktok_atual', 0) or 0),
        float(dados.get('investimento_display_atual', 0) or 0),
        float(dados.get('investimento_yt_atual', 0) or 0),
        float(dados.get('investimento_pmax_atual', 0) or 0)
    ])}
    
    Formato: Seção dividida em duas partes:
    
    1. APRENDIZADOS (3-4 bullet points):
       - O que funcionou bem
       - O que não funcionou
       - Insights importantes
    
    2. PRÓXIMOS PASSOS (4-5 ações concretas):
       - Ações de curto prazo (próximo mês)
       - Ações de médio prazo (próximo trimestre)
       - Recomendações de budget
       - Testes a serem realizados
       - Oportunidades identificadas
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
            data_elaboracao = st.date_input("Data de Elaboração")
    
    # Contexto e Concorrentes
    with st.expander("📌 Contexto e Concorrência", expanded=True):
        contexto_adicional = st.text_area(
            "Contexto Adicional da Marca/Período",
            placeholder="Ex: Lançamento de produto, sazonalidade, campanha especial, etc.",
            value="Campanha de lançamento de novo produto"
        )
        info_concorrentes = st.text_area(
            "Informações de Concorrentes",
            placeholder="Movimentações de concorrentes, share of voice, etc.",
            value="Concorrente principal aumentou investimento em 20%"
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
                st.number_input(f"{metrica_nome} - Atual", key=f"{metrica_key}_atual", value=1000000, step=1000)
            with col2:
                st.number_input(f"{metrica_nome} - Mês Passado", key=f"{metrica_key}_mes_passado", value=900000, step=1000)
            with col3:
                st.number_input(f"{metrica_nome} - Ano Passado", key=f"{metrica_key}_ano_passado", value=800000, step=1000)
    
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
                st.number_input(f"{plat_nome} - Atual (R$)", key=f"{plat_key}_atual", value=50000, step=1000)
            with col2:
                st.number_input(f"{plat_nome} - Mês Passado (R$)", key=f"{plat_key}_mes_passado", value=45000, step=1000)
            with col3:
                st.number_input(f"{plat_nome} - Ano Passado (R$)", key=f"{plat_key}_ano_passado", value=40000, step=1000)
    
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
                st.number_input(f"{seo_nome} - Atual", key=f"{seo_key}_atual", value=500000, step=1000)
            with col2:
                st.number_input(f"{seo_nome} - Mês Passado", key=f"{seo_key}_mes_passado", value=450000, step=1000)
            with col3:
                st.number_input(f"{seo_nome} - Ano Passado", key=f"{seo_key}_ano_passado", value=400000, step=1000)
        
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
        st.info("Faça upload das imagens dos criativos para análise")
        uploaded_files = st.file_uploader(
            "Escolha as imagens",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.session_state.imagens_descritas = []
            for uploaded_file in uploaded_files:
                bytes_data = uploaded_file.getvalue()
                with st.spinner(f"Analisando {uploaded_file.name}..."):
                    descricao = descrever_imagem(bytes_data)
                    st.session_state.imagens_descritas.append(descricao)
                    
                    with st.expander(f"📸 {uploaded_file.name}"):
                        st.image(uploaded_file, width=300)
                        st.markdown("**Descrição:**")
                        st.write(descricao)
    
    # Botão para gerar relatório
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        gerar_button = st.button("🚀 GERAR RELATÓRIO EXECUTIVO", use_container_width=True)

with tab_relatorio:
    if gerar_button or st.session_state.relatorio_completo:
        # Coletar todos os dados do estado da sessão
        dados = {}
        
        # Informações básicas
        dados['info_empresa'] = info_empresa
        dados['periodo_relatorio'] = periodo_relatorio
        dados['contexto_adicional'] = contexto_adicional
        dados['info_concorrentes'] = info_concorrentes
        dados['top_palavras_chave'] = lista_palavras_chave
        
        # Coletar métricas
        for key in st.session_state.keys():
            if key not in ['relatorio_completo', 'imagens_descritas']:
                dados[key] = st.session_state[key]
        
        # Gerar relatório completo
        with st.spinner("Gerando relatório executivo... (isso pode levar alguns minutos)"):
            
            # Fluxo sequencial de geração
            contexto = gerar_contexto_atual(dados)
            st.session_state.relatorio_completo['contexto_atual'] = contexto
            
            destaques = gerar_destaques(dados, contexto)
            st.session_state.relatorio_completo['destaques'] = destaques
            
            analise_criativos = gerar_analise_criativos(dados, st.session_state.imagens_descritas)
            st.session_state.relatorio_completo['criativos'] = analise_criativos
            
            analise_midias = gerar_analise_midias_pagas(dados, destaques)
            st.session_state.relatorio_completo['midias_pagas'] = analise_midias
            
            analise_seo = gerar_analise_seo(dados)
            st.session_state.relatorio_completo['seo'] = analise_seo
            
            # Consolidar análises para próximos passos
            analises_consolidadas = f"{contexto}\n{destaques}\n{analise_criativos}\n{analise_midias}\n{analise_seo}"
            proximos_passos = gerar_proximos_passos(dados, analises_consolidadas)
            st.session_state.relatorio_completo['proximos_passos'] = proximos_passos
        
        # Exibir relatório
        st.markdown("## 📊 RELATÓRIO EXECUTIVO")
        
        # Cabeçalho
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Empresa/Marca:** {info_empresa}")
            st.markdown(f"**Período:** {periodo_relatorio}")
        with col2:
            st.markdown(f"**Responsável:** {responsavel}")
            st.markdown(f"**Data:** {data_elaboracao}")
        
        st.markdown("---")
        
        # Seções do relatório
        with st.container():
            st.markdown("### 📌 Contexto Atual")
            st.markdown(st.session_state.relatorio_completo.get('contexto_atual', ''))
        
        with st.container():
            st.markdown("### ⭐ Destaques")
            st.markdown(st.session_state.relatorio_completo.get('destaques', ''))
        
        # Cards de métricas rápidas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Investimento Total", f"R$ {sum([float(dados.get('investimento_fb_atual', 0) or 0), float(dados.get('investimento_ig_atual', 0) or 0), float(dados.get('investimento_tiktok_atual', 0) or 0), float(dados.get('investimento_display_atual', 0) or 0), float(dados.get('investimento_yt_atual', 0) or 0), float(dados.get('investimento_pmax_atual', 0) or 0)]):,.2f}")
        with col2:
            st.metric("Visualizações", f"{dados.get('visualizacoes_atual', 0):,}")
        with col3:
            st.metric("Cliques", f"{dados.get('cliques_atual', 0):,}")
        with col4:
            st.metric("Engajamentos", f"{dados.get('engajamentos_atual', 0):,}")
        
        with st.container():
            st.markdown("### 🖼️ Análise de Criativos")
            st.markdown(st.session_state.relatorio_completo.get('criativos', ''))
        
        with st.container():
            st.markdown("### 💰 Mídias Pagas")
            st.markdown(st.session_state.relatorio_completo.get('midias_pagas', ''))
        
        with st.container():
            st.markdown("### 🔍 SEO")
            st.markdown(st.session_state.relatorio_completo.get('seo', ''))
            
            # Exibir palavras-chave
            if lista_palavras_chave:
                st.markdown("**Top 10 Palavras-Chave do Mês:**")
                palavras_html = "".join([f'<span class="keyword-badge">{kw}</span>' for kw in lista_palavras_chave])
                st.markdown(f'<div>{palavras_html}</div>', unsafe_allow_html=True)
        
        with st.container():
            st.markdown("### 🎯 Próximos Passos e Aprendizados")
            st.markdown(st.session_state.relatorio_completo.get('proximos_passos', ''))
        
        # Botão para baixar relatório
        relatorio_completo_texto = f"""
# RELATÓRIO EXECUTIVO - {info_empresa}

**Período:** {periodo_relatorio}
**Responsável:** {responsavel}
**Data:** {data_elaboracao}

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
            file_name=f"relatorio_executivo_{info_empresa.replace(' ', '_')}_{periodo_relatorio.replace('/', '_')}.md",
            mime="text/markdown"
        )
    else:
        st.info("👈 Preencha os dados na aba 'Inserir Dados' e clique em GERAR RELATÓRIO EXECUTIVO")

# Rodapé
st.markdown("---")
st.caption("""
Ferramenta de Geração de Relatórios Executivos com IA - Transforme dados em insights estratégicos com narrativa automatizada.
""")

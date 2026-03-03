import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from datetime import datetime
from PIL import Image
import io

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Relatório Executivo - IA",
    page_icon="📊"
)

# Inicializar Gemini
gemini_api_key = os.getenv("GEM_API_KEY")
genai.configure(api_key=gemini_api_key)
modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
modelo_visao = genai.GenerativeModel("gemini-2.5-flash")

# Título do aplicativo
st.title("📊 Relatório Executivo - IA Generativa")
st.markdown("---")

# Estado da sessão
if 'relatorio_gerado' not in st.session_state:
    st.session_state.relatorio_gerado = False
if 'descricoes_imagens' not in st.session_state:
    st.session_state.descricoes_imagens = []
if 'dados_processados' not in st.session_state:
    st.session_state.dados_processados = {}

# Função para descrever imagem
def descrever_imagem(imagem):
    try:
        response = modelo_visao.generate_content([
            "Descreva detalhadamente esta imagem de criativo/publicidade em até 100 palavras. Inclua elementos visuais, texto, cores e o que está sendo comunicado.",
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

# Funções de geração de conteúdo
def gerar_contexto_atual(dados, descricoes_imagens):
    prompt = f"""
    Com base nos dados abaixo, escreva um parágrafo de CONTEXTO ATUAL para um relatório executivo.
    Seja conciso e foque no panorama geral da campanha/período.
    
    **Dados do Período Atual:**
    - Visualizações: {dados.get('visualizacoes_atual', 0)}
    - Impressões: {dados.get('impressoes_atual', 0)}
    - Cliques: {dados.get('cliques_atual', 0)}
    - Engajamentos: {dados.get('engajamentos_atual', 0)}
    - Investimento Total: R$ {dados.get('investimento_total_atual', 0):,.2f}
    
    **Descrições de Criativos:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhuma imagem fornecida"}
    
    **Informações de Concorrentes:**
    {dados.get('info_concorrentes', 'Nenhuma informação')}
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_destaques(dados, contexto_atual):
    prompt = f"""
    Com base no contexto abaixo e nos dados de desempenho, escreva 3-5 DESTAQUES principais para o relatório executivo.
    Seja objetivo e destaque os maiores sucessos e descobertas.
    
    **Contexto Atual:**
    {contexto_atual}
    
    **Dados Comparativos:**
    - Visualizações: Atual {dados.get('visualizacoes_atual', 0)} | Mês Passado {dados.get('visualizacoes_mes_passado', 0)} | Variação: {dados.get('var_visualizacoes_mes', 0):.1f}%
    - Impressões: Atual {dados.get('impressoes_atual', 0)} | Mês Passado {dados.get('impressoes_mes_passado', 0)} | Variação: {dados.get('var_impressoes_mes', 0):.1f}%
    - Cliques: Atual {dados.get('cliques_atual', 0)} | Mês Passado {dados.get('cliques_mes_passado', 0)} | Variação: {dados.get('var_cliques_mes', 0):.1f}%
    - Engajamentos: Atual {dados.get('engajamentos_atual', 0)} | Mês Passado {dados.get('engajamentos_mes_passado', 0)} | Variação: {dados.get('var_engajamentos_mes', 0):.1f}%
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_criativos(dados, descricoes_imagens, destaques):
    prompt = f"""
    Com base nos DESTAQUES e nas descrições dos criativos, escreva uma análise detalhada sobre os CRIATIVOS.
    Explique como os elementos visuais contribuíram para o desempenho.
    
    **Destaques do Período:**
    {destaques}
    
    **Descrições dos Criativos:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhuma imagem fornecida"}
    
    **Métricas de Criativos:**
    - Custo por Engajamento: R$ {dados.get('cpe_atual', 0):.2f}
    - Custo por Clique: R$ {dados.get('cpc_atual', 0):.2f}
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_midias_pagas(dados, analise_criativos):
    prompt = f"""
    Com base na análise de criativos e nos dados abaixo, escreva uma análise detalhada de MÍDIAS PAGAS.
    Inclua performance por canal e recomendações de otimização.
    
    **Análise de Criativos:**
    {analise_criativos}
    
    **Investimentos por Canal (Atual):**
    - Facebook: R$ {dados.get('investimento_fb_atual', 0):,.2f}
    - Instagram: R$ {dados.get('investimento_ig_atual', 0):,.2f}
    - TikTok: R$ {dados.get('investimento_tt_atual', 0):,.2f}
    - Display: R$ {dados.get('investimento_display_atual', 0):,.2f}
    - YouTube: R$ {dados.get('investimento_yt_atual', 0):,.2f}
    - PMax: R$ {dados.get('investimento_pmax_atual', 0):,.2f}
    
    **Métricas de Performance:**
    - CPM: R$ {dados.get('cpm_atual', 0):.2f}
    - CPC: R$ {dados.get('cpc_atual', 0):.2f}
    - CPE: R$ {dados.get('cpe_atual', 0):.2f}
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_analise_seo(dados, analise_midias_pagas):
    prompt = f"""
    Com base na análise de mídias pagas e nos dados de SEO abaixo, escreva uma análise detalhada de SEO + CONTEÚDO.
    
    **Análise de Mídias Pagas:**
    {analise_midias_pagas}
    
    **Métricas SEO (Atual | Mês Passado):**
    - Visualizações: {dados.get('seo_visualizacoes_atual', 0)} | {dados.get('seo_visualizacoes_mes_passado', 0)}
    - Sessões: {dados.get('seo_sessoes_atual', 0)} | {dados.get('seo_sessoes_mes_passado', 0)}
    - Usuários: {dados.get('seo_usuarios_atual', 0)} | {dados.get('seo_usuarios_mes_passado', 0)}
    - Visualizações Orgânicas: {dados.get('seo_visualizacoes_org_atual', 0)} | {dados.get('seo_visualizacoes_org_mes_passado', 0)}
    - Sessões Orgânicas: {dados.get('seo_sessoes_org_atual', 0)} | {dados.get('seo_sessoes_org_mes_passado', 0)}
    - Usuários Orgânicos: {dados.get('seo_usuarios_org_atual', 0)} | {dados.get('seo_usuarios_org_mes_passado', 0)}
    
    **Top 10 Palavras-chave do Mês:**
    {dados.get('top_keywords', 'Nenhuma keyword fornecida')}
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

def gerar_proximos_passos(dados, analise_seo):
    prompt = f"""
    Com base na análise de SEO e nos dados gerais, escreva uma seção de PRÓXIMOS PASSOS E APRENDIZADOS.
    Inclua recomendações acionáveis para o próximo período.
    
    **Análise de SEO:**
    {analise_seo}
    
    **Informações de Concorrentes:**
    {dados.get('info_concorrentes', 'Nenhuma informação')}
    
    **Performance Geral:**
    - Variação Visualizações (vs mês passado): {dados.get('var_visualizacoes_mes', 0):.1f}%
    - Variação Visualizações (vs ano passado): {dados.get('var_visualizacoes_ano', 0):.1f}%
    """
    response = modelo_texto.generate_content(prompt)
    return response.text

# Formulário principal
with st.form("relatorio_form"):
    st.header("📝 Dados do Relatório")
    
    # Contexto e Destaques
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Contexto Geral")
        contexto_input = st.text_area("Contexto Atual (opcional)", height=100, placeholder="Descreva o contexto da campanha/período...")
        info_concorrentes = st.text_area("Informações de Concorrentes", height=100, placeholder="O que os concorrentes estão fazendo?")
    
    with col2:
        st.subheader("Upload de Criativos")
        imagens = st.file_uploader("Faça upload das imagens dos criativos", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    
    # Métricas Principais
    st.subheader("📊 Métricas de Performance")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Atual**")
        visualizacoes_atual = st.number_input("Visualizações", min_value=0, key="vis_atual")
        impressoes_atual = st.number_input("Impressões", min_value=0, key="imp_atual")
        cliques_atual = st.number_input("Cliques", min_value=0, key="cli_atual")
        engajamentos_atual = st.number_input("Engajamentos", min_value=0, key="eng_atual")
    
    with col2:
        st.markdown("**Mês Passado**")
        visualizacoes_mes_passado = st.number_input("Visualizações", min_value=0, key="vis_mes")
        impressoes_mes_passado = st.number_input("Impressões", min_value=0, key="imp_mes")
        cliques_mes_passado = st.number_input("Cliques", min_value=0, key="cli_mes")
        engajamentos_mes_passado = st.number_input("Engajamentos", min_value=0, key="eng_mes")
    
    with col3:
        st.markdown("**Ano Passado**")
        visualizacoes_ano_passado = st.number_input("Visualizações", min_value=0, key="vis_ano")
        impressoes_ano_passado = st.number_input("Impressões", min_value=0, key="imp_ano")
        cliques_ano_passado = st.number_input("Cliques", min_value=0, key="cli_ano")
        engajamentos_ano_passado = st.number_input("Engajamentos", min_value=0, key="eng_ano")
    
    # Investimentos
    st.subheader("💰 Investimentos por Canal")
    
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
        investimento_display_atual = st.number_input("Display (Atual)", min_value=0.0, format="%.2f")
        investimento_yt_atual = st.number_input("YouTube (Atual)", min_value=0.0, format="%.2f")
        investimento_pmax_atual = st.number_input("PMax (Atual)", min_value=0.0, format="%.2f")
    
    with col2:
        investimento_display_mes_passado = st.number_input("Display (Mês Passado)", min_value=0.0, format="%.2f")
        investimento_yt_mes_passado = st.number_input("YouTube (Mês Passado)", min_value=0.0, format="%.2f")
        investimento_pmax_mes_passado = st.number_input("PMax (Mês Passado)", min_value=0.0, format="%.2f")
    
    with col3:
        investimento_display_ano_passado = st.number_input("Display (Ano Passado)", min_value=0.0, format="%.2f")
        investimento_yt_ano_passado = st.number_input("YouTube (Ano Passado)", min_value=0.0, format="%.2f")
        investimento_pmax_ano_passado = st.number_input("PMax (Ano Passado)", min_value=0.0, format="%.2f")
    
    # Custos
    st.subheader("💰 Custos")
    
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
    st.subheader("🔍 SEO + Content")
    
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
    
    submitted = st.form_submit_button("🚀 Gerar Relatório Executivo")

if submitted:
    # Calcular totais e variações
    investimento_total_atual = (investimento_fb_atual + investimento_ig_atual + investimento_tt_atual + 
                                investimento_display_atual + investimento_yt_atual + investimento_pmax_atual)
    investimento_total_mes_passado = (investimento_fb_mes_passado + investimento_ig_mes_passado + investimento_tt_mes_passado + 
                                      investimento_display_mes_passado + investimento_yt_mes_passado + investimento_pmax_mes_passado)
    investimento_total_ano_passado = (investimento_fb_ano_passado + investimento_ig_ano_passado + investimento_tt_ano_passado + 
                                      investimento_display_ano_passado + investimento_yt_ano_passado + investimento_pmax_ano_passado)
    
    # Processar imagens
    descricoes_imagens = []
    if imagens:
        with st.spinner("Analisando imagens..."):
            for imagem_file in imagens:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_imagens.append(f"**{imagem_file.name}**: {descricao}")
    
    # Organizar dados
    dados = {
        # Métricas gerais
        'visualizacoes_atual': visualizacoes_atual,
        'visualizacoes_mes_passado': visualizacoes_mes_passado,
        'visualizacoes_ano_passado': visualizacoes_ano_passado,
        'impressoes_atual': impressoes_atual,
        'impressoes_mes_passado': impressoes_mes_passado,
        'impressoes_ano_passado': impressoes_ano_passado,
        'cliques_atual': cliques_atual,
        'cliques_mes_passado': cliques_mes_passado,
        'cliques_ano_passado': cliques_ano_passado,
        'engajamentos_atual': engajamentos_atual,
        'engajamentos_mes_passado': engajamentos_mes_passado,
        'engajamentos_ano_passado': engajamentos_ano_passado,
        
        # Investimentos
        'investimento_fb_atual': investimento_fb_atual,
        'investimento_fb_mes_passado': investimento_fb_mes_passado,
        'investimento_fb_ano_passado': investimento_fb_ano_passado,
        'investimento_ig_atual': investimento_ig_atual,
        'investimento_ig_mes_passado': investimento_ig_mes_passado,
        'investimento_ig_ano_passado': investimento_ig_ano_passado,
        'investimento_tt_atual': investimento_tt_atual,
        'investimento_tt_mes_passado': investimento_tt_mes_passado,
        'investimento_tt_ano_passado': investimento_tt_ano_passado,
        'investimento_display_atual': investimento_display_atual,
        'investimento_display_mes_passado': investimento_display_mes_passado,
        'investimento_display_ano_passado': investimento_display_ano_passado,
        'investimento_yt_atual': investimento_yt_atual,
        'investimento_yt_mes_passado': investimento_yt_mes_passado,
        'investimento_yt_ano_passado': investimento_yt_ano_passado,
        'investimento_pmax_atual': investimento_pmax_atual,
        'investimento_pmax_mes_passado': investimento_pmax_mes_passado,
        'investimento_pmax_ano_passado': investimento_pmax_ano_passado,
        'investimento_total_atual': investimento_total_atual,
        'investimento_total_mes_passado': investimento_total_mes_passado,
        'investimento_total_ano_passado': investimento_total_ano_passado,
        
        # Custos
        'cpe_atual': cpe_atual,
        'cpe_mes_passado': cpe_mes_passado,
        'cpe_ano_passado': cpe_ano_passado,
        'cpc_atual': cpc_atual,
        'cpc_mes_passado': cpc_mes_passado,
        'cpc_ano_passado': cpc_ano_passado,
        'cpv_atual': cpv_atual,
        'cpv_mes_passado': cpv_mes_passado,
        'cpv_ano_passado': cpv_ano_passado,
        'cpm_atual': cpm_atual,
        'cpm_mes_passado': cpm_mes_passado,
        'cpm_ano_passado': cpm_ano_passado,
        
        # SEO
        'seo_visualizacoes_atual': seo_visualizacoes_atual,
        'seo_visualizacoes_mes_passado': seo_visualizacoes_mes_passado,
        'seo_visualizacoes_ano_passado': seo_visualizacoes_ano_passado,
        'seo_sessoes_atual': seo_sessoes_atual,
        'seo_sessoes_mes_passado': seo_sessoes_mes_passado,
        'seo_sessoes_ano_passado': seo_sessoes_ano_passado,
        'seo_usuarios_atual': seo_usuarios_atual,
        'seo_usuarios_mes_passado': seo_usuarios_mes_passado,
        'seo_usuarios_ano_passado': seo_usuarios_ano_passado,
        'seo_visualizacoes_org_atual': seo_visualizacoes_org_atual,
        'seo_visualizacoes_org_mes_passado': seo_visualizacoes_org_mes_passado,
        'seo_visualizacoes_org_ano_passado': seo_visualizacoes_org_ano_passado,
        'seo_sessoes_org_atual': seo_sessoes_org_atual,
        'seo_sessoes_org_mes_passado': seo_sessoes_org_mes_passado,
        'seo_sessoes_org_ano_passado': seo_sessoes_org_ano_passado,
        'seo_usuarios_org_atual': seo_usuarios_org_atual,
        'seo_usuarios_org_mes_passado': seo_usuarios_org_mes_passado,
        'seo_usuarios_org_ano_passado': seo_usuarios_org_ano_passado,
        
        # Variações calculadas
        'var_visualizacoes_mes': calcular_variacao(visualizacoes_atual, visualizacoes_mes_passado),
        'var_visualizacoes_ano': calcular_variacao(visualizacoes_atual, visualizacoes_ano_passado),
        'var_impressoes_mes': calcular_variacao(impressoes_atual, impressoes_mes_passado),
        'var_impressoes_ano': calcular_variacao(impressoes_atual, impressoes_ano_passado),
        'var_cliques_mes': calcular_variacao(cliques_atual, cliques_mes_passado),
        'var_cliques_ano': calcular_variacao(cliques_atual, cliques_ano_passado),
        'var_engajamentos_mes': calcular_variacao(engajamentos_atual, engajamentos_mes_passado),
        'var_engajamentos_ano': calcular_variacao(engajamentos_atual, engajamentos_ano_passado),
        
        # Informações adicionais
        'info_concorrentes': info_concorrentes,
        'top_keywords': top_keywords,
        'contexto_input': contexto_input
    }
    
    # Gerar relatório
    with st.spinner("Gerando relatório executivo... (isso pode levar alguns minutos)"):
        try:
            # Gerar cada seção sequencialmente
            contexto_atual = gerar_contexto_atual(dados, descricoes_imagens)
            destaques = gerar_destaques(dados, contexto_atual)
            analise_criativos = gerar_analise_criativos(dados, descricoes_imagens, destaques)
            analise_midias_pagas = gerar_analise_midias_pagas(dados, analise_criativos)
            analise_seo = gerar_analise_seo(dados, analise_midias_pagas)
            proximos_passos = gerar_proximos_passos(dados, analise_seo)
            
            # Armazenar resultados
            st.session_state.relatorio_gerado = True
            st.session_state.dados_processados = dados
            st.session_state.descricoes_imagens = descricoes_imagens
            st.session_state.contexto_atual = contexto_atual
            st.session_state.destaques = destaques
            st.session_state.analise_criativos = analise_criativos
            st.session_state.analise_midias_pagas = analise_midias_pagas
            st.session_state.analise_seo = analise_seo
            st.session_state.proximos_passos = proximos_passos
            
        except Exception as e:
            st.error(f"Erro ao gerar relatório: {str(e)}")

# Exibir relatório
if st.session_state.relatorio_gerado:
    st.markdown("---")
    st.header("📄 Relatório Executivo Gerado")
    
    dados = st.session_state.dados_processados
    
    # Tabela de variações
    st.subheader("📊 Comparativos de Performance")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Visualizações (vs Mês Passado)", 
                 f"{dados.get('visualizacoes_atual', 0):,}", 
                 f"{dados.get('var_visualizacoes_mes', 0):.1f}%")
    with col2:
        st.metric("Impressões (vs Mês Passado)", 
                 f"{dados.get('impressoes_atual', 0):,}", 
                 f"{dados.get('var_impressoes_mes', 0):.1f}%")
    with col3:
        st.metric("Cliques (vs Mês Passado)", 
                 f"{dados.get('cliques_atual', 0):,}", 
                 f"{dados.get('var_cliques_mes', 0):.1f}%")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Visualizações (vs Ano Passado)", 
                 f"{dados.get('visualizacoes_atual', 0):,}", 
                 f"{dados.get('var_visualizacoes_ano', 0):.1f}%")
    with col2:
        st.metric("Impressões (vs Ano Passado)", 
                 f"{dados.get('impressoes_atual', 0):,}", 
                 f"{dados.get('var_impressoes_ano', 0):.1f}%")
    with col3:
        st.metric("Cliques (vs Ano Passado)", 
                 f"{dados.get('cliques_atual', 0):,}", 
                 f"{dados.get('var_cliques_ano', 0):.1f}%")
    
    st.markdown("---")
    
    # Seções do relatório
    st.subheader("📌 Contexto Atual")
    st.write(st.session_state.contexto_atual)
    
    st.subheader("⭐ Destaques")
    st.write(st.session_state.destaques)
    
    st.subheader("🎨 Análise de Criativos")
    if st.session_state.descricoes_imagens:
        for desc in st.session_state.descricoes_imagens:
            st.markdown(desc)
    st.write(st.session_state.analise_criativos)
    
    st.subheader("💰 Mídias Pagas")
    st.write(st.session_state.analise_midias_pagas)
    
    st.subheader("🔍 SEO + Content")
    st.write(st.session_state.analise_seo)
    
    st.subheader("📈 Próximos Passos e Aprendizados")
    st.write(st.session_state.proximos_passos)
    
    # Botão para baixar relatório
    relatorio_completo = f"""
# RELATÓRIO EXECUTIVO - {datetime.now().strftime('%d/%m/%Y')}

## 📊 Comparativos de Performance

**Vs Mês Passado:**
- Visualizações: {dados.get('visualizacoes_atual', 0):,} ({dados.get('var_visualizacoes_mes', 0):.1f}%)
- Impressões: {dados.get('impressoes_atual', 0):,} ({dados.get('var_impressoes_mes', 0):.1f}%)
- Cliques: {dados.get('cliques_atual', 0):,} ({dados.get('var_cliques_mes', 0):.1f}%)
- Engajamentos: {dados.get('engajamentos_atual', 0):,} ({dados.get('var_engajamentos_mes', 0):.1f}%)

**Vs Ano Passado:**
- Visualizações: {dados.get('visualizacoes_atual', 0):,} ({dados.get('var_visualizacoes_ano', 0):.1f}%)
- Impressões: {dados.get('impressoes_atual', 0):,} ({dados.get('var_impressoes_ano', 0):.1f}%)
- Cliques: {dados.get('cliques_atual', 0):,} ({dados.get('var_cliques_ano', 0):.1f}%)
- Engajamentos: {dados.get('engajamentos_atual', 0):,} ({dados.get('var_engajamentos_ano', 0):.1f}%)

## 📌 Contexto Atual
{st.session_state.contexto_atual}

## ⭐ Destaques
{st.session_state.destaques}

## 🎨 Análise de Criativos
{chr(10).join(st.session_state.descricoes_imagens) if st.session_state.descricoes_imagens else "Nenhum criativo enviado"}
{st.session_state.analise_criativos}

## 💰 Mídias Pagas
{st.session_state.analise_midias_pagas}

## 🔍 SEO + Content
{st.session_state.analise_seo}

## 📈 Próximos Passos e Aprendizados
{st.session_state.proximos_passos}

---
*Relatório gerado por IA em {datetime.now().strftime('%d/%m/%Y %H:%M')}*
"""
    
    st.download_button(
        label="📥 Baixar Relatório Completo (Markdown)",
        data=relatorio_completo,
        file_name=f"relatorio_executivo_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown"
    )

import io
import streamlit as st
import pandas as pd
from PIL import Image

from data.bigquery import fetch_bigquery_data, fetch_products_data
from ai.models import descrever_imagem, calcular_variacao
from ai.prompts import (
    gerar_cenario_atual, gerar_destaques, gerar_produtos_destaque,
    gerar_midias_pagas, gerar_social, gerar_seo_content,
    gerar_aprendizados, gerar_proximos_passos
)

TIPOS_ARQUIVO = ['csv', 'xlsx', 'xls', 'pdf', 'docx', 'doc', 'txt']

FRENTES_DISPONIVEIS = [
    "📊 Performance & Métricas",
    "💰 Mídias Pagas",
    "📱 Social & Criativos",
    "🔍 SEO & Conteúdo",
]

FRENTES_PADRAO = FRENTES_DISPONIVEIS  # todas selecionadas por padrão


def _ler_arquivo(arquivo):
    """Lê qualquer arquivo suportado e retorna texto para o prompt."""
    nome = arquivo.name.lower()
    try:
        if nome.endswith('.csv'):
            df = pd.read_csv(arquivo)
            preview = df.head(80).to_markdown(index=False)
            stats = df.describe(include='all').to_markdown()
            return (
                f"### Arquivo: {arquivo.name}\n"
                f"- **Linhas:** {len(df)} | **Colunas:** {len(df.columns)}\n"
                f"- **Colunas:** {', '.join(df.columns.tolist())}\n\n"
                f"**Resumo estatístico:**\n{stats}\n\n"
                f"**Dados (primeiras 80 linhas):**\n{preview}"
            )
        elif nome.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(arquivo)
            preview = df.head(80).to_markdown(index=False)
            stats = df.describe(include='all').to_markdown()
            return (
                f"### Arquivo: {arquivo.name}\n"
                f"- **Linhas:** {len(df)} | **Colunas:** {len(df.columns)}\n"
                f"- **Colunas:** {', '.join(df.columns.tolist())}\n\n"
                f"**Resumo estatístico:**\n{stats}\n\n"
                f"**Dados (primeiras 80 linhas):**\n{preview}"
            )
        elif nome.endswith('.txt'):
            texto = arquivo.read().decode('utf-8', errors='ignore')
            return f"### Arquivo: {arquivo.name}\n\n{texto[:8000]}"
        elif nome.endswith('.pdf'):
            try:
                import pypdf
                reader = pypdf.PdfReader(arquivo)
                texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(arquivo)
                    texto = "\n".join(p.extract_text() or "" for p in reader.pages)
                except ImportError:
                    return f"### Arquivo: {arquivo.name}\n⚠️ Instale pypdf para ler PDFs: pip install pypdf"
            return f"### Arquivo: {arquivo.name}\n\n{texto[:8000]}"
        elif nome.endswith(('.docx', '.doc')):
            try:
                import docx as docx_lib
                doc = docx_lib.Document(arquivo)
                texto = "\n".join(p.text for p in doc.paragraphs)
                return f"### Arquivo: {arquivo.name}\n\n{texto[:8000]}"
            except ImportError:
                return f"### Arquivo: {arquivo.name}\n⚠️ Instale python-docx para ler arquivos Word."
        else:
            texto = arquivo.read().decode('utf-8', errors='ignore')
            return f"### Arquivo: {arquivo.name}\n\n{texto[:8000]}"
    except Exception as e:
        return f"### Arquivo: {arquivo.name}\n⚠️ Erro ao ler: {str(e)}"


def renderizar_sincronizacao_bq(client_bq):
    """Botão de sincronização com BigQuery."""
    if st.button("🔄 Atualizar Dados (Syngenta)"):
        with st.spinner("Buscando dados históricos no BigQuery..."):
            res = fetch_bigquery_data(client_bq)

        if res:
            st.session_state.spend_atual = float(res.get('spend_atual') or 0.0)
            st.session_state.spend_mes = float(res.get('spend_mes') or 0.0)
            st.session_state.spend_ano = float(res.get('spend_ano') or 0.0)
            st.session_state.sess_atual = int(res.get('sess_atual') or 0)
            st.session_state.sess_mes = int(res.get('sess_mes') or 0)
            st.session_state.sess_ano = int(res.get('sess_ano') or 0)
            st.session_state.reach_atual = int(res.get('reach_atual') or 0)
            st.session_state.reach_mes = int(res.get('reach_mes') or 0)
            st.session_state.reach_ano = int(res.get('reach_ano') or 0)
            st.session_state.vtp_atual = int(res.get('vtp_atual') or 0)
            st.session_state.vtp_mes = int(res.get('vtp_mes') or 0)
            st.session_state.vtp_ano = int(res.get('vtp_ano') or 0)
            st.session_state.cli_atual = int(res.get('cli_atual') or 0)
            st.session_state.cli_mes = int(res.get('cli_mes') or 0)
            st.session_state.cli_ano = int(res.get('cli_ano') or 0)
            st.session_state.imp_atual = int(res.get('imp_atual') or 0)
            st.session_state.imp_mes = int(res.get('imp_mes') or 0)
            st.session_state.imp_ano = int(res.get('imp_ano') or 0)
            st.session_state.eng_atual = int(res.get('eng_atual') or 0)
            st.session_state.eng_mes = int(res.get('eng_mes') or 0)
            st.session_state.eng_ano = int(res.get('eng_ano') or 0)
            st.session_state.cpc_atual = float(res.get('cpc_atual') or 0.0)
            st.session_state.cpc_mes = float(res.get('cpc_mes') or 0.0)
            st.session_state.cpc_ano = float(res.get('cpc_ano') or 0.0)
            st.session_state.cpm_atual = float(res.get('cpm_atual') or 0.0)
            st.session_state.cpm_mes = float(res.get('cpm_mes') or 0.0)
            st.session_state.cpm_ano = float(res.get('cpm_ano') or 0.0)
            st.session_state.ctr_atual = float(res.get('ctr_atual') or 0.0)
            st.session_state.ctr_mes = float(res.get('ctr_mes') or 0.0)
            st.session_state.ctr_ano = float(res.get('ctr_ano') or 0.0)
            st.session_state.fb_atual = float(res.get('spend_fb_atual') or 0.0)
            st.session_state.fb_mes = float(res.get('spend_fb_mes') or 0.0)
            st.session_state.fb_ano = float(res.get('spend_fb_ano') or 0.0)
            st.session_state.google_atual = float(res.get('spend_google_atual') or 0.0)
            st.session_state.google_mes = float(res.get('spend_google_mes') or 0.0)
            st.session_state.google_ano = float(res.get('spend_google_ano') or 0.0)
            st.session_state.tt_atual = float(res.get('spend_tiktok_atual') or 0.0)
            st.session_state.tt_mes = float(res.get('spend_tiktok_mes') or 0.0)
            st.session_state.tt_ano = float(res.get('spend_tiktok_ano') or 0.0)
            st.success("Dados sincronizados com sucesso!")
            st.rerun()


def renderizar_formulario():
    """Renderiza o formulário principal. Retorna (submitted, form_values) ou (False, None)."""

    def criar_linha_metrica(label, key_prefix):
        c1, c2, c3 = st.columns(3)
        fmt = "%.2f" if any(x in key_prefix for x in ["invest", "spend", "cpc", "cpm", "cpe", "cpv", "ctr"]) else "%.0f"
        with c1:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_atual", format=fmt)
        with c2:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_mes", format=fmt)
        with c3:
            st.number_input(f"{label}", min_value=0.0, key=f"{key_prefix}_ano", format=fmt)

    with st.form("relatorio_form"):
        st.header("📝 Dados do Relatório")

        # ── SELEÇÃO DE FRENTES ──────────────────────────────────────────
        st.subheader("🗂️ Frentes do Relatório")
        st.markdown("Selecione quais seções devem compor o relatório:")
        frentes_selecionadas = st.multiselect(
            "Frentes",
            options=FRENTES_DISPONIVEIS,
            default=FRENTES_PADRAO,
            label_visibility="collapsed",
        )

        inc_performance = "📊 Performance & Métricas" in frentes_selecionadas
        inc_midias      = "💰 Mídias Pagas"           in frentes_selecionadas
        inc_social      = "📱 Social & Criativos"      in frentes_selecionadas
        inc_seo         = "🔍 SEO & Conteúdo"          in frentes_selecionadas

        st.markdown("---")

        # ── CONTEXTO GERAL ──────────────────────────────────────────────
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Contexto Geral")
            contexto_input = st.text_area("Contexto Atual (opcional)", height=100,
                                          placeholder="Descreva o contexto da campanha/período...")
            info_concorrentes = st.text_area("Informações de Concorrentes", height=100,
                                              placeholder="O que os concorrentes estão fazendo?")
        with col2:
            st.subheader("Upload de Criativos")
            st.markdown("**Criativos do Mês Atual**")
            imagens = st.file_uploader("Faça upload dos criativos atuais", type=['png', 'jpg', 'jpeg'],
                                       accept_multiple_files=True, key="upload_atual")
            st.markdown("**Criativos do Mês Passado** *(para comparação)*")
            imagens_mes_passado = st.file_uploader("Faça upload dos criativos do mês passado",
                                                   type=['png', 'jpg', 'jpeg'],
                                                   accept_multiple_files=True, key="upload_mes_passado")

        # ── PERFORMANCE & MÉTRICAS ──────────────────────────────────────
        if inc_performance:
            st.subheader("📊 Métricas de Performance")
            col_label1, col_label2, col_label3 = st.columns(3)
            with col_label1: st.markdown("### **Atual**")
            with col_label2: st.markdown("### **Mês Passado**")
            with col_label3: st.markdown("### **Ano Passado**")
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

        # ── MÍDIAS PAGAS ────────────────────────────────────────────────
        if inc_midias:
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
        else:
            # valores padrão para não quebrar os dicionários de dados
            investimento_fb_atual = investimento_ig_atual = investimento_tt_atual = 0.0
            investimento_ads_atual = investimento_yt_atual = investimento_pmax_atual = 0.0
            investimento_fb_mes_passado = investimento_ig_mes_passado = investimento_tt_mes_passado = 0.0
            investimento_ads_mes_passado = investimento_yt_mes_passado = investimento_pmax_mes_passado = 0.0
            investimento_fb_ano_passado = investimento_ig_ano_passado = investimento_tt_ano_passado = 0.0
            investimento_ads_ano_passado = investimento_yt_ano_passado = investimento_pmax_ano_passado = 0.0

        # ── SOCIAL & CRIATIVOS ──────────────────────────────────────────
        if inc_social:
            st.subheader("📱 Dados de Social")
            st.markdown(
                "Upload de dados das plataformas sociais. Aceita **CSV, Excel, PDF, Word, TXT** — "
                "o sistema interpreta qualquer formato via IA."
            )
            social_arquivos = st.file_uploader(
                "Upload de dados de Social",
                type=TIPOS_ARQUIVO,
                accept_multiple_files=True,
                key="upload_social_arquivos",
            )
        else:
            social_arquivos = []

        # ── SEO & CONTEÚDO ──────────────────────────────────────────────
        if inc_seo:
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

            top_keywords = st.text_area("Top 10 Palavras-chave do Mês", height=100,
                                        placeholder="Liste as principais palavras-chave...")

            st.markdown("**📂 Dados de SEO (arquivos)**")
            st.markdown(
                "Upload de dados de SEO. Aceita **CSV, Excel, PDF, Word, TXT** — "
                "qualquer exportação do Search Console, GA4, SEMrush, Ahrefs, etc."
            )
            seo_arquivos = st.file_uploader(
                "Upload de dados de SEO",
                type=TIPOS_ARQUIVO,
                accept_multiple_files=True,
                key="upload_seo_arquivos",
            )
        else:
            seo_visualizacoes_org_atual = seo_sessoes_org_atual = seo_usuarios_org_atual = 0
            seo_visualizacoes_org_mes_passado = seo_sessoes_org_mes_passado = seo_usuarios_org_mes_passado = 0
            seo_visualizacoes_org_ano_passado = seo_sessoes_org_ano_passado = seo_usuarios_org_ano_passado = 0
            top_keywords = ""
            seo_arquivos = []

        modelo_escolhido = st.selectbox("🤖 Modelo de IA", ["Gemini (Google)", "Claude (Anthropic)"])
        submitted = st.form_submit_button("🚀 Gerar Relatório Executivo")

    if not submitted:
        return False, None

    return True, {
        'frentes_selecionadas': frentes_selecionadas,
        'inc_performance': inc_performance,
        'inc_midias': inc_midias,
        'inc_social': inc_social,
        'inc_seo': inc_seo,
        'contexto_input': contexto_input,
        'info_concorrentes': info_concorrentes,
        'imagens': imagens,
        'imagens_mes_passado': imagens_mes_passado,
        'social_arquivos': social_arquivos,
        'seo_arquivos': seo_arquivos,
        'top_keywords': top_keywords,
        'modelo_escolhido': modelo_escolhido,
        'investimento_fb_atual': investimento_fb_atual,
        'investimento_ig_atual': investimento_ig_atual,
        'investimento_tt_atual': investimento_tt_atual,
        'investimento_ads_atual': investimento_ads_atual,
        'investimento_yt_atual': investimento_yt_atual,
        'investimento_pmax_atual': investimento_pmax_atual,
        'investimento_fb_mes_passado': investimento_fb_mes_passado,
        'investimento_ig_mes_passado': investimento_ig_mes_passado,
        'investimento_tt_mes_passado': investimento_tt_mes_passado,
        'investimento_ads_mes_passado': investimento_ads_mes_passado,
        'investimento_yt_mes_passado': investimento_yt_mes_passado,
        'investimento_pmax_mes_passado': investimento_pmax_mes_passado,
        'investimento_fb_ano_passado': investimento_fb_ano_passado,
        'investimento_ig_ano_passado': investimento_ig_ano_passado,
        'investimento_tt_ano_passado': investimento_tt_ano_passado,
        'investimento_ads_ano_passado': investimento_ads_ano_passado,
        'investimento_yt_ano_passado': investimento_yt_ano_passado,
        'investimento_pmax_ano_passado': investimento_pmax_ano_passado,
        'seo_visualizacoes_org_atual': seo_visualizacoes_org_atual,
        'seo_sessoes_org_atual': seo_sessoes_org_atual,
        'seo_usuarios_org_atual': seo_usuarios_org_atual,
        'seo_visualizacoes_org_mes_passado': seo_visualizacoes_org_mes_passado,
        'seo_sessoes_org_mes_passado': seo_sessoes_org_mes_passado,
        'seo_usuarios_org_mes_passado': seo_usuarios_org_mes_passado,
        'seo_visualizacoes_org_ano_passado': seo_visualizacoes_org_ano_passado,
        'seo_sessoes_org_ano_passado': seo_sessoes_org_ano_passado,
        'seo_usuarios_org_ano_passado': seo_usuarios_org_ano_passado,
    }


def processar_formulario(form_values, modelo_visao, modelo_gemini, cliente_anthropic, client_bq):
    """Processa os dados do formulário e executa o pipeline de etapas selecionadas."""
    fv = form_values
    modelo_escolhido = fv['modelo_escolhido']
    info_concorrentes = fv['info_concorrentes']
    top_keywords = fv['top_keywords']

    inc_performance = fv['inc_performance']
    inc_midias      = fv['inc_midias']
    inc_social      = fv['inc_social']
    inc_seo         = fv['inc_seo']

    investimento_total_atual = (fv['investimento_fb_atual'] + fv['investimento_ig_atual'] +
                                fv['investimento_tt_atual'] + fv['investimento_ads_atual'] +
                                fv['investimento_yt_atual'] + fv['investimento_pmax_atual'])
    investimento_total_mes_passado = (fv['investimento_fb_mes_passado'] + fv['investimento_ig_mes_passado'] +
                                      fv['investimento_tt_mes_passado'] + fv['investimento_ads_mes_passado'] +
                                      fv['investimento_yt_mes_passado'] + fv['investimento_pmax_mes_passado'])
    investimento_total_ano_passado = (fv['investimento_fb_ano_passado'] + fv['investimento_ig_ano_passado'] +
                                      fv['investimento_tt_ano_passado'] + fv['investimento_ads_ano_passado'] +
                                      fv['investimento_yt_ano_passado'] + fv['investimento_pmax_ano_passado'])

    # Processar criativos (imagens)
    descricoes_imagens = []
    if fv['imagens']:
        with st.spinner("Analisando criativos do mês atual..."):
            for imagem_file in fv['imagens']:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image, modelo_visao)
                descricoes_imagens.append(f"**[ATUAL] {imagem_file.name}**: {descricao}")

    descricoes_imagens_mes_passado = []
    if fv['imagens_mes_passado']:
        with st.spinner("Analisando criativos do mês passado..."):
            for imagem_file in fv['imagens_mes_passado']:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image, modelo_visao)
                descricoes_imagens_mes_passado.append(f"**[MES PASSADO] {imagem_file.name}**: {descricao}")

    # Processar arquivos de Social
    resumos_social = []
    if fv['social_arquivos']:
        with st.spinner("Lendo dados de Social..."):
            for arq in fv['social_arquivos']:
                resumos_social.append(_ler_arquivo(arq))

    # Processar arquivos de SEO
    resumos_seo = []
    if fv['seo_arquivos']:
        with st.spinner("Lendo dados de SEO..."):
            for arq in fv['seo_arquivos']:
                resumos_seo.append(_ler_arquivo(arq))

    # Montar dicionários de dados
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
        'var_invest_ano': calcular_variacao(st.session_state.get('spend_atual', 0), st.session_state.get('spend_ano', 0)),
        'var_sess_ano': calcular_variacao(st.session_state.get('sess_atual', 0), st.session_state.get('sess_ano', 0)),
        'var_reach_ano': calcular_variacao(st.session_state.get('reach_atual', 0), st.session_state.get('reach_ano', 0)),
        'var_vtp_ano': calcular_variacao(st.session_state.get('vtp_atual', 0), st.session_state.get('vtp_ano', 0)),
        'var_vis_ano': calcular_variacao(st.session_state.get('vis_atual', 0), st.session_state.get('vis_ano', 0)),
        'var_imp_ano': calcular_variacao(st.session_state.get('imp_atual', 0), st.session_state.get('imp_ano', 0)),
        'var_cli_ano': calcular_variacao(st.session_state.get('cli_atual', 0), st.session_state.get('cli_ano', 0)),
        'var_eng_ano': calcular_variacao(st.session_state.get('eng_atual', 0), st.session_state.get('eng_ano', 0)),
        'var_ctr_ano': calcular_variacao(st.session_state.get('ctr_atual', 0), st.session_state.get('ctr_ano', 0)),
        'var_invest_mes': calcular_variacao(st.session_state.get('spend_atual', 0), st.session_state.get('spend_mes', 0)),
        'var_sess_mes': calcular_variacao(st.session_state.get('sess_atual', 0), st.session_state.get('sess_mes', 0)),
        'var_reach_mes': calcular_variacao(st.session_state.get('reach_atual', 0), st.session_state.get('reach_mes', 0)),
        'var_vtp_mes': calcular_variacao(st.session_state.get('vtp_atual', 0), st.session_state.get('vtp_mes', 0)),
        'var_vis_mes': calcular_variacao(st.session_state.get('vis_atual', 0), st.session_state.get('vis_mes', 0)),
        'var_imp_mes': calcular_variacao(st.session_state.get('imp_atual', 0), st.session_state.get('imp_mes', 0)),
        'var_cli_mes': calcular_variacao(st.session_state.get('cli_atual', 0), st.session_state.get('cli_mes', 0)),
        'var_eng_mes': calcular_variacao(st.session_state.get('eng_atual', 0), st.session_state.get('eng_mes', 0)),
        'var_ctr_mes': calcular_variacao(st.session_state.get('ctr_atual', 0), st.session_state.get('ctr_mes', 0)),
        'info_concorrentes': info_concorrentes,
        'contexto_input': fv['contexto_input'],
        'cpe_atual': st.session_state.get('cpe_atual', 0),
        'cpc_atual': st.session_state.get('cpc_atual', 0),
        'top_keywords': top_keywords,
    }

    dados_custos = {
        'cpe_atual': st.session_state.get('cpe_atual', 0),
        'cpc_atual': st.session_state.get('cpc_atual', 0),
        'cpv_atual': st.session_state.get('cpv_atual', 0),
        'cpm_atual': st.session_state.get('cpm_atual', 0),
        'var_cpe_mes': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_mes', 0)),
        'var_cpc_mes': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_mes', 0)),
        'var_cpv_mes': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_mes', 0)),
        'var_cpm_mes': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_mes', 0)),
        'var_cpe_ano': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_ano', 0)),
        'var_cpc_ano': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_ano', 0)),
        'var_cpv_ano': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_ano', 0)),
        'var_cpm_ano': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_ano', 0)),
    }

    dados_investimentos = {
        'fb_atual': st.session_state.get('fb_atual', 0),
        'ig_atual': st.session_state.get('ig_atual', 0),
        'tt_atual': st.session_state.get('tt_atual', 0),
        'google_atual': st.session_state.get('google_atual', 0),
        'yt_atual': st.session_state.get('yt_atual', 0),
        'pmax_atual': st.session_state.get('pmax_atual', 0),
        'total_atual': investimento_total_atual,
        'var_fb_mes': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_mes', 0)),
        'var_ig_mes': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_mes', 0)),
        'var_tt_mes': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_mes', 0)),
        'var_google_mes': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_mes', 0)),
        'var_yt_mes': calcular_variacao(st.session_state.get('yt_atual', 0), st.session_state.get('yt_mes', 0)),
        'var_pmax_mes': calcular_variacao(st.session_state.get('pmax_atual', 0), st.session_state.get('pmax_mes', 0)),
        'var_total_mes': calcular_variacao(investimento_total_atual, investimento_total_mes_passado),
        'var_fb_ano': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_ano', 0)),
        'var_ig_ano': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_ano', 0)),
        'var_tt_ano': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_ano', 0)),
        'var_google_ano': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_ano', 0)),
        'var_yt_ano': calcular_variacao(st.session_state.get('yt_atual', 0), st.session_state.get('yt_ano', 0)),
        'var_pmax_ano': calcular_variacao(st.session_state.get('pmax_atual', 0), st.session_state.get('pmax_ano', 0)),
        'var_total_ano': calcular_variacao(investimento_total_atual, investimento_total_ano_passado),
    }

    dados_seo = {
        'vis_total_atual': st.session_state.get('seo_vis_atual', 0),
        'vis_total_mes': st.session_state.get('seo_vis_mes', 0),
        'vis_total_ano': st.session_state.get('seo_vis_ano', 0),
        'sess_total_atual': st.session_state.get('seo_sess_atual', 0),
        'sess_total_mes': st.session_state.get('seo_sess_mes', 0),
        'sess_total_ano': st.session_state.get('seo_sess_ano', 0),
        'user_total_atual': st.session_state.get('seo_user_atual', 0),
        'user_total_mes': st.session_state.get('seo_user_mes', 0),
        'user_total_ano': st.session_state.get('seo_user_ano', 0),
        'vis_org_atual': fv['seo_visualizacoes_org_atual'],
        'vis_org_mes': fv['seo_visualizacoes_org_mes_passado'],
        'vis_org_ano': fv['seo_visualizacoes_org_ano_passado'],
        'sess_org_atual': fv['seo_sessoes_org_atual'],
        'sess_org_mes': fv['seo_sessoes_org_mes_passado'],
        'sess_org_ano': fv['seo_sessoes_org_ano_passado'],
        'user_org_atual': fv['seo_usuarios_org_atual'],
        'user_org_mes': fv['seo_usuarios_org_mes_passado'],
        'user_org_ano': fv['seo_usuarios_org_ano_passado'],
        'var_vis_total_mes': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_mes', 0)),
        'var_vis_org_mes': calcular_variacao(fv['seo_visualizacoes_org_atual'], fv['seo_visualizacoes_org_mes_passado']),
        'var_sess_org_mes': calcular_variacao(fv['seo_sessoes_org_atual'], fv['seo_sessoes_org_mes_passado']),
        'var_vis_total_ano': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_ano', 0)),
        'var_vis_org_ano': calcular_variacao(fv['seo_visualizacoes_org_atual'], fv['seo_visualizacoes_org_ano_passado']),
        'var_sess_org_ano': calcular_variacao(fv['seo_sessoes_org_atual'], fv['seo_sessoes_org_ano_passado']),
        'top_keywords': top_keywords,
        'info_concorrentes': info_concorrentes,
    }

    # ── PIPELINE CONDICIONAL ────────────────────────────────────────────
    # Conta quantas etapas serão executadas para a barra de progresso
    etapas_ativas = [True, True]  # cenário atual + destaques sempre executam
    if inc_midias: etapas_ativas.append(True)
    if inc_social: etapas_ativas.append(True)
    if inc_seo: etapas_ativas.append(True)
    etapas_ativas += [True, True]  # aprendizados + próximos passos sempre executam
    total_etapas = len(etapas_ativas)
    etapa_atual = 0

    try:
        progress = st.progress(0, text="Iniciando pipeline de inteligência...")

        def avanca(label):
            nonlocal etapa_atual
            etapa_atual += 1
            progress.progress(etapa_atual / total_etapas, text=label)

        with st.spinner("Cenário Atual..."):
            etapa_cenario_atual = gerar_cenario_atual(
                dados_metrica_performance, dados_investimentos, dados_custos,
                info_concorrentes, modelo_escolhido, modelo_gemini, cliente_anthropic
            )
        avanca("Cenário Atual ✓")

        with st.spinner("Destaques..."):
            etapa_destaques = gerar_destaques(etapa_cenario_atual, modelo_escolhido, modelo_gemini, cliente_anthropic)
        avanca("Destaques ✓")

        dados_produtos = fetch_products_data(client_bq)
        with st.spinner("Produtos Destaque..."):
            etapa_produtos_destaque = gerar_produtos_destaque(
                etapa_cenario_atual, dados_produtos, modelo_escolhido, modelo_gemini, cliente_anthropic
            )

        etapa_midias_pagas = ""
        if inc_midias:
            with st.spinner("Mídias Pagas..."):
                etapa_midias_pagas = gerar_midias_pagas(
                    etapa_cenario_atual, dados_investimentos, dados_custos,
                    modelo_escolhido, modelo_gemini, cliente_anthropic
                )
            avanca("Mídias Pagas ✓")

        etapa_social = ""
        if inc_social:
            with st.spinner("Social..."):
                etapa_social = gerar_social(
                    etapa_cenario_atual, descricoes_imagens, descricoes_imagens_mes_passado,
                    dados_custos, modelo_escolhido, modelo_gemini, cliente_anthropic, resumos_social
                )
            avanca("Social ✓")

        etapa_seo = ""
        if inc_seo:
            with st.spinner("SEO..."):
                etapa_seo = gerar_seo_content(
                    etapa_cenario_atual, dados_seo, dados_custos,
                    modelo_escolhido, modelo_gemini, cliente_anthropic, resumos_seo
                )
            avanca("SEO ✓")

        with st.spinner("Aprendizados..."):
            etapa_aprendizados = gerar_aprendizados(
                etapa_cenario_atual, etapa_destaques, etapa_midias_pagas, etapa_social, etapa_seo,
                dados_metrica_performance, dados_custos, dados_seo,
                modelo_escolhido, modelo_gemini, cliente_anthropic
            )
        avanca("Aprendizados ✓")

        with st.spinner("Próximos Passos..."):
            etapa_proximos_passos = gerar_proximos_passos(
                etapa_cenario_atual, etapa_aprendizados, modelo_escolhido, modelo_gemini, cliente_anthropic
            )
        avanca("Pipeline completo!")

        st.session_state.relatorio_gerado = True
        st.session_state.dados_processados = dados_metrica_performance
        st.session_state.frentes_selecionadas = fv['frentes_selecionadas']
        st.session_state.descricoes_imagens = descricoes_imagens
        st.session_state.descricoes_imagens_mes_passado = descricoes_imagens_mes_passado
        st.session_state.resumos_social_csvs = resumos_social
        st.session_state.resumos_seo_csvs = resumos_seo
        st.session_state.etapa_cenario_atual = etapa_cenario_atual
        st.session_state.etapa_destaques = etapa_destaques
        st.session_state.etapa_produtos_destaque = etapa_produtos_destaque
        st.session_state.etapa_midias_pagas = etapa_midias_pagas
        st.session_state.etapa_social = etapa_social
        st.session_state.etapa_seo = etapa_seo
        st.session_state.etapa_aprendizados = etapa_aprendizados
        st.session_state.etapa_proximos_passos = etapa_proximos_passos

        st.rerun()

    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")

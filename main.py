import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import re
from datetime import datetime
from PIL import Image
import base64
import io
from google.cloud import bigquery
from google.oauth2 import service_account
from anthropic import Anthropic
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import plotly.graph_objects as go

# =============================================================================
# CONFIGURAÇÃO INICIAL (DEVE SER A PRIMEIRA COISA DO SCRIPT)
# =============================================================================

st.set_page_config(layout="wide", page_title="Relatório Executivo - IA", page_icon="📊")

# =============================================================================
# LOCK DE SENHA
# =============================================================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("### 🔒 Acesso Restrito")
    senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
    if st.button("Entrar"):
        if senha_digitada == st.secrets.get("senha_per", ""):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

# Inicialização do estado da sessão para evitar KeyError/AttributeError
chaves_sessao = [
    'relatorio_gerado', 'descricoes_imagens', 'descricoes_imagens_mes_passado',
    'dados_processados', 'contexto_atual', 'destaques', 'analise_criativos',
    'analise_midias_pagas', 'analise_seo', 'proximos_passos',
    'diagnostico_eficiencia', 'red_flags', 'mapa_oportunidades',
    'relatorio_cliente', 'slides_cliente', 'slides_interno'
]

for chave in chaves_sessao:
    if chave not in st.session_state:
        if chave == 'relatorio_gerado':
            st.session_state[chave] = False
        elif chave in ['descricoes_imagens', 'descricoes_imagens_mes_passado', 'dados_processados']:
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
        st.error(f"❌ Erro na conexão BigQuery: {str(e)}")
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
            print(f"📊 DADOS RECUPERADOS DO BIGQUERY - {datetime.now().strftime('%H:%M:%S')}")
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

# Gemini (sempre usado para visão/imagens + fallback)
gemini_api_key = os.getenv("GEM_API_KEY") or st.secrets.get("GEM_API_KEY", "")
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

def gerar_texto(prompt, modelo_escolhido="Gemini"):
    """Roteia a geração de texto para o modelo escolhido. Usa Gemini como fallback silencioso."""
    if modelo_escolhido == "Claude (Anthropic)" and cliente_anthropic:
        try:
            response = cliente_anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception:
            # Fallback silencioso para Gemini
            response = modelo_gemini.generate_content(prompt)
            return response.text
    else:
        response = modelo_gemini.generate_content(prompt)
        return response.text

# =============================================================================
# GERAÇÃO DO RELATÓRIO EM DOCX
# =============================================================================

MACFOR_AZUL = RGBColor(0x1B, 0x3A, 0x5C)       # Azul escuro corporativo
MACFOR_AZUL_CLARO = RGBColor(0x2E, 0x86, 0xC1)  # Azul para destaques
MACFOR_CINZA = RGBColor(0x5D, 0x6D, 0x7E)       # Cinza para texto secundário
MACFOR_VERDE = RGBColor(0x27, 0xAE, 0x60)       # Verde para positivo
MACFOR_BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
COR_FUNDO_HEADER_TAB = "1B3A5C"
COR_FUNDO_LINHA_ALT = "EBF5FB"


def _configurar_estilos(doc):
    """Configura os estilos globais do documento."""
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.15

    for level, (size, color, bold) in enumerate([
        (Pt(22), MACFOR_AZUL, True),
        (Pt(16), MACFOR_AZUL, True),
        (Pt(13), MACFOR_AZUL_CLARO, True),
    ], start=1):
        h = doc.styles[f'Heading {level}']
        h.font.name = 'Calibri'
        h.font.size = size
        h.font.color.rgb = color
        h.font.bold = bold
        h.paragraph_format.space_before = Pt(18 if level == 1 else 14)
        h.paragraph_format.space_after = Pt(8)


def _adicionar_header_footer(doc, mes_ref):
    """Adiciona header e footer profissionais a todas as seções."""
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
        section.header_distance = Cm(1)
        section.footer_distance = Cm(1)

        # --- HEADER ---
        header = section.header
        header.is_linked_to_previous = False
        htable = header.add_table(rows=1, cols=2, width=Inches(6.5))
        htable.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Remove bordas da tabela do header
        for cell in htable.row_cells(0):
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                                  '<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                                  '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                                  '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="1B3A5C"/>'
                                  '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                                  '</w:tcBorders>')
            tcPr.append(tcBorders)

        left_cell = htable.cell(0, 0)
        p = left_cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run("MACFOR")
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.color.rgb = MACFOR_AZUL
        run = p.add_run("  |  Relatório Executivo")
        run.font.size = Pt(9)
        run.font.color.rgb = MACFOR_CINZA

        right_cell = htable.cell(0, 1)
        p = right_cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run(f"Syngenta  |  {mes_ref}")
        run.font.size = Pt(9)
        run.font.color.rgb = MACFOR_CINZA

        # Remove parágrafo padrão vazio do header
        if header.paragraphs and header.paragraphs[0].text == '':
            header.paragraphs[0]._element.getparent().remove(header.paragraphs[0]._element)

        # --- FOOTER ---
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Linha separadora acima do footer
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}>'
                         '<w:top w:val="single" w:sz="4" w:space="4" w:color="1B3A5C"/>'
                         '</w:pBdr>')
        pPr.append(pBdr)

        run = p.add_run("Confidencial  |  Macfor Inteligência Digital  |  Página ")
        run.font.size = Pt(8)
        run.font.color.rgb = MACFOR_CINZA

        # Campo de número de página
        fld_char_begin = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
        fld_char_sep = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
        fld_char_end = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
        instr_text = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')

        run_pg = p.add_run()
        run_pg.font.size = Pt(8)
        run_pg.font.color.rgb = MACFOR_CINZA
        run_pg._r.append(fld_char_begin)
        run_pg._r.append(instr_text)
        run_pg._r.append(fld_char_sep)
        run_pg._r.append(fld_char_end)


def _adicionar_capa(doc, mes_ref):
    """Cria uma capa elegante e minimalista."""
    # Espaçamento superior
    for _ in range(6):
        doc.add_paragraph()

    # Linha decorativa superior
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    # Título principal
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    run = p.add_run("RELATÓRIO EXECUTIVO")
    run.font.size = Pt(32)
    run.font.bold = True
    run.font.color.rgb = MACFOR_AZUL
    run.font.name = 'Calibri'

    # Subtítulo
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    run = p.add_run("Inteligência de Mercado & Performance Digital")
    run.font.size = Pt(14)
    run.font.color.rgb = MACFOR_CINZA
    run.font.name = 'Calibri'

    # Linha decorativa inferior
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    # Espaçamento
    for _ in range(3):
        doc.add_paragraph()

    # Bloco Cliente / Agência
    dados_capa = [
        ("CLIENTE", "Syngenta"),
        ("AGÊNCIA", "Macfor Inteligência Digital"),
        ("PERÍODO", mes_ref),
        ("DATA DE EMISSÃO", datetime.now().strftime("%d de %B de %Y").replace(
            "January", "Janeiro").replace("February", "Fevereiro").replace(
            "March", "Março").replace("April", "Abril").replace(
            "May", "Maio").replace("June", "Junho").replace(
            "July", "Julho").replace("August", "Agosto").replace(
            "September", "Setembro").replace("October", "Outubro").replace(
            "November", "Novembro").replace("December", "Dezembro")),
    ]
    for label, valor in dados_capa:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{label}: ")
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = MACFOR_AZUL
        run = p.add_run(valor)
        run.font.size = Pt(10)
        run.font.color.rgb = MACFOR_CINZA

    # Quebra de página após a capa
    doc.add_page_break()


def _adicionar_sumario(doc):
    """Adiciona sumário (Table of Contents) via campo do Word."""
    p = doc.add_heading("Sumário", level=1)

    # Instrução de campo TOC
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    fld_char_begin = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
    instr_text = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText>')
    fld_char_sep = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>')
    fld_char_end = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')

    run._r.append(fld_char_begin)
    run._r.append(instr_text)
    run._r.append(fld_char_sep)

    # Texto placeholder
    run_placeholder = paragraph.add_run("[Atualize o sumário no Word: clique com botão direito > Atualizar campo]")
    run_placeholder.font.color.rgb = MACFOR_CINZA
    run_placeholder.font.size = Pt(9)
    run_placeholder.font.italic = True

    run2 = paragraph.add_run()
    run2._r.append(fld_char_end)

    doc.add_page_break()


def _adicionar_tabela_metricas(doc, titulo, dados_linhas):
    """Adiciona uma tabela de métricas elegante.

    dados_linhas: list de tuples (metrica, atual, variacao_mes, variacao_ano)
    """
    doc.add_heading(titulo, level=2)

    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'

    # Cabeçalho
    headers = ["Métrica", "Valor Atual", "Var. MoM", "Var. YoY"]
    for i, header_text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(header_text)
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = MACFOR_BRANCO
        run.font.name = 'Calibri'
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{COR_FUNDO_HEADER_TAB}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    # Linhas de dados
    for idx, (metrica, valor, var_mes, var_ano) in enumerate(dados_linhas):
        row = table.add_row()
        valores = [metrica, valor, var_mes, var_ano]
        for i, val in enumerate(valores):
            cell = row.cells[i]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            run.font.size = Pt(9)
            run.font.name = 'Calibri'
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT

            # Colorir variações
            if i >= 2 and isinstance(val, str):
                if val.startswith('+'):
                    run.font.color.rgb = MACFOR_VERDE
                elif val.startswith('-'):
                    run.font.color.rgb = RGBColor(0xE7, 0x4C, 0x3C)

            # Fundo alternado
            if idx % 2 == 0:
                shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{COR_FUNDO_LINHA_ALT}"/>')
                cell._tc.get_or_add_tcPr().append(shading)

    # Larguras das colunas
    for row in table.rows:
        row.cells[0].width = Cm(5.5)
        row.cells[1].width = Cm(3.5)
        row.cells[2].width = Cm(3)
        row.cells[3].width = Cm(3)

    doc.add_paragraph()  # Espaçamento


def _formatar_variacao(valor):
    """Formata variação com sinal."""
    if valor > 0:
        return f"+{valor:.1f}%"
    elif valor < 0:
        return f"{valor:.1f}%"
    return "0.0%"


def _formatar_numero(valor, prefixo="", sufixo=""):
    """Formata número com separador de milhar."""
    if isinstance(valor, float):
        if abs(valor) < 100:
            return f"{prefixo}{valor:,.2f}{sufixo}"
        return f"{prefixo}{valor:,.0f}{sufixo}"
    return f"{prefixo}{valor:,}{sufixo}"


def _markdown_para_docx(doc, texto_md, nivel_base=2):
    """Converte texto Markdown simplificado em parágrafos do docx."""
    if not texto_md:
        return

    linhas = texto_md.split('\n')
    for linha in linhas:
        linha_strip = linha.strip()
        if not linha_strip:
            continue

        # Headings
        if linha_strip.startswith('### '):
            doc.add_heading(linha_strip[4:].strip().strip('*'), level=min(nivel_base + 1, 3))
        elif linha_strip.startswith('## '):
            doc.add_heading(linha_strip[3:].strip().strip('*'), level=nivel_base)
        elif linha_strip.startswith('# '):
            doc.add_heading(linha_strip[2:].strip().strip('*'), level=max(nivel_base - 1, 1))
        elif linha_strip.startswith('---'):
            # Linha horizontal — adiciona espaçamento sutil
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
        elif linha_strip.startswith(('- ', '* ', '• ')):
            # Lista com bullet
            texto_item = linha_strip.lstrip('-*• ').strip()
            p = doc.add_paragraph(style='List Bullet')
            _aplicar_formatacao_inline(p, texto_item)
        elif re.match(r'^\d+[\.\)] ', linha_strip):
            # Lista numerada
            texto_item = re.sub(r'^\d+[\.\)] ', '', linha_strip).strip()
            p = doc.add_paragraph(style='List Number')
            _aplicar_formatacao_inline(p, texto_item)
        else:
            p = doc.add_paragraph()
            _aplicar_formatacao_inline(p, linha_strip)


def _aplicar_formatacao_inline(paragraph, texto):
    """Aplica bold e italic inline no texto."""
    # Limpa o texto padrão do parágrafo
    paragraph.clear()

    # Regex para **bold** e *italic*
    partes = re.split(r'(\*\*.*?\*\*|\*.*?\*)', texto)
    for parte in partes:
        if parte.startswith('**') and parte.endswith('**'):
            run = paragraph.add_run(parte[2:-2])
            run.bold = True
        elif parte.startswith('*') and parte.endswith('*'):
            run = paragraph.add_run(parte[1:-1])
            run.italic = True
        else:
            paragraph.add_run(parte)


def gerar_docx_relatorio(dados, dados_investimentos, dados_custos, dados_seo,
                          contexto_atual, destaques, analise_criativos,
                          analise_midias_pagas, analise_seo, proximos_passos,
                          descricoes_imagens, descricoes_imagens_mes_passado,
                          diagnostico_eficiencia="", red_flags="", mapa_oportunidades=""):
    """Gera o relatório executivo completo em DOCX."""

    doc = Document()
    mes_ref = datetime.now().strftime("%B/%Y").replace(
        "January", "Janeiro").replace("February", "Fevereiro").replace(
        "March", "Março").replace("April", "Abril").replace(
        "May", "Maio").replace("June", "Junho").replace(
        "July", "Julho").replace("August", "Agosto").replace(
        "September", "Setembro").replace("October", "Outubro").replace(
        "November", "Novembro").replace("December", "Dezembro")

    _configurar_estilos(doc)
    _adicionar_capa(doc, mes_ref)
    _adicionar_header_footer(doc, mes_ref)
    _adicionar_sumario(doc)

    # =================================================================
    # 1. COMPARATIVOS DE PERFORMANCE
    # =================================================================
    doc.add_heading("Comparativos de Performance", level=1)

    p = doc.add_paragraph()
    run = p.add_run("Visão consolidada dos principais indicadores de performance digital, "
                     "com variações mês a mês (MoM) e ano a ano (YoY).")
    run.font.italic = True
    run.font.color.rgb = MACFOR_CINZA

    metricas_perf = [
        ("Investimento", _formatar_numero(dados.get('spend_atual', 0), "R$ "),
         _formatar_variacao(dados.get('var_invest_mes', 0)),
         _formatar_variacao(dados.get('var_invest_ano', 0))),
        ("Sessões", _formatar_numero(dados.get('sess_atual', 0)),
         _formatar_variacao(dados.get('var_sess_mes', 0)),
         _formatar_variacao(dados.get('var_sess_ano', 0))),
        ("Alcance (Reach)", _formatar_numero(dados.get('reach_atual', 0)),
         _formatar_variacao(dados.get('var_reach_mes', 0)),
         _formatar_variacao(dados.get('var_reach_ano', 0))),
        ("Video Thruplays", _formatar_numero(dados.get('vtp_atual', 0)),
         _formatar_variacao(dados.get('var_vtp_mes', 0)),
         _formatar_variacao(dados.get('var_vtp_ano', 0))),
        ("Impressões", _formatar_numero(dados.get('imp_atual', 0)),
         _formatar_variacao(dados.get('var_imp_mes', 0)),
         _formatar_variacao(dados.get('var_imp_ano', 0))),
        ("Cliques", _formatar_numero(dados.get('cli_atual', 0)),
         _formatar_variacao(dados.get('var_cli_mes', 0)),
         _formatar_variacao(dados.get('var_cli_ano', 0))),
        ("Engajamentos", _formatar_numero(dados.get('eng_atual', 0)),
         _formatar_variacao(dados.get('var_eng_mes', 0)),
         _formatar_variacao(dados.get('var_eng_ano', 0))),
        ("CTR", _formatar_numero(dados.get('ctr_atual', 0), sufixo="%"),
         _formatar_variacao(dados.get('var_ctr_mes', 0)),
         _formatar_variacao(dados.get('var_ctr_ano', 0))),
    ]

    _adicionar_tabela_metricas(doc, "Indicadores Gerais", metricas_perf)

    # Tabela de Investimentos por canal
    inv_linhas = [
        ("Facebook", _formatar_numero(dados_investimentos.get('fb_atual', 0), "R$ "),
         _formatar_variacao(dados_investimentos.get('var_fb_mes', 0)),
         _formatar_variacao(dados_investimentos.get('var_fb_ano', 0))),
        ("Instagram", _formatar_numero(dados_investimentos.get('ig_atual', 0), "R$ "),
         _formatar_variacao(dados_investimentos.get('var_ig_mes', 0)),
         _formatar_variacao(dados_investimentos.get('var_ig_ano', 0))),
        ("TikTok", _formatar_numero(dados_investimentos.get('tt_atual', 0), "R$ "),
         _formatar_variacao(dados_investimentos.get('var_tt_mes', 0)),
         _formatar_variacao(dados_investimentos.get('var_tt_ano', 0))),
        ("Google Ads", _formatar_numero(dados_investimentos.get('google_atual', 0), "R$ "),
         _formatar_variacao(dados_investimentos.get('var_google_mes', 0)),
         _formatar_variacao(dados_investimentos.get('var_google_ano', 0))),
        ("Total", _formatar_numero(dados_investimentos.get('total_atual', 0), "R$ "),
         _formatar_variacao(dados_investimentos.get('var_total_mes', 0)),
         _formatar_variacao(dados_investimentos.get('var_total_ano', 0))),
    ]

    _adicionar_tabela_metricas(doc, "Investimentos por Canal", inv_linhas)

    # Tabela de Custos
    custos_linhas = [
        ("CPC", _formatar_numero(dados_custos.get('cpc_atual', 0), "R$ "),
         _formatar_variacao(dados_custos.get('var_cpc_mes', 0)),
         _formatar_variacao(dados_custos.get('var_cpc_ano', 0))),
        ("CPM", _formatar_numero(dados_custos.get('cpm_atual', 0), "R$ "),
         _formatar_variacao(dados_custos.get('var_cpm_mes', 0)),
         _formatar_variacao(dados_custos.get('var_cpm_ano', 0))),
        ("CPE", _formatar_numero(dados_custos.get('cpe_atual', 0), "R$ "),
         _formatar_variacao(dados_custos.get('var_cpe_mes', 0)),
         _formatar_variacao(dados_custos.get('var_cpe_ano', 0))),
        ("CPV", _formatar_numero(dados_custos.get('cpv_atual', 0), "R$ "),
         _formatar_variacao(dados_custos.get('var_cpv_mes', 0)),
         _formatar_variacao(dados_custos.get('var_cpv_ano', 0))),
    ]

    _adicionar_tabela_metricas(doc, "Indicadores de Custo e Eficiência", custos_linhas)

    doc.add_page_break()

    # =================================================================
    # 2. CONTEXTO ATUAL
    # =================================================================
    doc.add_heading("Contexto Atual", level=1)
    _markdown_para_docx(doc, contexto_atual)
    doc.add_page_break()

    # =================================================================
    # 3. DESTAQUES
    # =================================================================
    doc.add_heading("Destaques do Período", level=1)
    _markdown_para_docx(doc, destaques)
    doc.add_page_break()

    # =================================================================
    # 4. ANÁLISE DE CRIATIVOS
    # =================================================================
    doc.add_heading("Análise de Criativos", level=1)

    if descricoes_imagens:
        doc.add_heading("Criativos do Mês Atual", level=2)
        for desc in descricoes_imagens:
            _markdown_para_docx(doc, desc)

    if descricoes_imagens_mes_passado:
        doc.add_heading("Criativos do Mês Passado", level=2)
        for desc in descricoes_imagens_mes_passado:
            _markdown_para_docx(doc, desc)

    doc.add_heading("Inteligência Criativa", level=2)
    _markdown_para_docx(doc, analise_criativos)
    doc.add_page_break()

    # =================================================================
    # 5. MÍDIAS PAGAS
    # =================================================================
    doc.add_heading("Mídias Pagas", level=1)
    _markdown_para_docx(doc, analise_midias_pagas)
    doc.add_page_break()

    # =================================================================
    # 6. SEO + CONTENT
    # =================================================================
    doc.add_heading("SEO + Content", level=1)

    seo_linhas = [
        ("Visualizações (Total)", _formatar_numero(dados_seo.get('vis_total_atual', 0)),
         _formatar_variacao(dados_seo.get('var_vis_total_mes', 0)),
         _formatar_variacao(dados_seo.get('var_vis_total_ano', 0))),
        ("Sessões Orgânicas", _formatar_numero(dados_seo.get('sess_org_atual', 0)),
         _formatar_variacao(dados_seo.get('var_sess_org_mes', 0)),
         _formatar_variacao(dados_seo.get('var_sess_org_ano', 0))),
        ("Visualizações Orgânicas", _formatar_numero(dados_seo.get('vis_org_atual', 0)),
         _formatar_variacao(dados_seo.get('var_vis_org_mes', 0)),
         _formatar_variacao(dados_seo.get('var_vis_org_ano', 0))),
    ]
    _adicionar_tabela_metricas(doc, "Indicadores Orgânicos", seo_linhas)

    _markdown_para_docx(doc, analise_seo)
    doc.add_page_break()

    # =================================================================
    # 7. DIAGNÓSTICO DE EFICIÊNCIA OPERACIONAL
    # =================================================================
    if diagnostico_eficiencia:
        doc.add_heading("Diagnóstico de Eficiência Operacional", level=1)
        _markdown_para_docx(doc, diagnostico_eficiencia)
        doc.add_page_break()

    # =================================================================
    # 8. RED FLAGS & PONTOS DE ATENÇÃO
    # =================================================================
    if red_flags:
        doc.add_heading("Red Flags & Pontos de Atenção", level=1)
        _markdown_para_docx(doc, red_flags)
        doc.add_page_break()

    # =================================================================
    # 9. MAPA DE OPORTUNIDADES
    # =================================================================
    if mapa_oportunidades:
        doc.add_heading("Mapa de Oportunidades", level=1)
        _markdown_para_docx(doc, mapa_oportunidades)
        doc.add_page_break()

    # =================================================================
    # 10. PRÓXIMOS PASSOS
    # =================================================================
    doc.add_heading("Próximos Passos e Aprendizados", level=1)
    _markdown_para_docx(doc, proximos_passos)

    # =================================================================
    # RODAPÉ FINAL
    # =================================================================
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 50)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(8)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Relatório gerado por IA em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    run.font.size = Pt(8)
    run.font.italic = True
    run.font.color.rgb = MACFOR_CINZA

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Macfor Inteligência Digital | macfor.com.br")
    run.font.size = Pt(8)
    run.font.color.rgb = MACFOR_AZUL

    # Salvar em buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def gerar_docx_cliente(relatorio_cliente, dados, dados_investimentos, dados_custos, dados_seo):
    """Gera DOCX do relatório para o cliente — narrativo, elegante, focado em valor."""
    doc = Document()
    mes_ref = datetime.now().strftime("%B/%Y").replace(
        "January", "Janeiro").replace("February", "Fevereiro").replace(
        "March", "Março").replace("April", "Abril").replace(
        "May", "Maio").replace("June", "Junho").replace(
        "July", "Julho").replace("August", "Agosto").replace(
        "September", "Setembro").replace("October", "Outubro").replace(
        "November", "Novembro").replace("December", "Dezembro")

    _configurar_estilos(doc)

    # Capa diferenciada para o cliente
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    run = p.add_run("RELATÓRIO DE RESULTADOS")
    run.font.size = Pt(32)
    run.font.bold = True
    run.font.color.rgb = MACFOR_AZUL

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    run = p.add_run("Performance Digital & Inteligência Estratégica")
    run.font.size = Pt(14)
    run.font.color.rgb = MACFOR_CINZA

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    for _ in range(3):
        doc.add_paragraph()

    for label, valor in [("PREPARADO PARA", "Syngenta"), ("POR", "Macfor Inteligência Digital"), ("PERÍODO", mes_ref)]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{label}: ")
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = MACFOR_AZUL
        run = p.add_run(valor)
        run.font.size = Pt(10)
        run.font.color.rgb = MACFOR_CINZA

    doc.add_page_break()
    _adicionar_header_footer(doc, mes_ref)
    _adicionar_sumario(doc)

    # Tabelas de performance
    doc.add_heading("Painel de Performance", level=1)
    p = doc.add_paragraph()
    run = p.add_run("Resultados consolidados do período com variações históricas.")
    run.font.italic = True
    run.font.color.rgb = MACFOR_CINZA

    metricas_perf = [
        ("Investimento", _formatar_numero(dados.get('spend_atual', 0), "R$ "),
         _formatar_variacao(dados.get('var_invest_mes', 0)), _formatar_variacao(dados.get('var_invest_ano', 0))),
        ("Alcance", _formatar_numero(dados.get('reach_atual', 0)),
         _formatar_variacao(dados.get('var_reach_mes', 0)), _formatar_variacao(dados.get('var_reach_ano', 0))),
        ("Impressões", _formatar_numero(dados.get('imp_atual', 0)),
         _formatar_variacao(dados.get('var_imp_mes', 0)), _formatar_variacao(dados.get('var_imp_ano', 0))),
        ("Cliques", _formatar_numero(dados.get('cli_atual', 0)),
         _formatar_variacao(dados.get('var_cli_mes', 0)), _formatar_variacao(dados.get('var_cli_ano', 0))),
        ("Engajamentos", _formatar_numero(dados.get('eng_atual', 0)),
         _formatar_variacao(dados.get('var_eng_mes', 0)), _formatar_variacao(dados.get('var_eng_ano', 0))),
        ("CTR", _formatar_numero(dados.get('ctr_atual', 0), sufixo="%"),
         _formatar_variacao(dados.get('var_ctr_mes', 0)), _formatar_variacao(dados.get('var_ctr_ano', 0))),
    ]
    _adicionar_tabela_metricas(doc, "Indicadores de Performance", metricas_perf)
    doc.add_page_break()

    # Corpo narrativo compilado pela IA
    _markdown_para_docx(doc, relatorio_cliente)

    # Rodapé
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 50)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(8)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Macfor Inteligência Digital | macfor.com.br")
    run.font.size = Pt(8)
    run.font.color.rgb = MACFOR_AZUL

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def gerar_docx_slides(conteudo_slides, tipo="cliente"):
    """Gera DOCX com guia de slides (interno ou cliente)."""
    doc = Document()
    mes_ref = datetime.now().strftime("%B/%Y").replace(
        "January", "Janeiro").replace("February", "Fevereiro").replace(
        "March", "Março").replace("April", "Abril").replace(
        "May", "Maio").replace("June", "Junho").replace(
        "July", "Julho").replace("August", "Agosto").replace(
        "September", "Setembro").replace("October", "Outubro").replace(
        "November", "Novembro").replace("December", "Dezembro")

    _configurar_estilos(doc)

    # Capa
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    titulo = "GUIA DE SLIDES — APRESENTAÇÃO CLIENTE" if tipo == "cliente" else "GUIA DE SLIDES — REVIEW INTERNO"
    run = p.add_run(titulo)
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = MACFOR_AZUL

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    sub = "Roteiro para produção do deck de apresentação ao cliente Syngenta" if tipo == "cliente" else "Roteiro para review interno da equipe Macfor"
    run = p.add_run(sub)
    run.font.size = Pt(12)
    run.font.color.rgb = MACFOR_CINZA

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("_" * 60)
    run.font.color.rgb = MACFOR_AZUL_CLARO
    run.font.size = Pt(10)

    for _ in range(3):
        doc.add_paragraph()
    for label, valor in [("CLIENTE", "Syngenta"), ("PERÍODO", mes_ref), ("USO", "Apresentação ao Cliente" if tipo == "cliente" else "Review Interno Macfor")]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{label}: ")
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = MACFOR_AZUL
        run = p.add_run(valor)
        run.font.size = Pt(10)
        run.font.color.rgb = MACFOR_CINZA

    doc.add_page_break()
    _adicionar_header_footer(doc, mes_ref)

    # Conteúdo
    doc.add_heading("Roteiro de Slides", level=1)
    p = doc.add_paragraph()
    run = p.add_run("Este documento detalha o conteúdo, visual e dados-destaque para cada slide da apresentação. "
                     "Use como briefing para o time de design.")
    run.font.italic = True
    run.font.color.rgb = MACFOR_CINZA

    _markdown_para_docx(doc, conteudo_slides)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# Estado da sessão para os cliques (Sincroniza com o BigQuery)
if 'bq_cliques' not in st.session_state:
    st.session_state.bq_cliques = {"atual": 0, "mes_passado": 0, "ano_passado": 0}

if 'relatorio_gerado' not in st.session_state:
    st.session_state.relatorio_gerado = False

# Título do aplicativo
st.title("📊 Relatório Executivo - Inteligência de Negócio")
st.markdown("*Transformando dados brutos em inteligência de mercado para seu cliente*")
st.markdown("---")

# Seletor de modelo de IA para geração de texto
col_modelo1, col_modelo2 = st.columns([1, 3])
with col_modelo1:
    modelos_disponiveis = ["Gemini"]
    if cliente_anthropic:
        modelos_disponiveis.append("Claude (Anthropic)")
    modelo_escolhido = st.selectbox("Motor de IA para texto:", modelos_disponiveis)
with col_modelo2:
    if modelo_escolhido == "Claude (Anthropic)":
        st.info("Claude gera o texto analítico. Gemini continua descrevendo as imagens.")
    else:
        st.info("Gemini gera texto e descreve imagens.")

# Estado da sessão
if 'relatorio_gerado' not in st.session_state:
    st.session_state.relatorio_gerado = False
if 'descricoes_imagens' not in st.session_state:
    st.session_state.descricoes_imagens = []
if 'descricoes_imagens_mes_passado' not in st.session_state:
    st.session_state.descricoes_imagens_mes_passado = []
if 'dados_processados' not in st.session_state:
    st.session_state.dados_processados = {}

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

def gerar_yoy_para_contexto(dados_metrica_performance, descricoes_imagens, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é um Diretor de Inteligência de Mercado sênior de uma agência de marketing digital de alta performance (Macfor).
    Sua entrega NÃO é um relatório de métricas — é uma LEITURA ESTRATÉGICA DE MERCADO que posiciona o cliente como tomador de decisão informado.
    O cliente (Syngenta — multinacional do agronegócio) espera da Macfor a mesma profundidade analítica que receberia de uma consultoria McKinsey aplicada ao digital.

    Sua missão: transformar variações numéricas em INTELIGÊNCIA DE MERCADO ACIONÁVEL.
    Para cada dado, responda mentalmente antes de escrever:
    1. O QUE mudou? (fato)
    2. POR QUE mudou? (causa provável — sazonalidade agro, pressão competitiva, maturidade de campanha, mudança algorítmica)
    3. O QUE ISSO SIGNIFICA para o negócio? (implicação estratégica)
    4. QUAL É O RISCO se não agirmos? (cenário de inação)
    5. QUAL É A OPORTUNIDADE? (janela estratégica)

    Compare o desempenho ATUAL (2026) com o MESMO MÊS DO ANO PASSADO (2025) e extraia inteligência competitiva.

    **TABELA DE VARIAÇÕES YoY (Ano sobre Ano):**
    | Métrica | Variação YoY |
    |---------|-------------|
    | Investimento | {dados_metrica_performance.get('var_invest_ano', 0):+.1f}% |
    | Sessões no Site | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
    | Alcance (Reach) | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Video Thruplays | {dados_metrica_performance.get('var_vtp_ano', 0):+.1f}% |
    | Visualizações | {dados_metrica_performance.get('var_vis_ano', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |
    | Cliques | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
    | CTR (%) | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |

    **TABELA DE VARIAÇÕES MoM (Mês sobre Mês):**
    | Métrica | Variação MoM |
    |---------|-------------|
    | Investimento | {dados_metrica_performance.get('var_invest_mes', 0):+.1f}% |
    | Sessões no Site | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% |
    | Alcance (Reach) | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% |
    | Video Thruplays | {dados_metrica_performance.get('var_vtp_mes', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% |
    | Cliques | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% |
    | CTR (%) | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% |

    **VALORES ABSOLUTOS ATUAIS:**
    - Investimento: R$ {dados_metrica_performance.get('spend_atual', 0):,.2f}
    - Sessões: {dados_metrica_performance.get('sess_atual', 0):,}
    - Alcance: {dados_metrica_performance.get('reach_atual', 0):,}
    - Impressões: {dados_metrica_performance.get('imp_atual', 0):,}
    - Cliques: {dados_metrica_performance.get('cli_atual', 0):,}
    - Engajamentos: {dados_metrica_performance.get('eng_atual', 0):,}
    - CTR: {dados_metrica_performance.get('ctr_atual', 0):.2f}%

    **FRAMEWORK DE ANÁLISE OBRIGATÓRIO:**

    1. **ANÁLISE DE CORRELAÇÕES CRUZADAS:**
       - Cruze SEMPRE investimento vs. resultado: se o investimento caiu X% mas cliques subiram Y%, calcule o ganho de eficiência por real investido e comunique como "Efeito Tesoura" ou "Ganho de Produtividade Digital".
       - Cruze alcance vs. sessões: se alcance caiu mas sessões subiram, interprete como qualificação de audiência.
       - Cruze impressões vs. CTR: se impressões caíram mas CTR subiu, a mensagem está mais relevante para o público alcançado.
       - Cruze engajamento vs. cliques: se engajamento subiu mais que cliques, o conteúdo está gerando conversa (brand awareness); se cliques subiram mais, está gerando demanda.

    2. **CONTEXTO DO AGRONEGÓCIO (SYNGENTA):**
       - Considere o calendário safra (safrinha, safra de verão, entressafra) ao interpretar variações.
       - O setor agro tem ciclos de decisão longos — variações de curto prazo podem refletir movimentos de meses atrás.
       - Relacione com possíveis eventos do setor (feiras, lançamentos de produto, safra).

    3. **DIAGNÓSTICO ESTRATÉGICO:**
       - Classifique a saúde da operação: ACELERAÇÃO (métricas-chave subindo), MANUTENÇÃO (estável), ATENÇÃO (sinais de desaceleração), ou ALERTA (quedas generalizadas).
       - Identifique métricas que estão DESCOLADAS do padrão (ex: tudo subiu mas uma métrica caiu — por quê?).

    4. **PONTOS POSITIVOS (com evidência numérica):**
       - Liste os 3 maiores ganhos do período e explique o que cada um representa para o negócio.

    5. **RED FLAGS (sinais de alerta):**
       - Se alguma métrica caiu mais de 15%, classifique como RED FLAG e proponha hipótese de causa.
       - Se custos (CPC/CPM) subiram enquanto resultados caíram, sinalize pressão competitiva.

    **Descrições dos criativos utilizados no período:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhum criativo fornecido para análise."}

    **FORMATO:** Texto analítico e consultivo, sem repetições. Tom de devolutiva estratégica de alto nível.
    Estruture em: Panorama Geral > Correlações Estratégicas > Pontos Positivos > Red Flags > Implicações para o Negócio.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_analise_concorrencia(dados_metrica_performance, info_concorrentes, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o Head de Inteligência Competitiva da Macfor, agência de marketing digital de alta performance.
    Sua entrega é uma análise que posiciona o cliente (Syngenta) com clareza sobre seu cenário competitivo — como uma consultoria estratégica faria, mas aplicada ao universo digital.

    **DADOS DE PERFORMANCE DA SYNGENTA (Período Atual):**
    - Investimento Total: R$ {dados_metrica_performance.get('spend_atual', 0):,.2f}
    - Alcance: {dados_metrica_performance.get('reach_atual', 0):,}
    - Impressões: {dados_metrica_performance.get('imp_atual', 0):,}
    - CTR: {dados_metrica_performance.get('ctr_atual', 0):.2f}%
    - Cliques: {dados_metrica_performance.get('cli_atual', 0):,}
    - Engajamentos: {dados_metrica_performance.get('eng_atual', 0):,}
    - Sessões no Site: {dados_metrica_performance.get('sess_atual', 0):,}

    **VARIAÇÕES YoY da Syngenta:**
    - Investimento: {dados_metrica_performance.get('var_invest_ano', 0):+.1f}%
    - Cliques: {dados_metrica_performance.get('var_cli_ano', 0):+.1f}%
    - CTR: {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}%
    - Impressões: {dados_metrica_performance.get('var_imp_ano', 0):+.1f}%

    **INTELIGÊNCIA COMPETITIVA (Reportado pelo usuário):**
    {info_concorrentes if info_concorrentes else "Nenhuma informação específica fornecida sobre os movimentos dos concorrentes."}

    **FRAMEWORK DE ANÁLISE COMPETITIVA OBRIGATÓRIO:**

    1. **MAPA DE POSICIONAMENTO DIGITAL:**
       - Com base nos dados disponíveis, posicione a Syngenta no cenário competitivo digital do agro.
       - Se temos dados de concorrentes, compare diretamente. Se não, analise a performance da Syngenta contra benchmarks conhecidos do setor agro digital (CTR médio agro: 0.8-1.5%, CPC médio agro: R$1.50-3.00).
       - Identifique: onde a Syngenta está ACIMA do mercado (vantagem competitiva) e onde está ABAIXO (vulnerabilidade).

    2. **ANÁLISE DE AMEAÇAS:**
       - Identifique sinais de pressão competitiva nos dados (ex: CPC subindo pode indicar mais concorrentes no leilão de ads).
       - Se o custo por resultado está subindo sem aumento de investimento dos concorrentes, pode ser saturação de canal.
       - Aponte quais movimentos competitivos exigem resposta estratégica.

    3. **JANELAS DE OPORTUNIDADE:**
       - Identifique espaços onde a Syngenta pode avançar antes da concorrência.
       - Analise: canais subutilizados, formatos emergentes, nichos de audiência desprotegidos.
       - Considere o timing do agronegócio (safra, entressafra, feiras).

    4. **ANÁLISE SWOT DIGITAL (resumida):**
       - Forças: métricas acima do benchmark
       - Fraquezas: métricas abaixo do benchmark ou em queda
       - Oportunidades: gaps competitivos identificados
       - Ameaças: pressões de mercado detectadas

    5. **SHARE OF VOICE ESTIMADO:**
       - Com base no investimento e alcance, estime a participação da Syngenta no "share of voice" digital do setor.
       - Se o investimento caiu mas o alcance se manteve, a eficiência de mídia está gerando vantagem competitiva.

    **FORMATO:** Texto analítico e consultivo. Tom de briefing estratégico para C-Level.
    Estruture em: Posicionamento Competitivo > Ameaças Identificadas > Oportunidades Estratégicas > SWOT Digital > Recomendações de Posicionamento.
    CASO NÃO TENHA INFORMAÇÃO DE CONCORRENTES, analise a posição da Syngenta contra benchmarks do setor e sinalize que a coleta de inteligência competitiva deve ser priorizada.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_contexto_atual(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, analise_yoy, analise_concorrencia, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o Diretor de Estratégia e Inteligência de Mercado da Macfor — a seção "CONTEXTO ATUAL" é a ABERTURA do relatório executivo.
    Ela precisa funcionar como um BRIEFING ESTRATÉGICO DE ALTO NÍVEL que, em poucos parágrafos, posicione o C-Level da Syngenta sobre:
    (a) o que aconteceu, (b) por que aconteceu, (c) o que isso significa para o negócio, (d) o que deve ser feito.

    Pense como um sócio de consultoria estratégica entregando um board paper — cada frase deve gerar valor de decisão.

    ### DADOS DE ENTRADA (INTELLIGENCE FEED):

    **1. ANÁLISE HISTÓRICA YoY (já processada):**
    {analise_yoy}

    **2. CENÁRIO COMPETITIVO (já processado):**
    {analise_concorrencia}

    **3. PAINEL DE INVESTIMENTO:**
    | Canal | Investimento Atual | Var. MoM | Var. YoY |
    |-------|-------------------|----------|----------|
    | Total | R$ {dados_investimentos.get('total_atual', 0):,.2f} | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |
    | Meta (FB+IG) | R$ {dados_investimentos.get('fb_atual', 0) + dados_investimentos.get('ig_atual', 0):,.2f} | — | — |
    | Google Ads | R$ {dados_investimentos.get('google_atual', 0):,.2f} | {dados_investimentos.get('var_google_mes', 0):+.1f}% | {dados_investimentos.get('var_google_ano', 0):+.1f}% |
    | TikTok | R$ {dados_investimentos.get('tt_atual', 0):,.2f} | {dados_investimentos.get('var_tt_mes', 0):+.1f}% | {dados_investimentos.get('var_tt_ano', 0):+.1f}% |

    **4. PAINEL DE EFICIÊNCIA:**
    | Indicador | Valor Atual | Var. MoM | Var. YoY |
    |-----------|------------|----------|----------|
    | CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
    | CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |
    | CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
    | CTR | {dados_metrica_performance.get('ctr_atual', 0):.2f}% | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |

    **5. PAINEL DE RESULTADOS:**
    | Métrica | Valor Atual | Var. MoM | Var. YoY |
    |---------|------------|----------|----------|
    | Alcance | {dados_metrica_performance.get('reach_atual', 0):,} | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('imp_atual', 0):,} | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |
    | Cliques | {dados_metrica_performance.get('cli_atual', 0):,} | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('eng_atual', 0):,} | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
    | Sessões | {dados_metrica_performance.get('sess_atual', 0):,} | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |

    **6. CRIATIVOS:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhuma imagem fornecida"}

    ### FRAMEWORK DE ANÁLISE OBRIGATÓRIO:

    **A) DIAGNÓSTICO DE SAÚDE DA OPERAÇÃO DIGITAL:**
    Classifique em: ACELERAÇÃO / MANUTENÇÃO / ATENÇÃO / ALERTA — com justificativa baseada em dados.

    **B) ANÁLISE POR PILAR ESTRATÉGICO:**
    1. **Saúde Financeira e ROI:** O cliente está pagando mais ou menos por resultado? Calcule "custo por resultado" implícito e compare com períodos anteriores. Se investimento caiu mas resultados se mantiveram, destaque o EFEITO TESOURA como ganho de produtividade.
    2. **Pressão de Mercado e Competitividade:** O que os custos de mídia revelam sobre a dinâmica competitiva? CPC/CPM subindo = mais concorrentes no leilão. CPC/CPM caindo = oportunidade de dominar share.
    3. **Alavancagem Criativa:** Os criativos estão gerando diferenciação? Correlacione CTR com elementos visuais/narrativos identificados. CTR acima de 1.5% no agro = criativo excepcional.
    4. **Funil de Conversão Digital:** Analise o fluxo Impressões > Cliques > Sessões. Onde há gargalo? Onde há eficiência?
    5. **Maturidade Digital:** Avalie se a operação está construindo ativos digitais de longo prazo (audiência, autoridade, dados de público) ou apenas comprando resultados pontuais.

    **C) PONTOS POSITIVOS (TOP 3):** com evidência numérica e implicação para o negócio.
    **D) RED FLAGS (sinais de alerta):** métricas que exigem atenção imediata, com causa provável e risco de inação.
    **E) PONTOS DE MELHORIA:** oportunidades de otimização identificadas nos dados.

    ### FORMATO:
    Texto analítico de alto nível, consultivo, sem repetições.
    Estruture em: Diagnóstico Geral > Pilares Estratégicos > Pontos Positivos > Red Flags > Pontos de Melhoria > Pautas Sugeridas para Slides.
    Ao sugerir slides: se investimento caiu mas resultados se mantiveram, sugira "Gráfico de Efeito Tesoura".
    """

    return gerar_texto(prompt, modelo_escolhido)


def gerar_destaques(dados_metrica_performance, contexto_atual, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o Head de Inteligência de Negócio da Macfor. Esta seção é o HIGHLIGHT REEL do relatório — os 5-7 insights de MAIOR IMPACTO ESTRATÉGICO do período.
    Cada destaque deve funcionar como um "headline" de inteligência: uma frase de abertura que capture a atenção do C-Level, seguida de contexto analítico que demonstre profundidade.

    O cliente (Syngenta) espera que cada destaque responda: "O que isso significa para o meu negócio e o que eu devo fazer?"

    **CONTEXTO ACUMULADO (já processado):**
    {contexto_atual}

    **DADOS DE PERFORMANCE COMPLETOS:**
    | Métrica | Atual | Var. MoM | Var. YoY |
    |---------|-------|----------|----------|
    | Investimento | R$ {dados_metrica_performance.get('spend_atual', 0):,.2f} | {dados_metrica_performance.get('var_invest_mes', 0):+.1f}% | {dados_metrica_performance.get('var_invest_ano', 0):+.1f}% |
    | Sessões | {dados_metrica_performance.get('sess_atual', 0):,} | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
    | Alcance | {dados_metrica_performance.get('reach_atual', 0):,} | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('imp_atual', 0):,} | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |
    | Cliques | {dados_metrica_performance.get('cli_atual', 0):,} | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('eng_atual', 0):,} | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
    | CTR | {dados_metrica_performance.get('ctr_atual', 0):.2f}% | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |

    **CRIATIVOS ANALISADOS:**
    {chr(10).join(st.session_state.get('descricoes_imagens', [])) if st.session_state.get('descricoes_imagens') else "Sem criativos — usar placeholders."}

    ### FRAMEWORK OBRIGATÓRIO PARA CADA DESTAQUE:

    Para cada destaque, siga esta estrutura mental (mas escreva de forma fluida, não como formulário):
    1. **HEADLINE:** Uma frase de impacto que capture o insight (ex: "Efeito Tesoura: investimento menor, resultado maior")
    2. **EVIDÊNCIA:** Dados que sustentam o insight (variações, correlações)
    3. **SIGNIFICADO:** O que isso revela sobre o mercado/público/estratégia
    4. **IMPLICAÇÃO:** O que o cliente deve fazer com essa informação

    ### CATEGORIAS OBRIGATÓRIAS DE DESTAQUES:

    1. **DESTAQUE DE EFICIÊNCIA:** Se investimento caiu mas resultado subiu/manteve → "Efeito Tesoura" / "Ganho de Produtividade Digital"
    2. **DESTAQUE DE CRESCIMENTO:** A métrica de maior crescimento positivo e o que ela indica
    3. **DESTAQUE DE RISCO:** A principal RED FLAG do período — métrica preocupante com causa e recomendação
    4. **DESTAQUE DE OPORTUNIDADE:** Janela estratégica identificada nos dados que o cliente deveria capitalizar
    5. **DESTAQUE COMPETITIVO:** O que a performance digital revela sobre o posicionamento da Syngenta vs. mercado

    Se faltar informação de criativos, use: "[INSERIR: criativo/produto campeão do período para análise visual]"

    ### FORMATO:
    Texto analítico com cada destaque claramente separado por subtítulo.
    Tom: consultivo, direto, orientado a decisão. Cada destaque deve gerar uma reação no cliente ("preciso agir sobre isso").
    Ao final, sugira pautas para slides priorizando os destaques de maior impacto.
    """

    return gerar_texto(prompt, modelo_escolhido)

def gerar_analise_criativos(dados_custos, descricoes_imagens, descricoes_imagens_mes_passado, destaques, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o Head de Inteligência Criativa da Macfor — sua análise transforma peças visuais em INTELIGÊNCIA DE NEGÓCIO.
    O cliente (Syngenta) não quer saber apenas "o que o criativo mostra" — quer entender o IMPACTO MENSURÁVEL de cada decisão criativa no resultado de negócio.

    **DESTAQUES DO PERÍODO (contexto acumulado):**
    {destaques}

    **CRIATIVOS DO MÊS ATUAL:**
    {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhum criativo do mês atual fornecido."}

    **CRIATIVOS DO MÊS PASSADO (para comparação evolutiva):**
    {chr(10).join(descricoes_imagens_mes_passado) if descricoes_imagens_mes_passado else "Nenhum criativo do mês passado fornecido."}

    **INDICADORES DE EFICIÊNCIA CRIATIVA:**
    | Indicador | Valor | Var. MoM | Var. YoY |
    |-----------|-------|----------|----------|
    | CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
    | CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
    | CPV | R$ {dados_custos.get('cpv_atual', 0):.2f} | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |
    | CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |

    ### FRAMEWORK DE INTELIGÊNCIA CRIATIVA (7 DIMENSÕES):

    **1. ESTRATÉGIA NARRATIVA E POSICIONAMENTO:**
    - Qual é a narrativa central? (autoridade técnica, identificação com produtor, aspiracional, educacional)
    - O posicionamento criativo está alinhado com os objetivos de negócio da Syngenta?
    - Como essa narrativa se diferencia dos concorrentes no agro?

    **2. PSICOLOGIA DO PÚBLICO-ALVO:**
    - Quais gatilhos psicológicos estão sendo ativados? (urgência safra, medo de perda, prova social, autoridade técnica)
    - O criativo "fala a língua" do produtor rural? (regionalismo, linguagem técnica, visual de campo)
    - Qual é o nível de sofisticação da abordagem vs. o que o público espera?

    **3. ANÁLISE DE EVOLUÇÃO CRIATIVA (se houver mês anterior):**
    - O que mudou de um mês para outro e POR QUE essa mudança faz sentido estrategicamente?
    - Quais elementos foram mantidos (e funcionam como "âncora de marca")?
    - A evolução indica APRENDIZADO DA CAMPANHA ou apenas variação sem direção?
    - Correlacione mudanças visuais/narrativas com variações de CTR/CPC/CPE.

    **4. ROI CRIATIVO (o que cada elemento visual gera de retorno):**
    - Se CPE caiu, qual elemento criativo provavelmente causou isso? (CTA mais claro, cor mais chamativa, mensagem mais direta)
    - Se CPC subiu, o criativo pode estar gerando curiosidade sem entregar a promessa (click-bait negativo)?
    - Calcule o "custo-benefício criativo": quanto cada peça está custando para engajar vs. converter.

    **5. PONTOS POSITIVOS DOS CRIATIVOS:**
    - Elementos visuais/narrativos que demonstram maturidade criativa
    - Diferenciação competitiva identificada
    - Alinhamento com tendências de consumo de conteúdo

    **6. PONTOS DE MELHORIA (com recomendação acionável):**
    - Oportunidades de otimização visual (cores, composição, CTA)
    - Gaps de formato (falta de vídeo curto, carrossel, etc.)
    - Testes A/B sugeridos com base na análise

    **7. RED FLAGS CRIATIVAS:**
    - Fadiga de criativo (mesmo conceito por muito tempo sem renovação)
    - Desalinhamento entre promessa do criativo e landing page
    - Excesso de dependência de um formato/narrativa

    ### FORMATO:
    Texto analítico e consultivo. Estruture em: Narrativa e Posicionamento > Psicologia do Público > Evolução Criativa > ROI Criativo > Pontos Positivos > Pontos de Melhoria > Red Flags > Pautas para Slides.
    Se faltar criativos: "[Inserir miniatura do criativo com maior engajamento para análise visual]"
    """
    return gerar_texto(prompt, modelo_escolhido)


def gerar_analise_midias_pagas(dados_investimentos, dados_custos, analise_criativos, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o VP de Mídia e Performance da Macfor — sua análise transforma dados de investimento em INTELIGÊNCIA DE ALOCAÇÃO ESTRATÉGICA.
    O cliente (Syngenta) precisa entender não apenas "quanto gastou e quanto rendeu", mas O QUE CADA CANAL REVELA sobre o mercado, o público e as oportunidades de crescimento.

    **ANÁLISE DE CRIATIVOS (contexto acumulado):**
    {analise_criativos}

    **PAINEL COMPLETO DE INVESTIMENTOS:**
    | Canal | Atual | Var. MoM | Var. YoY |
    |-------|-------|----------|----------|
    | Facebook | R$ {dados_investimentos.get('fb_atual', 0):,.2f} | {dados_investimentos.get('var_fb_mes', 0):+.1f}% | {dados_investimentos.get('var_fb_ano', 0):+.1f}% |
    | Instagram | R$ {dados_investimentos.get('ig_atual', 0):,.2f} | {dados_investimentos.get('var_ig_mes', 0):+.1f}% | {dados_investimentos.get('var_ig_ano', 0):+.1f}% |
    | TikTok | R$ {dados_investimentos.get('tt_atual', 0):,.2f} | {dados_investimentos.get('var_tt_mes', 0):+.1f}% | {dados_investimentos.get('var_tt_ano', 0):+.1f}% |
    | Google Ads | R$ {dados_investimentos.get('google_atual', 0):,.2f} | {dados_investimentos.get('var_google_mes', 0):+.1f}% | {dados_investimentos.get('var_google_ano', 0):+.1f}% |
    | YouTube | R$ {dados_investimentos.get('yt_atual', 0):,.2f} | — | — |
    | PMax | R$ {dados_investimentos.get('pmax_atual', 0):,.2f} | — | — |
    | **TOTAL** | **R$ {dados_investimentos.get('total_atual', 0):,.2f}** | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |

    **PAINEL DE EFICIÊNCIA:**
    | Indicador | Valor | Var. MoM | Var. YoY |
    |-----------|-------|----------|----------|
    | CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |
    | CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
    | CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
    | CPV | R$ {dados_custos.get('cpv_atual', 0):.2f} | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |

    ### FRAMEWORK DE INTELIGÊNCIA DE MÍDIA (6 DIMENSÕES):

    **1. EFICIÊNCIA DE CAPITAL (ROI por Canal):**
    - Para cada canal com investimento > 0, calcule a relação investimento/resultado implícita.
    - Identifique: qual canal está gerando mais resultado por real investido?
    - Se o investimento total caiu mas os resultados se mantiveram: destaque como GANHO DE PRODUTIVIDADE OPERACIONAL.
    - Compare CPM/CPC atuais com benchmarks agro (CPM agro: R$15-30, CPC agro: R$1.50-3.00).

    **2. INTELIGÊNCIA POR ECOSSISTEMA:**
    - **Meta (FB+IG):** Motor de alcance e engajamento. O que a performance revela sobre a audiência da Syngenta neste ecossistema? Há sinais de saturação ou crescimento?
    - **Google Ads + PMax:** Motor de intenção e conversão. O search indica demanda ativa do mercado? PMax está aprendendo ou ainda em fase de otimização?
    - **TikTok:** Canal emergente para agro. O que a performance indica sobre a penetração da Syngenta em audiências mais jovens/digitais?
    - **YouTube:** Construção de autoridade via vídeo longo. Qual o papel estratégico no funil?

    **3. ANÁLISE DE MIX DE MÍDIA:**
    - A distribuição atual entre canais é ótima? Há canais sobre-investidos ou sub-investidos?
    - Baseado nos resultados: qual seria a redistribuição ideal para maximizar ROI?
    - Considere o papel de cada canal no funil: awareness (TikTok/YT) > consideração (Meta) > conversão (Google).

    **4. DINÂMICA DE CUSTOS E COMPETIÇÃO:**
    - CPM subindo = mais concorrentes disputando a mesma audiência (pressão de leilão).
    - CPC subindo sem aumento de CPM = criativo menos relevante (Quality Score caindo).
    - CPC caindo = criativo mais relevante OU menos concorrência OU melhor segmentação.
    - Interprete cada movimento de custo como SINAL DE MERCADO para o cliente.

    **5. PONTOS POSITIVOS:**
    - Canais com melhor relação custo-efetividade
    - Ganhos de eficiência identificados (efeito tesoura, redução de custos)
    - Estratégias de alocação que estão funcionando

    **6. RED FLAGS E PONTOS DE MELHORIA:**
    - Canais com custo crescente sem retorno proporcional
    - Concentração excessiva de investimento em um único canal (risco de dependência)
    - Oportunidades de teste em canais/formatos subutilizados
    - Gaps no funil que precisam de investimento incremental

    ### FORMATO:
    Texto analítico de alto nível. Estruture em: Eficiência de Capital > Inteligência por Ecossistema > Mix de Mídia > Dinâmica de Custos > Pontos Positivos > Red Flags > Pautas para Slides.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_analise_seo(dados_seo, analise_midias_pagas, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o Head de Inteligência de Conteúdo e SEO da Macfor.
    Esta seção traduz dados de tráfego orgânico em INTELIGÊNCIA DE MERCADO ESTRATÉGICA — o SEO revela o que o mercado BUSCA ATIVAMENTE, e isso é ouro para a tomada de decisão do cliente.

    **ANÁLISE DE MÍDIAS PAGAS (contexto acumulado):**
    {analise_midias_pagas}

    **PAINEL COMPLETO SEO + CONTENT:**
    | Métrica | Atual | Mês Passado | Var. MoM |
    |---------|-------|-------------|----------|
    | Visualizações (Total) | {dados_seo.get('vis_total_atual', 0):,} | {dados_seo.get('vis_total_mes', 0):,} | {dados_seo.get('var_vis_total_mes', 0):+.1f}% |
    | Sessões (Total) | {dados_seo.get('sess_total_atual', 0):,} | {dados_seo.get('sess_total_mes', 0):,} | — |
    | Usuários (Total) | {dados_seo.get('user_total_atual', 0):,} | {dados_seo.get('user_total_mes', 0):,} | — |
    | Visualizações Orgânicas | {dados_seo.get('vis_org_atual', 0):,} | {dados_seo.get('vis_org_mes', 0):,} | {dados_seo.get('var_vis_org_mes', 0):+.1f}% |
    | Sessões Orgânicas | {dados_seo.get('sess_org_atual', 0):,} | {dados_seo.get('sess_org_mes', 0):,} | {dados_seo.get('var_sess_org_mes', 0):+.1f}% |
    | Usuários Orgânicos | {dados_seo.get('user_org_atual', 0):,} | {dados_seo.get('user_org_mes', 0):,} | — |

    **TOP KEYWORDS DO MÊS:**
    {dados_seo.get('top_keywords', 'Nenhuma keyword fornecida')}

    ### FRAMEWORK DE INTELIGÊNCIA SEO (6 DIMENSÕES):

    **1. DEMANDA DE MERCADO (o que as buscas revelam):**
    - As keywords indicam que tipo de demanda? (informacional: pesquisando; transacional: comprando; navegacional: já conhece a marca)
    - Quais keywords revelam INTENÇÃO DE COMPRA vs. apenas curiosidade?
    - Há keywords de concorrentes aparecendo? (oportunidade de interceptação)

    **2. INDEPENDÊNCIA DE MÍDIA (orgânico vs. pago):**
    - Calcule a proporção orgânico/total: quanto do tráfego é "gratuito" vs. comprado?
    - Se o orgânico está crescendo: a Syngenta está construindo um ATIVO DIGITAL de longo prazo.
    - Se o orgânico está caindo: dependência de mídia paga está aumentando (risco estratégico).
    - Meta ideal para agro: 30-40% orgânico / 60-70% pago.

    **3. AUTORIDADE DE MARCA:**
    - As keywords de marca (Syngenta, produtos Syngenta) estão crescendo ou caindo?
    - Keywords de marca crescendo = awareness gerando efeito de busca (mídia paga alimentando orgânico).
    - Keywords genéricas do setor: a Syngenta está aparecendo para termos genéricos? (ex: "defensivos agrícolas", "fungicida soja")

    **4. ANÁLISE DE FUNIL DE CONTEÚDO:**
    - Visualizações altas mas sessões baixas = conteúdo sendo visto mas não gerando interesse profundo.
    - Sessões crescendo mais que visualizações = conteúdo está engajando (boa retenção).
    - Usuários únicos crescendo = alcance orgânico expandindo.

    **5. PONTOS POSITIVOS:**
    - Keywords que estão ganhando posição
    - Crescimento de tráfego orgânico (economia de mídia)
    - Conteúdos que estão gerando autoridade

    **6. RED FLAGS E OPORTUNIDADES:**
    - Keywords perdendo posição (risco de perder território orgânico)
    - Tráfego orgânico caindo (sinal de alerta SEO)
    - Gaps de conteúdo: o que o público busca e a Syngenta ainda não responde?
    - Oportunidades de content marketing baseadas em tendências de busca do agro

    ### FORMATO:
    Texto analítico e consultivo. Estruture em: Demanda de Mercado > Independência de Mídia > Autoridade de Marca > Funil de Conteúdo > Pontos Positivos > Red Flags e Oportunidades > Pautas para Slides.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_diagnostico_eficiencia(dados_metrica_performance, dados_investimentos, dados_custos, modelo_escolhido="Gemini"):
    """Nova seção: Diagnóstico de Eficiência Operacional — análise profunda do ROI."""
    prompt = f"""
    Você é o CFO Digital da Macfor — sua missão é traduzir dados de marketing em LINGUAGEM DE RETORNO SOBRE INVESTIMENTO que um Diretor Financeiro entenderia.
    Esta seção é exclusiva sobre EFICIÊNCIA: cada real investido está rendendo mais ou menos resultado?

    **DADOS FINANCEIROS:**
    | Indicador | Atual | Var. MoM | Var. YoY |
    |-----------|-------|----------|----------|
    | Investimento Total | R$ {dados_investimentos.get('total_atual', 0):,.2f} | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |
    | CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
    | CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |
    | CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
    | CPV | R$ {dados_custos.get('cpv_atual', 0):.2f} | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |

    **RESULTADOS:**
    | Métrica | Atual | Var. MoM | Var. YoY |
    |---------|-------|----------|----------|
    | Cliques | {dados_metrica_performance.get('cli_atual', 0):,} | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('eng_atual', 0):,} | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
    | Sessões | {dados_metrica_performance.get('sess_atual', 0):,} | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
    | Alcance | {dados_metrica_performance.get('reach_atual', 0):,} | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('imp_atual', 0):,} | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |

    ### ANÁLISE OBRIGATÓRIA:

    **1. ÍNDICE DE PRODUTIVIDADE DIGITAL (IPD):**
    Compare a variação do investimento com a variação dos resultados. Se o investimento caiu X% mas resultados caíram apenas Y% (Y < X), calcule o ganho de produtividade: "com Z% menos investimento, entregamos apenas W% menos resultado — ganho líquido de produtividade de P%."
    Se resultados SUBIRAM com investimento menor: EFEITO TESOURA confirmado. Quantifique.

    **2. CUSTO POR RESULTADO UNITÁRIO:**
    - Custo por clique, custo por engajamento, custo por sessão, custo por mil impressões.
    - Compare cada um com o mês passado e o ano passado.
    - Classifique: OTIMIZANDO (custo caindo), ESTÁVEL, ou INFLACIONANDO (custo subindo).

    **3. EFICIÊNCIA DE FUNIL:**
    - Taxa de conversão implícita: Impressões → Cliques (CTR), Cliques → Sessões (taxa de aterrissagem).
    - Onde está o gargalo? Onde está a eficiência?

    **4. BENCHMARKS DO SETOR AGRO:**
    - Compare métricas com benchmarks: CTR agro (0.8-1.5%), CPC agro (R$1.50-3.00), CPM agro (R$15-30).
    - Posicione a Syngenta: ACIMA do mercado, NA MÉDIA, ou ABAIXO.

    **5. SCORE DE SAÚDE FINANCEIRA DIGITAL:**
    Atribua um score de 1 a 10 para a eficiência da operação digital, justificando cada ponto.

    ### FORMATO:
    Texto analítico com foco financeiro. Estruture em: IPD > Custo Unitário > Funil > Benchmarks > Score > Recomendações de Otimização de Budget.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_red_flags(dados_metrica_performance, dados_custos, dados_investimentos, contexto_atual, modelo_escolhido="Gemini"):
    """Nova seção: Red Flags & Pontos de Atenção — sinais de alerta que exigem ação."""
    prompt = f"""
    Você é o Risk Analyst da Macfor — sua missão é identificar TODOS os sinais de alerta nos dados que exigem atenção imediata do cliente.
    Esta seção é o "sistema de alarme precoce" do relatório: o cliente precisa saber onde há risco ANTES que vire problema.

    **CONTEXTO ACUMULADO:**
    {contexto_atual}

    **DADOS DE PERFORMANCE:**
    | Métrica | Var. MoM | Var. YoY |
    |---------|----------|----------|
    | Investimento | {dados_metrica_performance.get('var_invest_mes', 0):+.1f}% | {dados_metrica_performance.get('var_invest_ano', 0):+.1f}% |
    | Sessões | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
    | Alcance | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Impressões | {dados_metrica_performance.get('var_imp_mes', 0):+.1f}% | {dados_metrica_performance.get('var_imp_ano', 0):+.1f}% |
    | Cliques | {dados_metrica_performance.get('var_cli_mes', 0):+.1f}% | {dados_metrica_performance.get('var_cli_ano', 0):+.1f}% |
    | Engajamentos | {dados_metrica_performance.get('var_eng_mes', 0):+.1f}% | {dados_metrica_performance.get('var_eng_ano', 0):+.1f}% |
    | CTR | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |

    **DADOS DE CUSTOS:**
    | Custo | Var. MoM | Var. YoY |
    |-------|----------|----------|
    | CPC | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
    | CPM | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |
    | CPE | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
    | CPV | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |

    ### FRAMEWORK DE DETECÇÃO DE RED FLAGS:

    Para cada red flag, siga a estrutura:
    **SINAL** → **CAUSA PROVÁVEL** → **RISCO SE NÃO AGIR** → **AÇÃO RECOMENDADA** → **URGÊNCIA (Alta/Média/Baixa)**

    **CATEGORIAS DE RED FLAGS A INVESTIGAR:**

    1. **INFLAÇÃO DE CUSTOS:** CPC/CPM/CPE subindo mais de 10% (MoM ou YoY). Causa: pressão competitiva, fadiga de criativo, ou queda de relevância.

    2. **QUEDA DE RESULTADOS:** Métricas-chave caindo mais de 15%. Causa: sazonalidade, saturação de audiência, ou mudança algorítmica.

    3. **DESCOLAMENTO NEGATIVO:** Investimento subindo mas resultados caindo (oposto do Efeito Tesoura). Sinal de ineficiência crescente.

    4. **CONCENTRAÇÃO DE RISCO:** Mais de 60% do investimento em um único canal. Se esse canal tiver problema (algoritmo, ban, crise), o impacto é desproporcional.

    5. **FADIGA DE AUDIÊNCIA:** Alcance caindo + frequência subindo = mesma audiência sendo impactada repetidamente. Risco de rejeição de marca.

    6. **GARGALO DE FUNIL:** Muitas impressões mas poucos cliques (CTR baixo), ou muitos cliques mas poucas sessões (problemas de landing page ou tracking).

    7. **DEPENDÊNCIA DE PAGO:** Se o tráfego orgânico está estagnado ou caindo enquanto o pago cresce, há risco de dependência.

    8. **SINAIS POSITIVOS MASCARANDO PROBLEMAS:** Exemplo: cliques subindo mas engajamento caindo pode indicar tráfego de baixa qualidade.

    ### FORMATO:
    Liste cada Red Flag identificada com: Severidade (ALTA/MÉDIA/BAIXA), Sinal nos Dados, Causa Provável, Risco de Inação, Ação Recomendada.
    Se NÃO houver red flags: documente como "Operação Saudável — sem sinais de alerta significativos" e explique por quê.
    Ao final, liste também SINAIS POSITIVOS que compensam os riscos (para dar equilíbrio ao relatório).
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_mapa_oportunidades(dados_metrica_performance, dados_investimentos, dados_custos, dados_seo, analise_seo, modelo_escolhido="Gemini"):
    """Nova seção: Mapa de Oportunidades — onde o cliente pode crescer."""
    prompt = f"""
    Você é o Chief Strategy Officer da Macfor — sua missão é identificar TODAS as oportunidades de crescimento que os dados revelam para a Syngenta.
    Esta seção é o "mapa do tesouro" do relatório: onde estão as oportunidades inexploradas e como capturá-las.

    **ANÁLISE SEO (contexto acumulado):**
    {analise_seo}

    **PANORAMA DE PERFORMANCE:**
    | Métrica | Atual | Var. MoM | Var. YoY |
    |---------|-------|----------|----------|
    | Investimento | R$ {dados_investimentos.get('total_atual', 0):,.2f} | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |
    | Alcance | {dados_metrica_performance.get('reach_atual', 0):,} | {dados_metrica_performance.get('var_reach_mes', 0):+.1f}% | {dados_metrica_performance.get('var_reach_ano', 0):+.1f}% |
    | Sessões | {dados_metrica_performance.get('sess_atual', 0):,} | {dados_metrica_performance.get('var_sess_mes', 0):+.1f}% | {dados_metrica_performance.get('var_sess_ano', 0):+.1f}% |
    | CTR | {dados_metrica_performance.get('ctr_atual', 0):.2f}% | {dados_metrica_performance.get('var_ctr_mes', 0):+.1f}% | {dados_metrica_performance.get('var_ctr_ano', 0):+.1f}% |

    **DADOS ORGÂNICOS:**
    - Tráfego Orgânico: {dados_seo.get('vis_org_atual', 0):,} visualizações
    - Keywords: {dados_seo.get('top_keywords', 'Não informado')}

    **EFICIÊNCIA:**
    - CPC: R$ {dados_custos.get('cpc_atual', 0):.2f} | CPM: R$ {dados_custos.get('cpm_atual', 0):.2f}

    ### FRAMEWORK DE MAPEAMENTO DE OPORTUNIDADES:

    **1. OPORTUNIDADES DE CANAL:**
    - Canais subutilizados: se TikTok tem investimento zero ou mínimo, há oportunidade de first-mover no agro.
    - Canais com CPC baixo: indicam menor concorrência = oportunidade de dominar.
    - YouTube para agro: produtor rural consome vídeo técnico — oportunidade de autoridade.
    - PMax / Performance Max: aprendizado de máquina do Google pode revelar audiências inesperadas.

    **2. OPORTUNIDADES DE AUDIÊNCIA:**
    - Se o alcance está crescendo mas o engajamento não acompanha: há audiência disponível que não está sendo ativada.
    - Segmentações testáveis: faixa etária, região, interesse em culturas específicas.
    - Lookalike audiences dos melhores performers.

    **3. OPORTUNIDADES DE CONTEÚDO:**
    - Gaps de keyword: o que o público busca e a Syngenta não tem conteúdo?
    - Formatos emergentes: Reels, Shorts, carrosséis educativos, UGC (conteúdo de produtor).
    - Content marketing técnico: guias de safra, calculadoras de ROI agrícola, webinars.

    **4. OPORTUNIDADES DE EFICIÊNCIA:**
    - Testes A/B prioritários baseados nos dados (CTA, cores, headlines, formatos).
    - Otimizações de lance e orçamento baseadas em hora do dia / dia da semana.
    - Retargeting: audiências que clicaram mas não converteram.

    **5. OPORTUNIDADES SAZONAIS (AGRO):**
    - Calendário safra: quais culturas/produtos devem ser priorizados nos próximos meses?
    - Feiras e eventos do setor: oportunidades de campanha pré/durante/pós-evento.
    - Entressafra: momento de construir awareness para a próxima safra.

    **6. OPORTUNIDADES COMPETITIVAS:**
    - Se concorrentes estão ausentes de algum canal, é janela de first-mover.
    - Se custos de mídia estão caindo: momento de investir mais por menos.
    - Se o tráfego orgânico está crescendo: escalar conteúdo para reduzir dependência de pago.

    ### PARA CADA OPORTUNIDADE, ENTREGUE:
    - **Descrição** da oportunidade
    - **Potencial de impacto** (Alto/Médio/Baixo)
    - **Investimento necessário** (tempo, budget, recursos)
    - **Prazo de retorno** (curto: 1-3 meses / médio: 3-6 meses / longo: 6-12 meses)
    - **Ação recomendada** específica

    ### FORMATO:
    Texto analítico e propositivo. Estruture em: Oportunidades de Canal > Audiência > Conteúdo > Eficiência > Sazonais > Competitivas.
    Priorize as 3 oportunidades de maior impacto como "QUICK WINS" no início.
    """
    return gerar_texto(prompt, modelo_escolhido)

def gerar_proximos_passos(dados_metrica_performance, analise_seo, diagnostico_eficiencia, red_flags, mapa_oportunidades, modelo_escolhido="Gemini"):
    prompt = f"""
    Você é o CEO da Macfor entregando pessoalmente as recomendações finais ao board da Syngenta.
    Esta seção é a SÍNTESE ESTRATÉGICA FINAL — ela condensa TODA a inteligência acumulada no relatório em recomendações concretas, priorizadas e acionáveis.
    O cliente deve sair desta seção sabendo EXATAMENTE o que fazer, por que fazer e em que ordem.

    **INTELIGÊNCIA ACUMULADA:**

    **Análise SEO e Content:**
    {analise_seo}

    **Diagnóstico de Eficiência:**
    {diagnostico_eficiencia}

    **Red Flags Identificadas:**
    {red_flags}

    **Mapa de Oportunidades:**
    {mapa_oportunidades}

    **DADOS-CHAVE:**
    - Investimento: R$ {dados_metrica_performance.get('spend_atual', 0):,.2f} (MoM: {dados_metrica_performance.get('var_invest_mes', 0):+.1f}%, YoY: {dados_metrica_performance.get('var_invest_ano', 0):+.1f}%)
    - CTR: {dados_metrica_performance.get('ctr_atual', 0):.2f}%
    - Concorrentes: {dados_metrica_performance.get('info_concorrentes', 'Não informado')}

    ### FRAMEWORK DE PRÓXIMOS PASSOS (4 BLOCOS):

    **BLOCO 1: INTELIGÊNCIA DO PERÍODO (O que aprendemos)**
    - Síntese das 3-5 descobertas mais importantes de todo o relatório.
    - O que esses dados revelam sobre o mercado agro digital como um todo?
    - O que mudou na dinâmica competitiva?
    - Quais hipóteses foram confirmadas e quais foram refutadas?

    **BLOCO 2: AÇÕES IMEDIATAS (Próximos 30 dias)**
    - Red flags que exigem correção urgente.
    - Quick wins de otimização que podem gerar resultado rápido.
    - Ajustes de budget/lance/segmentação baseados nos dados.
    - Cada ação deve ter: O QUÊ fazer, POR QUÊ fazer, RESULTADO esperado.

    **BLOCO 3: MOVIMENTOS ESTRATÉGICOS (Próximos 60-90 dias)**
    - Oportunidades de canal e audiência a explorar.
    - Testes estruturados a implementar (A/B de criativos, novos formatos, novas segmentações).
    - Investimentos em conteúdo e SEO para reduzir dependência de pago.
    - Preparação para próximas janelas sazonais do agro.

    **BLOCO 4: VISÃO DE LONGO PRAZO (Próximos 6-12 meses)**
    - Construção de ativos digitais (audiência proprietária, autoridade SEO, dados de público).
    - Evolução do mix de mídia ideal para maximizar ROI.
    - Posicionamento competitivo desejado e como chegar lá.
    - KPIs de referência para acompanhamento (quais métricas monitorar e quais targets atingir).

    ### FORMATO:
    Texto executivo, direto, orientado a ação. Cada recomendação deve ser ESPECÍFICA, MENSURÁVEL e com PRAZO.
    Tom: consultivo e propositivo — o cliente deve sentir que tem um parceiro estratégico, não apenas um fornecedor de métricas.
    Ao final, sugira pautas para slides priorizando as recomendações de maior impacto.
    """
    return gerar_texto(prompt, modelo_escolhido)


def compilar_relatorio_cliente(contexto_atual, destaques, analise_criativos, analise_midias_pagas,
                                analise_seo, proximos_passos, mapa_oportunidades, modelo_escolhido="Gemini"):
    """Compila todas as análises em um relatório narrativo para apresentação ao cliente."""
    prompt = f"""
    Você é o Diretor de Contas da Macfor, responsável por REESCREVER toda a inteligência acumulada no relatório
    em um documento PARA O CLIENTE (Syngenta).

    **CONTEXTO CRÍTICO:** Somos uma agência de marketing digital CONTRATADA pela Syngenta. Este documento é a
    nossa ENTREGA MENSAL — é assim que justificamos nosso fee, demonstramos valor e garantimos a renovação do contrato.

    **DIFERENÇA FUNDAMENTAL vs. relatório interno:**
    - NÃO exponha vulnerabilidades da nossa operação — apresente como aprendizados e otimizações.
    - NÃO use linguagem de "estamos testando" — use "implementamos a estratégia X que gerou Y."
    - CADA dado deve ser ENQUADRADO como valor entregue pela Macfor ao cliente.
    - Red flags devem ser apresentadas como "oportunidades identificadas pela nossa equipe" e não como problemas.
    - O tom é de PARCEIRO ESTRATÉGICO entregando resultado, não de fornecedor prestando contas.
    - DEMONSTRE EXPERTISE: use benchmarks de mercado, referências do setor agro, frameworks estratégicos.
    - O cliente deve sair da leitura pensando: "estou bem assessorado, a Macfor entende do meu negócio."

    **INTELIGÊNCIA ACUMULADA (BASE PARA REESCRITA):**

    **Contexto Atual:**
    {contexto_atual}

    **Destaques:**
    {destaques}

    **Análise de Criativos:**
    {analise_criativos}

    **Mídias Pagas:**
    {analise_midias_pagas}

    **SEO + Content:**
    {analise_seo}

    **Mapa de Oportunidades:**
    {mapa_oportunidades}

    **Próximos Passos:**
    {proximos_passos}

    ### ESTRUTURA OBRIGATÓRIA DO DOCUMENTO PARA O CLIENTE:

    **1. SUMÁRIO EXECUTIVO (1 parágrafo)**
    Síntese de alto nível: o que o período representou para a marca Syngenta no digital.
    Tom: confiante, estratégico, orientado a resultado.

    **2. PANORAMA DO PERÍODO**
    Contextualização do cenário de mercado e como a Syngenta se posicionou.
    Foque no que FOI CONQUISTADO, não no que faltou.

    **3. RESULTADOS E CONQUISTAS**
    Apresente os dados como CONQUISTAS. Use framing positivo:
    - "Alcançamos X impressões" em vez de "as impressões foram X"
    - "Otimizamos o CPC em X%" em vez de "o CPC variou X%"
    - Se algo caiu: "redirecionamos investimento para canais de maior eficiência, resultando em..."

    **4. INTELIGÊNCIA DE MERCADO ENTREGUE**
    Posicione a Macfor como consultoria: mostre insights que SÓ uma equipe especializada poderia ter extraído.
    Use frases como: "Nossa análise identificou que...", "A inteligência competitiva revela..."

    **5. ESTRATÉGIA CRIATIVA E PERFORMANCE**
    Demonstre a relação causa-efeito entre as decisões criativas e os resultados.
    O cliente precisa ver que cada peça foi pensada estrategicamente.

    **6. VISÃO DE MÍDIA E EFICIÊNCIA DE INVESTIMENTO**
    Demonstre que cada real do cliente foi investido com inteligência.
    Destaque ganhos de eficiência como valor direto entregue pela Macfor.

    **7. OPORTUNIDADES IDENTIFICADAS PARA O PRÓXIMO PERÍODO**
    Apresente as oportunidades como "o que a Macfor está preparando para capitalizar."
    Tom: proativo, antecipando movimentos de mercado.

    **8. RECOMENDAÇÕES ESTRATÉGICAS**
    Recomendações concretas enquadradas como "nossa recomendação baseada na inteligência acumulada."
    Cada recomendação deve ter: ação, justificativa, resultado esperado.

    ### FORMATO:
    Texto elegante, profissional, com tom consultivo de alto nível.
    Sem jargões internos de agência. Sem autocrítica. Sem incertezas.
    O cliente deve sentir que tem o melhor parceiro digital do mercado.
    """
    return gerar_texto(prompt, modelo_escolhido)


def compilar_guia_slides(contexto_atual, destaques, analise_criativos, analise_midias_pagas,
                          analise_seo, diagnostico_eficiencia, red_flags, mapa_oportunidades,
                          proximos_passos, tipo="cliente", modelo_escolhido="Gemini"):
    """Gera guia de slides para apresentação (interno ou cliente)."""

    if tipo == "cliente":
        instrucao_tom = """
        **TOM E ABORDAGEM (CLIENTE):**
        - Cada slide deve DEMONSTRAR VALOR entregue pela Macfor.
        - Enquadre TUDO como conquista, aprendizado ou oportunidade identificada.
        - Red flags viram "oportunidades de otimização proativas".
        - Use dados como prova de competência e resultado.
        - O deck deve construir a narrativa: "investiu bem → resultados sólidos → próximos movimentos estratégicos."
        - Visual sugerido: clean, corporativo, cores Macfor + Syngenta.
        - O cliente deve sair da apresentação renovando o contrato mentalmente.
        """
        excluir = "NÃO inclua: red flags internas, autocríticas, dados de margem/fee, discussões de processo interno."
    else:
        instrucao_tom = """
        **TOM E ABORDAGEM (INTERNO):**
        - Seja 100% HONESTO sobre o que funcionou e o que não funcionou.
        - Red flags devem ser destacadas com urgência e plano de ação.
        - Inclua notas sobre: ajustes de processo, problemas de execução, aprendizados operacionais.
        - Métricas de eficiência da equipe, tempo de entrega, qualidade de peças.
        - Discussão aberta sobre o que mudar na estratégia.
        - Análise de risco para renovação do contrato com o cliente.
        """
        excluir = "INCLUA: autocríticas, problemas de processo, riscos de churn do cliente, gaps de entrega."

    prompt = f"""
    Você é o Head de Planejamento Estratégico da Macfor. Crie um GUIA COMPLETO DE SLIDES para apresentação {"ao cliente Syngenta" if tipo == "cliente" else "interna da equipe Macfor"}.

    {instrucao_tom}
    {excluir}

    **INTELIGÊNCIA ACUMULADA:**

    **Contexto:** {contexto_atual}
    **Destaques:** {destaques}
    **Criativos:** {analise_criativos}
    **Mídias Pagas:** {analise_midias_pagas}
    **SEO:** {analise_seo}
    **Diagnóstico de Eficiência:** {diagnostico_eficiencia}
    **Red Flags:** {red_flags}
    **Oportunidades:** {mapa_oportunidades}
    **Próximos Passos:** {proximos_passos}

    ### FORMATO OBRIGATÓRIO — PARA CADA SLIDE:

    **Slide N — [Título do Slide]**
    - **Objetivo:** O que este slide precisa comunicar
    - **Conteúdo principal:** Bullet points com os dados/insights-chave
    - **Visual sugerido:** Tipo de gráfico, tabela ou elemento visual recomendado
    - **Texto de apoio:** Frase ou parágrafo que o apresentador deve falar
    - **Dado-destaque:** O número ou insight que deve estar em evidência no slide

    ### ESTRUTURA DE DECK {"PARA CLIENTE" if tipo == "cliente" else "INTERNO"}:

    {"**Slide 1 — Capa** (Relatório Executivo | Syngenta | Mês/Ano | Macfor)" if tipo == "cliente" else "**Slide 1 — Capa** (Review Interno | Syngenta | Mês/Ano)"}
    **Slide 2 — Sumário Executivo** (1 parágrafo + 3 métricas-destaque)
    **Slide 3 — Panorama de Performance** (tabela comparativa MoM + YoY)
    **Slide 4 — {"Conquistas do Período" if tipo == "cliente" else "Diagnóstico de Saúde da Operação"}**
    **Slide 5 — {"Inteligência de Mercado" if tipo == "cliente" else "Red Flags e Pontos de Atenção"}**
    **Slide 6 — Análise de Criativos** (com miniaturas sugeridas)
    **Slide 7 — Performance de Mídias Pagas** (gráficos de investimento por canal + eficiência)
    **Slide 8 — {"Eficiência do Investimento" if tipo == "cliente" else "Análise de ROI e Produtividade"}** {"(Efeito Tesoura se aplicável)" if tipo == "cliente" else ""}
    **Slide 9 — SEO + Content** (orgânico vs pago + keywords)
    **Slide 10 — {"Oportunidades Identificadas" if tipo == "cliente" else "Mapa de Oportunidades + Priorização"}**
    **Slide 11 — Próximos Passos** (ações 30/60/90 dias)
    {"**Slide 12 — Agradecimento + Contato Macfor**" if tipo == "cliente" else "**Slide 12 — Plano de Ação Interno + Responsáveis**"}

    Detalhe CADA slide. Não pule nenhum. Cada slide deve ter conteúdo suficiente para ser produzido pelo time de design.
    """
    return gerar_texto(prompt, modelo_escolhido)


if st.button("🔄 Atualizar Dados (Syngenta)"):
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
    st.header("📝 Dados do Relatório")
    
    # Contexto e Destaques
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Contexto Geral")
        contexto_input = st.text_area("Contexto Atual (opcional)", height=100, placeholder="Descreva o contexto da campanha/período...")
        info_concorrentes = st.text_area("Informações de Concorrentes", height=100, placeholder="O que os concorrentes estão fazendo?")
    
    with col2:
        st.subheader("Upload de Criativos")
        st.markdown("**Criativos do Mês Atual**")
        imagens = st.file_uploader("Faça upload dos criativos atuais", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_atual")
        st.markdown("**Criativos do Mês Passado** *(para comparação)*")
        imagens_mes_passado = st.file_uploader("Faça upload dos criativos do mês passado", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="upload_mes_passado")
    
# Métricas Principais
    st.subheader("📊 Métricas de Performance")
    
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

    # Processar imagens do mês passado (sempre com Gemini)
    descricoes_imagens_mes_passado = []
    if imagens_mes_passado:
        with st.spinner("Analisando criativos do mês passado..."):
            for imagem_file in imagens_mes_passado:
                image = Image.open(imagem_file)
                descricao = descrever_imagem(image)
                descricoes_imagens_mes_passado.append(f"**[MES PASSADO] {imagem_file.name}**: {descricao}")
    
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

    # Gerar relatório — cada etapa individualmente com spinner próprio
    try:
        progress = st.progress(0, text="Iniciando pipeline de inteligência...")

        with st.spinner("1/14 — Análise YoY..."):
            analise_yoy = gerar_yoy_para_contexto(dados_metrica_performance, descricoes_imagens, modelo_escolhido)
        progress.progress(1/14, text="1/14 ✓ Análise YoY")

        with st.spinner("2/14 — Análise de Concorrência..."):
            analise_concorrencia = gerar_analise_concorrencia(dados_metrica_performance, info_concorrentes, modelo_escolhido)
        progress.progress(2/14, text="2/14 ✓ Concorrência")

        with st.spinner("3/14 — Contexto Atual..."):
            contexto_atual = gerar_contexto_atual(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, analise_yoy, analise_concorrencia, modelo_escolhido)
        progress.progress(3/14, text="3/14 ✓ Contexto Atual")

        with st.spinner("4/14 — Destaques..."):
            destaques = gerar_destaques(dados_metrica_performance, contexto_atual, modelo_escolhido)
        progress.progress(4/14, text="4/14 ✓ Destaques")

        with st.spinner("5/14 — Análise de Criativos..."):
            analise_criativos = gerar_analise_criativos(dados_custos, descricoes_imagens, descricoes_imagens_mes_passado, destaques, modelo_escolhido)
        progress.progress(5/14, text="5/14 ✓ Criativos")

        with st.spinner("6/14 — Mídias Pagas..."):
            analise_midias_pagas = gerar_analise_midias_pagas(dados_investimentos, dados_custos, analise_criativos, modelo_escolhido)
        progress.progress(6/14, text="6/14 ✓ Mídias Pagas")

        with st.spinner("7/14 — SEO & Conteúdo..."):
            analise_seo = gerar_analise_seo(dados_seo, analise_midias_pagas, modelo_escolhido)
        progress.progress(7/14, text="7/14 ✓ SEO")

        with st.spinner("8/14 — Diagnóstico de Eficiência..."):
            diagnostico_eficiencia = gerar_diagnostico_eficiencia(dados_metrica_performance, dados_investimentos, dados_custos, modelo_escolhido)
        progress.progress(8/14, text="8/14 ✓ Diagnóstico")

        with st.spinner("9/14 — Red Flags..."):
            red_flags = gerar_red_flags(dados_metrica_performance, dados_custos, dados_investimentos, contexto_atual, modelo_escolhido)
        progress.progress(9/14, text="9/14 ✓ Red Flags")

        with st.spinner("10/14 — Mapa de Oportunidades..."):
            mapa_oportunidades = gerar_mapa_oportunidades(dados_metrica_performance, dados_investimentos, dados_custos, dados_seo, analise_seo, modelo_escolhido)
        progress.progress(10/14, text="10/14 ✓ Oportunidades")

        with st.spinner("11/14 — Próximos Passos..."):
            proximos_passos = gerar_proximos_passos(dados_metrica_performance, analise_seo, diagnostico_eficiencia, red_flags, mapa_oportunidades, modelo_escolhido)
        progress.progress(11/14, text="11/14 ✓ Próximos Passos")

        with st.spinner("12/14 — Compilando relatório do cliente..."):
            relatorio_cliente = compilar_relatorio_cliente(contexto_atual, destaques, analise_criativos, analise_midias_pagas, analise_seo, proximos_passos, mapa_oportunidades, modelo_escolhido)
        progress.progress(12/14, text="12/14 ✓ Relatório Cliente")

        with st.spinner("13/14 — Guia de slides — Cliente..."):
            slides_cliente = compilar_guia_slides(contexto_atual, destaques, analise_criativos, analise_midias_pagas, analise_seo, diagnostico_eficiencia, red_flags, mapa_oportunidades, proximos_passos, tipo="cliente", modelo_escolhido=modelo_escolhido)
        progress.progress(13/14, text="13/14 ✓ Slides Cliente")

        with st.spinner("14/14 — Guia de slides — Interno..."):
            slides_interno = compilar_guia_slides(contexto_atual, destaques, analise_criativos, analise_midias_pagas, analise_seo, diagnostico_eficiencia, red_flags, mapa_oportunidades, proximos_passos, tipo="interno", modelo_escolhido=modelo_escolhido)
        progress.progress(14/14, text="14/14 ✓ Pipeline completo!")

        # Armazenar resultados
        st.session_state.relatorio_gerado = True
        st.session_state.dados_processados = dados_metrica_performance
        st.session_state.descricoes_imagens = descricoes_imagens
        st.session_state.descricoes_imagens_mes_passado = descricoes_imagens_mes_passado
        st.session_state.contexto_atual = contexto_atual
        st.session_state.destaques = destaques
        st.session_state.analise_criativos = analise_criativos
        st.session_state.analise_midias_pagas = analise_midias_pagas
        st.session_state.analise_seo = analise_seo
        st.session_state.diagnostico_eficiencia = diagnostico_eficiencia
        st.session_state.red_flags = red_flags
        st.session_state.mapa_oportunidades = mapa_oportunidades
        st.session_state.proximos_passos = proximos_passos
        st.session_state.relatorio_cliente = relatorio_cliente
        st.session_state.slides_cliente = slides_cliente
        st.session_state.slides_interno = slides_interno

        st.rerun()

    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")

# Exibir relatório
if st.session_state.relatorio_gerado:
    st.markdown("---")
    st.header("📄 Relatório Executivo Gerado")

    dados = st.session_state.dados_processados

    # =====================================================================
    # PAINEL DE CARDS — KPIs PRINCIPAIS
    # =====================================================================
    st.subheader("📊 Painel de Performance")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Investimento", f"R$ {dados.get('spend_atual', 0):,.0f}",
                  f"{dados.get('var_invest_mes', 0):+.1f}% MoM")
    with col2:
        st.metric("Cliques", f"{dados.get('cli_atual', 0):,}",
                  f"{dados.get('var_cli_mes', 0):+.1f}% MoM")
    with col3:
        st.metric("Impressões", f"{dados.get('imp_atual', 0):,}",
                  f"{dados.get('var_imp_mes', 0):+.1f}% MoM")
    with col4:
        st.metric("CTR", f"{dados.get('ctr_atual', 0):.2f}%",
                  f"{dados.get('var_ctr_mes', 0):+.1f}% MoM")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Alcance", f"{dados.get('reach_atual', 0):,}",
                  f"{dados.get('var_reach_mes', 0):+.1f}% MoM")
    with col2:
        st.metric("Sessões", f"{dados.get('sess_atual', 0):,}",
                  f"{dados.get('var_sess_mes', 0):+.1f}% MoM")
    with col3:
        st.metric("Engajamentos", f"{dados.get('eng_atual', 0):,}",
                  f"{dados.get('var_eng_mes', 0):+.1f}% MoM")
    with col4:
        st.metric("Video Thruplays", f"{dados.get('vtp_atual', 0):,}",
                  f"{dados.get('var_vtp_mes', 0):+.1f}% MoM")

    st.markdown("---")

    # =====================================================================
    # GRÁFICOS — Linha 1: Variações MoM vs YoY (Barras agrupadas)
    # =====================================================================
    st.subheader("📈 Variações MoM vs YoY")

    metricas_nomes = ["Invest.", "Sessões", "Alcance", "Impressões", "Cliques", "Engajam.", "CTR"]
    var_mom = [
        dados.get('var_invest_mes', 0), dados.get('var_sess_mes', 0),
        dados.get('var_reach_mes', 0), dados.get('var_imp_mes', 0),
        dados.get('var_cli_mes', 0), dados.get('var_eng_mes', 0),
        dados.get('var_ctr_mes', 0)
    ]
    var_yoy = [
        dados.get('var_invest_ano', 0), dados.get('var_sess_ano', 0),
        dados.get('var_reach_ano', 0), dados.get('var_imp_ano', 0),
        dados.get('var_cli_ano', 0), dados.get('var_eng_ano', 0),
        dados.get('var_ctr_ano', 0)
    ]

    fig_variacoes = go.Figure()
    fig_variacoes.add_trace(go.Bar(
        name='MoM (%)', x=metricas_nomes, y=var_mom,
        marker_color=['#27AE60' if v >= 0 else '#E74C3C' for v in var_mom],
        text=[f"{v:+.1f}%" for v in var_mom], textposition='outside',
        textfont=dict(size=10)
    ))
    fig_variacoes.add_trace(go.Bar(
        name='YoY (%)', x=metricas_nomes, y=var_yoy,
        marker_color=['#2E86C1' if v >= 0 else '#E67E22' for v in var_yoy],
        text=[f"{v:+.1f}%" for v in var_yoy], textposition='outside',
        textfont=dict(size=10)
    ))
    fig_variacoes.update_layout(
        barmode='group', height=400,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri', size=12),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(title='Variação (%)', zeroline=True, zerolinecolor='#BDC3C7', gridcolor='#EAECEE'),
        xaxis=dict(title=''),
        margin=dict(t=40, b=40)
    )
    st.plotly_chart(fig_variacoes, use_container_width=True)

    # =====================================================================
    # GRÁFICOS — Linha 2: Investimento por Canal (Pizza) + Custos (Radar)
    # =====================================================================
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Distribuição de Investimento por Canal**")
        canais = ['Facebook', 'Instagram', 'TikTok', 'Google Ads', 'YouTube', 'PMax']
        valores_canais = [
            st.session_state.get('fb_atual', 0), st.session_state.get('ig_atual', 0),
            st.session_state.get('tt_atual', 0), st.session_state.get('google_atual', 0),
            st.session_state.get('yt_atual', 0), st.session_state.get('pmax_atual', 0)
        ]
        # Filtrar canais com valor > 0
        canais_filtrados = [c for c, v in zip(canais, valores_canais) if v > 0]
        valores_filtrados = [v for v in valores_canais if v > 0]

        if valores_filtrados:
            fig_pizza = go.Figure(data=[go.Pie(
                labels=canais_filtrados, values=valores_filtrados,
                hole=0.45,
                marker=dict(colors=['#3498DB', '#E91E63', '#000000', '#4CAF50', '#FF0000', '#FF9800']),
                textinfo='label+percent', textposition='outside',
                textfont=dict(size=11)
            )])
            fig_pizza.update_layout(
                height=380, showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                annotations=[dict(text=f"R$ {sum(valores_filtrados):,.0f}", x=0.5, y=0.5,
                                  font_size=14, font_color='#1B3A5C', showarrow=False)]
            )
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("Nenhum investimento por canal informado.")

    with col_g2:
        st.markdown("**Indicadores de Custo (Atual vs Mês Passado)**")
        custos_labels = ['CPC', 'CPM', 'CPE', 'CPV']
        custos_atual = [
            st.session_state.get('cpc_atual', 0), st.session_state.get('cpm_atual', 0),
            st.session_state.get('cpe_atual', 0), st.session_state.get('cpv_atual', 0)
        ]
        custos_mes = [
            st.session_state.get('cpc_mes', 0), st.session_state.get('cpm_mes', 0),
            st.session_state.get('cpe_mes', 0), st.session_state.get('cpv_mes', 0)
        ]

        if any(v > 0 for v in custos_atual):
            fig_custos = go.Figure()
            fig_custos.add_trace(go.Bar(
                name='Atual', x=custos_labels, y=custos_atual,
                marker_color='#1B3A5C',
                text=[f"R$ {v:.2f}" for v in custos_atual], textposition='outside'
            ))
            fig_custos.add_trace(go.Bar(
                name='Mês Passado', x=custos_labels, y=custos_mes,
                marker_color='#AEB6BF',
                text=[f"R$ {v:.2f}" for v in custos_mes], textposition='outside'
            ))
            fig_custos.update_layout(
                barmode='group', height=380,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Calibri', size=12),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                yaxis=dict(title='R$', gridcolor='#EAECEE'),
                margin=dict(t=40, b=20)
            )
            st.plotly_chart(fig_custos, use_container_width=True)
        else:
            st.info("Nenhum indicador de custo informado.")

    # =====================================================================
    # GRÁFICO — Efeito Tesoura (se aplicável)
    # =====================================================================
    var_inv_mom = dados.get('var_invest_mes', 0)
    var_cli_mom = dados.get('var_cli_mes', 0)
    var_eng_mom = dados.get('var_eng_mes', 0)
    tesoura_detectada = (var_inv_mom < -5 and (var_cli_mom > 0 or var_eng_mom > 0))

    if tesoura_detectada:
        st.subheader("✂️ Efeito Tesoura Detectado")
        st.caption("Investimento em queda com resultados em alta — sinal de ganho de produtividade digital.")

        periodos = ['Mês Passado', 'Mês Atual']
        inv_vals = [100, 100 + var_inv_mom]
        cli_vals = [100, 100 + var_cli_mom]

        fig_tesoura = go.Figure()
        fig_tesoura.add_trace(go.Scatter(
            x=periodos, y=inv_vals, name='Investimento',
            line=dict(color='#E74C3C', width=3, dash='dash'),
            mode='lines+markers+text',
            text=[f"{inv_vals[0]:.0f}", f"{inv_vals[1]:.0f}"], textposition='top center'
        ))
        fig_tesoura.add_trace(go.Scatter(
            x=periodos, y=cli_vals, name='Cliques',
            line=dict(color='#27AE60', width=3),
            mode='lines+markers+text',
            text=[f"{cli_vals[0]:.0f}", f"{cli_vals[1]:.0f}"], textposition='bottom center'
        ))
        fig_tesoura.update_layout(
            height=300,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri'), yaxis=dict(title='Índice (base 100)', gridcolor='#EAECEE'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            margin=dict(t=40, b=30)
        )
        st.plotly_chart(fig_tesoura, use_container_width=True)

    # =====================================================================
    # TABELA COMPARATIVA COMPLETA
    # =====================================================================
    st.subheader("📋 Tabela Comparativa Completa")
    tabela_dados = {
        'Métrica': ['Investimento', 'Sessões', 'Alcance', 'Impressões', 'Cliques', 'Engajamentos', 'CTR (%)'],
        'Atual': [
            f"R$ {dados.get('spend_atual', 0):,.0f}", f"{dados.get('sess_atual', 0):,}",
            f"{dados.get('reach_atual', 0):,}", f"{dados.get('imp_atual', 0):,}",
            f"{dados.get('cli_atual', 0):,}", f"{dados.get('eng_atual', 0):,}",
            f"{dados.get('ctr_atual', 0):.2f}%"
        ],
        'Var. MoM': [
            f"{dados.get('var_invest_mes', 0):+.1f}%", f"{dados.get('var_sess_mes', 0):+.1f}%",
            f"{dados.get('var_reach_mes', 0):+.1f}%", f"{dados.get('var_imp_mes', 0):+.1f}%",
            f"{dados.get('var_cli_mes', 0):+.1f}%", f"{dados.get('var_eng_mes', 0):+.1f}%",
            f"{dados.get('var_ctr_mes', 0):+.1f}%"
        ],
        'Var. YoY': [
            f"{dados.get('var_invest_ano', 0):+.1f}%", f"{dados.get('var_sess_ano', 0):+.1f}%",
            f"{dados.get('var_reach_ano', 0):+.1f}%", f"{dados.get('var_imp_ano', 0):+.1f}%",
            f"{dados.get('var_cli_ano', 0):+.1f}%", f"{dados.get('var_eng_ano', 0):+.1f}%",
            f"{dados.get('var_ctr_ano', 0):+.1f}%"
        ]
    }
    st.dataframe(pd.DataFrame(tabela_dados), use_container_width=True, hide_index=True)

    st.markdown("---")

    # =====================================================================
    # SEÇÕES ANALÍTICAS DO RELATÓRIO
    # =====================================================================
    st.subheader("📌 Contexto Atual")
    st.write(st.session_state.contexto_atual)

    st.subheader("⭐ Destaques")
    st.write(st.session_state.destaques)

    st.subheader("🎨 Análise de Criativos")
    if st.session_state.descricoes_imagens:
        st.markdown("**Criativos do Mês Atual:**")
        for desc in st.session_state.descricoes_imagens:
            st.markdown(desc)
    if st.session_state.descricoes_imagens_mes_passado:
        st.markdown("**Criativos do Mês Passado:**")
        for desc in st.session_state.descricoes_imagens_mes_passado:
            st.markdown(desc)
    st.write(st.session_state.analise_criativos)

    st.subheader("💰 Mídias Pagas")
    st.write(st.session_state.analise_midias_pagas)

    st.subheader("🔍 SEO + Content")
    st.write(st.session_state.analise_seo)

    st.subheader("📊 Diagnóstico de Eficiência Operacional")
    st.write(st.session_state.diagnostico_eficiencia)

    st.subheader("🚨 Red Flags & Pontos de Atenção")
    st.write(st.session_state.red_flags)

    st.subheader("🗺️ Mapa de Oportunidades")
    st.write(st.session_state.mapa_oportunidades)

    st.subheader("📈 Próximos Passos e Aprendizados")
    st.write(st.session_state.proximos_passos)
    
    # =====================================================================
    # DOWNLOADS — 4 DOCUMENTOS
    # =====================================================================
    st.markdown("---")
    st.subheader("📥 Documentos para Download")

    try:
        # Montar dicionários de apoio para DOCX
        dados_inv_docx = {
            'fb_atual': st.session_state.get('fb_atual', 0),
            'ig_atual': st.session_state.get('ig_atual', 0),
            'tt_atual': st.session_state.get('tt_atual', 0),
            'google_atual': st.session_state.get('google_atual', 0),
            'yt_atual': st.session_state.get('yt_atual', 0),
            'pmax_atual': st.session_state.get('pmax_atual', 0),
            'total_atual': (st.session_state.get('fb_atual', 0) + st.session_state.get('ig_atual', 0) +
                            st.session_state.get('tt_atual', 0) + st.session_state.get('google_atual', 0) +
                            st.session_state.get('yt_atual', 0) + st.session_state.get('pmax_atual', 0)),
            'var_fb_mes': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_mes', 0)),
            'var_ig_mes': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_mes', 0)),
            'var_tt_mes': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_mes', 0)),
            'var_google_mes': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_mes', 0)),
            'var_total_mes': 0,
            'var_fb_ano': calcular_variacao(st.session_state.get('fb_atual', 0), st.session_state.get('fb_ano', 0)),
            'var_ig_ano': calcular_variacao(st.session_state.get('ig_atual', 0), st.session_state.get('ig_ano', 0)),
            'var_tt_ano': calcular_variacao(st.session_state.get('tt_atual', 0), st.session_state.get('tt_ano', 0)),
            'var_google_ano': calcular_variacao(st.session_state.get('google_atual', 0), st.session_state.get('google_ano', 0)),
            'var_total_ano': 0,
        }
        dados_custos_docx = {
            'cpc_atual': st.session_state.get('cpc_atual', 0), 'cpm_atual': st.session_state.get('cpm_atual', 0),
            'cpe_atual': st.session_state.get('cpe_atual', 0), 'cpv_atual': st.session_state.get('cpv_atual', 0),
            'var_cpc_mes': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_mes', 0)),
            'var_cpm_mes': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_mes', 0)),
            'var_cpe_mes': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_mes', 0)),
            'var_cpv_mes': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_mes', 0)),
            'var_cpc_ano': calcular_variacao(st.session_state.get('cpc_atual', 0), st.session_state.get('cpc_ano', 0)),
            'var_cpm_ano': calcular_variacao(st.session_state.get('cpm_atual', 0), st.session_state.get('cpm_ano', 0)),
            'var_cpe_ano': calcular_variacao(st.session_state.get('cpe_atual', 0), st.session_state.get('cpe_ano', 0)),
            'var_cpv_ano': calcular_variacao(st.session_state.get('cpv_atual', 0), st.session_state.get('cpv_ano', 0)),
        }
        dados_seo_docx = {
            'vis_total_atual': st.session_state.get('seo_vis_atual', 0),
            'sess_org_atual': st.session_state.get('seo_sess_org_atual', 0),
            'vis_org_atual': st.session_state.get('seo_vis_org_atual', 0),
            'var_vis_total_mes': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_mes', 0)),
            'var_sess_org_mes': calcular_variacao(st.session_state.get('seo_sess_org_atual', 0), st.session_state.get('seo_sess_org_mes', 0)),
            'var_vis_org_mes': calcular_variacao(st.session_state.get('seo_vis_org_atual', 0), st.session_state.get('seo_vis_org_mes', 0)),
            'var_vis_total_ano': calcular_variacao(st.session_state.get('seo_vis_atual', 0), st.session_state.get('seo_vis_ano', 0)),
            'var_sess_org_ano': calcular_variacao(st.session_state.get('seo_sess_org_atual', 0), st.session_state.get('seo_sess_org_ano', 0)),
            'var_vis_org_ano': calcular_variacao(st.session_state.get('seo_vis_org_atual', 0), st.session_state.get('seo_vis_org_ano', 0)),
        }

        ts = datetime.now().strftime('%Y%m%d_%H%M')

        # --- DOC 1: RELATÓRIO INTERNO (DOCX) ---
        docx_interno = gerar_docx_relatorio(
            dados=dados, dados_investimentos=dados_inv_docx, dados_custos=dados_custos_docx,
            dados_seo=dados_seo_docx, contexto_atual=st.session_state.contexto_atual,
            destaques=st.session_state.destaques, analise_criativos=st.session_state.analise_criativos,
            analise_midias_pagas=st.session_state.analise_midias_pagas, analise_seo=st.session_state.analise_seo,
            proximos_passos=st.session_state.proximos_passos,
            descricoes_imagens=st.session_state.descricoes_imagens,
            descricoes_imagens_mes_passado=st.session_state.descricoes_imagens_mes_passado,
            diagnostico_eficiencia=st.session_state.get('diagnostico_eficiencia', ''),
            red_flags=st.session_state.get('red_flags', ''),
            mapa_oportunidades=st.session_state.get('mapa_oportunidades', ''),
        )

        # --- DOC 2: RELATÓRIO PARA O CLIENTE (DOCX) ---
        docx_cliente = gerar_docx_cliente(
            relatorio_cliente=st.session_state.get('relatorio_cliente', ''),
            dados=dados, dados_investimentos=dados_inv_docx,
            dados_custos=dados_custos_docx, dados_seo=dados_seo_docx,
        )

        # --- DOC 3: GUIA DE SLIDES — CLIENTE (DOCX) ---
        docx_slides_cliente = gerar_docx_slides(
            conteudo_slides=st.session_state.get('slides_cliente', ''),
            tipo="cliente"
        )

        # --- DOC 4: GUIA DE SLIDES — INTERNO (DOCX) ---
        docx_slides_interno = gerar_docx_slides(
            conteudo_slides=st.session_state.get('slides_interno', ''),
            tipo="interno"
        )

        # Layout de 4 botões
        st.markdown("**Relatórios:**")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📄 Relatório Interno (DOCX)",
                data=docx_interno,
                file_name=f"INTERNO_relatorio_executivo_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Relatório completo para uso interno da Macfor — com red flags, diagnóstico de eficiência e análise crua."
            )
        with col_d2:
            st.download_button(
                label="📄 Relatório para o Cliente (DOCX)",
                data=docx_cliente,
                file_name=f"CLIENTE_relatorio_resultados_syngenta_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Relatório de resultados para apresentação ao cliente Syngenta — tom consultivo, focado em valor entregue."
            )

        st.markdown("**Guias de Slides:**")
        col_d3, col_d4 = st.columns(2)
        with col_d3:
            st.download_button(
                label="🎯 Guia de Slides — Interno (DOCX)",
                data=docx_slides_interno,
                file_name=f"SLIDES_INTERNO_syngenta_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Roteiro para deck de review interno — inclui autocríticas, red flags e plano de ação."
            )
        with col_d4:
            st.download_button(
                label="🎯 Guia de Slides — Cliente (DOCX)",
                data=docx_slides_cliente,
                file_name=f"SLIDES_CLIENTE_syngenta_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Roteiro para deck de apresentação ao cliente — focado em conquistas e valor."
            )

    except Exception as e:
        st.error(f"Erro ao gerar documentos: {str(e)}")

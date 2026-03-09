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
    'dados_processados', 'analise_performance', 'analise_operacional',
    'relatorio_interno_completo', 'relatorio_cliente_completo'
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
                          analise_performance, analise_operacional,
                          relatorio_interno_completo):
    """Gera o relatório executivo interno completo em DOCX (pipeline consolidado de 4 etapas)."""

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
    # 1. COMPARATIVOS DE PERFORMANCE (tabelas numéricas)
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

    doc.add_page_break()

    # =================================================================
    # 2. ANÁLISE DE PERFORMANCE E CONTEXTO (Etapa 1 da IA)
    # =================================================================
    doc.add_heading("Análise de Performance e Contexto", level=1)
    _markdown_para_docx(doc, analise_performance)
    doc.add_page_break()

    # =================================================================
    # 3. ANÁLISE OPERACIONAL (Etapa 2 da IA)
    # =================================================================
    doc.add_heading("Análise Operacional", level=1)
    _markdown_para_docx(doc, analise_operacional)
    doc.add_page_break()

    # =================================================================
    # 4. RELATÓRIO INTERNO COMPLETO (Etapa 3 da IA)
    # =================================================================
    doc.add_heading("Diagnóstico Interno Completo", level=1)
    _markdown_para_docx(doc, relatorio_interno_completo)

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


def gerar_docx_cliente(relatorio_cliente_completo, analise_performance, analise_operacional,
                        dados, dados_investimentos, dados_custos, dados_seo):
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

    # Análise de Performance e Contexto (seção compartilhada)
    doc.add_heading("Panorama de Performance", level=1)
    _markdown_para_docx(doc, analise_performance)
    doc.add_page_break()

    # Análise Operacional (seção compartilhada)
    doc.add_heading("Análise Operacional", level=1)
    _markdown_para_docx(doc, analise_operacional)
    doc.add_page_break()

    # Corpo narrativo compilado pela IA (relatório do cliente)
    doc.add_heading("Relatório de Resultados", level=1)
    _markdown_para_docx(doc, relatorio_cliente_completo)

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

def gerar_analise_performance(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, info_concorrentes, modelo_escolhido="Gemini"):
    """ETAPA 1: Análise de Performance e Contexto — substitui gerar_yoy, gerar_analise_concorrencia, gerar_contexto_atual e gerar_destaques."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva um documento analítico completo sobre a performance digital da Syngenta neste período. Este texto é a PRIMEIRA ETAPA de um relatório executivo de 4 etapas. Ele será usado como base para todas as análises seguintes.

O documento deve cobrir quatro blocos em sequência, em prosa corrida, técnica e narrativa. Não use listas de bullet points como estrutura principal — escreva parágrafos densos com dados concretos.

---

**BLOCO 1 — PANORAMA DE PERFORMANCE (YoY e MoM)**

Escreva um relato comparando a performance digital da Syngenta no período atual versus o mês anterior e versus o mesmo período do ano passado.

Dados de Performance:
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

Cubra: estado geral da operação (crescimento, estabilidade ou retração); os 3 pontos positivos mais relevantes com números; sinais de alerta com queda acima de 10%; nota sobre sazonalidade do agronegócio se relevante.

CRUZAMENTO DE DADOS OBRIGATÓRIO — esta é a parte mais importante da análise. Para cada par de métricas abaixo, verifique o que está acontecendo e interprete:

- Investimento vs. Cliques/Sessões/Engajamentos: se investimento caiu mas resultados subiram ou se mantiveram, é ganho de produtividade (Efeito Tesoura — quantifique: "com X%% menos investimento, entregamos Y%% mais cliques"). Se investimento subiu e resultados caíram, é perda de eficiência — descreva a gravidade.
- Investimento vs. CPC/CPM/CPE: se investimento caiu e custos unitários também caíram, a operação está ficando mais eficiente. Se investimento caiu mas custos subiram, há pressão competitiva no leilão de mídia.
- Impressões vs. CTR: se impressões caíram mas CTR subiu, a mensagem está mais relevante para um público menor e mais qualificado. Se ambos caíram, há problema de criativo ou segmentação.
- Alcance vs. Sessões: se alcance caiu mas sessões subiram, o público alcançado é mais qualificado — está convertendo melhor. Se alcance subiu mas sessões caíram, há desconexão entre mídia e destino.
- Engajamentos vs. Cliques: se engajamento subiu mais que cliques, o conteúdo gera conversa mas não ação (awareness). Se cliques subiram mais que engajamento, gera demanda direta (performance).
- CPC vs. CTR: se CPC caiu e CTR subiu simultaneamente, a relevância do anúncio melhorou. Se CPC subiu e CTR caiu, o anúncio está perdendo relevância e pagando mais por resultado.
- Impressões vs. Alcance: se impressões subiram mais que alcance, a frequência aumentou (mesmo público vendo mais vezes — risco de fadiga). Se alcance subiu mais que impressões, está alcançando gente nova.

Não liste esses cruzamentos mecanicamente. Identifique quais combinações estão de fato acontecendo nos dados e descreva APENAS essas, interpretando o que significam para a operação. Se uma combinação não se aplica (variação irrelevante), ignore-a.

---

**BLOCO 2 — CONTEXTO COMPETITIVO**

Informações de Concorrentes: {info_concorrentes if info_concorrentes else "Nenhuma informação fornecida. Analise apenas com base na evolução histórica da Syngenta."}

Analise em profundidade:
- Posicionamento competitivo: se houver dados de concorrentes, compare volume de presença digital, share of voice estimado, e posicionamento de mensagem. Se não houver, analise a evolução interna da Syngenta como proxy — custos subindo sem mudança de volume indicam mais competidores no leilão.
- Pressão competitiva nos custos: correlacione variações de CPC/CPM com o cenário competitivo. CPC subindo sem mudança de criativo ou segmentação é sinal clássico de mais anunciantes disputando o mesmo público. Quantifique: "o aumento de X%% no CPM sugere que Y novos competidores entraram no leilão ou aumentaram budget."
- Sazonalidade agro vs. comportamento digital: o período atual é safra, entressafra, planejamento? Produtores rurais têm ciclos de decisão de compra de insumos — correlacione com os dados de busca/engajamento.
- Janelas de oportunidade: identifique gaps competitivos concretos. Se concorrentes não estão investindo em determinado canal ou formato, quantifique o custo de oportunidade de não explorar.
- SWOT digital baseado EXCLUSIVAMENTE nos dados: Forças (métricas acima da média histórica), Fraquezas (métricas abaixo), Oportunidades (canais/formatos subexplorados, sazonalidade favorável), Ameaças (custos crescentes, dependência de canal, fadiga criativa). Cada item do SWOT deve referenciar um número concreto dos dados.

---

**BLOCO 3 — DIAGNÓSTICO ATUAL (Contexto Sintético)**

Dados Complementares:
Investimentos: Total R$ {dados_investimentos.get('total_atual', 0):,.2f} (MoM: {dados_investimentos.get('var_total_mes', 0):+.1f}%, YoY: {dados_investimentos.get('var_total_ano', 0):+.1f}%) | Meta: R$ {dados_investimentos.get('fb_atual', 0) + dados_investimentos.get('ig_atual', 0):,.2f} | Google: R$ {dados_investimentos.get('google_atual', 0):,.2f} | TikTok: R$ {dados_investimentos.get('tt_atual', 0):,.2f}
Custos: CPC R$ {dados_custos.get('cpc_atual', 0):.2f} (MoM: {dados_custos.get('var_cpc_mes', 0):+.1f}%) | CPM R$ {dados_custos.get('cpm_atual', 0):.2f} (MoM: {dados_custos.get('var_cpm_mes', 0):+.1f}%) | CPE R$ {dados_custos.get('cpe_atual', 0):.2f} (MoM: {dados_custos.get('var_cpe_mes', 0):+.1f}%)
Criativos: {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhum criativo fornecido."}

Sintetize os blocos anteriores em uma abertura executiva com profundidade analítica:
- O que aconteceu: resumo factual dos movimentos mais significativos com números exatos.
- Por que aconteceu: construa hipóteses causais cruzando os dados. Se CPC caiu e CTR subiu, a causa provável é melhoria de relevância do anúncio. Se investimento caiu e sessões subiram, pode ser efeito do orgânico compensando. Não afirme causalidade sem evidência nos dados — use "os dados sugerem que" quando houver correlação mas não causalidade clara.
- O que significa: traduza os números em implicações estratégicas. "A queda de X%% no CPM combinada com aumento de Y%% no CTR indica que a operação está entrando em um ciclo virtuoso de eficiência" ou "o aumento simultâneo de CPC e CPM com queda de CTR configura um cenário de alerta — a operação está pagando mais por menos resultado."
- Eficiência do funil completo: calcule as taxas de conversão entre cada etapa (Impressões → Cliques = CTR, Cliques → Sessões = taxa de aterrissagem, Alcance → Engajamento = taxa de engajamento). Compare MoM. Onde o funil está estreitando? Onde está alargando?
- Veredicto executivo: em uma frase, classifique o período como EXPANSÃO, OTIMIZAÇÃO, ESTABILIDADE, CONTRAÇÃO ou CRISE, justificando com os 3 dados mais relevantes.

---

**BLOCO 4 — DESTAQUES DO PERÍODO**

Extraia 5 a 7 fatos mais relevantes do período. Para cada destaque:
- Título curto e impactante (ex: "Efeito Tesoura Confirmado: -12%% investimento, +8%% cliques")
- Parágrafo narrativo denso com: o dado exato, o contexto que o torna relevante (comparação MoM/YoY), a causa provável baseada nos cruzamentos de dados dos blocos anteriores, e a implicação prática (o que fazer com essa informação).
- Classificação: CONQUISTA, ALERTA ou OPORTUNIDADE.

Cubra obrigatoriamente:
1. Principal ganho de eficiência — quantifique em termos de "economia" ou "produtividade" (ex: "cada clique custou R$ X a menos, gerando economia estimada de R$ Y no período").
2. Métrica de maior crescimento — e o que está causando esse crescimento (é sustentável ou pontual?).
3. Principal sinal de alerta — com cenário projetado: "se essa tendência continuar por mais 2 meses, o impacto estimado é..."
4. Correlação mais significativa entre métricas — qual cruzamento de dados revelou o insight mais importante?
5. Oportunidade concreta com maior potencial de impacto — estimativa de ganho se implementada.
6. Tendência geral: a operação está melhorando, piorando ou se transformando? Qual é a trajetória dos últimos períodos disponíveis?
7. (Opcional) Fato contraintuitivo — algo que parece negativo mas é positivo, ou vice-versa, quando contextualizado.

---

**REGRAS GERAIS:**
- Não invente dados ou benchmarks. Use apenas os números fornecidos.
- Cada frase deve conter um dado concreto. Sem linguagem genérica.
- Tom: técnico, direto, de especialista sênior. Prosa corrida, narrativo.
- Não use listas de bullet points como estrutura principal.
- Escreva em português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido)


def gerar_analise_operacional(dados_investimentos, dados_custos, dados_seo, descricoes_imagens, descricoes_imagens_mes_passado, analise_performance, modelo_escolhido="Gemini"):
    """ETAPA 2: Análise Operacional — substitui gerar_analise_criativos, gerar_analise_midias_pagas e gerar_analise_seo."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva um documento analítico completo cobrindo a operação digital da Syngenta em três dimensões: criativos, mídias pagas e SEO/conteúdo. Esta é a SEGUNDA ETAPA do relatório. Você já possui a análise de performance e contexto da etapa anterior.

Escreva em prosa corrida, técnica e narrativa. Não use listas de bullet points como estrutura principal. Cada afirmação deve ser sustentada por dados concretos.

---

**ANÁLISE DE PERFORMANCE E CONTEXTO (Etapa 1 — já realizada):**
{analise_performance}

---

**BLOCO 1 — ANÁLISE DE CRIATIVOS**

Criativos do Mês Atual: {chr(10).join(descricoes_imagens) if descricoes_imagens else "Nenhum criativo do mês atual fornecido."}
Criativos do Mês Passado: {chr(10).join(descricoes_imagens_mes_passado) if descricoes_imagens_mes_passado else "Nenhum criativo do mês passado fornecido."}

Indicadores de Eficiência Criativa:
| Indicador | Valor | Var. MoM | Var. YoY |
|-----------|-------|----------|----------|
| CPE | R$ {dados_custos.get('cpe_atual', 0):.2f} | {dados_custos.get('var_cpe_mes', 0):+.1f}% | {dados_custos.get('var_cpe_ano', 0):+.1f}% |
| CPC | R$ {dados_custos.get('cpc_atual', 0):.2f} | {dados_custos.get('var_cpc_mes', 0):+.1f}% | {dados_custos.get('var_cpc_ano', 0):+.1f}% |
| CPV | R$ {dados_custos.get('cpv_atual', 0):.2f} | {dados_custos.get('var_cpv_mes', 0):+.1f}% | {dados_custos.get('var_cpv_ano', 0):+.1f}% |
| CPM | R$ {dados_custos.get('cpm_atual', 0):.2f} | {dados_custos.get('var_cpm_mes', 0):+.1f}% | {dados_custos.get('var_cpm_ano', 0):+.1f}% |

Analise em profundidade:
- Estratégia narrativa: qual mensagem central cada criativo comunica? Para qual público? Está alinhado com o momento do agronegócio (safra, entressafra, lançamento)?
- Psicologia aplicada: quais gatilhos estão sendo usados (urgência, autoridade técnica, prova social, identificação com o produtor rural, medo de perda de safra)? Está falando a linguagem do campo ou é genérico demais?
- Evolução mês a mês: se há criativos dos dois meses, o que mudou? A mudança foi intencional e estratégica ou aleatória? Quais elementos visuais foram mantidos como âncora de marca?
- ROI criativo: correlacione CADA mudança visual/narrativa identificada com as variações de CPE/CPC. Se CPE caiu, qual elemento provavelmente causou (CTA mais claro, cor mais contrastante, mensagem mais direta)? Se CPC subiu, o criativo pode estar gerando curiosidade sem entregar a promessa?
- Fadiga criativa: se os criativos são muito similares mês a mês, há risco de saturação do público. Se são muito diferentes, pode faltar consistência de marca.
- Recomendações concretas: testes A/B específicos sugeridos (ex: "testar versão com CTA direto vs. CTA de curiosidade"), formatos a explorar (carrossel, Reels, UGC de produtor), ajustes de composição visual.

---

**BLOCO 2 — MÍDIAS PAGAS POR CANAL**

Investimentos por Canal:
| Canal | Atual | Var. MoM | Var. YoY |
|-------|-------|----------|----------|
| Facebook | R$ {dados_investimentos.get('fb_atual', 0):,.2f} | {dados_investimentos.get('var_fb_mes', 0):+.1f}% | {dados_investimentos.get('var_fb_ano', 0):+.1f}% |
| Instagram | R$ {dados_investimentos.get('ig_atual', 0):,.2f} | {dados_investimentos.get('var_ig_mes', 0):+.1f}% | {dados_investimentos.get('var_ig_ano', 0):+.1f}% |
| TikTok | R$ {dados_investimentos.get('tt_atual', 0):,.2f} | {dados_investimentos.get('var_tt_mes', 0):+.1f}% | {dados_investimentos.get('var_tt_ano', 0):+.1f}% |
| Google Ads | R$ {dados_investimentos.get('google_atual', 0):,.2f} | {dados_investimentos.get('var_google_mes', 0):+.1f}% | {dados_investimentos.get('var_google_ano', 0):+.1f}% |
| YouTube | R$ {dados_investimentos.get('yt_atual', 0):,.2f} | — | — |
| PMax | R$ {dados_investimentos.get('pmax_atual', 0):,.2f} | — | — |
| TOTAL | R$ {dados_investimentos.get('total_atual', 0):,.2f} | {dados_investimentos.get('var_total_mes', 0):+.1f}% | {dados_investimentos.get('var_total_ano', 0):+.1f}% |

Analise em profundidade:
- Eficiência de capital por canal: para cada canal, calcule o custo proporcional (quanto do investimento total consome) e cruze com a participação nos resultados da Etapa 1. Se Meta consome 60%% do budget mas gera 40%% dos cliques, há ineficiência. Se Google consome 25%% e gera 35%% dos cliques, é o canal mais eficiente — quantifique a diferença.
- Análise por ecossistema: Meta (Facebook + Instagram): qual a sinergia entre as plataformas? O conteúdo é adaptado ou replicado? A audiência é complementar ou sobreposta? Google (Search + PMax): qual a relação entre investimento em search e crescimento orgânico? PMax está canibalizando tráfego orgânico de marca? TikTok: está gerando awareness real ou é vanity metric? YouTube: CPV está competitivo? O formato de vídeo está alinhado com o que funciona no agro?
- Mix de mídia: calcule a concentração de investimento (se um canal tem mais de 50%% do total, sinalize risco de dependência). Proponha um mix ideal baseado na eficiência observada nos dados — não em teoria, mas nos números reais do período.
- Realocação sugerida: se R$ X fossem movidos do canal A para o canal B, qual seria o impacto estimado baseado no CPC/CPM de cada canal? Quantifique a oportunidade.
- Tendência de alocação: o mix está mudando MoM? A mudança é intencional e estratégica ou reativa? Está alinhada com os resultados?

CRUZAMENTO DE DADOS POR CANAL — cruze os investimentos entre canais e com os custos globais:
- Se um canal teve investimento aumentado e os custos globais (CPC/CPM) caíram, esse canal pode estar puxando a eficiência para cima.
- Se um canal concentra mais de 50%% do investimento total, sinalize risco de dependência.
- Se TikTok ou YouTube têm investimento zero ou mínimo comparado a Meta/Google, descreva como oportunidade de diversificação.
- Se o investimento total caiu mas a distribuição entre canais mudou, analise se a realocação foi inteligente (migrou para canais mais eficientes?) ou apenas um corte proporcional.
- Cruze variações MoM de cada canal: quais canais cresceram e quais encolheram? Isso está alinhado com os resultados gerais da Etapa 1?

---

**BLOCO 3 — SEO E CONTEÚDO**

Dados SEO:
| Métrica | Atual | Mês Passado | Var. MoM |
|---------|-------|-------------|----------|
| Visualizações (Total) | {dados_seo.get('vis_total_atual', 0):,} | {dados_seo.get('vis_total_mes', 0):,} | {dados_seo.get('var_vis_total_mes', 0):+.1f}% |
| Sessões (Total) | {dados_seo.get('sess_total_atual', 0):,} | {dados_seo.get('sess_total_mes', 0):,} | — |
| Usuários (Total) | {dados_seo.get('user_total_atual', 0):,} | {dados_seo.get('user_total_mes', 0):,} | — |
| Visualizações Orgânicas | {dados_seo.get('vis_org_atual', 0):,} | {dados_seo.get('vis_org_mes', 0):,} | {dados_seo.get('var_vis_org_mes', 0):+.1f}% |
| Sessões Orgânicas | {dados_seo.get('sess_org_atual', 0):,} | {dados_seo.get('sess_org_mes', 0):,} | {dados_seo.get('var_sess_org_mes', 0):+.1f}% |
| Usuários Orgânicos | {dados_seo.get('user_org_atual', 0):,} | {dados_seo.get('user_org_mes', 0):,} | — |

Top Keywords: {dados_seo.get('top_keywords', 'Nenhuma keyword fornecida')}

Analise em profundidade:
- Demanda de mercado via buscas: as top keywords são de marca (ex: "Syngenta") ou genéricas (ex: "fungicida para soja")? Keywords de marca indicam awareness consolidado. Keywords genéricas indicam captura de demanda ativa. Qual é a proporção e o que isso significa para a estratégia?
- Autoridade de marca: se o tráfego orgânico está crescendo, a Syngenta está ganhando autoridade nos motores de busca. Se está caindo, o conteúdo não está respondendo às perguntas do público ou concorrentes estão produzindo conteúdo melhor. Analise a taxa de crescimento/queda e o que ela implica.
- Funil de conteúdo: visualizações → sessões → usuários. Qual a taxa de conversão entre cada etapa? Se há muitas visualizações mas poucas sessões, o conteúdo aparece nos resultados mas não atrai clique (problema de meta description/título). Se há muitas sessões mas poucos usuários únicos, são retornos frequentes (fidelização — positivo).
- Qualidade do tráfego orgânico vs. pago: o orgânico está gerando sessões mais longas? Mais páginas por visita? Se os dados permitem, compare a qualidade do usuário orgânico vs. pago.
- Content gap analysis: baseado nas keywords, quais temas o público está buscando que a Syngenta não está cobrindo? Onde há volume de busca sem conteúdo correspondente?
- Custo evitado pelo orgânico: cada sessão orgânica é uma sessão que não precisou ser comprada via pago. Calcule: sessões orgânicas × CPC médio = "o tráfego orgânico representou R$ X em economia de mídia paga."

CRUZAMENTO ORGÂNICO VS. PAGO:
- Calcule a proporção de tráfego orgânico sobre o total. Se o orgânico está crescendo enquanto o pago se mantém, a marca está construindo independência de mídia.
- Se o orgânico está caindo enquanto o pago cresce, a dependência de investimento está aumentando — isso é um risco de longo prazo.
- Se ambos crescem, a operação está saudável em ambas as frentes. Se ambos caem, há um problema estrutural.
- Cruze sessões orgânicas com os dados de investimento da Etapa 1: cada real a menos em pago que é compensado por orgânico é economia direta.

---

**REGRAS GERAIS:**
- Não invente dados ou benchmarks. Use apenas os números fornecidos.
- Não repita o que foi dito na Etapa 1 — construa sobre ela e avance.
- Tom: técnico, narrativo, de especialista sênior. Prosa corrida.
- Escreva em português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido)


def gerar_relatorio_interno(analise_performance, analise_operacional, dados_metrica_performance, dados_investimentos, dados_custos, dados_seo, modelo_escolhido="Gemini"):
    """ETAPA 3: Relatório Interno Completo — substitui gerar_diagnostico_eficiencia, gerar_red_flags, gerar_mapa_oportunidades, gerar_proximos_passos e compilar_guia_slides(interno)."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva o RELATÓRIO INTERNO COMPLETO da operação digital da Syngenta. Este documento é EXCLUSIVAMENTE INTERNO da Macfor — deve ser 100%% honesto, cru, com autocrítica e riscos identificados sem filtro.

Esta é a TERCEIRA ETAPA. Você já possui as duas análises anteriores. NÃO repita o que já foi dito — construa sobre elas com profundidade adicional e honestidade total.

---

**ETAPA 1 — ANÁLISE DE PERFORMANCE E CONTEXTO:**
{analise_performance}

**ETAPA 2 — ANÁLISE OPERACIONAL:**
{analise_operacional}

---

**DADOS COMPLEMENTARES:**

Investimentos: Total R$ {dados_investimentos.get('total_atual', 0):,.2f} (MoM: {dados_investimentos.get('var_total_mes', 0):+.1f}%, YoY: {dados_investimentos.get('var_total_ano', 0):+.1f}%)
CPC: R$ {dados_custos.get('cpc_atual', 0):.2f} (MoM: {dados_custos.get('var_cpc_mes', 0):+.1f}%, YoY: {dados_custos.get('var_cpc_ano', 0):+.1f}%) | CPM: R$ {dados_custos.get('cpm_atual', 0):.2f} (MoM: {dados_custos.get('var_cpm_mes', 0):+.1f}%, YoY: {dados_custos.get('var_cpm_ano', 0):+.1f}%) | CPE: R$ {dados_custos.get('cpe_atual', 0):.2f} (MoM: {dados_custos.get('var_cpe_mes', 0):+.1f}%, YoY: {dados_custos.get('var_cpe_ano', 0):+.1f}%) | CPV: R$ {dados_custos.get('cpv_atual', 0):.2f} (MoM: {dados_custos.get('var_cpv_mes', 0):+.1f}%, YoY: {dados_custos.get('var_cpv_ano', 0):+.1f}%)
Cliques: {dados_metrica_performance.get('cli_atual', 0):,} (MoM: {dados_metrica_performance.get('var_cli_mes', 0):+.1f}%, YoY: {dados_metrica_performance.get('var_cli_ano', 0):+.1f}%) | Engajamentos: {dados_metrica_performance.get('eng_atual', 0):,} (MoM: {dados_metrica_performance.get('var_eng_mes', 0):+.1f}%) | Sessões: {dados_metrica_performance.get('sess_atual', 0):,} (MoM: {dados_metrica_performance.get('var_sess_mes', 0):+.1f}%) | Alcance: {dados_metrica_performance.get('reach_atual', 0):,} (MoM: {dados_metrica_performance.get('var_reach_mes', 0):+.1f}%) | Impressões: {dados_metrica_performance.get('imp_atual', 0):,} (MoM: {dados_metrica_performance.get('var_imp_mes', 0):+.1f}%)
Tráfego Orgânico: {dados_seo.get('vis_org_atual', 0):,} visualizações | Keywords: {dados_seo.get('top_keywords', 'Não informado')}

---

Escreva o documento com os seguintes blocos, em prosa corrida:

**BLOCO 1 — DIAGNÓSTICO DE EFICIÊNCIA OPERACIONAL**

Índice de Produtividade Digital (IPD): calcule a razão entre variação de resultados e variação de investimento. Se investimento caiu 10%% e cliques caíram 5%%, o IPD = 0.5 (perdeu metade da proporção — eficiência melhorou). Se investimento caiu 10%% e cliques SUBIRAM 5%%, o IPD = -0.5 (ganho de produtividade — Efeito Tesoura confirmado). Calcule o IPD para cada par investimento/métrica (cliques, sessões, engajamentos, alcance) e apresente uma tabela mental de eficiência.

Custo por resultado unitário — para CADA custo (CPC, CPM, CPE, CPV):
1. Classifique como OTIMIZANDO (queda >5%%), ESTÁVEL (-5%% a +5%%) ou INFLACIONANDO (alta >5%%)
2. Cruze MoM com YoY: se CPC caiu MoM mas subiu YoY, a melhoria é recente e ainda não recuperou o patamar histórico — quantifique quanto falta
3. Calcule o impacto financeiro: "a queda de X%% no CPC, aplicada sobre Y cliques, representa economia de R$ Z vs. o mês anterior"
4. Identifique a CAUSA provável: otimização de campanha? Menor competição no leilão? Mudança de mix de canais? Sazonalidade?

Eficiência de funil — calcule TODAS as taxas de conversão:
- Impressões → Cliques (CTR): está melhorando? O criativo/copy está mais relevante?
- Cliques → Sessões (taxa de aterrissagem): se sessões < cliques, há perda no caminho (página lenta, redirect quebrado, bounce imediato). Quantifique a perda.
- Alcance → Engajamento (taxa de engajamento por pessoa alcançada): está subindo? O conteúdo é mais envolvente?
- Impressões → Alcance (frequência média): impressões/alcance = frequência. Acima de 3x indica saturação. Acima de 5x é fadiga crítica.

Score de Saúde Digital (1-10): construa o score com critérios explícitos:
- Custos todos otimizando: +2 pontos. Todos inflacionando: -2 pontos.
- Efeito Tesoura presente: +2 pontos. Efeito Tesoura invertido (mais gasto, menos resultado): -2 pontos.
- Orgânico crescendo: +1 ponto. Orgânico caindo: -1 ponto.
- Funil sem gargalos: +1 ponto. Gargalo identificado: -1 ponto.
- Base: 5 pontos (operação neutra). Justifique cada ajuste.

CRUZAMENTOS OBRIGATÓRIOS — vá além da superfície:
- Matriz de custos 4x4: cruze TODOS os 4 custos entre si. Se CPC cai mas CPM sobe, a relevância melhorou (mais cliques por impressão) mas o custo de exibição aumentou (mais competição). Se CPE cai e CPC sobe, o conteúdo engaja mas não converte em clique. Se CPV cai e tudo mais sobe, vídeo é o formato mais eficiente. Descreva o PADRÃO GERAL: "3 de 4 custos estão caindo, indicando..."
- Economia real calculada: para cada custo que caiu, calcule: custo_anterior × volume_atual - custo_atual × volume_atual = economia em reais. Some tudo: "a otimização total do período representa R$ X em economia operacional."
- Trajetória MoM vs. YoY: para cada métrica, identifique o padrão: (a) subiu MoM E YoY = crescimento consistente, (b) subiu MoM, caiu YoY = recuperação em andamento, (c) caiu MoM, subiu YoY = retração recente em tendência positiva, (d) caiu MoM E YoY = declínio estrutural. Quantos indicadores estão em cada categoria?
- Orgânico como hedge: calcule %% do tráfego total que é orgânico. Compare com o mês anterior. Se cresceu, a operação está construindo um "colchão" que reduz dependência de mídia paga. Quantifique: "se o investimento em pago fosse cortado pela metade, o orgânico sustentaria X%% da operação atual."

**BLOCO 2 — RED FLAGS E PONTOS DE ATENÇÃO**

Para cada red flag, construa uma ficha completa:
- SINAL: o dado exato que dispara o alerta (ex: "CPM subiu 18%% MoM enquanto impressões caíram 7%%")
- EVIDÊNCIA CRUZADA: outro dado que confirma ou agrava o sinal (ex: "confirmado pelo aumento de 12%% no CPC no mesmo período")
- CAUSA PROVÁVEL: hipótese baseada nos dados, não especulação (ex: "aumento de competidores no leilão Meta, evidenciado pelo aumento de custos sem mudança de segmentação")
- IMPACTO QUANTIFICADO: traduza em reais ou %% (ex: "se a tendência continuar por mais 2 meses, o custo por clique subirá de R$ X para R$ Y, aumentando o custo mensal em R$ Z")
- CENÁRIO PROJETADO: o que acontece em 30, 60 e 90 dias se nada for feito?
- AÇÃO RECOMENDADA: específica e executável (não "melhorar criativos", mas "testar 3 novos criativos com CTA direto focando no público 35-54 no Google Ads")
- URGÊNCIA: CRÍTICA (agir esta semana), ALTA (agir em 15 dias), MÉDIA (agir em 30 dias), BAIXA (monitorar)

Investigue CADA um destes cenários — se não se aplica, diga por quê:
1. Inflação de custos acima de 10%% em qualquer métrica — qual custo, por quê, e quanto está custando a mais
2. Queda de resultados acima de 15%% em qualquer métrica — é sazonal, estrutural, ou pontual?
3. Efeito Tesoura invertido: investimento subiu E resultados caíram — calcule a perda de produtividade
4. Concentração de risco: se um canal representa mais de 50%% do investimento, o que acontece se ele ficar indisponível ou os custos dobrarem?
5. Fadiga de audiência: frequência média acima de 3x, CTR em queda constante por 2+ meses
6. Gargalo de funil: onde a maior perda proporcional está acontecendo (impressões→cliques? cliques→sessões?)
7. Dependência de pago: se orgânico representa menos de 20%% do tráfego, é risco estrutural
8. Desalinhamento criativo-resultado: se criativos mudaram mas métricas não reagiram (positiva ou negativamente), o problema pode ser de segmentação, não de criativo

Se a operação está saudável (nenhum alerta significativo), documente com a mesma profundidade: POR QUE está saudável, quais métricas confirmam, e quais sinais positivos merecem destaque.

**BLOCO 3 — MAPA DE OPORTUNIDADES**

Para cada oportunidade, construa o business case:
- OPORTUNIDADE: descrição clara e específica (não "investir mais em TikTok", mas "realocar R$ X de Facebook para TikTok focando em vídeos curtos de demonstração de produto, onde o CPV é Y%% menor")
- EVIDÊNCIA NOS DADOS: qual dado sustenta essa oportunidade (ex: "TikTok tem CPV de R$ 0.03 vs. R$ 0.08 no YouTube — 62%% mais barato")
- POTENCIAL DE IMPACTO: quantifique em reais ou %% (ex: "realocando 15%% do budget Meta para TikTok, estimamos ganho de X engajamentos adicionais a custo Y%% menor")
- INVESTIMENTO NECESSÁRIO: em reais, horas de equipe, ou ambos
- PRAZO DE RETORNO: quando os primeiros resultados seriam visíveis (7 dias? 30 dias? 90 dias?)
- RISCO DE NÃO AGIR: o que se perde por não explorar (ex: "concorrentes podem ocupar esse espaço primeiro")
- AÇÃO ESPECÍFICA: passo a passo executável em 3-5 itens

Categorize e ordene por impacto/esforço:
1. QUICK WINS (alto impacto, baixo esforço) — 3 oportunidades que podem ser implementadas em até 7 dias com os recursos atuais. Ex: ajuste de bid, redistribuição de budget entre campanhas, teste A/B de copy.
2. MOVIMENTOS TÁTICOS (alto impacto, médio esforço) — 2-3 oportunidades que exigem planejamento de 2-4 semanas. Ex: novo formato criativo, entrada em novo canal, reestruturação de campanhas.
3. APOSTAS ESTRATÉGICAS (alto impacto, alto esforço) — 1-2 oportunidades de longo prazo. Ex: programa de conteúdo orgânico, influencer marketing no agro, automação de campanhas.

Cubra obrigatoriamente: oportunidades de canal (canais subexplorados), audiência (segmentos não atingidos), conteúdo (temas com demanda não atendida via keywords), eficiência (realocações de budget baseadas em dados), sazonalidade agro (próxima safra, eventos do setor), e competitivas (espaços vazios que a concorrência não ocupa).

**BLOCO 4 — PRÓXIMOS PASSOS E PLANO DE AÇÃO**

Bloco de Inteligência Acumulada: 3-5 descobertas mais importantes do período, cada uma com:
- O insight em uma frase
- O dado que o sustenta
- A implicação para os próximos 30-90 dias
- Como esse insight muda a estratégia (ou confirma que a estratégia atual está correta)

AÇÕES IMEDIATAS (0-30 dias) — máxima especificidade:
Para cada ação: o que fazer, quem deve fazer (mídia, criativo, conteúdo, estratégia), prazo, KPI de sucesso, e como medir.
Prioridades: (1) resolver red flags urgentes com impacto financeiro quantificado, (2) implementar quick wins do mapa de oportunidades, (3) ajustes de budget baseados na análise de eficiência por canal, (4) testes A/B prioritários com hipótese clara.

MOVIMENTOS TÁTICOS (30-60 dias):
Para cada movimento: objetivo, recurso necessário, resultado esperado com meta numérica, risco de execução.
Prioridades: (1) novos canais/formatos identificados como oportunidade, (2) reestruturação de campanhas com baixa eficiência, (3) programa de conteúdo para fortalecer orgânico, (4) otimização de landing pages se há gargalo clique→sessão.

VISÃO ESTRATÉGICA (60-180 dias):
Para cada diretriz: a tese, as evidências nos dados, o investimento estimado, o retorno projetado.
Temas: (1) mix de mídia ideal baseado nos dados de eficiência atuais — qual seria a distribuição ótima? (2) meta de %% orgânico sobre total para reduzir dependência de pago, (3) construção de ativos digitais proprietários (conteúdo evergreen, base de leads, comunidade), (4) posicionamento competitivo — onde a Syngenta deve estar daqui a 6 meses que não está hoje?

MATRIZ DE PRIORIZAÇÃO FINAL: ordene TODAS as ações (imediatas + táticas + estratégicas) em uma sequência lógica de execução, indicando dependências ("ação B só pode começar após ação A") e conflitos de recurso ("ações C e D competem pelo mesmo budget — escolher uma").

**BLOCO 5 — GUIA DE COMPOSIÇÃO DE SLIDES PARA REVIEW INTERNO**

Este não é um resumo de conteúdo — é um BRIEFING CRIATIVO para o designer e o apresentador. O deck conta uma história: abre com contexto, constrói tensão com problemas, resolve com soluções, e fecha com direção clara.

ARCO NARRATIVO DO DECK: Contexto (slides 1-3) → Diagnóstico (slides 4-6) → Profundidade Operacional (slides 7-9) → Direção (slides 10-12).

Para CADA um dos 12 slides, especifique:

**COMPOSIÇÃO VISUAL:**
- Layout: descreva a disposição dos elementos na tela (ex: "2/3 esquerdo: gráfico de barras agrupadas. 1/3 direito: 3 KPI cards empilhados com setas de variação. Rodapé: faixa com insight em destaque.")
- Hierarquia visual: o que o olho deve ver PRIMEIRO (dado-destaque em fonte grande), SEGUNDO (gráfico de suporte), TERCEIRO (contexto/texto)
- Paleta de cores: use MACFOR_AZUL (#1B3A5C) para títulos e elementos âncora, MACFOR_AZUL_CLARO (#2E86C1) para dados positivos, MACFOR_VERDE (#27AE60) para crescimento, vermelho (#E74C3C) para alertas, MACFOR_CINZA (#5D6D7E) para textos secundários
- Tipografia: títulos em fonte bold condensada, dados-destaque em fonte extra-bold tamanho 48+, texto corrido em regular tamanho 14-16

**CONTEÚDO E DADOS:**
- Título do slide (curto, impactante, com dado quando possível — ex: "Efeito Tesoura: -12%% custo, +8%% resultado")
- Objetivo narrativo: por que esse slide existe na sequência? O que ele prepara para o próximo?
- Dados específicos a exibir: quais números, em qual formato (absoluto, %%, variação)
- Tipo de visualização com justificativa: por que barras agrupadas e não linha? Por que donut e não barras? A escolha deve servir à narrativa.

**DIREÇÃO PARA O APRESENTADOR:**
- Talking points: 2-3 frases que o apresentador deve dizer, conectando este slide ao anterior e ao próximo
- Transição: como introduzir o próximo slide (ex: "Esses resultados positivos nos permitem focar agora nos pontos que exigem atenção...")
- Pergunta a provocar: se relevante, qual pergunta retórica engaja a audiência (ex: "Se o CPC caiu 15%%, por que não estamos investindo mais?")

Estrutura do deck:
1. **Capa** — título "Review Interno | Syngenta | [Mês/Ano]", logo Macfor, cor sólida MACFOR_AZUL. Sem dados.
2. **Sumário Executivo** — Score de Saúde (número grande central), 3 KPIs principais com variação, veredicto do período em 1 frase. Objetivo: dar o veredito antes do detalhe.
3. **Panorama de Performance** — gráfico de barras agrupadas MoM/YoY com 4-6 métricas principais. Destaque visual no Efeito Tesoura se existir. Transição: "agora vamos entender o que está por trás desses números."
4. **Diagnóstico de Saúde Financeira** — tabela de custos (CPC/CPM/CPE/CPV) com semáforo de cores (verde/amarelo/vermelho). Economia calculada em destaque. Transição: "onde estão os riscos?"
5. **Red Flags** — layout de cards de alerta (ícone + título + impacto quantificado). Máximo 4 flags por slide. Vermelho para urgência alta, amarelo para média. Transição: "como estamos respondendo criativamente?"
6. **Análise de Criativos** — 2-3 thumbnails dos criativos lado a lado com métricas embaixo (CPE, CPC). Setas conectando elementos visuais a resultados. Transição: "e o investimento está distribuído da melhor forma?"
7. **Performance de Mídias Pagas** — donut chart de mix de mídia + barras de eficiência por canal. Destaque visual no canal mais eficiente e no mais ineficiente. Transição: "olhando além do pago..."
8. **ROI e Produtividade** — gráfico de scatter ou waterfall mostrando investimento vs. resultado. Cálculo de economia em destaque. Efeito Tesoura visual se aplicável.
9. **SEO + Content** — gráfico de linha orgânico vs. pago ao longo do tempo. %% orgânico em destaque. Custo evitado em callout. Transição: "com esse diagnóstico completo, quais são as oportunidades?"
10. **Mapa de Oportunidades** — matriz 2x2 (impacto x esforço) com as oportunidades posicionadas. Quick wins destacados em verde. Transição: "vamos ao plano..."
11. **Próximos Passos** — timeline visual (0-30, 30-60, 60-180 dias) com ações posicionadas. Destaque nos 3 primeiros quick wins. Transição: "quem faz o quê?"
12. **Plano de Ação + Responsáveis** — tabela com: ação, responsável, prazo, KPI, status. Fechamento com próxima reunião de review.

Tom: 100%% honesto. Inclua autocríticas, problemas de processo, riscos de churn do cliente, gaps de entrega. O time interno precisa sair dessa reunião sabendo exatamente o que está bom, o que está ruim, e o que fazer.

---

**REGRAS GERAIS:**
- Não invente dados ou benchmarks. Use apenas os números fornecidos.
- Compare sempre: valor atual vs. MoM vs. YoY. Esses são os ÚNICOS benchmarks válidos.
- Tom: técnico, honesto, de especialista sênior falando internamente. Sem diplomacia excessiva. Prosa corrida.
- Escreva em português do Brasil.
"""
    return gerar_texto(prompt, modelo_escolhido)


def gerar_relatorio_cliente(analise_performance, analise_operacional, relatorio_interno_completo, modelo_escolhido="Gemini"):
    """ETAPA 4: Relatório do Cliente Completo — substitui compilar_relatorio_cliente e compilar_guia_slides(cliente)."""
    prompt = f"""
Você é um especialista sênior em marketing digital. Escreva o RELATÓRIO COMPLETO PARA O CLIENTE (Syngenta). Este documento é a entrega mensal da Macfor — é assim que a agência justifica seu fee, demonstra valor e garante a renovação do contrato.

Esta é a QUARTA e ÚLTIMA ETAPA. Você possui todas as análises anteriores. Reescreva e reinterprete TUDO com tom de parceiro estratégico entregando resultado.

---

**ETAPA 1 — ANÁLISE DE PERFORMANCE E CONTEXTO:**
{analise_performance}

**ETAPA 2 — ANÁLISE OPERACIONAL:**
{analise_operacional}

**ETAPA 3 — RELATÓRIO INTERNO (base para reescrita diplomática):**
{relatorio_interno_completo}

---

**DIFERENÇA FUNDAMENTAL VS. RELATÓRIO INTERNO:**
- NÃO exponha vulnerabilidades — apresente como aprendizados e otimizações.
- NÃO use "estamos testando" — use "implementamos a estratégia X que gerou Y."
- CADA dado deve ser ENQUADRADO como valor entregue pela Macfor.
- Red flags viram "oportunidades identificadas proativamente pela equipe."
- O tom é de PARCEIRO ESTRATÉGICO entregando resultado, não de fornecedor prestando contas.
- Use dados históricos da própria Syngenta (MoM e YoY) como referência. NÃO invente benchmarks.
- O cliente deve sair pensando: "estou bem assessorado, a Macfor entende do meu negócio."

---

Escreva o documento com os seguintes blocos:

**BLOCO 1 — SUMÁRIO EXECUTIVO**
Abertura em 2-3 parágrafos de alto nível. Estrutura:
- Frase de abertura com o veredicto do período em tom confiante (ex: "O mês de [período] consolidou um ciclo de ganho de eficiência na operação digital da Syngenta, com destaque para...")
- O dado mais impressionante do período em destaque narrativo, contextualizado com MoM/YoY
- Síntese dos 3 principais resultados, cada um com número e enquadramento positivo
- Se houver Efeito Tesoura: destaque como conquista central ("com X%% menos investimento, entregamos Y%% mais resultados — eficiência que se traduz em R$ Z de economia operacional")
- Fechamento com visão de futuro: o que o próximo mês reserva baseado na trajetória atual
O cliente deve ler APENAS este bloco e já sentir que o mês foi produtivo e que a Macfor está gerando valor.

**BLOCO 2 — PANORAMA DO PERÍODO**
Contextualização profunda do cenário com foco em CONQUISTAS:
- Momento do mercado agro: safra, entressafra, lançamento de produtos? Como a operação digital se alinhou ao momento comercial da Syngenta?
- Evolução da presença digital: compare o tamanho da operação (alcance, impressões, engajamentos) com o período anterior. Enquadre crescimentos como expansão de presença. Enquadre reduções como "otimização focada em qualidade sobre quantidade."
- Eficiência histórica: compare os custos atuais com o YoY. Se melhoraram, é "maturação da operação." Se pioraram, é "investimento em novos públicos/formatos com curva de aprendizado esperada."
- Posicionamento digital da marca: como a Syngenta está se posicionando vs. o que o mercado espera? O conteúdo está gerando autoridade técnica?
Cada afirmação deve ter um dado concreto. Não há espaço para generalidades.

**BLOCO 3 — RESULTADOS E CONQUISTAS**
Apresente CADA métrica como conquista tangível com profundidade:
- Para cada métrica principal (investimento, sessões, alcance, impressões, cliques, engajamentos, CTR, VTP), construa uma narrativa de conquista:
  - O número em si, com comparação MoM e YoY
  - O enquadramento positivo: crescimentos são "alcançamos", "superamos o período anterior em X%%". Quedas são "otimizamos foco" ou "redirecionamos para canais de maior eficiência, resultando em..."
  - A implicação para o negócio: "os X mil cliques adicionais representam Y potenciais produtores rurais impactados pela mensagem da Syngenta"
- Eficiência como conquista central: "cada real investido gerou X%% mais resultado que no período anterior"
- Cruze resultados com investimento: demonstre produtividade. O cliente quer saber se o dinheiro dele está sendo bem usado.
- Se houver métricas negativas, NUNCA ignore — reframe com diplomacia: "identificamos oportunidade de otimização em [métrica], com ajustes já em implementação para o próximo ciclo."

**BLOCO 4 — INTELIGÊNCIA DE MERCADO ENTREGUE**
Posicione a Macfor como consultoria estratégica que vai além da operação:
- Insights competitivos: o que a equipe identificou sobre o cenário competitivo digital no agro? Use linguagem de consultoria: "Nossa inteligência de mercado identificou que..."
- Tendências de comportamento: o que os dados de busca (keywords) revelam sobre o que o público-alvo está procurando? "Identificamos crescimento de X%% nas buscas por [tema], sinalizando demanda latente que a Syngenta pode capturar."
- Correlações não-óbvias: apresente 2-3 cruzamentos de dados que só um especialista identificaria. Enquadre como valor exclusivo: "A análise cruzada de [métrica A] com [métrica B] revelou um padrão de [insight] — informação que permite antecipar [ação]."
- Sazonalidade e timing: como os dados se alinham com o calendário agrícola? Quais janelas de oportunidade foram identificadas para os próximos meses?
O cliente deve sentir que está recebendo consultoria estratégica, não apenas um relatório de métricas.

**BLOCO 5 — ESTRATÉGIA CRIATIVA E PERFORMANCE**
Demonstre relação causa-efeito entre decisões criativas e resultados com profundidade analítica:
- Para cada criativo/campanha relevante: qual foi a DECISÃO estratégica (mensagem, visual, CTA, formato), qual foi o RESULTADO (CPE, CPC, engajamento), e qual a CORRELAÇÃO entre os dois.
- Evolução criativa: se houve mudança de criativo entre meses, demonstre que foi intencional e baseada em dados: "com base nos resultados do período anterior, ajustamos [elemento], gerando melhoria de X%% em [métrica]."
- Linguagem e posicionamento: como os criativos posicionam a Syngenta? Estão construindo autoridade técnica, proximidade com o produtor rural, ou ambos? Com quais resultados?
- Testes realizados: se houve testes A/B ou variações, apresente resultados como "aprendizado acumulado": "o teste de [variável] confirmou que [abordagem A] gera X%% mais [métrica] que [abordagem B] — inteligência que aplicaremos no próximo ciclo."
- Próximas evoluções criativas: antecipe o que será testado/implementado, enquadrando como proatividade.

**BLOCO 6 — VISÃO DE MÍDIA E EFICIÊNCIA DE INVESTIMENTO**
Este é o bloco mais importante para o cliente — é sobre o dinheiro dele:
- Distribuição de investimento por canal com justificativa estratégica para cada alocação: "X%% do budget foi direcionado a [canal] por sua eficiência superior em [métrica], gerando Y%% dos resultados totais."
- Eficiência por canal: qual canal entrega mais resultado por real? Apresente como "inteligência de alocação."
- Ganhos de eficiência quantificados: "a otimização de [ação] gerou economia de R$ X, equivalente a Y%% do investimento total."
- Se houver Efeito Tesoura: descreva em detalhe narrativo como conquista central: "pela segunda vez consecutiva, entregamos mais resultado com menos investimento — o CPC caiu X%% enquanto os cliques subiram Y%%, configurando ganho de produtividade de Z%%."
- Custo por resultado em contexto: "cada sessão custou R$ X — valor Y%% inferior ao período anterior, demonstrando maturação da operação."
- Construção de eficiência ao longo do tempo: se há dados YoY, mostre a curva de aprendizado. "Em relação ao mesmo período do ano anterior, a operação é X%% mais eficiente por real investido."

**BLOCO 7 — OPORTUNIDADES IDENTIFICADAS PARA O PRÓXIMO PERÍODO**
Apresente como proatividade da equipe Macfor — o cliente quer um parceiro que antecipa, não que reage:
- Para cada oportunidade (3-5): enquadre como "a equipe Macfor identificou proativamente que [oportunidade], com potencial estimado de [impacto]."
- Justifique cada oportunidade com dados do período: "o crescimento de X%% em [métrica] indica que [público/canal/formato] tem potencial subexplorado."
- Conecte oportunidades ao calendário agro: "com a [safra/entressafra/evento] se aproximando, identificamos janela para [ação] com potencial de [resultado]."
- Apresente o plano de captura: "para capitalizar, nossa equipe já está preparando [ação específica] para implementação em [prazo]."
- Tom: confiante e antecipativo. O cliente deve sentir que a Macfor está sempre um passo à frente.

**BLOCO 8 — RECOMENDAÇÕES ESTRATÉGICAS**
Recomendações concretas enquadradas como "consultoria estratégica baseada na inteligência acumulada":
- Para cada recomendação (3-5):
  - RECOMENDAÇÃO: ação clara e específica (não "investir mais em digital" mas "aumentar alocação em Google Ads em 15%%, redirecionando de Facebook, para capturar demanda de busca ativa identificada nas keywords")
  - JUSTIFICATIVA COM DADOS: qual dado sustenta essa recomendação (ex: "Google Ads gera sessões a CPC 30%% inferior ao Facebook, com taxa de aterrissagem 20%% superior")
  - RESULTADO ESPERADO: quantifique o ganho projetado (ex: "estimamos ganho de X sessões adicionais por mês, com economia de R$ Y")
  - TIMELINE: quando começa e quando os resultados serão visíveis
- Ordene por impacto: a recomendação mais impactante primeiro.
- Feche com visão de parceria: "essas recomendações refletem o compromisso da Macfor em não apenas executar, mas evoluir continuamente a estratégia digital da Syngenta."

**BLOCO 9 — GUIA DE COMPOSIÇÃO DE SLIDES PARA APRESENTAÇÃO AO CLIENTE**

Este é um BRIEFING CRIATIVO completo para o designer e o apresentador. O deck para o cliente conta uma história de VALOR ENTREGUE: abre com impacto, constrói confiança com resultados, demonstra inteligência estratégica, e fecha com visão de futuro. O cliente deve sair pensando: "meu investimento está bem aplicado."

ARCO NARRATIVO DO DECK: Impacto (slides 1-3) → Resultados (slides 4-6) → Inteligência (slides 7-9) → Futuro (slides 10-12).

Para CADA um dos 12 slides, especifique:

**COMPOSIÇÃO VISUAL:**
- Layout: disposição dos elementos na tela (ex: "header com KPI-destaque em fonte 48pt. Centro: gráfico de barras com anotações. Rodapé: insight contextual em itálico.")
- Hierarquia visual: PRIMEIRO (dado-conquista em destaque, fonte grande, cor de contraste), SEGUNDO (visualização que sustenta a conquista), TERCEIRO (contexto narrativo)
- Paleta de cores: MACFOR_AZUL (#1B3A5C) para elementos institucionais, MACFOR_AZUL_CLARO (#2E86C1) para dados principais, MACFOR_VERDE (#27AE60) para crescimento e conquistas, dourado/âmbar para destaques premium, MACFOR_CINZA (#5D6D7E) para textos secundários. NUNCA usar vermelho — substituir por MACFOR_CINZA para dados neutros ou MACFOR_AZUL_CLARO para "oportunidades."
- Tipografia: títulos em bold condensada, dados-destaque em extra-bold 48+, insight em regular 16pt. Evitar texto demais — máximo 6 linhas de texto por slide.
- Estilo visual: clean, premium, com bastante espaço em branco. O slide deve respirar. Menos é mais.

**CONTEÚDO E DADOS:**
- Título do slide: sempre positivo e orientado a conquista (não "Resultados do Período" mas "Performance que Supera o Histórico: +X%% em Engajamento")
- Objetivo narrativo: qual sentimento esse slide deve provocar no cliente? (confiança, impressão, clareza, entusiasmo)
- Dados específicos: quais números, como apresentados. Sempre enquadrar como conquista ou oportunidade.
- Tipo de visualização com justificativa narrativa: o gráfico deve CONTAR a história, não apenas exibir dados. Barras para comparação/superação, linhas para tendência de crescimento, donut para mostrar diversificação, waterfall para mostrar construção de valor.

**DIREÇÃO PARA O APRESENTADOR:**
- Talking points: 2-3 frases na linguagem do parceiro estratégico. Usar "nós" inclusivo. Conectar resultado a decisão ("quando decidimos realocar budget para Google, o resultado foi...")
- Transição: como conduzir para o próximo slide mantendo a narrativa de valor
- Momento de pausa: se houver um dado impressionante, indicar ao apresentador para pausar e deixar o número impactar antes de continuar

Estrutura do deck:
1. **Capa** — "Relatório Executivo de Performance Digital | Syngenta | [Mês/Ano]". Logo Syngenta + logo Macfor. Fundo MACFOR_AZUL escuro, tipografia branca/dourada. Sofisticado e premium.
2. **Sumário Executivo** — 1 número-destaque central em fonte 72pt (a maior conquista do período). 3-4 KPIs secundários em cards horizontais abaixo. 1 frase de veredicto executivo. Objetivo: o cliente saber em 5 segundos se o mês foi bom. Transição: "vamos detalhar cada uma dessas conquistas."
3. **Panorama de Performance** — gráfico de barras agrupadas (período atual vs. anterior) com as 5 métricas principais. Setas verdes nos crescimentos. Anotações inline nos destaques. Objetivo: visão geral dos números com enquadramento positivo. Transição: "esses números refletem decisões estratégicas específicas..."
4. **Conquistas do Período** — layout de 3-4 "cards de conquista" com ícone, título, número e contexto (ex: "Eficiência Máxima: CPC caiu 15%% — cada clique custou R$ X a menos"). Fundo branco, cards com borda MACFOR_AZUL_CLARO. Objetivo: transformar dados em conquistas tangíveis.
5. **Inteligência de Mercado** — visual de mapa ou radar com posicionamento competitivo. Se não houver dados de concorrentes, usar gráfico de tendência mostrando evolução consistente. Callout: "insight exclusivo identificado pela Macfor." Objetivo: demonstrar valor consultivo além da operação. Transição: "essa inteligência guia nossas decisões criativas..."
6. **Estratégia Criativa** — 2-3 thumbnails dos criativos com métricas de performance embaixo. Setas visuais conectando elementos do criativo (CTA, visual, copy) ao resultado. Objetivo: mostrar que cada peça é pensada estrategicamente, não aleatória. Transição: "a estratégia criativa é potencializada pela inteligência de mídia..."
7. **Performance de Mídias Pagas** — donut chart de distribuição de investimento por canal + barras de eficiência. Destaque no canal com melhor ROI. Narrativa: "diversificação inteligente que maximiza resultado." Objetivo: mostrar gestão sofisticada do budget.
8. **Eficiência do Investimento** — o slide mais importante. Se houver Efeito Tesoura, gráfico de linhas cruzadas (investimento caindo, resultados subindo) com área sombreada representando a economia. Número de economia em destaque: "R$ X em ganho de eficiência." Se não houver Efeito Tesoura, waterfall chart mostrando como cada otimização contribuiu. Objetivo: o cliente ver ROI tangível. Pausa dramática aqui.
9. **SEO + Conteúdo** — gráfico de área mostrando crescimento do orgânico. Custo evitado em callout: "o crescimento orgânico representou R$ X em economia de mídia." Top keywords em lista visual. Objetivo: mostrar construção de ativo de longo prazo. Transição: "com essa base sólida, identificamos oportunidades para o próximo período..."
10. **Oportunidades Identificadas** — 3-4 oportunidades em formato de cards com: ícone, título, potencial estimado. Layout limpo, cada card com gradiente sutil. Enquadrar como "a Macfor identificou proativamente." Objetivo: mostrar proatividade e visão de futuro.
11. **Próximos Passos** — timeline visual elegante (próximo mês, 60 dias, 90 dias) com 2-3 ações em cada fase. Cada ação com resultado esperado. Objetivo: o cliente saber exatamente o que vem a seguir e sentir segurança. Transição: "estamos prontos para mais um mês de excelência."
12. **Encerramento** — "Obrigado pela confiança." Dados de contato da equipe Macfor. Frase de fechamento: "Transformando dados em decisões, decisões em resultados." Logo Syngenta + Macfor. Fundo MACFOR_AZUL.

REGRAS DO DECK CLIENTE:
- NUNCA usar vermelho para dados negativos — substituir por cinza ou reframing positivo
- NUNCA expor red flags, autocríticas, ou problemas internos
- CADA slide deve ter no máximo 1 ideia principal — não sobrecarregar
- CADA dado deve ser enquadrado como valor entregue pela Macfor
- O deck deve funcionar mesmo se o apresentador não estiver lá (auto-explicativo)
- Máximo 6 linhas de texto por slide — o visual conta a história, o texto apoia

---

**REGRAS GERAIS:**
- Não invente dados ou benchmarks. Use apenas os números das etapas anteriores.
- Tom: elegante, profissional, consultivo de alto nível. Sem jargões internos de agência. Sem autocrítica. Sem incertezas.
- O cliente deve sentir que tem o melhor parceiro digital do mercado.
- Escreva em prosa corrida, técnica e narrativa. Não use listas de bullet points como estrutura principal.
- Escreva em português do Brasil.
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
        progress = st.progress(0, text="Iniciando pipeline de inteligência (4 etapas)...")

        with st.spinner("1/4 — Análise de Performance e Contexto..."):
            analise_performance = gerar_analise_performance(dados_metrica_performance, dados_investimentos, dados_custos, descricoes_imagens, info_concorrentes, modelo_escolhido)
        progress.progress(1/4, text="1/4 -- Análise de Performance e Contexto")

        with st.spinner("2/4 — Análise Operacional..."):
            analise_operacional = gerar_analise_operacional(dados_investimentos, dados_custos, dados_seo, descricoes_imagens, descricoes_imagens_mes_passado, analise_performance, modelo_escolhido)
        progress.progress(2/4, text="2/4 -- Análise Operacional")

        with st.spinner("3/4 — Relatório Interno Completo..."):
            relatorio_interno_completo = gerar_relatorio_interno(analise_performance, analise_operacional, dados_metrica_performance, dados_investimentos, dados_custos, dados_seo, modelo_escolhido)
        progress.progress(3/4, text="3/4 -- Relatório Interno Completo")

        with st.spinner("4/4 — Relatório do Cliente Completo..."):
            relatorio_cliente_completo = gerar_relatorio_cliente(analise_performance, analise_operacional, relatorio_interno_completo, modelo_escolhido)
        progress.progress(4/4, text="4/4 -- Pipeline completo!")

        # Armazenar resultados
        st.session_state.relatorio_gerado = True
        st.session_state.dados_processados = dados_metrica_performance
        st.session_state.descricoes_imagens = descricoes_imagens
        st.session_state.descricoes_imagens_mes_passado = descricoes_imagens_mes_passado
        st.session_state.analise_performance = analise_performance
        st.session_state.analise_operacional = analise_operacional
        st.session_state.relatorio_interno_completo = relatorio_interno_completo
        st.session_state.relatorio_cliente_completo = relatorio_cliente_completo

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
    # SEÇÕES ANALÍTICAS DO RELATÓRIO (Pipeline consolidado de 4 etapas)
    # =====================================================================
    st.subheader("📌 Etapa 1 — Análise de Performance e Contexto")
    st.write(st.session_state.analise_performance)

    st.subheader("⚙️ Etapa 2 — Análise Operacional")
    st.write(st.session_state.analise_operacional)

    st.subheader("📊 Etapa 3 — Relatório Interno Completo")
    st.write(st.session_state.relatorio_interno_completo)

    st.subheader("📄 Etapa 4 — Relatório do Cliente Completo")
    st.write(st.session_state.relatorio_cliente_completo)
    
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
            dados_seo=dados_seo_docx,
            analise_performance=st.session_state.get('analise_performance', ''),
            analise_operacional=st.session_state.get('analise_operacional', ''),
            relatorio_interno_completo=st.session_state.get('relatorio_interno_completo', ''),
        )

        # --- DOC 2: RELATÓRIO PARA O CLIENTE (DOCX) ---
        docx_cliente = gerar_docx_cliente(
            relatorio_cliente_completo=st.session_state.get('relatorio_cliente_completo', ''),
            analise_performance=st.session_state.get('analise_performance', ''),
            analise_operacional=st.session_state.get('analise_operacional', ''),
            dados=dados, dados_investimentos=dados_inv_docx,
            dados_custos=dados_custos_docx, dados_seo=dados_seo_docx,
        )

        # --- DOC 3: GUIA DE SLIDES — CLIENTE (DOCX) ---
        # Slide content is embedded in relatorio_cliente_completo
        docx_slides_cliente = gerar_docx_slides(
            conteudo_slides=st.session_state.get('relatorio_cliente_completo', ''),
            tipo="cliente"
        )

        # --- DOC 4: GUIA DE SLIDES — INTERNO (DOCX) ---
        # Slide content is embedded in relatorio_interno_completo
        docx_slides_interno = gerar_docx_slides(
            conteudo_slides=st.session_state.get('relatorio_interno_completo', ''),
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

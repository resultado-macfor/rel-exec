import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(layout="wide", page_title="Relatório Executivo - IA", page_icon="📊")

from ui.auth import verificar_autenticacao, inicializar_sessao
from ai.models import inicializar_modelos
from data.bigquery import get_bigquery_client
from ui.form import renderizar_sincronizacao_bq, renderizar_formulario, processar_formulario
from ui.dashboard import renderizar_dashboard


verificar_autenticacao()
inicializar_sessao()
modelo_gemini, modelo_visao, cliente_anthropic = inicializar_modelos()
client_bq = get_bigquery_client()
renderizar_sincronizacao_bq(client_bq)
submitted, form_values = renderizar_formulario()

if submitted and form_values:
    processar_formulario(form_values, modelo_visao, modelo_gemini, cliente_anthropic, client_bq)


renderizar_dashboard()

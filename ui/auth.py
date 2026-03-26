import os
import streamlit as st
from config.settings import CHAVES_SESSAO


def verificar_autenticacao():
    """Exibe tela de login se não autenticado. Retorna True se autenticado."""
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        senha_correta = os.getenv("senha_per", "")
        st.markdown("### 🔒 Acesso Restrito")
        senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar"):
            if senha_digitada == senha_correta:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
        st.stop()

    return True


def inicializar_sessao():
    """Inicializa todas as chaves do session_state para evitar KeyError."""
    for chave in CHAVES_SESSAO:
        if chave not in st.session_state:
            if chave == 'relatorio_gerado':
                st.session_state[chave] = False
            elif chave in ['descricoes_imagens', 'descricoes_imagens_mes_passado',
                           'resumos_social_csvs', 'resumos_seo_csvs']:
                st.session_state[chave] = []
            elif chave == 'dados_processados':
                st.session_state[chave] = {}
            else:
                st.session_state[chave] = ""

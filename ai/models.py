import os
import streamlit as st
import google.generativeai as genai
from anthropic import Anthropic


def inicializar_modelos():
    """Inicializa e retorna os modelos de IA disponíveis."""
    gemini_api_key = os.getenv("GEM_API_KEY", "")
    genai.configure(api_key=gemini_api_key)
    modelo_gemini = genai.GenerativeModel("gemini-2.5-flash")
    modelo_visao = genai.GenerativeModel("gemini-2.5-flash")

    anthropic_api_key = os.getenv("ANTH_KEY")

    cliente_anthropic = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

    return modelo_gemini, modelo_visao, cliente_anthropic


def gerar_texto(prompt, modelo_escolhido, modelo_gemini, cliente_anthropic):
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
            response = modelo_gemini.generate_content(prompt)
            return response.text
    else:
        response = modelo_gemini.generate_content(prompt)
        return response.text


def descrever_imagem(imagem, modelo_visao):
    """Descreve um criativo de marketing usando Gemini Vision."""
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


def calcular_variacao(atual, anterior):
    """Calcula variação percentual entre dois valores."""
    if anterior and anterior != 0:
        return ((atual - anterior) / anterior) * 100
    return 0

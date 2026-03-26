import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from ai.models import calcular_variacao
from relatorio_docx.builder import gerar_docx_relatorio, gerar_docx_cliente


def renderizar_dashboard():
    """Exibe o relatório gerado com KPIs, gráficos, narrativa e botões de download."""
    if not st.session_state.relatorio_gerado:
        return

    st.markdown("---")
    st.header("📄 Relatório Executivo Gerado")

    dados = st.session_state.dados_processados

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
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Distribuição de Investimento por Canal**")
        canais = ['Facebook', 'Instagram', 'TikTok', 'Google Ads', 'YouTube', 'PMax']
        valores_canais = [
            st.session_state.get('fb_atual', 0), st.session_state.get('ig_atual', 0),
            st.session_state.get('tt_atual', 0), st.session_state.get('google_atual', 0),
            st.session_state.get('yt_atual', 0), st.session_state.get('pmax_atual', 0)
        ]
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
    frentes = st.session_state.get('frentes_selecionadas', [])

    st.subheader("📌 1 — Cenário Atual")
    st.write(st.session_state.etapa_cenario_atual)

    st.subheader("⭐ 2 — Destaques")
    st.write(st.session_state.etapa_destaques)

    if st.session_state.get('etapa_produtos_destaque'):
        st.subheader("🌱 2.5 — Produtos Destaque por Categoria")
        st.write(st.session_state.etapa_produtos_destaque)

    if "💰 Mídias Pagas" in frentes and st.session_state.get('etapa_midias_pagas'):
        st.subheader("💰 3 — Mídias Pagas")
        st.write(st.session_state.etapa_midias_pagas)

    if "📱 Social & Criativos" in frentes and st.session_state.get('etapa_social'):
        st.subheader("📱 4 — Social")
        st.write(st.session_state.etapa_social)

    if "🔍 SEO & Conteúdo" in frentes and st.session_state.get('etapa_seo'):
        st.subheader("🔍 5 — SEO")
        st.write(st.session_state.etapa_seo)

    st.subheader("💡 6 — Aprendizados")
    st.write(st.session_state.etapa_aprendizados)

    st.subheader("🚀 7 — Próximos Passos")
    st.write(st.session_state.etapa_proximos_passos)

    st.markdown("---")
    st.subheader("📥 Documentos para Download")

    try:
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
            'cpc_atual': st.session_state.get('cpc_atual', 0),
            'cpm_atual': st.session_state.get('cpm_atual', 0),
            'cpe_atual': st.session_state.get('cpe_atual', 0),
            'cpv_atual': st.session_state.get('cpv_atual', 0),
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
        etapas = {
            'etapa_cenario_atual': st.session_state.get('etapa_cenario_atual', ''),
            'etapa_destaques': st.session_state.get('etapa_destaques', ''),
            'etapa_midias_pagas': st.session_state.get('etapa_midias_pagas', ''),
            'etapa_social': st.session_state.get('etapa_social', ''),
            'etapa_seo': st.session_state.get('etapa_seo', ''),
            'etapa_aprendizados': st.session_state.get('etapa_aprendizados', ''),
            'etapa_proximos_passos': st.session_state.get('etapa_proximos_passos', ''),
        }

        docx_interno = gerar_docx_relatorio(
            dados=dados, dados_investimentos=dados_inv_docx, dados_custos=dados_custos_docx,
            dados_seo=dados_seo_docx, **etapas,
        )
        docx_cliente = gerar_docx_cliente(
            dados=dados, dados_investimentos=dados_inv_docx,
            dados_custos=dados_custos_docx, dados_seo=dados_seo_docx, **etapas,
        )

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📄 Relatório Interno (DOCX)",
                data=docx_interno,
                file_name=f"INTERNO_relatorio_executivo_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Relatório completo para uso interno da Macfor — 7 seções com análise profunda."
            )
        with col_d2:
            st.download_button(
                label="📄 Relatório para o Cliente (DOCX)",
                data=docx_cliente,
                file_name=f"CLIENTE_relatorio_resultados_syngenta_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                help="Relatório de resultados para apresentação ao cliente Syngenta."
            )

    except Exception as e:
        st.error(f"Erro ao gerar documentos: {str(e)}")

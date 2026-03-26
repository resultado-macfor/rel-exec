import os
import streamlit as st
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account


@st.cache_resource
def get_bigquery_client():
    try:
        service_account_info = None

        if all(key in os.environ for key in ['project_id', 'private_key', 'client_email']):
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


def check_datasources(client_bq):
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


def fetch_bigquery_data(client_bq):
    if client_bq is None:
        st.error("Conexão com BigQuery não disponível.")
        return None

    query_expandida = """
    SELECT
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

            print("\n" + "="*60)
            print(f"📊 DADOS RECUPERADOS DO BIGQUERY - {datetime.now().strftime('%H:%M:%S')}")
            print("="*60)
            for chave, valor in dados_dict.items():
                display_val = f"{valor:,.2f}" if isinstance(valor, (float, int)) else valor
                print(f"{chave.ljust(30)}: {display_val}")
            print("="*60 + "\n")

            return dados_dict
        return None
    except Exception as e:
        st.error(f"Erro na query: {str(e)}")
        return None


def fetch_products_data(client_bq):
    """Busca produtos destaque por categoria via app_view_media_plan."""
    if client_bq is None:
        return None

    query_produtos = """
    WITH base AS (
        SELECT
            category_or_project,
            product,
            SUM(investment_realized)  AS spend_total,
            SUM(impressions_realized) AS impressions_total,
            SUM(clicks_realized)      AS clicks_total,
            SUM(clicks_realized) / NULLIF(SUM(impressions_realized), 0) AS ctr_media,
            SUM(reach_realized)       AS reach_total
        FROM `macfor-media-flow.ads.app_view_media_plan`
        WHERE
            UPPER(client) LIKE '%SYNGENTA%'
            AND start_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
            AND start_date <  DATE_TRUNC(CURRENT_DATE(), MONTH)
            AND product IS NOT NULL
            AND category_or_project IS NOT NULL
        GROUP BY category_or_project, product
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (PARTITION BY category_or_project ORDER BY spend_total DESC) AS rank_spend,
            ROW_NUMBER() OVER (PARTITION BY category_or_project ORDER BY impressions_total DESC) AS rank_imp,
            ROW_NUMBER() OVER (PARTITION BY category_or_project ORDER BY ctr_media DESC) AS rank_ctr
        FROM base
    )
    SELECT
        category_or_project,
        product,
        ROUND(spend_total, 2)       AS spend_total,
        impressions_total,
        clicks_total,
        ROUND(ctr_media, 4)         AS ctr_media,
        reach_total,
        rank_spend,
        rank_imp,
        rank_ctr
    FROM ranked
    WHERE rank_spend <= 5
    ORDER BY category_or_project, rank_spend
    """
    try:
        df = client_bq.query(query_produtos).to_dataframe()
        if df.empty:
            return None
        result = {}
        for _, row in df.iterrows():
            cat = row['category_or_project']
            if cat not in result:
                result[cat] = []
            result[cat].append(row.to_dict())
        return result
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {str(e)}")
        return None

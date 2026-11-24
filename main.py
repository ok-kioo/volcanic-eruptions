import os
from decimal import Decimal

import boto3
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

AWS_ACCESS_KEY_ID=os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN")
AWS_REGION = "us-east-1"
TABLE_NAME = "VolcanoClusters"

NUMERIC_COLS = [
    "center_lat", "center_lng", "elevation_count", "total_elevation",
    "total_events", "total_vei", "vei_count", "year_count", "year_sum",
]


def load_data() -> pd.DataFrame:
    """Lê todos os itens da tabela VolcanoClusters (com paginação)."""
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
    )
    table = dynamodb.Table(TABLE_NAME)

    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame(columns=["h3_index", *NUMERIC_COLS])

    # DynamoDB devolve Decimal (ou string); normaliza para float
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(
            df[col].map(lambda v: str(v).replace("'", "") if isinstance(v, (Decimal, str)) else v),
            errors="coerce",
        )
    df = df.dropna(subset=["center_lat", "center_lng"])

    # Métricas derivadas para o gráfico
    df["vei_medio"] = (df["total_vei"] / df["vei_count"]).where(df["vei_count"] > 0, 0)
    df["elevacao_media"] = (df["total_elevation"] / df["elevation_count"]).where(df["elevation_count"] > 0)
    df["ano_medio"] = (df["year_sum"] / df["year_count"]).where(df["year_count"] > 0)
    return df


def build_figure() -> "px.scatter_geo":
    df = load_data()

    fig = px.scatter_geo(
        df,
        lat="center_lat",
        lon="center_lng",
        size="total_events",
        color="vei_medio",
        color_continuous_scale="YlOrRd",
        size_max=28,
        projection="natural earth",
        hover_name="h3_index",
        hover_data={
            "center_lat": False,
            "center_lng": False,
            "total_events": True,
            "vei_medio": ":.2f",
            "elevacao_media": ":.0f",
            "ano_medio": ":.0f",
        },
        labels={
            "total_events": "Erupções",
            "vei_medio": "VEI médio",
            "elevacao_media": "Elevação média (m)",
            "ano_medio": "Ano médio",
        },
    )
    fig.update_geos(
        showland=True, landcolor="#e8e8e8",
        showocean=True, oceancolor="#dbe9f4",
        showcountries=True, countrycolor="#b0b0b0",
        center=dict(lat=10, lon=0),
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title="VEI médio"),
    )
    return fig


app = Dash(__name__)

# Remove margens do body e a barra de rolagem
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Erupções de Vulcânicas</title>
        {%favicon%}
        {%css%}
        <style>
            html, body { margin: 0; padding: 0; height: 100vh; overflow: hidden; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
"""


def serve_layout():
    # Função: os dados são relidos do DynamoDB a cada carregamento da página
    return html.Div(
        style={
            "height": "100vh", "display": "flex", "flexDirection": "column",
            "alignItems": "center", "overflow": "hidden",
            "fontFamily": "Arial, sans-serif",
        },
        children=[
            html.H1(
                "Erupções de Vulcânicas",
                style={"margin": "12px 0", "height": "40px", "lineHeight": "40px"},
            ),
            dcc.Graph(
                figure=build_figure(),
                style={"width": "95vw", "height": "calc(100vh - 70px)"},
                config={"responsive": True},
            ),
        ],
    )


app.layout = serve_layout

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
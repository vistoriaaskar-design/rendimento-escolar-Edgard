import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------
# Configuração da página
# ------------------------------------------------------------
st.set_page_config(page_title="Dashboard Educacional - Matemática", layout="wide")

COR_PRIMARIA = "#6C63FF"
COR_ALERTA = "#D32F2F"
COR_AVISO = "#F57C00"
COR_SUCESSO = "#2E7D32"

# ------------------------------------------------------------
# Função para carregar dados de uma turma específica
# ------------------------------------------------------------
@st.cache_data
def load_turma(sheet_name, turma_nome):
    arquivo = "Notas - 1º etapa.xlsx"
    
    # Tenta encontrar a linha de cabeçalho com "Alunos"
    df_raw = pd.read_excel(arquivo, sheet_name=sheet_name, header=None)
    header_row = None
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains("Alunos", case=False, na=False).any():
            header_row = i
            break
    
    if header_row is None:
        st.error(f"Não foi possível encontrar cabeçalho na planilha {sheet_name}")
        return None
    
    df = pd.read_excel(arquivo, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how='all')
    
    # Localizar coluna de alunos
    col_aluno = None
    for col in df.columns:
        if 'aluno' in str(col).lower():
            col_aluno = col
            break
    if col_aluno is None:
        st.error(f"Coluna de alunos não encontrada em {sheet_name}")
        return None
    
    df = df.dropna(subset=[col_aluno])
    df = df[df[col_aluno].astype(str).str.strip() != ""]
    
    # Mapeamento de colunas
    rename_map = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if 'aluno' in col_lower:
            rename_map[col] = "Aluno"
        elif 'caderno' in col_lower:
            rename_map[col] = "Caderno"
        elif 'para casa' in col_lower or 'paracasa' in col_lower:
            rename_map[col] = "ParaCasa"
        elif 'livro' in col_lower:
            rename_map[col] = "Livro"
        elif 'comportamento' in col_lower:
            rename_map[col] = "Comportamento"
        elif 'avaliação' in col_lower or 'avaliacao' in col_lower:
            rename_map[col] = "Avaliacao"
        elif 'resultado final' in col_lower or 'resultadofinal' in col_lower:
            rename_map[col] = "ResultadoFinal"
        elif 'recuperação' in col_lower or 'recuperacao' in col_lower:
            rename_map[col] = "Recuperacao"
    
    df = df.rename(columns=rename_map)
    
    # Garantir colunas essenciais
    for col in ["Aluno", "Caderno", "ParaCasa", "Livro", "Comportamento", "Avaliacao", "ResultadoFinal"]:
        if col not in df.columns:
            df[col] = 0
    
    # Converter para numérico
    for col in ["Caderno", "ParaCasa", "Livro", "Comportamento", "Avaliacao", "ResultadoFinal", "Recuperacao"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # Adicionar coluna de turma
    df["Turma"] = turma_nome
    return df

# ------------------------------------------------------------
# Carregar ambas as turmas
# ------------------------------------------------------------
try:
    df_a = load_turma("Planilha1", "4º A")
    df_b = load_turma("Planilha2", "4º B")
    df = pd.concat([df_a, df_b], ignore_index=True)
    st.success(f"Dados carregados! Total de alunos: {len(df)}")
except Exception as e:
    st.error(f"Erro ao carregar: {e}")
    st.stop()

# ------------------------------------------------------------
# Filtros laterais
# ------------------------------------------------------------
st.sidebar.header("🔍 Filtros")

# Filtro de turma
turmas = ["Todas", "4º A", "4º B"]
turma_selecionada = st.sidebar.selectbox("Turma", turmas)

# Aplicar filtro
if turma_selecionada == "4º A":
    df_filtro = df[df["Turma"] == "4º A"]
elif turma_selecionada == "4º B":
    df_filtro = df[df["Turma"] == "4º B"]
else:
    df_filtro = df.copy()

# Filtro de status
status_opcao = st.sidebar.selectbox(
    "Status do aluno",
    ["Todos", "Acima da média (>=18)", "Em recuperação (<18)"]
)

if status_opcao == "Acima da média (>=18)":
    df_filtrado = df_filtro[df_filtro["ResultadoFinal"] >= 18]
elif status_opcao == "Em recuperação (<18)":
    df_filtrado = df_filtro[df_filtro["ResultadoFinal"] < 18]
else:
    df_filtrado = df_filtro.copy()

# ------------------------------------------------------------
# KPIs (com arredondamento de 1 casa)
# ------------------------------------------------------------
media_geral = round(df_filtrado["ResultadoFinal"].mean(), 1)
total_alunos = len(df_filtrado)
aprovados = (df_filtrado["ResultadoFinal"] >= 18).sum()
taxa_aprovacao = round(aprovados / total_alunos * 100, 1) if total_alunos > 0 else 0
recuperacao = total_alunos - aprovados
nota_max = df_filtrado["ResultadoFinal"].max()
nota_min = df_filtrado["ResultadoFinal"].min()

# Layout
st.title(f"📊 Matemática - 1ª Etapa ({turma_selecionada if turma_selecionada != 'Todas' else '4º A e B'})")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("🌟 Média da turma", f"{media_geral:.1f} pts")
col2.metric("✅ Aprovados (≥18)", f"{aprovados} ({taxa_aprovacao:.1f}%)")
col3.metric("⚠️ Recuperação", f"{recuperacao}")
col4.metric("📈 Max / Min", f"{nota_max:.1f} / {nota_min:.1f}")

st.markdown("---")

# Gráfico de barras individual
df_plot = df_filtrado.sort_values("ResultadoFinal", ascending=False)
fig_bar = px.bar(
    df_plot, x="Aluno", y="ResultadoFinal",
    title="Resultado Final por aluno",
    text="ResultadoFinal",
    color="ResultadoFinal",
    color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"]
)
fig_bar.add_hline(y=media_geral, line_dash="dash", line_color="blue", annotation_text=f"Média {media_geral:.1f}")
fig_bar.add_hline(y=18, line_dash="dot", line_color="green", annotation_text="Meta 18")
fig_bar.update_layout(height=500, xaxis_tickangle=-45)
fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
st.plotly_chart(fig_bar, use_container_width=True)

# Colunas: Pizza + Top/Bottom
col_left, col_right = st.columns(2)
with col_left:
    acima_media = (df_filtrado["ResultadoFinal"] >= media_geral).sum()
    abaixo_media = total_alunos - acima_media
    fig_pie = px.pie(
        names=["Acima da média", "Abaixo da média"],
        values=[acima_media, abaixo_media],
        color_discrete_sequence=[COR_PRIMARIA, COR_AVISO],
        hole=0.4
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("🏆 Top 5")
    st.dataframe(df_filtrado.nlargest(5, "ResultadoFinal")[["Aluno", "ResultadoFinal"]].style.format({"ResultadoFinal": "{:.1f}"}))
    st.subheader("⚠️ Bottom 5")
    st.dataframe(df_filtrado.nsmallest(5, "ResultadoFinal")[["Aluno", "ResultadoFinal"]].style.format({"ResultadoFinal": "{:.1f}"}))

# ------------------------------------------------------------
# Diagnóstico por Atividade (gráfico horizontal de percentuais)
# ------------------------------------------------------------
st.markdown("---")
st.subheader("📉 Diagnóstico por Atividade")
st.caption("Média percentual de aproveitamento por critério (menor = maior dificuldade coletiva)")

# Calcular médias e percentuais
atividades = {
    "Para Casa": (df_filtrado["ParaCasa"].mean(), 5),
    "Livro": (df_filtrado["Livro"].mean(), 5),
    "Avaliação": (df_filtrado["Avaliacao"].mean(), 10),
    "Caderno": (df_filtrado["Caderno"].mean(), 5),
    "Comportamento": (df_filtrado["Comportamento"].mean(), 5)
}

# Ordenar do pior para o melhor percentual
percentuais = []
for nome, (media, maximo) in atividades.items():
    pct = (media / maximo) * 100
    percentuais.append((nome, media, maximo, pct))

percentuais.sort(key=lambda x: x[3])  # ordena por percentual

# Criar DataFrame para o gráfico horizontal
df_diagnostico = pd.DataFrame(percentuais, columns=["Atividade", "Média", "Máximo", "Percentual"])

fig_horiz = px.bar(
    df_diagnostico,
    x="Percentual",
    y="Atividade",
    orientation='h',
    text="Percentual",
    color="Percentual",
    color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"],
    labels={"Percentual": "Aproveitamento (%)", "Atividade": ""},
    title="Aproveitamento por tipo de atividade"
)
fig_horiz.update_traces(
    texttemplate='%{text:.1f}%',
    textposition='outside',
    marker=dict(line=dict(width=0))
)
fig_horiz.update_layout(
    xaxis=dict(range=[0, 100], title="Percentual de aproveitamento"),
    yaxis=dict(categoryorder='array', categoryarray=df_diagnostico["Atividade"].tolist()),
    height=400,
    showlegend=False
)
st.plotly_chart(fig_horiz, use_container_width=True)

# Adicionar card com o pior desempenho
pior_atividade = df_diagnostico.iloc[0]["Atividade"]
pior_percentual = df_diagnostico.iloc[0]["Percentual"]
pior_media = df_diagnostico.iloc[0]["Média"]
pior_max = df_diagnostico.iloc[0]["Máximo"]
st.info(f"⚠️ **Crítico:** {pior_atividade} – {pior_media:.1f}/{pior_max} ({pior_percentual:.0f}%)")

# ------------------------------------------------------------
# Radar individual (mantido, sem alterações)
# ------------------------------------------------------------
st.markdown("---")
st.subheader("👨‍🎓 Detalhamento individual – Radar de dificuldades")
aluno_selecionado = st.selectbox("Escolha um aluno:", sorted(df_filtro["Aluno"].unique()))
if aluno_selecionado:
    aluno = df_filtro[df_filtro["Aluno"] == aluno_selecionado].iloc[0]
    notas_radar = {
        "Caderno": aluno["Caderno"] * 2,
        "Para Casa": aluno["ParaCasa"] * 2,
        "Livro": aluno["Livro"] * 2,
        "Comportamento": aluno["Comportamento"] * 2,
        "Avaliação": aluno["Avaliacao"]
    }
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=list(notas_radar.values()),
        theta=list(notas_radar.keys()),
        fill='toself',
        name=aluno_selecionado,
        line_color=COR_PRIMARIA
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=[10,10,10,10,10],
        theta=list(notas_radar.keys()),
        fill=None,
        name="Máximo possível",
        line=dict(color="gray", dash="dash")
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(range=[0, 10], tickmode='linear', dtick=2)),
        showlegend=True,
        title=f"Perfil de desempenho - {aluno_selecionado}"
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Identificar menor nota
    menor = min(notas_radar, key=notas_radar.get)
    nota_original = aluno[menor.replace(' ', '') if menor != 'Avaliação' else 'Avaliacao']
    st.warning(f"⚠️ **Principal dificuldade:** {menor} (nota {nota_original:.1f} de {5 if menor != 'Avaliação' else 10})")

st.caption("Dashboard adaptado para 4º A e 4º B | Dados da 1ª Etapa | Meta de aprovação: 18 pontos")
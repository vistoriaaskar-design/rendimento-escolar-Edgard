import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ------------------------------------------------------------
# Configuração da página
# ------------------------------------------------------------
st.set_page_config(page_title="Dashboard Educacional - MultiMatéria", layout="wide")

COR_PRIMARIA = "#6C63FF"
COR_ALERTA = "#D32F2F"
COR_AVISO = "#F57C00"
COR_SUCESSO = "#2E7D32"

# ------------------------------------------------------------
# Função para extrair metadados de uma planilha (matéria, turma, professora)
# ------------------------------------------------------------
def extrair_metadados(df_raw, sheet_name):
    """
    Examina as primeiras linhas da planilha (sem cabeçalho) para encontrar:
    - Professora
    - Matéria (ex: MATEMÁTICA, CIÊNCIAS)
    - Turma (ex: 4º A, 4º B)
    """
    texto_inicial = " ".join(df_raw.iloc[:10].astype(str).sum())
    professora = ""
    materia = ""
    turma = ""
    
    # Procura por "Professora:"
    match_prof = re.search(r'Professora:\s*([^\n]+)', texto_inicial, re.IGNORECASE)
    if match_prof:
        professora = match_prof.group(1).strip()
    else:
        professora = "Não informada"
    
    # Procura por MATEMÁTICA ou CIÊNCIAS (case insensitive)
    if re.search(r'MATEMÁTICA', texto_inicial, re.IGNORECASE):
        materia = "MATEMÁTICA"
    elif re.search(r'CIÊNCIAS', texto_inicial, re.IGNORECASE):
        materia = "CIÊNCIAS"
    else:
        materia = "GERAL"
    
    # Procura por padrão de turma: "4º A", "4º B", etc.
    match_turma = re.search(r'(\d+º\s*[A-Z])', texto_inicial)
    if match_turma:
        turma = match_turma.group(1)
    else:
        turma = sheet_name  # fallback
    
    return professora, materia, turma

# ------------------------------------------------------------
# Função para carregar dados de UMA planilha (com estrutura flexível)
# ------------------------------------------------------------
def carregar_planilha(arquivo, sheet_name):
    # Lê sem cabeçalho para inspecionar
    df_raw = pd.read_excel(arquivo, sheet_name=sheet_name, header=None)
    
    # Extrai metadados
    professora, materia, turma = extrair_metadados(df_raw, sheet_name)
    
    # Encontra a linha que contém "Alunos" (cabeçalho)
    header_row = None
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains("Alunos", case=False, na=False).any():
            header_row = i
            break
    
    if header_row is None:
        st.warning(f"Planilha {sheet_name}: não encontrou linha com 'Alunos'. Ignorada.")
        return None
    
    # Lê a partir da linha do cabeçalho
    df = pd.read_excel(arquivo, sheet_name=sheet_name, header=header_row)
    
    # Remove linhas totalmente vazias
    df = df.dropna(how='all')
    
    # Identifica a coluna de alunos
    col_aluno = None
    for col in df.columns:
        if 'aluno' in str(col).lower():
            col_aluno = col
            break
    if col_aluno is None:
        st.warning(f"Planilha {sheet_name}: coluna de alunos não encontrada. Ignorada.")
        return None
    
    # Remove linhas sem nome de aluno
    df = df.dropna(subset=[col_aluno])
    df = df[df[col_aluno].astype(str).str.strip() != ""]
    
    # Renomeia a coluna de aluno para "Aluno" e armazena o nome original
    df = df.rename(columns={col_aluno: "Aluno"})
    
    # Identifica todas as colunas que são atividades (notas)
    # Excluímos colunas que não são notas: Nº, Aluno, Resultado Final, Recuperação, Turma, Matéria, etc.
    colunas_excluir = ["Nº", "Aluno", "Resultado Final", "Recuperação", "Turma", "Matéria"]
    colunas_atividades = []
    for col in df.columns:
        col_upper = str(col).upper()
        # Se a coluna não está nas excluídas e não é numérica vazia... aceitamos como atividade
        if col not in colunas_excluir and not col.startswith("Unnamed"):
            # Testa se a coluna tem valores numéricos (exceto cabeçalho)
            if df[col].dtype in ['float64', 'int64'] or pd.to_numeric(df[col], errors='coerce').notna().any():
                colunas_atividades.append(col)
    
    # Converte colunas de atividades para numérico
    for col in colunas_atividades:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Identifica coluna de Resultado Final (pode ter nomes variados)
    col_resultado = None
    for col in df.columns:
        if "resultado final" in str(col).lower() or "resultado" in str(col).lower():
            col_resultado = col
            break
    if col_resultado is None:
        # Se não existir, criamos somando todas as atividades (pode não ser ideal, mas evita erro)
        df["ResultadoFinal"] = df[colunas_atividades].sum(axis=1)
        col_resultado = "ResultadoFinal"
    else:
        df = df.rename(columns={col_resultado: "ResultadoFinal"})
    
    # Coluna de recuperação (opcional)
    col_rec = None
    for col in df.columns:
        if "recuperação" in str(col).lower():
            col_rec = col
            break
    if col_rec:
        df = df.rename(columns={col_rec: "Recuperacao"})
        df["Recuperacao"] = pd.to_numeric(df["Recuperacao"], errors='coerce').fillna(0)
    else:
        df["Recuperacao"] = 0
    
    # Adiciona metadados
    df["Matéria"] = materia
    df["Turma"] = turma
    df["Professora"] = professora
    
    # Guarda a lista de atividades originais
    df.attrs["atividades"] = colunas_atividades
    
    return df

# ------------------------------------------------------------
# Carregar todas as planilhas do arquivo Excel
# ------------------------------------------------------------
@st.cache_data
def carregar_todos_dados(arquivo="Notas - 1º etapa.xlsx"):
    xl = pd.ExcelFile(arquivo)
    todas_planilhas = []
    for sheet in xl.sheet_names:
        st.info(f"Carregando planilha: {sheet}")
        df_sheet = carregar_planilha(arquivo, sheet)
        if df_sheet is not None:
            todas_planilhas.append(df_sheet)
    if not todas_planilhas:
        st.error("Nenhuma planilha válida encontrada.")
        return None
    df_full = pd.concat(todas_planilhas, ignore_index=True)
    return df_full

# ------------------------------------------------------------
# Carregar dados
# ------------------------------------------------------------
try:
    df = carregar_todos_dados()
    if df is None:
        st.stop()
    st.success(f"Dados carregados! Total de registros: {len(df)}")
    # Exibe as matérias e turmas disponíveis
    materias_disponiveis = sorted(df["Matéria"].unique())
    turmas_disponiveis = sorted(df["Turma"].unique())
    st.sidebar.markdown(f"**📚 Matérias:** {', '.join(materias_disponiveis)}")
    st.sidebar.markdown(f"**🏫 Turmas:** {', '.join(turmas_disponiveis)}")
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ------------------------------------------------------------
# Filtros laterais
# ------------------------------------------------------------
st.sidebar.header("🔍 Filtros Dinâmicos")

# Filtro de Matéria (dinâmico)
materia_selecionada = st.sidebar.selectbox("Matéria", ["Todas"] + materias_disponiveis)

if materia_selecionada != "Todas":
    df_filtro_materia = df[df["Matéria"] == materia_selecionada]
else:
    df_filtro_materia = df

# Filtro de Turma (dinâmico, baseado na matéria selecionada)
turmas_filtradas = sorted(df_filtro_materia["Turma"].unique())
turma_selecionada = st.sidebar.selectbox("Turma", ["Todas"] + turmas_filtradas)

if turma_selecionada != "Todas":
    df_filtro_turma = df_filtro_materia[df_filtro_materia["Turma"] == turma_selecionada]
else:
    df_filtro_turma = df_filtro_materia

# Filtro de Status do aluno
status_opcao = st.sidebar.selectbox(
    "Status do aluno",
    ["Todos", "Acima da média (>=18)", "Em recuperação (<18)"]
)

if status_opcao == "Acima da média (>=18)":
    df_filtrado = df_filtro_turma[df_filtro_turma["ResultadoFinal"] >= 18]
elif status_opcao == "Em recuperação (<18)":
    df_filtrado = df_filtro_turma[df_filtro_turma["ResultadoFinal"] < 18]
else:
    df_filtrado = df_filtro_turma

# Botão de exportar CSV
csv = df_filtrado.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 Baixar dados filtrados (CSV)",
    data=csv,
    file_name=f'dados_{materia_selecionada}_{turma_selecionada}_{status_opcao}.csv',
    mime='text/csv',
)

# ------------------------------------------------------------
# Cabeçalho com nome da professora
# ------------------------------------------------------------
# Pega o nome da professora (pode variar, mas pegamos o primeiro valor)
nome_professora = df["Professora"].iloc[0] if not df.empty else "Poliana Camila"
st.title(f"📊 Dashboard Educacional")
st.markdown(f"**Professora:** {nome_professora}")
st.caption(f"Matéria: {materia_selecionada}  |  Turma: {turma_selecionada}  |  Total de alunos: {len(df_filtrado)}")
st.markdown("---")

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
media_geral = round(df_filtrado["ResultadoFinal"].mean(), 1)
total_alunos = len(df_filtrado)
aprovados = (df_filtrado["ResultadoFinal"] >= 18).sum()
taxa_aprovacao = round(aprovados / total_alunos * 100, 1) if total_alunos > 0 else 0
recuperacao = total_alunos - aprovados
nota_max = df_filtrado["ResultadoFinal"].max()
nota_min = df_filtrado["ResultadoFinal"].min()

col1, col2, col3, col4 = st.columns(4)
col1.metric("🌟 Média da turma", f"{media_geral:.1f} pts")
col2.metric("✅ Aprovados (≥18)", f"{aprovados} ({taxa_aprovacao:.1f}%)")
col3.metric("⚠️ Recuperação", f"{recuperacao}")
col4.metric("📈 Max / Min", f"{nota_max:.1f} / {nota_min:.1f}")

st.markdown("---")

# ------------------------------------------------------------
# Abas
# ------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Comparativo Turmas", "🔥 Mapa de Calor", "👨‍🎓 Detalhamento Individual"])

# ---------- ABA 1: VISÃO GERAL ----------
with tab1:
    # Gráfico de barras por aluno
    df_plot = df_filtrado.sort_values("ResultadoFinal", ascending=False)
    fig_bar = px.bar(
        df_plot, x="Aluno", y="ResultadoFinal",
        title=f"Resultado Final por aluno - {materia_selecionada} {turma_selecionada}",
        text="ResultadoFinal",
        color="ResultadoFinal",
        color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"]
    )
    fig_bar.add_hline(y=media_geral, line_dash="dash", line_color="blue", annotation_text=f"Média {media_geral:.1f}")
    fig_bar.add_hline(y=18, line_dash="dot", line_color="green", annotation_text="Meta 18")
    fig_bar.update_layout(height=500, xaxis_tickangle=-45)
    fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
    st.plotly_chart(fig_bar, use_container_width=True)
    
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
    
    # Diagnóstico por atividade (dinâmico)
    st.subheader("📉 Diagnóstico por Atividade")
    st.caption("Média percentual de aproveitamento por critério (menor = maior dificuldade coletiva)")
    
    # Obtém as atividades disponíveis para o conjunto filtrado (podem variar conforme matéria)
    # Extraímos as colunas que são atividades (excluindo as de metadados)
    colunas_meta = ["Aluno", "ResultadoFinal", "Recuperacao", "Matéria", "Turma", "Professora"]
    atividades_filtro = [c for c in df_filtrado.columns if c not in colunas_meta and df_filtrado[c].dtype in ['float64', 'int64']]
    
    if atividades_filtro:
        # Calcula percentuais
        dados_atividades = []
        for ativ in atividades_filtro:
            media_nota = df_filtrado[ativ].mean()
            # Tenta adivinhar máximo: se a coluna contém 'avalia' assume 10, senão 5
            maximo = 10 if 'avalia' in ativ.lower() else 5
            pct = (media_nota / maximo) * 100
            dados_atividades.append((ativ, media_nota, maximo, pct))
        dados_atividades.sort(key=lambda x: x[3])
        df_diag = pd.DataFrame(dados_atividades, columns=["Atividade", "Média", "Máximo", "Percentual"])
        
        fig_horiz = px.bar(
            df_diag, x="Percentual", y="Atividade", orientation='h',
            text="Percentual", color="Percentual",
            color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"],
            labels={"Percentual": "Aproveitamento (%)", "Atividade": ""}
        )
        fig_horiz.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_horiz.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_horiz, use_container_width=True)
        
        pior = df_diag.iloc[0]
        st.info(f"⚠️ **Crítico:** {pior['Atividade']} – {pior['Média']:.1f}/{pior['Máximo']} ({pior['Percentual']:.0f}%)")
    else:
        st.warning("Nenhuma atividade identificada para este filtro.")

# ---------- ABA 2: COMPARATIVO ENTRE TURMAS (para a mesma matéria) ----------
with tab2:
    st.subheader(f"📊 Comparativo de turmas - {materia_selecionada}")
    if materia_selecionada != "Todas":
        df_comp = df[df["Matéria"] == materia_selecionada]
        turmas_comp = sorted(df_comp["Turma"].unique())
        if len(turmas_comp) >= 2:
            # Calcula médias de resultado final por turma
            medias_turmas = df_comp.groupby("Turma")["ResultadoFinal"].mean().reset_index()
            fig_comp_res = px.bar(medias_turmas, x="Turma", y="ResultadoFinal", text="ResultadoFinal",
                                  title="Média do Resultado Final por Turma",
                                  labels={"ResultadoFinal": "Média (pts)"},
                                  color="Turma", color_discrete_sequence=[COR_PRIMARIA, COR_SUCESSO])
            fig_comp_res.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            st.plotly_chart(fig_comp_res, use_container_width=True)
            
            # Diferença
            medias_dict = medias_turmas.set_index("Turma")["ResultadoFinal"].to_dict()
            if "4º B" in medias_dict and "4º A" in medias_dict:
                diff = medias_dict["4º B"] - medias_dict["4º A"]
                st.metric("🏆 Diferença (4ºB - 4ºA)", f"{diff:+.1f} pts", delta=f"{diff/30*100:+.1f}%")
        else:
            st.info("Apenas uma turma disponível para esta matéria. Selecione 'Todas' no filtro de matéria para comparar.")
    else:
        st.info("Selecione uma matéria específica (não 'Todas') para comparar turmas.")

# ---------- ABA 3: MAPA DE CALOR ----------
with tab3:
    st.subheader("🔥 Mapa de Calor: Aluno vs Atividade")
    st.caption("Notas normalizadas de 0 a 10 (quanto mais vermelho, maior dificuldade).")
    if atividades_filtro and len(df_filtrado) > 0:
        # Prepara matriz
        alunos_nomes = df_filtrado["Aluno"].tolist()
        dados_calor = []
        for aluno in alunos_nomes:
            linha = []
            for ativ in atividades_filtro:
                nota = df_filtrado[df_filtrado["Aluno"] == aluno][ativ].values[0]
                maximo = 10 if 'avalia' in ativ.lower() else 5
                nota_norm = (nota / maximo) * 10
                linha.append(round(nota_norm, 1))
            dados_calor.append(linha)
        
        fig_heat = go.Figure(data=go.Heatmap(
            z=dados_calor,
            x=atividades_filtro,
            y=alunos_nomes,
            colorscale='RdYlGn_r',
            text=[[f"{val:.1f}" for val in linha] for linha in dados_calor],
            texttemplate="%{text}",
            textfont={"size": 10},
            colorbar=dict(title="Nota (0-10)")
        ))
        fig_heat.update_layout(height=800, xaxis=dict(title="Atividade"), yaxis=dict(title="Aluno", tickfont=dict(size=9)))
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("Sem atividades ou alunos para gerar o mapa de calor.")

# ---------- ABA 4: RADAR INDIVIDUAL ----------
with tab4:
    st.subheader("👨‍🎓 Radar de dificuldades por aluno")
    if len(df_filtrado) > 0:
        aluno_selecionado = st.selectbox("Escolha um aluno:", sorted(df_filtrado["Aluno"].unique()), key="select_aluno")
        if aluno_selecionado:
            aluno_row = df_filtrado[df_filtrado["Aluno"] == aluno_selecionado].iloc[0]
            # Notas normalizadas para radar (0-10)
            radar_data = {}
            for ativ in atividades_filtro:
                nota = aluno_row[ativ]
                maximo = 10 if 'avalia' in ativ.lower() else 5
                radar_data[ativ] = (nota / maximo) * 10
            # Categorias e valores
            categorias = list(radar_data.keys())
            valores = list(radar_data.values())
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=valores, theta=categorias, fill='toself', name=aluno_selecionado, line_color=COR_PRIMARIA))
            fig_radar.add_trace(go.Scatterpolar(r=[10]*len(categorias), theta=categorias, fill=None, name="Máximo possível", line=dict(color="gray", dash="dash")))
            fig_radar.update_layout(polar=dict(radialaxis=dict(range=[0,10], dtick=2)), showlegend=True)
            st.plotly_chart(fig_radar, use_container_width=True)
            
            # Identifica pior desempenho
            pior_ativ = min(radar_data, key=radar_data.get)
            nota_original = aluno_row[pior_ativ]
            max_original = 10 if 'avalia' in pior_ativ.lower() else 5
            st.warning(f"⚠️ **Principal dificuldade:** {pior_ativ} (nota {nota_original:.1f} de {max_original})")
    else:
        st.warning("Nenhum aluno para exibir.")

st.markdown("---")
st.caption("Dashboard universal – lê todas as planilhas e se adapta a diferentes matérias, turmas e atividades.")

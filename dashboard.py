import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ------------------------------------------------------------
# Configuração da página
# ------------------------------------------------------------
st.set_page_config(page_title="Dashboard Educacional", layout="wide")

COR_PRIMARIA = "#6C63FF"
COR_ALERTA = "#D32F2F"
COR_AVISO = "#F57C00"
COR_SUCESSO = "#2E7D32"

# ------------------------------------------------------------
# Função para extrair metadados de forma limpa
# ------------------------------------------------------------
def extrair_metadados(df_raw, sheet_name):
    """
    Retorna (professora, materia, turma) extraídos das primeiras linhas.
    """
    texto_inicial = " ".join(df_raw.iloc[:15].astype(str).sum())
    
    # Professora
    prof_match = re.search(r'Professora:\s*([^\n]+)', texto_inicial, re.IGNORECASE)
    professora = prof_match.group(1).strip() if prof_match else "Não informada"
    
    # Matéria: procura por MATEMÁTICA ou CIÊNCIAS (palavra isolada)
    materia = "GERAL"
    if re.search(r'\bMATEMÁTICA\b', texto_inicial, re.IGNORECASE):
        materia = "MATEMÁTICA"
    elif re.search(r'\bCIÊNCIAS\b', texto_inicial, re.IGNORECASE):
        materia = "CIÊNCIAS"
    
    # Turma: procura padrão como "4º A", "4º B", "4° A", etc.
    # Evita capturar "1º ETAPA" verificando se o match termina com letra e não tem "ETAPA" depois
    turma_match = re.search(r'(\d+º?\s*[A-Z])(?:\s|$)', texto_inicial)
    if turma_match:
        possible_turma = turma_match.group(1)
        # Se o que vem depois não for "ETAPA" (case insensitive)
        pos_end = turma_match.end()
        if pos_end < len(texto_inicial) and re.search(r'ETAPA', texto_inicial[pos_end:pos_end+10], re.IGNORECASE):
            # Tentar próximo padrão
            turma_match = re.search(r'(\d+º?\s*[A-Z])(?:\s|$)', texto_inicial[pos_end+5:])
            if turma_match:
                possible_turma = turma_match.group(1)
            else:
                possible_turma = "Turma não identificada"
        turma = possible_turma
    else:
        turma = sheet_name  # fallback
    
    # Limpeza: remover espaços extras
    turma = turma.strip()
    return professora, materia, turma

# ------------------------------------------------------------
# Carregar dados de uma planilha (silencioso, sem st.info)
# ------------------------------------------------------------
def carregar_planilha(arquivo, sheet_name):
    try:
        df_raw = pd.read_excel(arquivo, sheet_name=sheet_name, header=None)
        professora, materia, turma = extrair_metadados(df_raw, sheet_name)
        
        # Encontra linha com "Alunos"
        header_row = None
        for i, row in df_raw.iterrows():
            if row.astype(str).str.contains("Alunos", case=False, na=False).any():
                header_row = i
                break
        if header_row is None:
            return None
        
        df = pd.read_excel(arquivo, sheet_name=sheet_name, header=header_row)
        df = df.dropna(how='all')
        
        # Identifica coluna de alunos
        col_aluno = None
        for col in df.columns:
            if 'aluno' in str(col).lower():
                col_aluno = col
                break
        if col_aluno is None:
            return None
        df = df.dropna(subset=[col_aluno])
        df = df[df[col_aluno].astype(str).str.strip() != ""]
        df = df.rename(columns={col_aluno: "Aluno"})
        
        # Identifica colunas de atividades (numéricas)
        colunas_excluir = ["Nº", "Aluno", "Resultado Final", "Recuperação", "Turma", "Matéria"]
        atividades = []
        for col in df.columns:
            if col not in colunas_excluir and not col.startswith("Unnamed"):
                if pd.to_numeric(df[col], errors='coerce').notna().any():
                    atividades.append(col)
        for col in atividades:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Resultado Final
        col_res = None
        for col in df.columns:
            if "resultado final" in str(col).lower():
                col_res = col
                break
        if col_res is None:
            df["ResultadoFinal"] = df[atividades].sum(axis=1)
        else:
            df = df.rename(columns={col_res: "ResultadoFinal"})
            df["ResultadoFinal"] = pd.to_numeric(df["ResultadoFinal"], errors='coerce').fillna(0)
        
        # Recuperação (opcional)
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
        
        df["Matéria"] = materia
        df["Turma"] = turma
        df["Professora"] = professora
        df.attrs["atividades"] = atividades
        return df
    except Exception:
        return None

# ------------------------------------------------------------
# Carregar todas as planilhas (sem mensagens)
# ------------------------------------------------------------
@st.cache_data
def carregar_todos_dados(arquivo="Notas - 1º etapa.xlsx"):
    xl = pd.ExcelFile(arquivo)
    todas = []
    for sheet in xl.sheet_names:
        df_sheet = carregar_planilha(arquivo, sheet)
        if df_sheet is not None:
            todas.append(df_sheet)
    if not todas:
        return None
    df_full = pd.concat(todas, ignore_index=True)
    return df_full

# ------------------------------------------------------------
# Carregar dados
# ------------------------------------------------------------
df = carregar_todos_dados()
if df is None:
    st.error("Nenhum dado válido encontrado. Verifique o arquivo Excel.")
    st.stop()

# ------------------------------------------------------------
# Sidebar - Filtros (primeiro Turma, depois Matéria)
# ------------------------------------------------------------
st.sidebar.header("🔍 Filtros")

# Lista de turmas disponíveis (exclui "Turma não identificada" e vazios)
turmas_disponiveis = sorted([t for t in df["Turma"].unique() if t and "não identificada" not in t])
turma_selecionada = st.sidebar.selectbox("🏫 Turma", ["Todas"] + turmas_disponiveis)

# Filtra por turma
if turma_selecionada != "Todas":
    df_turma = df[df["Turma"] == turma_selecionada]
else:
    df_turma = df

# Lista de matérias disponíveis nessa turma (ou todas)
materias_disponiveis = sorted(df_turma["Matéria"].unique())
materia_selecionada = st.sidebar.selectbox("📚 Matéria", ["Todas"] + materias_disponiveis)

if materia_selecionada != "Todas":
    df_materia = df_turma[df_turma["Matéria"] == materia_selecionada]
else:
    df_materia = df_turma

# Status
status_opcao = st.sidebar.selectbox("📊 Status do aluno", ["Todos", "Acima da média (>=18)", "Em recuperação (<18)"])
if status_opcao == "Acima da média (>=18)":
    df_filtrado = df_materia[df_materia["ResultadoFinal"] >= 18]
elif status_opcao == "Em recuperação (<18)":
    df_filtrado = df_materia[df_materia["ResultadoFinal"] < 18]
else:
    df_filtrado = df_materia

# Exportar CSV
csv = df_filtrado.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Baixar CSV", csv, f"dados_{turma_selecionada}_{materia_selecionada}.csv", "text/csv")

# ------------------------------------------------------------
# Cabeçalho limpo
# ------------------------------------------------------------
nome_professora = df["Professora"].iloc[0] if not df.empty else "Poliana Camila"
st.title(f"📊 Dashboard Educacional")
st.markdown(f"**Professora:** {nome_professora}")
st.caption(f"**Turma:** {turma_selecionada if turma_selecionada != 'Todas' else 'Todas'}  |  **Matéria:** {materia_selecionada if materia_selecionada != 'Todas' else 'Todas'}  |  **Alunos:** {len(df_filtrado)}")
st.markdown("---")

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
if len(df_filtrado) > 0:
    media_geral = round(df_filtrado["ResultadoFinal"].mean(), 1)
    aprovados = (df_filtrado["ResultadoFinal"] >= 18).sum()
    taxa_aprovacao = round(aprovados / len(df_filtrado) * 100, 1)
    recuperacao = len(df_filtrado) - aprovados
    nota_max = df_filtrado["ResultadoFinal"].max()
    nota_min = df_filtrado["ResultadoFinal"].min()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌟 Média", f"{media_geral:.1f} pts")
    col2.metric("✅ Aprovados (≥18)", f"{aprovados} ({taxa_aprovacao:.1f}%)")
    col3.metric("⚠️ Recuperação", f"{recuperacao}")
    col4.metric("📈 Max / Min", f"{nota_max:.1f} / {nota_min:.1f}")
    st.markdown("---")
    
    # Abas
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Comparativo Turmas", "🔥 Mapa de Calor", "👨‍🎓 Detalhamento"])
    
    # --- Aba 1: Visão Geral ---
    with tab1:
        fig_bar = px.bar(df_filtrado.sort_values("ResultadoFinal", ascending=False),
                         x="Aluno", y="ResultadoFinal", text="ResultadoFinal",
                         color="ResultadoFinal", color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"])
        fig_bar.add_hline(y=media_geral, line_dash="dash", line_color="blue", annotation_text=f"Média {media_geral}")
        fig_bar.add_hline(y=18, line_dash="dot", line_color="green", annotation_text="Meta 18")
        fig_bar.update_layout(height=500, xaxis_tickangle=-45)
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)
        
        colL, colR = st.columns(2)
        with colL:
            acima = (df_filtrado["ResultadoFinal"] >= media_geral).sum()
            abaixo = len(df_filtrado) - acima
            fig_pie = px.pie(names=["Acima da média", "Abaixo da média"], values=[acima, abaixo],
                             color_discrete_sequence=[COR_PRIMARIA, COR_AVISO], hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with colR:
            st.subheader("🏆 Top 5")
            st.dataframe(df_filtrado.nlargest(5, "ResultadoFinal")[["Aluno", "ResultadoFinal"]].style.format({"ResultadoFinal": "{:.1f}"}))
            st.subheader("⚠️ Bottom 5")
            st.dataframe(df_filtrado.nsmallest(5, "ResultadoFinal")[["Aluno", "ResultadoFinal"]].style.format({"ResultadoFinal": "{:.1f}"}))
        
        # Diagnóstico por atividade
        st.subheader("📉 Diagnóstico por Atividade")
        atividades = [c for c in df_filtrado.columns if c not in ["Aluno", "ResultadoFinal", "Recuperacao", "Matéria", "Turma", "Professora"] and df_filtrado[c].dtype in ['float64', 'int64']]
        if atividades:
            dados_ativ = []
            for at in atividades:
                media = df_filtrado[at].mean()
                maximo = 10 if 'avalia' in at.lower() else 5
                pct = (media / maximo) * 100
                dados_ativ.append((at, media, maximo, pct))
            dados_ativ.sort(key=lambda x: x[3])
            df_ativ = pd.DataFrame(dados_ativ, columns=["Atividade", "Média", "Máximo", "Percentual"])
            fig_h = px.bar(df_ativ, x="Percentual", y="Atividade", orientation='h', text="Percentual",
                           color="Percentual", color_continuous_scale=["#D32F2F", "#F57C00", "#2E7D32"])
            fig_h.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_h.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_h, use_container_width=True)
            pior = df_ativ.iloc[0]
            st.info(f"⚠️ **Crítico:** {pior['Atividade']} – {pior['Média']:.1f}/{pior['Máximo']} ({pior['Percentual']:.0f}%)")
    
    # --- Aba 2: Comparativo Turmas (apenas para a mesma matéria) ---
    with tab2:
        if materia_selecionada != "Todas" and turma_selecionada == "Todas":
            df_comp = df[df["Matéria"] == materia_selecionada]
            medias_turmas = df_comp.groupby("Turma")["ResultadoFinal"].mean().reset_index()
            fig_comp = px.bar(medias_turmas, x="Turma", y="ResultadoFinal", text="ResultadoFinal",
                              color="Turma", title=f"Comparativo - {materia_selecionada}")
            fig_comp.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("Selecione uma matéria específica e 'Todas' as turmas para ver o comparativo.")
    
    # --- Aba 3: Mapa de Calor ---
    with tab3:
        if atividades and len(df_filtrado) > 0:
            matriz = []
            for aluno in df_filtrado["Aluno"]:
                linha = []
                for at in atividades:
                    nota = df_filtrado[df_filtrado["Aluno"] == aluno][at].values[0]
                    maximo = 10 if 'avalia' in at.lower() else 5
                    linha.append(round((nota / maximo) * 10, 1))
                matriz.append(linha)
            fig_heat = go.Figure(data=go.Heatmap(z=matriz, x=atividades, y=df_filtrado["Aluno"],
                                                colorscale='RdYlGn_r', text=[[f"{v:.1f}" for v in linha] for linha in matriz],
                                                texttemplate="%{text}", textfont={"size": 9}))
            fig_heat.update_layout(height=800, xaxis_title="Atividade", yaxis_title="Aluno")
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.warning("Sem dados para o mapa de calor.")
    
    # --- Aba 4: Radar Individual ---
    with tab4:
        if len(df_filtrado) > 0:
            aluno_sel = st.selectbox("Escolha o aluno", sorted(df_filtrado["Aluno"].unique()))
            aluno_row = df_filtrado[df_filtrado["Aluno"] == aluno_sel].iloc[0]
            radar_vals = {}
            for at in atividades:
                nota = aluno_row[at]
                maximo = 10 if 'avalia' in at.lower() else 5
                radar_vals[at] = (nota / maximo) * 10
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=list(radar_vals.values()), theta=list(radar_vals.keys()),
                                                fill='toself', name=aluno_sel, line_color=COR_PRIMARIA))
            fig_radar.add_trace(go.Scatterpolar(r=[10]*len(radar_vals), theta=list(radar_vals.keys()),
                                                fill=None, name="Máximo", line=dict(color="gray", dash="dash")))
            fig_radar.update_layout(polar=dict(radialaxis=dict(range=[0,10], dtick=2)))
            st.plotly_chart(fig_radar, use_container_width=True)
            pior_at = min(radar_vals, key=radar_vals.get)
            nota_orig = aluno_row[pior_at]
            max_orig = 10 if 'avalia' in pior_at.lower() else 5
            st.warning(f"⚠️ **Principal dificuldade:** {pior_at} (nota {nota_orig:.1f} de {max_orig})")
else:
    st.warning("Nenhum aluno encontrado com os filtros selecionados.")
    
st.markdown("---")
st.caption("Dashboard universal – atualize o Excel e recarregue a página.")

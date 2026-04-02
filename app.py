import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(page_title="Gestor de Tarefas", layout="wide")

# Inicialização do banco de dados na memória (Em produção real, usaríamos um banco SQL)
if 'dados' not in st.session_state:
    st.session_state.dados = pd.DataFrame(columns=['Tipo', 'Data', 'Assunto', 'Descricao'])
if 'logado' not in st.session_state:
    st.session_state.logado = False

# --- FUNÇÕES DE APOIO ---
def login():
    st.title("🔐 Acesso ao Sistema")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == "admin" and senha == "123456":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")

def calcular_status(data_vencimento):
    hoje = datetime.now().date()
    diferenca = (data_vencimento - hoje).days
    if diferenca < 0:
        return "Vencido", "red"
    elif 0 <= diferenca <= 2:
        return "Próximos 2 dias", "gold"
    else:
        return "3 dias ou mais", "blue"

# --- INTERFACE PRINCIPAL ---
if not st.session_state.logado:
    login()
else:
    # Sidebar para adicionar novos itens
    with st.sidebar:
        st.header("➕ Novo Item")
        tipo = st.selectbox("Tipo", ["LEMBRETE", "COMPROMISSO"])
        data = st.date_input("Data de Vencimento")
        assunto = st.text_input("Assunto")
        desc = st.text_area("Descrição")
        if st.button("Salvar"):
            novo_item = pd.DataFrame([[tipo, data, assunto, desc]], columns=['Tipo', 'Data', 'Assunto', 'Descricao'])
            st.session_state.dados = pd.concat([st.session_state.dados, novo_item], ignore_index=True)
            st.success("Salvo com sucesso!")

    # Menu Superior (Abas)
    tab_inicio, tab_lembretes, tab_compromissos = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])

    # --- ABA INÍCIO (GRÁFICOS) ---
    with tab_inicio:
        st.header("Resumo de Status")
        col1, col2 = st.columns(2)
        
        for i, tipo_item in enumerate(["LEMBRETE", "COMPROMISSO"]):
            df_filtrado = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_item].copy()
            counts = {"red": 0, "gold": 0, "blue": 0}
            
            if not df_filtrado.empty:
                for d in df_filtrado['Data']:
                    _, cor = calcular_status(d)
                    counts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[counts["red"], counts["gold"], counts["blue"]],
                y=["Vencido", "Até 2 dias", "3+ dias"],
                orientation='h',
                marker_color=["red", "gold", "blue"]
            ))
            fig.update_layout(title=f"{tipo_item}S ({len(df_filtrado)})", height=300, margin=dict(l=20, r=20, t=40, b=20))
            
            if i == 0: col1.plotly_chart(fig, use_container_width=True)
            else: col2.plotly_chart(fig, use_container_width=True)

    # --- ABAS DE LISTAGEM ---
    def renderizar_lista(tipo_nome):
        df = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_nome].copy()
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values(by='Data')
        
        for _, row in df.iterrows():
            dia_semana = row['Data'].strftime('%A').upper() # Em inglês, ajuste para PT-BR se desejar
            data_formatada = row['Data'].strftime('%d/%m/%Y')
            
            with st.expander(f"**{dia_semana}** | {data_formatada} | **{row['Assunto']}**"):
                st.write(f"**Descrição:** {row['Descricao']}")

    with tab_lembretes:
        st.header("Meus Lembretes")
        renderizar_lista("LEMBRETE")

    with tab_compromissos:
        st.header("Meus Compromissos")
        renderizar_lista("COMPROMISSO")
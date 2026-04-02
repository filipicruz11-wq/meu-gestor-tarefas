import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(page_title="Gestor de Tarefas", layout="wide")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'dados' not in st.session_state:
    st.session_state.dados = pd.DataFrame(columns=['ID', 'Tipo', 'Data', 'Assunto', 'Descricao'])
if 'logado' not in st.session_state:
    st.session_state.logado = False
# Variáveis para controlar o que está escrito nos campos
if 'texto_assunto' not in st.session_state:
    st.session_state.texto_assunto = ""
if 'texto_desc' not in st.session_state:
    st.session_state.texto_desc = ""

# --- FUNÇÕES DE LÓGICA ---
def calcular_status(data_vencimento):
    hoje = datetime.now().date()
    diferenca = (data_vencimento - hoje).days
    if diferenca <= 0:
        return "Vencido", "red"
    elif 1 <= diferenca <= 2:
        return "Próximos 2 dias", "gold"
    else:
        return "3 dias ou mais", "blue"

def limpar_campos():
    st.session_state.texto_assunto = ""
    st.session_state.texto_desc = ""

# --- INTERFACE DE LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso ao Sistema")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == "admin" and senha == "123456":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")
else:
    # --- SIDEBAR (CADASTRO) ---
    with st.sidebar:
        st.header("➕ Cadastro")
        tipo = st.selectbox("Tipo", ["LEMBRETE", "COMPROMISSO"])
        data = st.date_input("Data de Vencimento")
        
        # Aqui está o segredo: o valor vem da variável de estado
        assunto = st.text_input("Assunto", value=st.session_state.texto_assunto)
        desc = st.text_area("Descrição", value=st.session_state.texto_desc)
        
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("Salvar", use_container_width=True):
            if assunto:
                novo_id = datetime.now().strftime('%Y%m%d%H%M%S')
                novo_item = pd.DataFrame([[novo_id, tipo, data, assunto, desc]], 
                                        columns=['ID', 'Tipo', 'Data', 'Assunto', 'Descricao'])
                st.session_state.dados = pd.concat([st.session_state.dados, novo_item], ignore_index=True)
                limpar_campos()
                st.success("Salvo!")
                st.rerun() # O rerun limpa a tela e aplica os campos vazios
            else:
                st.warning("Preencha o assunto.")
        
        if col_btn2.button("Limpar", use_container_width=True):
            limpar_campos()
            st.rerun()

    # --- ABAS ---
    abas = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])

    # --- ABA INÍCIO ---
    with abas[0]:
        st.header("Resumo de Status")
        col1, col2 = st.columns(2)
        
        for i, tipo_item in enumerate(["LEMBRETE", "COMPROMISSO"]):
            df_f = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_item]
            counts = {"red": 0, "gold": 0, "blue": 0}
            for d in df_f['Data']:
                _, cor = calcular_status(pd.to_datetime(d).date() if isinstance(d, str) else d)
                counts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[counts["red"], counts["gold"], counts["blue"]],
                y=["Vencido", "Até 2 dias", "3+ dias"],
                orientation='h', marker_color=["red", "gold", "blue"]
            ))
            fig.update_layout(title=f"{tipo_item}S", height=300)
            
            if i == 0:
                col1.plotly_chart(fig, use_container_width=True)
                if col1.button(f"Ver Lista de {tipo_item}s"):
                    st.info("Clique na aba 'LEMBRETES' no topo da página.")
            else:
                col2.plotly_chart(fig, use_container_width=True)
                if col2.button(f"Ver Lista de {tipo_item}s"):
                    st.info("Clique na aba 'COMPROMISSOS' no topo da página.")

    # --- FUNÇÃO DE LISTAGEM ---
    def renderizar_lista(tipo_nome, aba_obj):
        with aba_obj:
            df = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_nome].copy()
            if not df.empty:
                df['Data'] = pd.to_datetime(df['Data'])
                df = df.sort_values(by='Data')
                
                for _, row in df.iterrows():
                    dias = {"Monday":"SEGUNDA-FEIRA", "Tuesday":"TERÇA-FEIRA", "Wednesday":"QUARTA-FEIRA", 
                            "Thursday":"QUINTA-FEIRA", "Friday":"SEXTA-FEIRA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    dia_pt = dias[row['Data'].strftime('%A')]
                    data_f = row['Data'].strftime('%d/%m/%Y')
                    
                    col_texto, col_edit, col_del = st.columns([0.7, 0.15, 0.15])
                    
                    with col_texto:
                        with st.expander(f"**{dia_pt}** | {data_f} | **{row['Assunto']}**"):
                            st.write(row['Descricao'])
                    
                    if col_edit.button("📝", key=f"ed_{row['ID']}"):
                        st.session_state.texto_assunto = row['Assunto']
                        st.session_state.texto_desc = row['Descricao']
                        st.session_state.dados = st.session_state.dados[st.session_state.dados['ID'] != row['ID']]
                        st.rerun()

                    if col_del.button("🗑️", key=f"dl_{row['ID']}"):
                        st.session_state.dados = st.session_state.dados[st.session_state.dados['ID'] != row['ID']]
                        st.rerun()
            else:
                st.write("Nenhum item cadastrado.")

    renderizar_lista("LEMBRETE", abas[1])
    renderizar_lista("COMPROMISSO", abas[2])

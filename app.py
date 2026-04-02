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
if 'aba_ativa' not in st.session_state:
    st.session_state.aba_ativa = 0

# --- FUNÇÕES DE LÓGICA ---
def calcular_status(data_vencimento):
    hoje = datetime.now().date()
    # Se a data for HOJE ou anterior, já conta como Vencido
    diferenca = (data_vencimento - hoje).days
    if diferenca <= 0:
        return "Vencido", "red"
    elif 1 <= diferenca <= 2:
        return "Próximos 2 dias", "gold"
    else:
        return "3 dias ou mais", "blue"

def limpar_campos():
    st.session_state.input_assunto = ""
    st.session_state.input_desc = ""

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
        tipo = st.selectbox("Tipo", ["LEMBRETE", "COMPROMISSO"], key="input_tipo")
        data = st.date_input("Data de Vencimento", key="input_data")
        assunto = st.text_input("Assunto", key="input_assunto")
        desc = st.text_area("Descrição", key="input_desc")
        
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("Salvar", use_container_width=True):
            if assunto:
                novo_id = datetime.now().strftime('%Y%m%d%H%M%S')
                novo_item = pd.DataFrame([[novo_id, tipo, data, assunto, desc]], 
                                        columns=['ID', 'Tipo', 'Data', 'Assunto', 'Descricao'])
                st.session_state.dados = pd.concat([st.session_state.dados, novo_item], ignore_index=True)
                limpar_campos()
                st.success("Salvo!")
                st.rerun()
            else:
                st.warning("Preencha o assunto.")
        
        if col_btn2.button("Limpar", use_container_width=True):
            limpar_campos()
            st.rerun()

    # --- ABAS ---
    # Usamos o index para permitir que o gráfico mude a aba
    abas = ["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"]
    escolha_aba = st.tabs(abas)

    # --- ABA INÍCIO ---
    with escolha_aba[0]:
        st.header("Resumo de Status")
        col1, col2 = st.columns(2)
        
        for i, tipo_item in enumerate(["LEMBRETE", "COMPROMISSO"]):
            df_f = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_item]
            counts = {"red": 0, "gold": 0, "blue": 0}
            for d in df_f['Data']:
                _, cor = calcular_status(d)
                counts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[counts["red"], counts["gold"], counts["blue"]],
                y=["Vencido", "Até 2 dias", "3+ dias"],
                orientation='h', marker_color=["red", "gold", "blue"]
            ))
            fig.update_layout(title=f"{tipo_item}S (Clique para ver lista)", height=300)
            
            # Exibe o gráfico e botão de redirecionamento
            if i == 0:
                col1.plotly_chart(fig, use_container_width=True)
                if col1.button(f"Ir para {tipo_item}S"):
                    st.info("Role para cima e clique na aba correspondente.")
            else:
                col2.plotly_chart(fig, use_container_width=True)
                if col2.button(f"Ir para {tipo_item}S"):
                    st.info("Role para cima e clique na aba correspondente.")

    # --- FUNÇÃO DE LISTAGEM COM EDITAR/EXCLUIR ---
    def renderizar_lista(tipo_nome, aba_obj):
        with aba_obj:
            df = st.session_state.dados[st.session_state.dados['Tipo'] == tipo_nome].copy()
            df['Data'] = pd.to_datetime(df['Data'])
            df = df.sort_values(by='Data')
            
            if df.empty:
                st.write("Nenhum item cadastrado.")
            
            for index, row in df.iterrows():
                # Tradução manual simplificada para PT-BR
                dias = {"Monday":"SEGUNDA-FEIRA", "Tuesday":"TERÇA-FEIRA", "Wednesday":"QUARTA-FEIRA", 
                        "Thursday":"QUINTA-FEIRA", "Friday":"SEXTA-FEIRA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                dia_pt = dias[row['Data'].strftime('%A')]
                data_f = row['Data'].strftime('%d/%m/%Y')
                
                col_texto, col_edit, col_excluir = st.columns([0.7, 0.15, 0.15])
                
                with col_texto:
                    with st.expander(f"**{dia_pt}** | {data_f} | **{row['Assunto']}**"):
                        # Correção: apenas o texto puro da descrição
                        st.write(row['Descricao'])
                
                if col_edit.button("📝", key=f"edit_{row['ID']}"):
                    st.session_state.input_assunto = row['Assunto']
                    st.session_state.input_desc = row['Descricao']
                    # Remove o antigo para salvar o novo "editado"
                    st.session_state.dados = st.session_state.dados[st.session_state.dados['ID'] != row['ID']]
                    st.warning("Dados carregados no menu lateral para edição!")

                if col_excluir.button("🗑️", key=f"del_{row['ID']}"):
                    st.session_state.dados = st.session_state.dados[st.session_state.dados['ID'] != row['ID']]
                    st.rerun()

    renderizar_lista("LEMBRETE", escolha_aba[1])
    renderizar_lista("COMPROMISSO", escolha_aba[2])

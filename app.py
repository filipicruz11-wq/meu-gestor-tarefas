import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY, tipo TEXT, data TEXT, assunto TEXT, descricao TEXT
            )
        """))
        conn.commit()

inicializar_db()

# --- ESTADOS E RESET ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'form_reset_key' not in st.session_state: st.session_state.form_reset_key = 0

# Valores temporários para edição
if 'edit_assunto' not in st.session_state: st.session_state.edit_assunto = ""
if 'edit_desc' not in st.session_state: st.session_state.edit_desc = ""

def resetar_formulario():
    st.session_state.editando_id = None
    st.session_state.edit_assunto = ""
    st.session_state.edit_desc = ""
    st.session_state.form_reset_key += 1 # Força o Streamlit a recriar os campos vazios

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #f1f3f5 !important;
        border: 2px solid #ced4da !important;
        border-radius: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    u = st.text_input("Usuário")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and s == "123456":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Dados incorretos.")
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        
        # O segredo do reset está na key dinâmica (form_reset_key)
        # Adicionamos o "" como primeira opção para forçar a escolha
        tipo = st.selectbox("Selecione o Tipo", ["", "LEMBRETE", "COMPROMISSO"], key=f"tipo_{st.session_state.form_reset_key}")
        data_venc = st.date_input("Vencimento", format="DD/MM/YYYY", key=f"data_{st.session_state.form_reset_key}")
        
        # Se estiver editando, usamos o valor salvo, se não, usamos o campo resetado
        assunto = st.text_input("Assunto", value=st.session_state.edit_assunto, key=f"assunto_{st.session_state.form_reset_key}")
        desc = st.text_area("Descrição", value=st.session_state.edit_desc, key=f"desc_{st.session_state.form_reset_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar", use_container_width=True):
            if not tipo:
                st.error("Escolha LEMBRETE ou COMPROMISSO!")
            elif not assunto:
                st.error("O Assunto é obrigatório!")
            else:
                with engine.connect() as conn:
                    if st.session_state.editando_id:
                        conn.execute(text("UPDATE tarefas SET tipo=:t, data=:d, assunto=:a, descricao=:de WHERE id=:i"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc, "i": st.session_state.editando_id})
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, data, assunto, descricao) VALUES (:t, :d, :a, :de)"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc})
                    conn.commit()
                st.success("Salvo!")
                resetar_formulario()
                st.rerun()
        
        if c2.button("🧹 Limpar", use_container_width=True):
            resetar_formulario()
            st.rerun()

    # --- CORPO ---
    tab_dash, tab_lem, tab_com = st.tabs(["🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS"])
    
    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'data', 'assunto', 'descricao'])

    # Dashboard
    with tab_dash:
        st.subheader("Visão Geral")
        col_l, col_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            hoje = datetime.now().date()
            for d in dff['data']:
                dv = datetime.strptime(d, '%Y-%m-%d').date()
                dif = (dv - hoje).days
                if dif <= 0: cts["red"] += 1
                elif 1 <= dif <= 2: cts["gold"] += 1
                else: cts["blue"] += 1
            
            fig = go.Figure(go.Bar(x=[cts["red"], cts["gold"], cts["blue"]],
                                   y=["Vencido", "2 dias", "3+ dias"],
                                   orientation='h', marker_color=["red", "gold", "blue"]))
            fig.update_layout(title=f"{nome}S", height=250, margin=dict(l=10, r=10, t=40, b=10))
            if i == 0: col_l.plotly_chart(fig, use_container_width=True)
            else: col_c.plotly_chart(fig, use_container_width=True)

    # Listas
    def listar(tipo_nome, tab_obj):
        with tab_obj:
            dff = df[df['tipo'] == tipo_nome].sort_values(by='data')
            if dff.empty: st.info(f"Sem {tipo_nome.lower()}s.")
            else:
                for _, row in dff.iterrows():
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    dias = {"Monday":"SEGUNDA", "Tuesday":"TERÇA", "Wednesday":"QUARTA", "Thursday":"QUINTA", "Friday":"SEXTA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                    dia_pt = dias[dt.strftime('%A')]
                    
                    c_info, c_ed, c_del = st.columns([0.8, 0.1, 0.1])
                    with c_info:
                        with st.expander(f"**{dia_pt}** | {dt.strftime('%d/%m/%Y')} | {row['assunto']}"):
                            st.write(row['descricao'] if row['descricao'] else "Sem descrição.")
                    
                    if c_ed.button("📝", key=f"ed_{row['id']}"):
                        st.session_state.editando_id = row['id']
                        st.session_state.edit_assunto = row['assunto']
                        st.session_state.edit_desc = row['descricao']
                        # Não chamamos resetar aqui para não apagar o que acabamos de carregar
                        st.rerun()
                        
                    if c_del.button("🗑️", key=f"del_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                            conn.commit()
                        st.rerun()

    listar("LEMBRETE", tab_lem)
    listar("COMPROMISSO", tab_com)

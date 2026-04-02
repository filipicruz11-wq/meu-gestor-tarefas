import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide", page_icon="📅")

# --- CONEXÃO COM BANCO (Otimizada com Cache) ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

@st.cache_resource
def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY, 
                tipo TEXT, 
                data TEXT, 
                assunto TEXT, 
                descricao TEXT
            )
        """))
        conn.commit()

inicializar_db()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_data' not in st.session_state: st.session_state.val_data = datetime.now().date()
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""
if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_data = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS (FOCO EM COMPACTAÇÃO) ---
st.markdown("""
    <style>
    /* Remove espaços em branco no topo */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    
    /* Compacta o espaço entre QUALQUER elemento do Streamlit */
    [data-testid="stVerticalBlock"] > div {
        margin-bottom: -0.9rem !important;
        padding-bottom: 0px !important;
    }

    /* Estiliza o Expander para ser uma linha fina */
    .streamlit-expanderHeader {
        padding: 0.1rem 0.5rem !important;
        border: none !important;
        background-color: transparent !important;
        font-size: 14px !important;
    }
    .streamlit-expanderContent {
        border: none !important;
        background-color: #fcfcfc !important;
    }

    /* Alinhamento vertical perfeito das colunas */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        height: 35px !important; /* Força altura fixa para as linhas */
    }

    /* Linha divisória ultra fina */
    hr {
        margin: 0.1rem 0px !important;
        padding: 0px !important;
        border: 0;
        border-top: 1px solid #eee;
    }

    /* Estilo dos inputs na sidebar */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #f8f9fa !important;
    }

    /* Esconder o botão de fechar expander que às vezes sobra */
    .streamlit-expanderHeader svg {
        width: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def obter_estilo(data_str):
    dv = datetime.strptime(data_str, '%Y-%m-%d').date()
    hoje = datetime.now().date()
    dif = (dv - hoje).days
    if dif < 0: return "#E74C3C", "🔴 VENCIDO"
    elif 0 <= dif <= 2: return "#F1C40F", "🟡 URGENTE"
    else: return "#3498DB", "🔵 NO PRAZO"

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Agenda CEJUSC")
    col_u, col_s = st.columns(2)
    with col_u: u = st.text_input("Usuário")
    with col_s: s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and s == "123456":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Dados incorretos.")
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.subheader("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO"]
        idx_atual = lista_tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in lista_tipos else 0
        
        tipo = st.selectbox("Tipo", lista_tipos, index=idx_atual, key=f"t_{st.session_state.campo_key}")
        data_venc = st.date_input("Vencimento", value=st.session_state.val_data, format="DD/MM/YYYY", key=f"d_{st.session_state.campo_key}")
        assunto = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        desc = st.text_area("Descrição", value=st.session_state.val_desc, key=f"de_{st.session_state.campo_key}", height=100)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar", use_container_width=True):
            if not tipo or not assunto:
                st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    if st.session_state.editando_id:
                        conn.execute(text("UPDATE tarefas SET tipo=:t, data=:d, assunto=:a, descricao=:de WHERE id=:i"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc, "i": st.session_state.editando_id})
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, data, assunto, descricao) VALUES (:t, :d, :a, :de)"),
                                   {"t": tipo, "d": str(data_venc), "a": assunto, "de": desc})
                    conn.commit()
                st.success("Sucesso!")
                limpar_tudo()
                st.rerun()
        
        if c2.button("🧹 Limpar", use_container_width=True):
            limpar_tudo()
            st.rerun()
        
        st.divider()
        if st.button("🚪 Sair"):
            st.session_state.logado = False
            st.rerun()

    # --- CARREGAMENTO DE DADOS ---
    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'data', 'assunto', 'descricao'])

    # --- CONTEÚDO PRINCIPAL (ABAS) ---
    t_dash, t_lem, t_com = st.tabs(["🏠 DASHBOARD", "📝 LEMBRETES", "📅 COMPROMISSOS"])

    # Aba Dashboard
    with t_dash:
        st.subheader("Resumo de Atividades")
        col_l, col_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"#E74C3C": 0, "#F1C40F": 0, "#3498DB": 0}
            for d in dff['data']:
                cor, _ = obter_estilo(d)
                cts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[cts["#E74C3C"], cts["#F1C40F"], cts["#3498DB"]],
                y=["Vencido", "Urgente", "No Prazo"],
                orientation='h',
                marker_color=["#E74C3C", "#F1C40F", "#3498DB"],
                text=[cts["#E74C3C"], cts["#F1C40F"], cts["#3498DB"]],
                textposition='outside'
            ))
            fig.update_layout(title=f"{nome}S ({len(dff)})", height=200, margin=dict(l=0, r=0, t=30, b=0),
                              xaxis=dict(visible=False), yaxis=dict(autorange="reversed"))
            if i == 0: col_l.plotly_chart(fig, use_container_width=True)
            else: col_c.plotly_chart(fig, use_container_width=True)

    # Função de Listagem Compacta
    def listar(tipo_nome, tab):
        with tab:
            dff = df[df['tipo'] == tipo_nome].sort_values(by='data')
            if dff.empty:
                st.info(f"Nenhum {tipo_nome.lower()} registrado.")
            else:
                # Cabeçalho da Lista
                st.markdown("<div style='font-weight:bold; color:#555; padding-bottom:5px;'>Status | Dia | Data | Assunto</div>", unsafe_allow_html=True)
                
                for _, row in dff.iterrows():
                    cor_hex, texto_status = obter_estilo(row['data'])
                    dt = datetime.strptime(row['data'], '%Y-%m-%d')
                    dias_semana = {"Monday":"SEG", "Tuesday":"TER", "Wednesday":"QUA", "Thursday":"QUI", "Friday":"SEX", "Saturday":"SÁB", "Sunday":"DOM"}
                    dia_pt = dias_semana[dt.strftime('%A')]
                    data_f = dt.strftime('%d/%m/%Y')
                    
                    # Colunas com larguras otimizadas para compactação
                    c_status, c_dia, c_data, c_assunto, c_ed, c_del = st.columns([0.13, 0.07, 0.10, 0.56, 0.07, 0.07])
                    
                    with c_status:
                        st.markdown(f"<span style='color:{cor_hex}; font-weight:bold; font-size:12px;'>{texto_status}</span>", unsafe_allow_html=True)
                    with c_dia:
                        st.markdown(f"<span style='color:#777;'>{dia_pt}</span>", unsafe_allow_html=True)
                    with c_data:
                        st.markdown(f"**{data_f}**")
                    with c_assunto:
                        with st.expander(f"**{row['assunto']}**"):
                            st.write(row['descricao'] if row['descricao'] else "_Sem descrição detalhada._")
                    
                    with c_ed:
                        if st.button("📝", key=f"ed_{tipo_nome}_{row['id']}"):
                            st.session_state.editando_id = row['id']
                            st.session_state.val_tipo = row['tipo']
                            st.session_state.val_data = datetime.strptime(row['data'], '%Y-%m-%d').date()
                            st.session_state.val_assunto = row['assunto']
                            st.session_state.val_desc = row['descricao']
                            st.session_state.campo_key = f"edit_{row['id']}_{datetime.now().timestamp()}"
                            st.rerun()
                    with c_del:
                        if st.button("🗑️", key=f"del_{tipo_nome}_{row['id']}"):
                            with engine.connect() as conn:
                                conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                                conn.commit()
                            st.rerun()
                    
                    st.markdown("<hr>", unsafe_allow_html=True)

    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import time

# Configuração da página
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- CONEXÃO COM BANCO ---
DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
engine = create_engine(DB_URL)

def inicializar_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY, tipo TEXT, prazo TEXT, assunto TEXT, descricao TEXT
            )
        """))
        try:
            conn.execute(text("ALTER TABLE tarefas RENAME COLUMN data TO prazo;"))
        except:
            pass
        conn.commit()

inicializar_db()

# --- CAIXA DE DIÁLOGO (MODAL) ---
@st.dialog("Detalhes da Atividade")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    if descricao:
        # Adicionamos um parágrafo vazio antes para garantir que a 1ª linha não cole no título
        st.markdown(f'<div class="caixa-texto-cejusc"><pre>{descricao}</pre></div>', unsafe_allow_html=True)
    else:
        st.write("Sem descrição disponível.")
        
    if st.button("Fechar", width="stretch"):
        st.rerun()

# --- ESTADOS DO SISTEMA ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None

if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_prazo' not in st.session_state: st.session_state.val_prazo = datetime.now().date()
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""

if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS (CORREÇÃO DE ESPAÇAMENTO DA 1ª LINHA) ---
st.markdown(f"""
    <style data-cache-breaker="{int(time.time())}">
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {{
        background-color: #f1f3f5 !important;
        border: 2px solid #ced4da !important;
    }}
    textarea {{ spellcheck: false !important; }}
    [data-testid="column"] {{ display: flex; align-items: center; }}
    hr {{ margin-top: 5px !important; margin-bottom: 5px !important; }}
    .stButton button {{ text-align: left !important; padding-left: 0px !important; }}
    
    /* ESTILO REFORÇADO PARA A DESCRIÇÃO */
    .caixa-texto-cejusc {{
        margin-top: 20px !important; /* Força espaço após o título */
        display: block !important;
    }}
    
    .caixa-texto-cejusc pre {{
        font-family: inherit !important;
        white-space: pre-wrap !important; /* Mantém quebras de linha */
        word-wrap: break-word !important;
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: inherit !important;
        font-size: 16px !important;
        line-height: 1.5 !important; /* Melhora o espaçamento entre linhas */
    }}
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
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA"]
        idx_atual = lista_tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in lista_tipos else 0
        
        tipo_selecionado = st.selectbox("Selecione o Tipo", lista_tipos, index=idx_atual, key=f"t_{st.session_state.campo_key}")
        
        tipos_sem_prazo = ["INFORMAÇÃO", "CONTATO", "AUDIÊNCIA"]
        if tipo_selecionado not in tipos_sem_prazo:
            data_venc = st.date_input("Vencimento", value=st.session_state.val_prazo, format="DD/MM/YYYY", key=f"d_{st.session_state.campo_key}")
        else:
            data_venc = datetime.now().date()
            
        assunto_input = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        desc_input = st.text_area("Descrição", value=st.session_state.val_desc, key=f"de_{st.session_state.campo_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar", width="stretch"):
            if not tipo_selecionado or not assunto_input:
                st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    params = {"t": tipo_selecionado, "p": str(data_venc), "a": str(assunto_input), "de": str(desc_input)}
                    if st.session_state.editando_id:
                        params["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), params)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), params)
                    conn.commit()
                st.success("Salvo!")
                limpar_tudo()
                st.rerun()
        
        if c2.button("🧹 Limpar", width="stretch"):
            limpar_tudo()
            st.rerun()

    # ABAS
    t_dash, t_lem, t_com, t_info, t_cont, t_aud = st.tabs([
        "🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS", "ℹ️ INFORMAÇÕES", "📞 CONTATOS", "⚖️ AUDIÊNCIAS"
    ])
    
    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    def obter_estilo(prazo_str):
        try:
            dv = datetime.strptime(str(prazo_str), '%Y-%m-%d').date()
            hoje = datetime.now().date()
            dif = (dv - hoje).days
            if dif <= 0: return "red", "🔴 VENCIDO"
            elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
            else: return "blue", "🔵 FUTURO"
        except:
            return "blue", "🔵 SEM DATA"

    with t_dash:
        st.subheader("Visão Geral")
        col_l, col_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            if 'prazo' in dff.columns:
                for p in dff['prazo']:
                    cor, _ = obter_estilo(p)
                    cts[cor] += 1
            
            fig = go.Figure(go.Bar(
                x=[cts["red"], cts["gold"], cts["blue"]],
                y=["Vencido", "2 dias", "3+ dias"],
                orientation='h',
                marker_color=["red", "gold", "blue"],
                text=[cts["red"], cts["gold"], cts["blue"]], 
                textposition='outside'
            ))
            fig.update_layout(title=f"{nome}S", height=250, margin=dict(l=10, r=50, t=40, b=10), xaxis=dict(visible=False))
            if i == 0: col_l.plotly_chart(fig, use_container_width=True)
            else: col_c.plotly_chart(fig, use_container_width=True)

    def listar(tipo_nome, tab):
        with tab:
            if 'prazo' in df.columns:
                dff = df[df['tipo'] == tipo_nome].sort_values(by='prazo')
                if dff.empty: st.info(f"Nenhum item em {tipo_nome.lower()}.")
                else:
                    st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                    st.markdown("---")
                    for _, row in dff.iterrows():
                        cor_hex, texto_status = obter_estilo(row['prazo'])
                        dt = datetime.strptime(row['prazo'], '%Y-%m-%d')
                        dias = {"Monday":"SEGUNDA", "Tuesday":"TERÇA", "Wednesday":"QUARTA", "Thursday":"QUINTA", "Friday":"SEXTA", "Saturday":"SÁBADO", "Sunday":"DOMINGO"}
                        
                        c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                        c1.write(texto_status)
                        c2.write(dias[dt.strftime('%A')])
                        c3.write(dt.strftime('%d/%m/%Y'))
                        
                        if c4.button(f"**{row['assunto']}**", key=f"b_{row['id']}", width="stretch"):
                            exibir_detalhes(row['assunto'], row['descricao'])
                        
                        if c5.button("📝", key=f"e_{row['id']}"):
                            st.session_state.editando_id = row['id']
                            st.session_state.val_tipo = row['tipo']
                            st.session_state.val_prazo = datetime.strptime(row['prazo'], '%Y-%m-%d').date()
                            st.session_state.val_assunto = row['assunto']
                            st.session_state.val_desc = row['descricao']
                            st.session_state.campo_key = f"ed_{row['id']}_{datetime.now().timestamp()}"
                            st.rerun()
                            
                        if c6.button("🗑️", key=f"d_{row['id']}"):
                            with engine.connect() as conn:
                                conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                                conn.commit()
                            st.rerun()
                        st.markdown("---")

    def listar_simplificado(tipo_nome, tab, icone="📌"):
        with tab:
            dff = df[df['tipo'] == tipo_nome].sort_values(by='assunto')
            if dff.empty: st.info(f"Nada em {tipo_nome.lower()}.")
            else:
                for _, row in dff.iterrows():
                    c1, c2, c3 = st.columns([0.85, 0.075, 0.075])
                    if c1.button(f"{icone} **{row['assunto']}**", key=f"bs_{row['id']}", width="stretch"):
                        exibir_detalhes(row['assunto'], row['descricao'])
                    if c2.button("📝", key=f"es_{row['id']}"):
                        st.session_state.editando_id = row['id']
                        st.session_state.val_tipo = row['tipo']
                        st.session_state.val_assunto = row['assunto']
                        st.session_state.val_desc = row['descricao']
                        st.session_state.campo_key = f"eds_{row['id']}_{datetime.now().timestamp()}"
                        st.rerun()
                    if c3.button("🗑️", key=f"ds_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": row['id']})
                            conn.commit()
                        st.rerun()
                    st.markdown("---")

    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)
    listar_simplificado("INFORMAÇÃO", t_info, icone="📌")
    listar_simplificado("CONTATO", t_cont, icone="👤")
    listar_simplificado("AUDIÊNCIA", t_aud, icone="⚖️")

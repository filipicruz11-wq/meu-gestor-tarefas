import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import time
import calendar
import holidays

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
        conn.commit()

inicializar_db()

# --- CAIXA DE DIÁLOGO (MODAL) ---
@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    if descricao:
        descricao_limpa = descricao.replace("<span>", "").replace("</span>", "")
        descricao_formatada = descricao_limpa.replace("\n", "<br>")
        st.markdown(f'<div class="caixa-texto-fix">{descricao_formatada}</div>', unsafe_allow_html=True)
    else:
        st.write("Sem descrição disponível.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Fechar", width="stretch"):
        st.rerun()

# --- ESTADOS DO SISTEMA ---
# Tenta recuperar o login da URL para persistir no F5
query_params = st.query_params
if "logged" in query_params and query_params["logged"] == "true":
    st.session_state.logado = True

if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

# Estados para o formulário de cadastro
for key in ['val_tipo', 'val_assunto', 'val_desc']:
    if key not in st.session_state: st.session_state[key] = ""
if 'val_prazo' not in st.session_state: st.session_state.val_prazo = datetime.now().date()

# Controle do calendário
if 'cal_mes' not in st.session_state: st.session_state.cal_mes = datetime.now().month
if 'cal_ano' not in st.session_state: st.session_state.cal_ano = datetime.now().year

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS ---
st.markdown(f"""
    <style>
    .caixa-texto-fix {{ margin-top: 20px !important; font-family: sans-serif !important; font-size: 14px !important; line-height: 1.7 !important; color: #1E1E1E !important; }}
    .cal-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; table-layout: fixed; }}
    .cal-header {{ background-color: #f1f3f5; font-weight: bold; text-align: center; padding: 15px; border: 1px solid #dee2e6; }}
    .cal-day {{ height: 120px; text-align: right; vertical-align: top; padding: 10px; border: 1px solid #dee2e6; font-size: 18px; }}
    .dia-util {{ background-color: white; }}
    .dia-fds {{ background-color: #fff5f5; color: #e03131; }}
    .dia-feriado {{ background-color: #fff9db; color: #f08c00; font-weight: bold; }}
    .dia-vazio {{ background-color: #f8f9fa; }}
    </style>
    """, unsafe_allow_html=True)

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.container():
        with st.form("login_form"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            submit = st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True)
            if submit:
                if u == "admin" and s == "123456":
                    st.session_state.logado = True
                    st.query_params["logged"] = "true" # Salva na URL para o F5
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📝 " + ("Editar Item" if st.session_state.editando_id else "Novo Cadastro"))
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        
        tipo_selecionado = st.selectbox("Tipo", lista_tipos, key=f"t_{st.session_state.campo_key}")
        
        if tipo_selecionado not in ["INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]:
            data_venc = st.date_input("Vencimento", value=st.session_state.val_prazo, format="DD/MM/YYYY")
        else:
            data_venc = datetime.now().date()
            
        assunto_input = st.text_input("Assunto", value=st.session_state.val_assunto)
        desc_input = st.text_area("Descrição", value=st.session_state.val_desc, height=200)
        
        if st.button("✅ Salvar", use_container_width=True):
            if not tipo_selecionado or not assunto_input:
                st.error("Preencha Tipo e Assunto!")
            else:
                with engine.connect() as conn:
                    p = {"t": tipo_selecionado, "p": str(data_venc), "a": assunto_input, "de": desc_input}
                    if st.session_state.editando_id:
                        p["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), p)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), p)
                    conn.commit()
                st.success("Salvo!")
                limpar_tudo()
                st.rerun()
        
        if st.button("🧹 Limpar", use_container_width=True):
            limpar_tudo()
            st.rerun()
            
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.query_params.clear()
            st.rerun()

    # --- ABAS ---
    t_dash, t_lem, t_com, t_info, t_cont, t_aud, t_mod, t_cal = st.tabs([
        "🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS", "ℹ️ INFORMAÇÕES", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO"
    ])

    try:
        df = pd.read_sql("SELECT * FROM tarefas", engine)
    except:
        df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    def obter_estilo(p_str):
        try:
            dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
            hoje = datetime.now().date()
            dif = (dv - hoje).days
            if dif <= 0: return "🔴 VENCIDO"
            elif 1 <= dif <= 2: return "🟡 PRÓXIMO"
            else: return "🔵 FUTURO"
        except: return "🔵 SEM DATA"

    # Funções de listagem
    def listar(tipo, tab):
        with tab:
            dff = df[df['tipo'] == tipo].sort_values(by='prazo')
            if dff.empty: st.info(f"Vazio.")
            else:
                for _, r in dff.iterrows():
                    c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                    dt = datetime.strptime(r['prazo'], '%Y-%m-%d')
                    c1.write(obter_estilo(r['prazo']))
                    c2.write(dt.strftime('%A'))
                    c3.write(dt.strftime('%d/%m/%Y'))
                    if c4.button(f"**{r['assunto']}**", key=f"b_{r['id']}", use_container_width=True):
                        exibir_detalhes(r['assunto'], r['descricao'])
                    if c5.button("📝", key=f"e_{r['id']}"):
                        st.session_state.editando_id, st.session_state.val_tipo = r['id'], r['tipo']
                        st.session_state.val_assunto, st.session_state.val_desc = r['assunto'], r['descricao']
                        st.session_state.val_prazo = dt.date()
                        st.rerun()
                    if c6.button("🗑️", key=f"d_{r['id']}"):
                        with engine.connect() as cn:
                            cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                            cn.commit()
                        st.rerun()
                    st.markdown("---")

    def listar_simples(tipo, tab, icone):
        with tab:
            dff = df[df['tipo'] == tipo].sort_values(by='assunto')
            for _, r in dff.iterrows():
                c1, c2, c3 = st.columns([0.85, 0.075, 0.075])
                if c1.button(f"{icone} **{r['assunto']}**", key=f"s_{r['id']}", use_container_width=True):
                    exibir_detalhes(r['assunto'], r['descricao'])
                if c2.button("📝", key=f"es_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo = r['id'], r['tipo']
                    st.session_state.val_assunto, st.session_state.val_desc = r['assunto'], r['descricao']
                    st.rerun()
                if c3.button("🗑️", key=f"ds_{r['id']}"):
                    with engine.connect() as cn:
                        cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']})
                        cn.commit()
                    st.rerun()
                st.markdown("---")

    # --- ABA CALENDÁRIO ---
    with t_cal:
        col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
        with col_c2:
            c1, c2, c3 = st.columns([1, 3, 1])
            if c1.button("⬅️ Ant."):
                st.session_state.cal_mes -= 1
                if st.session_state.cal_mes < 1: st.session_state.cal_mes, st.session_state.cal_ano = 12, st.session_state.cal_ano - 1
                st.rerun()
            meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            c2.markdown(f"<h3 style='text-align:center'>{meses[st.session_state.cal_mes]} {st.session_state.cal_ano}</h3>", unsafe_allow_html=True)
            if c3.button("Próx. ➡️"):
                st.session_state.cal_mes += 1
                if st.session_state.cal_mes > 12: st.session_state.cal_mes, st.session_state.cal_ano = 1, st.session_state.cal_ano + 1
                st.rerun()

        cal = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
        br_holidays = holidays.BR()
        html = '<table class="cal-table"><tr>'
        for sem in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]: html += f'<th class="cal-header">{sem}</th>'
        html += '</tr>'
        for semana in cal:
            html += '<tr>'
            for i, dia in enumerate(semana):
                if dia == 0: html += '<td class="cal-day dia-vazio"></td>'
                else:
                    data_at = datetime(st.session_state.cal_ano, st.session_state.cal_mes, dia)
                    classe = "dia-fds" if i >= 5 else "dia-util"
                    feriado = br_holidays.get(data_at)
                    if feriado: classe = "dia-feriado"
                    txt_f = f'<div style="font-size:10px; color:#f08c00">{feriado}</div>' if feriado else ""
                    html += f'<td class="cal-day {classe}"><b>{dia}</b>{txt_f}</td>'
            html += '</tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    # Chamadas das abas
    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)
    listar_simples("INFORMAÇÃO", t_info, "📌")
    listar_simples("CONTATO", t_cont, "📞")
    listar_simples("AUDIÊNCIA", t_aud, "⚖️")
    listar_simples("MODELO", t_mod, "📄")

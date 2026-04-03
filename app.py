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
if "logged" in st.query_params and st.query_params["logged"] == "true":
    st.session_state.logado = True

if 'logado' not in st.session_state: st.session_state.logado = False
if 'editando_id' not in st.session_state: st.session_state.editando_id = None
if 'campo_key' not in st.session_state: st.session_state.campo_key = "init"

if 'val_tipo' not in st.session_state: st.session_state.val_tipo = ""
if 'val_assunto' not in st.session_state: st.session_state.val_assunto = ""
if 'val_desc' not in st.session_state: st.session_state.val_desc = ""
if 'val_prazo' not in st.session_state: st.session_state.val_prazo = datetime.now().date()

if 'cal_mes' not in st.session_state: st.session_state.cal_mes = datetime.now().month
if 'cal_ano' not in st.session_state: st.session_state.cal_ano = datetime.now().year

def limpar_tudo():
    st.session_state.editando_id = None
    st.session_state.val_tipo = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.campo_key = f"limpar_{datetime.now().timestamp()}"

# --- ESTILIZAÇÃO CSS (Calendário com fundo e bordas reforçadas) ---
st.markdown(f"""
    <style>
    .caixa-texto-fix {{ margin-top: 10px !important; font-family: sans-serif !important; font-size: 14px !important; line-height: 1.5 !important; color: #1E1E1E !important; }}
    
    /* Calendário com fundo colorido e bordas pretas finas */
    .cal-table {{ 
        width: 100%; 
        border-collapse: collapse; 
        font-family: sans-serif; 
        table-layout: fixed; 
        background-color: #f8f9fa; /* Fundo cinza bem claro para destacar do site */
        border: 2px solid #adb5bd;
    }}
    .cal-header {{ 
        background-color: #e9ecef; 
        font-weight: bold; 
        text-align: center; 
        padding: 8px; 
        border: 1px solid #adb5bd; 
        font-size: 14px; 
    }}
    .cal-day {{ 
        height: 85px; 
        text-align: right; 
        vertical-align: top; 
        padding: 5px; 
        border: 1px solid #adb5bd; 
        font-size: 14px; 
    }}
    .dia-util {{ background-color: #ffffff; }}
    .dia-fds {{ background-color: #fff5f5; color: #e03131; }}
    .dia-feriado {{ background-color: #fff9db; color: #f08c00; font-weight: bold; }}
    .dia-vazio {{ background-color: #f1f3f5; border: 1px solid #dee2e6; }}

    hr {{ margin: 4px 0px !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login_form"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.query_params["logged"] = "true"
                st.rerun()
            else: st.error("Dados incorretos.")
else:
    with st.sidebar:
        st.header("📝 " + ("Editar" if st.session_state.editando_id else "Novo"))
        lista_tipos = ["", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        tipo_sel = st.selectbox("Tipo", lista_tipos, key=f"t_{st.session_state.campo_key}")
        
        if tipo_sel not in ["INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]:
            dt_venc = st.date_input("Vencimento", value=st.session_state.val_prazo)
        else: dt_venc = datetime.now().date()
            
        ass_in = st.text_input("Assunto", value=st.session_state.val_assunto)
        des_in = st.text_area("Descrição", value=st.session_state.val_desc, height=150)
        
        if st.button("✅ Salvar", use_container_width=True):
            if not tipo_sel or not ass_in: st.error("Erro!")
            else:
                with engine.connect() as conn:
                    p = {"t": tipo_sel, "p": str(dt_venc), "a": ass_in, "de": des_in}
                    if st.session_state.editando_id:
                        p["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), p)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), p)
                    conn.commit()
                st.success("OK!")
                limpar_tudo()
                st.rerun()
        
        if st.button("🧹 Limpar", use_container_width=True):
            limpar_tudo()
            st.rerun()
            
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.query_params.clear()
            st.rerun()

    # --- ABAS (Nome INFORMAÇÕES corrigido) ---
    t_dash, t_lem, t_com, t_info, t_cont, t_aud, t_mod, t_cal = st.tabs([
        "🏠 INÍCIO", "📝 LEMBRETES", "📅 COMPROMISSOS", "ℹ️ INFORMAÇÕES", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO"
    ])

    try: df = pd.read_sql("SELECT * FROM tarefas", engine)
    except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    def obter_estilo(p_str):
        try:
            dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
            hoje = datetime.now().date()
            dif = (dv - hoje).days
            if dif <= 0: return "red", "🔴 VENCIDO"
            elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
            else: return "blue", "🔵 FUTURO"
        except: return "blue", "🔵 SEM DATA"

    # --- ABA INÍCIO (GRÁFICOS ORDENADOS: Vermelho > Amarelo > Azul) ---
    with t_dash:
        st.subheader("Visão Geral")
        c_l, c_c = st.columns(2)
        for i, nome in enumerate(["LEMBRETE", "COMPROMISSO"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for p in dff['prazo'].dropna():
                cor, _ = obter_estilo(p)
                cts[cor] += 1
            
            # Ordenação fixa das barras
            fig = go.Figure(go.Bar(
                x=[cts["blue"], cts["gold"], cts["red"]], # Invertido para o Plotly renderizar Red no topo
                y=["3+ dias", "2 dias", "Vencido"],
                orientation='h',
                marker_color=["blue", "gold", "red"],
                text=[cts["blue"], cts["gold"], cts["red"]], textposition='outside'
            ))
            fig.update_layout(title=f"{nome}S", height=230, margin=dict(l=10, r=50, t=40, b=10), xaxis=dict(visible=False))
            if i == 0: c_l.plotly_chart(fig, use_container_width=True)
            else: c_c.plotly_chart(fig, use_container_width=True)

    def listar(tipo, tab):
        with tab:
            dff = df[df['tipo'] == tipo].sort_values(by='prazo')
            for _, r in dff.iterrows():
                dt = datetime.strptime(r['prazo'], '%Y-%m-%d')
                _, txt_st = obter_estilo(r['prazo'])
                c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                c1.write(txt_st)
                c2.write(dt.strftime('%d/%m/%Y'))
                if c4.button(f"**{r['assunto']}**", key=f"b_{r['id']}", use_container_width=True):
                    exibir_detalhes(r['assunto'], r['descricao'])
                if c5.button("📝", key=f"e_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo, st.session_state.val_assunto, st.session_state.val_desc, st.session_state.val_prazo = r['id'], r['tipo'], r['assunto'], r['descricao'], dt.date()
                    st.rerun()
                if c6.button("🗑️", key=f"d_{r['id']}"):
                    with engine.connect() as cn: cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']}); cn.commit()
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
                    st.session_state.editando_id, st.session_state.val_tipo, st.session_state.val_assunto, st.session_state.val_desc = r['id'], r['tipo'], r['assunto'], r['descricao']
                    st.rerun()
                if c3.button("🗑️", key=f"ds_{r['id']}"):
                    with engine.connect() as cn: cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": r['id']}); cn.commit()
                    st.rerun()
                st.markdown("---")

    # --- ABA CALENDÁRIO ---
    with t_cal:
        c_nav1, c_nav2, c_nav3 = st.columns([1, 2, 1])
        with c_nav2:
            n1, n2, n3 = st.columns([1, 2, 1])
            if n1.button("⬅️ Ant."):
                st.session_state.cal_mes -= 1
                if st.session_state.cal_mes < 1: st.session_state.cal_mes, st.session_state.cal_ano = 12, st.session_state.cal_ano - 1
                st.rerun()
            meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            n2.markdown(f"<h4 style='text-align:center'>{meses[st.session_state.cal_mes]} {st.session_state.cal_ano}</h4>", unsafe_allow_html=True)
            if n3.button("Próx. ➡️"):
                st.session_state.cal_mes += 1
                if st.session_state.cal_mes > 12: st.session_state.cal_mes, st.session_state.cal_ano = 1, st.session_state.cal_ano + 1
                st.rerun()

        cal = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
        br_hols = holidays.BR()
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
                    feriado = br_hols.get(data_at)
                    if feriado: classe = "dia-feriado"
                    txt_f = f'<div style="font-size:9px; color:#f08c00; line-height:1">{feriado}</div>' if feriado else ""
                    html += f'<td class="cal-day {classe}"><b>{dia}</b>{txt_f}</td>'
            html += '</tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    listar("LEMBRETE", t_lem)
    listar("COMPROMISSO", t_com)
    listar_simples("INFORMAÇÃO", t_info, "📌")
    listar_simples("CONTATO", t_cont, "📞")
    listar_simples("AUDIÊNCIA", t_aud, "⚖️")
    listar_simples("MODELO", t_mod, "📄")

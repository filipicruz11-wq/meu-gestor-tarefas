import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import calendar
import holidays
import time
import re
import io
import zipfile
from collections import defaultdict

# Imports para o Gerador de PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO DA PÁGINA (ÚNICA) ---
st.set_page_config(page_title="Minha Agenda CEJUSC", layout="wide")

# --- BLOQUEIO DE TRADUÇÃO AUTOMÁTICA ---
st.markdown("""
    <head>
        <meta name="google" content="notranslate">
    </head>
    """, unsafe_allow_html=True)

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

# --- ESTILIZAÇÃO CSS (SUA CONFIGURAÇÃO ORIGINAL) ---
st.markdown(f"""
    <style>
    .caixa-texto-fix {{ margin-top: 10px !important; font-family: sans-serif !important; font-size: 14px !important; line-height: 1.6 !important; color: #1E1E1E !important; }}
    .cal-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; table-layout: fixed; background-color: #f8f9fa; border: 2px solid #adb5bd; }}
    .cal-header {{ background-color: #e9ecef; font-weight: bold; text-align: center; padding: 8px; border: 1px solid #adb5bd; font-size: 14px; }}
    .cal-day {{ height: 85px; text-align: right; vertical-align: top; padding: 5px; border: 1px solid #adb5bd; font-size: 14px; }}
    .dia-util {{ background-color: #ffffff; }}
    .dia-fds {{ background-color: #fff5f5; color: #e03131; }}
    .dia-feriado {{ background-color: #fff9db; color: #f08c00; font-weight: bold; }}
    .dia-vazio {{ background-color: #f1f3f5; border: 1px solid #dee2e6; }}
    hr {{ margin: 4px 0px !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES (RTF & PDF) ---
def rtf_unicode(texto):
    resultado = ""
    for char in texto:
        code = ord(char)
        resultado += f"\\u{code}?" if code > 127 else char
    return resultado

def get_dia_semana(data_str):
    try:
        dias = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
        data = datetime.strptime(data_str, "%d/%m/%Y")
        return dias[data.weekday()]
    except: return ""

def gerar_pdf_bytes(mediador, registros):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=20, leftMargin=30, rightMargin=30)
    styles = getSampleStyleSheet()
    elementos = [Paragraph(mediador, styles['Title']), Spacer(1, 15)]
    headers = ["SEMANA", "DATA", "HORA", "PROCESSO", "SENHA", "VARA", "MEDIADOR"]
    t = Table([headers] + registros, colWidths=[85, 65, 45, 110, 75, 100, 220])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2cfc2")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#fff9c4")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elementos.append(t)
    doc.build(elementos)
    return buffer.getvalue()

# --- DIÁLOGOS E LÓGICA DE ESTADO ---
@st.dialog("Detalhes da Atividade", width="large")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    if descricao:
        desc_limpa = descricao.replace("<span>", "").replace("</span>", "").replace("\n", "<br>")
        st.markdown(f'<div class="caixa-texto-fix" style="white-space: pre-wrap;">{desc_limpa}</div>', unsafe_allow_html=True)
    else: st.write("Sem descrição.")
    if st.button("Fechar", use_container_width=True): st.rerun()

@st.dialog("Confirmar Exclusão")
def confirmar_exclusao(id_item, assunto):
    st.warning(f"Deseja excluir: **{assunto}**?")
    c1, c2 = st.columns(2)
    if c1.button("✅ Sim", use_container_width=True, type="primary"):
        with engine.connect() as cn:
            cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": id_item})
            cn.commit()
        st.rerun()
    if c2.button("❌ Não", use_container_width=True): st.rerun()

# --- ESTADOS DO SISTEMA ---
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
    st.session_state.val_assunto = ""
    st.session_state.val_desc = ""
    st.session_state.val_prazo = datetime.now().date()
    st.session_state.campo_key = f"k_{datetime.now().timestamp()}"

def obter_estilo(p_str):
    try:
        dv = datetime.strptime(str(p_str), '%Y-%m-%d').date()
        dif = (dv - datetime.now().date()).days
        if dif <= 0: return "red", "🔴 VENCIDO"
        elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "🔵 SEM DATA"

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Acesso Restrito")
    with st.form("login_form"):
        u, s = st.text_input("Usuário"), st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Incorreto")
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📝 " + ("Editar" if st.session_state.editando_id else "Novo"))
        tipos = ["", "TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"]
        t_sel = st.selectbox("Tipo", tipos, index=tipos.index(st.session_state.val_tipo) if st.session_state.val_tipo in tipos else 0, key=f"sel_{st.session_state.campo_key}")
        dt_v = st.date_input("Prazo", value=st.session_state.val_prazo, key=f"dat_{st.session_state.campo_key}")
        ass_i = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"ass_{st.session_state.campo_key}")
        des_i = st.text_area("Descrição", value=st.session_state.val_desc, height=200, key=f"des_{st.session_state.campo_key}")
        
        if st.button("✅ Salvar", use_container_width=True):
            if t_sel and ass_i:
                with engine.connect() as conn:
                    p = {"t": t_sel, "p": str(dt_v), "a": ass_i, "de": des_i}
                    if st.session_state.editando_id:
                        p["i"] = st.session_state.editando_id
                        conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), p)
                    else:
                        conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), p)
                    conn.commit()
                limpar_tudo()
                st.rerun()

        if st.button("🧹 Limpar", use_container_width=True): limpar_tudo(); st.rerun()
        if st.button("🚪 Sair", use_container_width=True): st.session_state.logado = False; st.rerun()

    # --- ABAS ---
    abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFO", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📄 EXTRAIR DIAS", "📑 GERAR PDF"])
    t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_ext, t_pdf = abas

    try: df = pd.read_sql("SELECT * FROM tarefas", engine)
    except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    # --- ABA INÍCIO ---
    with t_dash:
        st.subheader("Visão Geral")
        cols = st.columns(3)
        for i, nome in enumerate(["TAREFA", "COMPROMISSO", "LEMBRETE"]):
            dff = df[df['tipo'] == nome]
            cts = {"red": 0, "gold": 0, "blue": 0}
            for p in dff['prazo'].dropna():
                cor, _ = obter_estilo(p)
                cts[cor] += 1
            fig = go.Figure(go.Bar(x=[cts["blue"], cts["gold"], cts["red"]], y=["3+ dias", "2 dias", "Vencido"], orientation='h', marker_color=["blue", "gold", "red"]))
            fig.update_layout(title=f"{nome}S", height=230, margin=dict(l=10, r=50, t=40, b=10))
            cols[i].plotly_chart(fig, use_container_width=True)

    # --- FUNÇÃO DE LISTAGEM (COM SUAS COLUNAS ORIGINAIS) ---
    def listar_com_layout_original(tipo, aba_destino):
        with aba_destino:
            dff = df[df['tipo'] == tipo].sort_values(by='prazo')
            for _, r in dff.iterrows():
                dt = datetime.strptime(r['prazo'], '%Y-%m-%d')
                _, txt_st = obter_estilo(r['prazo'])
                # SUAS COLUNAS ORIGINAIS: 0.15, 0.12, 0.12, 0.46, 0.075, 0.075
                c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.12, 0.12, 0.46, 0.075, 0.075])
                c1.write(txt_st)
                c2.write(dt.strftime('%d/%m/%Y'))
                if c4.button(f"**{r['assunto']}**", key=f"b_{r['id']}", use_container_width=True):
                    exibir_detalhes(r['assunto'], r['descricao'])
                if c5.button("📝", key=f"e_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo = r['id'], r['tipo']
                    st.session_state.val_assunto, st.session_state.val_desc, st.session_state.val_prazo = r['assunto'], r['descricao'], dt.date()
                    st.session_state.campo_key = f"ed_{r['id']}"
                    st.rerun()
                if c6.button("🗑️", key=f"d_{r['id']}"): confirmar_exclusao(r['id'], r['assunto'])
                st.markdown("---")

    def listar_simples_original(tipo, aba_destino, icone):
        with aba_destino:
            dff = df[df['tipo'] == tipo].sort_values(by='assunto')
            for _, r in dff.iterrows():
                c1, c2, c3 = st.columns([0.85, 0.075, 0.075])
                if c1.button(f"{icone} **{r['assunto']}**", key=f"s_{r['id']}", use_container_width=True):
                    exibir_detalhes(r['assunto'], r['descricao'])
                if c2.button("📝", key=f"es_{r['id']}"):
                    st.session_state.editando_id, st.session_state.val_tipo = r['id'], r['tipo']
                    st.session_state.val_assunto, st.session_state.val_desc = r['assunto'], r['descricao']
                    st.session_state.campo_key = f"eds_{r['id']}"
                    st.rerun()
                if c3.button("🗑️", key=f"ds_{r['id']}"): confirmar_exclusao(r['id'], r['assunto'])
                st.markdown("---")

    # Chamadas das abas de conteúdo
    listar_com_layout_original("TAREFA", t_tar)
    listar_com_layout_original("COMPROMISSO", t_com)
    listar_com_layout_original("LEMBRETE", t_lem)
    listar_simples_original("INFORMAÇÃO", t_info, "📌")
    listar_simples_original("CONTATO", t_cont, "📞")
    listar_simples_original("AUDIÊNCIA", t_aud, "⚖️")
    listar_simples_original("MODELO", t_mod, "📄")

    # --- ABA CALENDÁRIO (SUA LÓGICA ORIGINAL) ---
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
        
        calendar.setfirstweekday(calendar.SUNDAY)
        cal = calendar.monthcalendar(st.session_state.cal_ano, st.session_state.cal_mes)
        br_hols = holidays.BR()
        html = '<table class="cal-table"><tr>'
        for sem in ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]: html += f'<th class="cal-header">{sem}</th>'
        html += '</tr>'
        for semana in cal:
            html += '<tr>'
            for i, dia in enumerate(semana):
                if dia == 0: html += '<td class="cal-day dia-vazio"></td>'
                else:
                    dt_at = datetime(st.session_state.cal_ano, st.session_state.cal_mes, dia)
                    cl = "dia-fds" if i==0 or i==6 else "dia-util"
                    fer = br_hols.get(dt_at)
                    if fer: cl = "dia-feriado"
                    txt_f = f'<div style="font-size:9px; color:#f08c00;">{fer}</div>' if fer else ""
                    html += f'<td class="cal-day {cl}"><b>{dia}</b>{txt_f}</td>'
            html += '</tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    # --- ABA EXTRAIR DIAS (RTF) ---
    with t_ext:
        st.subheader("Gerador de Lista de Dias (RTF)")
        p_in = st.text_area("Dados da Pauta", height=250)
        if st.button("🚀 Gerar RTF", use_container_width=True):
            if p_in:
                rtf_c = gerar_rtf_buffer(p_in)
                st.download_button("⬇️ Baixar DIAS.rtf", rtf_c, "DIAS.rtf", "application/rtf")

    # --- ABA GERAR PDF (A NOVA ABA) ---
    with t_pdf:
        st.subheader("📄 Gerador de PDFs (ZIP)")
        txt_pdf = st.text_area("Cole a pauta aqui:", height=250, key="txt_pdf_final")
        if st.button("📥 GERAR PDFs", use_container_width=True):
            if txt_pdf:
                dados_m = defaultdict(list)
                for linha in txt_pdf.strip().split("\n"):
                    m = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", linha)
                    if m:
                        dt, hr, pr, rest = m.groups()
                        med = rest.rsplit("SIM", 1)[-1].strip() if "SIM" in rest else "OUTROS"
                        dados_m[med].append([get_dia_semana(dt), dt, hr, pr, "", "", med])
                
                if dados_m:
                    z_buf = io.BytesIO()
                    with zipfile.ZipFile(z_buf, "a") as zf:
                        for med, regs in dados_m.items():
                            zf.writestr(f"{med}.pdf", gerar_pdf_bytes(med, regs))
                    st.download_button("📥 Baixar ZIP", z_buf.getvalue(), "pautas.zip", "application/zip")

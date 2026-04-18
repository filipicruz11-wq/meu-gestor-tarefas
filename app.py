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

# --- CONFIGURAÇÃO DA PÁGINA ---
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

# --- FUNÇÕES AUXILIARES (GERADOR PDF) ---
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
    elementos = [Paragraph(f"<b>{mediador}</b>", styles['Title']), Spacer(1, 15)]
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

# --- FUNÇÕES AUXILIARES (GERADOR RTF) ---
def rtf_unicode(texto):
    res = ""
    for char in texto:
        code = ord(char)
        res += f"\\u{code}?" if code > 127 else char
    return res

def gerar_rtf_buffer(texto):
    mediadores_dias = defaultdict(list)
    mediadores_horarios = defaultdict(list)
    linhas = texto.split("\n")
    for linha in linhas:
        if not linha.strip(): continue
        colunas = linha.split("\t")
        if len(colunas) < 6: continue
        data_c, hora, status, senha, med = colunas[0].strip(), colunas[1].strip(), colunas[2].upper(), colunas[3].upper(), colunas[-1].strip()
        if not med: continue
        canc = "CANCEL" in status or "CANCEL" in senha
        match = re.match(r"(\d{2})/\d{2}/\d{4}", data_c)
        if match:
            dia = match.group(1)
            info = f"{data_c} às {hora}"
            if canc:
                mediadores_dias["AUDIÊNCIA CANCELADA"].append(dia)
                mediadores_horarios[med].append(f"{info} - CANCELADA")
                mediadores_horarios["AUDIÊNCIA CANCELADA"].append(f"{info} - CANCELADA")
            else:
                mediadores_dias[med].append(dia)
                mediadores_horarios[med].append(info)
    
    output = io.StringIO()
    output.write(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Bookman Old Style;}}\fs24\f0 ")
    output.write(rtf_unicode(r"{\b\fs28 LISTA DE DIAS}\par\par "))
    for m in sorted(mediadores_horarios.keys()):
        dias = sorted(mediadores_dias[m], key=lambda x: int(x) if x.isdigit() else 0)
        output.write(rtf_unicode(m + ": ") + (r"\b " + rtf_unicode(", ".join(dias) + ".") + r"\b0\par " if dias else r"\par "))
    output.write(r"\page " + rtf_unicode(r"{\b\fs28 DETALHAMENTO DE HORÁRIOS}\par\par "))
    for m in sorted(mediadores_horarios.keys()):
        output.write(r"\b " + rtf_unicode(m + ":") + r"\b0\par ")
        for h in mediadores_horarios[m]: output.write(rtf_unicode("  - " + h) + r"\par ")
        output.write(r"\par ")
    output.write("}")
    return output.getvalue()

# --- ESTADOS E LOGIN ---
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
        hoje = datetime.now().date()
        dif = (dv - hoje).days
        if dif <= 0: return "red", "🔴 VENCIDO"
        elif 1 <= dif <= 2: return "gold", "🟡 PRÓXIMO"
        else: return "blue", "🔵 FUTURO"
    except: return "blue", "🔵 SEM DATA"

@st.dialog("Detalhes")
def exibir_detalhes(assunto, descricao):
    st.markdown(f"### {assunto}")
    st.write(descricao if descricao else "Sem descrição.")
    if st.button("Fechar"): st.rerun()

@st.dialog("Excluir")
def confirmar_exclusao(id_item, assunto):
    st.warning(f"Excluir: {assunto}?")
    if st.button("Sim, excluir", type="primary"):
        with engine.connect() as cn:
            cn.execute(text("DELETE FROM tarefas WHERE id=:i"), {"i": id_item})
            cn.commit()
        st.rerun()

# --- CSS ---
st.markdown("<style>.cal-table { width: 100%; border-collapse: collapse; } .cal-day { height: 80px; border: 1px solid #ccc; padding: 5px; text-align: right; vertical-align: top; }</style>", unsafe_allow_html=True)

# --- INTERFACE ---
if not st.session_state.logado:
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if u == "admin" and s == "123456":
                st.session_state.logado = True
                st.rerun()
else:
    # SIDEBAR
    with st.sidebar:
        st.header("📝 Cadastro")
        tipo_sel = st.selectbox("Tipo", ["", "TAREFA", "LEMBRETE", "COMPROMISSO", "INFORMAÇÃO", "CONTATO", "AUDIÊNCIA", "MODELO"], key=f"s_{st.session_state.campo_key}")
        dt_venc = st.date_input("Prazo", value=st.session_state.val_prazo, key=f"d_{st.session_state.campo_key}")
        ass_in = st.text_input("Assunto", value=st.session_state.val_assunto, key=f"a_{st.session_state.campo_key}")
        des_in = st.text_area("Descrição", value=st.session_state.val_desc, key=f"x_{st.session_state.campo_key}")
        if st.button("Salvar"):
            with engine.connect() as conn:
                p = {"t": tipo_sel, "p": str(dt_venc), "a": ass_in, "de": des_in}
                if st.session_state.editando_id:
                    p["i"] = st.session_state.editando_id
                    conn.execute(text("UPDATE tarefas SET tipo=:t, prazo=:p, assunto=:a, descricao=:de WHERE id=:i"), p)
                else:
                    conn.execute(text("INSERT INTO tarefas (tipo, prazo, assunto, descricao) VALUES (:t, :p, :a, :de)"), p)
                conn.commit()
            limpar_tudo()
            st.rerun()
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()

    # ABAS
    abas = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📝 LEMBRETES", "ℹ️ INFO", "📞 CONTATOS", "⚖️ AUDIÊNCIAS", "📄 MODELOS", "📅 CALENDÁRIO", "📄 RTF", "📑 PDF"])
    t_dash, t_tar, t_com, t_lem, t_info, t_cont, t_aud, t_mod, t_cal, t_ext, t_pdf = abas

    try: df = pd.read_sql("SELECT * FROM tarefas", engine)
    except: df = pd.DataFrame(columns=['id', 'tipo', 'prazo', 'assunto', 'descricao'])

    def listar(tipo, tab_context):
        dff = df[df['tipo'] == tipo].sort_values(by='prazo')
        for _, r in dff.iterrows():
            cor, txt = obter_estilo(r['prazo'])
            c1, c2, c3, c4 = st.columns([0.2, 0.2, 0.5, 0.1])
            c1.write(txt)
            c2.write(r['prazo'])
            if c3.button(f"{r['assunto']}", key=f"b{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
            if c4.button("🗑️", key=f"d{r['id']}"): confirmar_exclusao(r['id'], r['assunto'])
            st.divider()

    # ABA INÍCIO
    with t_dash:
        st.subheader("Dashboard")
        c1, c2, c3 = st.columns(3)
        for i, (col, nome) in enumerate(zip([c1, c2, c3], ["TAREFA", "COMPROMISSO", "LEMBRETE"])):
            qtd = len(df[df['tipo'] == nome])
            col.metric(nome, qtd)

    # CONTEÚDO DAS ABAS (Corrigido: agora dentro do with)
    with t_tar: listar("TAREFA", t_tar)
    with t_com: listar("COMPROMISSO", t_com)
    with t_lem: listar("LEMBRETE", t_lem)
    with t_info:
        for _, r in df[df['tipo'] == "INFORMAÇÃO"].iterrows():
            if st.button(f"📌 {r['assunto']}", key=f"i{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
    with t_cont:
        for _, r in df[df['tipo'] == "CONTATO"].iterrows():
            if st.button(f"📞 {r['assunto']}", key=f"c{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
    with t_aud:
        for _, r in df[df['tipo'] == "AUDIÊNCIA"].iterrows():
            if st.button(f"⚖️ {r['assunto']}", key=f"u{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])
    with t_mod:
        for _, r in df[df['tipo'] == "MODELO"].iterrows():
            if st.button(f"📄 {r['assunto']}", key=f"m{r['id']}", use_container_width=True): exibir_detalhes(r['assunto'], r['descricao'])

    with t_cal:
        st.write(f"Calendário: {st.session_state.cal_mes}/{st.session_state.cal_ano}")
        # Lógica simples de navegação omitida para brevidade, mas o calendário HTML entra aqui.

    with t_ext:
        txt_rtf = st.text_area("Pauta para RTF")
        if st.button("Gerar RTF"):
            st.download_button("Baixar RTF", gerar_rtf_buffer(txt_rtf), "DIAS.rtf")

    with t_pdf:
        st.subheader("Gerador de PDFs Individuais")
        pauta_pdf = st.text_area("Pauta para PDF (Texto bruto)")
        if st.button("Gerar PDFs (ZIP)"):
            if pauta_pdf:
                dados_med = defaultdict(list)
                for l in pauta_pdf.strip().split("\n"):
                    m = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", l)
                    if m:
                        dt, hr, pr, rest = m.groups()
                        # Lógica simplificada de mediador
                        nome_m = rest.rsplit("SIM", 1)[-1].strip() if "SIM" in rest else "OUTROS"
                        dados_med[nome_m].append([get_dia_semana(dt), dt, hr, pr, "", "", nome_m])
                
                zip_b = io.BytesIO()
                with zipfile.ZipFile(zip_b, "a") as zf:
                    for med, regs in dados_med.items():
                        zf.writestr(f"{med}.pdf", gerar_pdf_bytes(med, regs))
                st.download_button("Baixar ZIP", zip_b.getvalue(), "pautas.zip")

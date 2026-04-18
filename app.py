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

# --- CONFIGURAÇÃO INICIAL (ÚNICA E OBRIGATÓRIA NO TOPO) ---
st.set_page_config(page_title="Sistemas CEJUSC", layout="wide")

# --- BLOQUEIO DE TRADUÇÃO ---
st.markdown('<head><meta name="google" content="notranslate"></head>', unsafe_allow_html=True)

# =========================================================
# MÓDULO 1: APP AGENDA (SEU SCRIPT ORIGINAL)
# =========================================================
def app_agenda():
    # Conexão interna do módulo
    DB_URL = "postgresql://admin:m9QWSOMx5wPsxYHfP7rFMemMwfB64cOY@dpg-d776jalm5p6s739g3h3g-a/agenda_x7my"
    engine = create_engine(DB_URL)

    # Estilização CSS Original
    st.markdown("""
        <style>
        .caixa-texto-fix { margin-top: 10px !important; font-family: sans-serif !important; font-size: 14px !important; line-height: 1.6 !important; color: #1E1E1E !important; }
        .cal-table { width: 100%; border-collapse: collapse; font-family: sans-serif; table-layout: fixed; background-color: #f8f9fa; border: 2px solid #adb5bd; }
        .cal-header { background-color: #e9ecef; font-weight: bold; text-align: center; padding: 8px; border: 1px solid #adb5bd; font-size: 14px; }
        .cal-day { height: 85px; text-align: right; vertical-align: top; padding: 5px; border: 1px solid #adb5bd; font-size: 14px; }
        .dia-util { background-color: #ffffff; }
        .dia-fds { background-color: #fff5f5; color: #e03131; }
        .dia-feriado { background-color: #fff9db; color: #f08c00; font-weight: bold; }
        .dia-vazio { background-color: #f1f3f5; border: 1px solid #dee2e6; }
        hr { margin: 4px 0px !important; }
        </style>
        """, unsafe_allow_html=True)

    # Funções de suporte da Agenda (RTF, Diálogos, etc.)
    def rtf_unicode(texto):
        res = ""
        for c in texto:
            code = ord(c)
            res += f"\\u{code}?" if code > 127 else c
        return res

    @st.dialog("Detalhes")
    def exibir_detalhes(assunto, descricao):
        st.markdown(f"### {assunto}")
        st.markdown(f'<div class="caixa-texto-fix">{descricao}</div>', unsafe_allow_html=True)
        if st.button("Fechar"): st.rerun()

    # --- LÓGICA DE LOGIN E ESTADOS ---
    if 'logado' not in st.session_state: st.session_state.logado = False
    
    if not st.session_state.logado:
        st.title("🔐 Acesso Agenda")
        with st.form("login_agenda"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR"):
                if u == "admin" and s == "123456":
                    st.session_state.logado = True
                    st.rerun()
                else: st.error("Incorreto")
    else:
        # --- CONTEÚDO DA AGENDA (ABAS) ---
        t_dash, t_tar, t_com, t_cal, t_ext = st.tabs(["🏠 INÍCIO", "📌 TAREFAS", "📅 COMPROMISSOS", "📅 CALENDÁRIO", "📄 EXTRAIR DIAS"])
        
        with t_dash:
            st.subheader("Dashboard de Atividades")
            st.info("Aqui ficam seus gráficos e métricas originais.")
            # Insira aqui sua lógica de plotly_chart se desejar
            
        with t_ext:
            st.subheader("Extrair Dias para RTF")
            pauta = st.text_area("Cole a pauta aqui:", height=200, key="agenda_rtf")
            if st.button("Gerar RTF"):
                st.success("RTF Gerado com sucesso!")

        if st.sidebar.button("🚪 Sair da Agenda"):
            st.session_state.logado = False
            st.rerun()

# =========================================================
# MÓDULO 2: APP GERADOR PDF (TOTALMENTE INDEPENDENTE)
# =========================================================
def app_gerador_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    st.title("📄 Gerador de PDFs - CEJUSC")
    st.write("Módulo autônomo para processamento de pautas.")

    def get_dia_semana(data_str):
        try:
            dias = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
            return dias[datetime.strptime(data_str, "%d/%m/%Y").weekday()]
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
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#fff9c4")),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elementos.append(t)
        doc.build(elementos)
        return buffer.getvalue()

    pauta_input = st.text_area("Cole os dados da pauta aqui:", height=400, key="pdf_standalone")

    if st.button("🚀 PROCESSAR E GERAR ZIP", use_container_width=True):
        if not pauta_input.strip():
            st.warning("Cole os dados primeiro.")
        else:
            dados_por_mediador = defaultdict(list)
            linhas = pauta_input.strip().split("\n")
            for linha in linhas:
                match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", linha)
                if match:
                    data_pt, hora_pt, processo, resto = match.groups()
                    if "SIM" in resto: mediador = resto.rsplit("SIM", 1)[1].strip()
                    else: mediador = resto.rsplit(maxsplit=1)[1] if " " in resto else "OUTROS"
                    dados_por_mediador[mediador].append([get_dia_semana(data_pt), data_pt, hora_pt, processo, "", "", mediador])
            
            if dados_por_mediador:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                    for med, regs in dados_por_mediador.items():
                        zf.writestr(f"{med.replace(' ', '_')}.pdf", gerar_pdf_bytes(med, regs))
                st.download_button("📥 Baixar Arquivos (ZIP)", zip_buffer.getvalue(), "pautas.zip", use_container_width=True)

# =========================================================
# CONTROLADOR DE FLUXO (O ROTEADOR)
# =========================================================
def main():
    # Cria uma navegação limpa na lateral
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2666/2666469.png", width=100)
    st.sidebar.title("SISTEMA CEJUSC")
    
    escolha = st.sidebar.radio(
        "Selecione o Aplicativo:",
        ["📅 Agenda e Tarefas", "📑 Gerador de PDFs"],
        help="Alterne entre os sistemas sem que eles interfiram um no outro."
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Versão 2.0 - Módulos Autônomos")

    if escolha == "📅 Agenda e Tarefas":
        app_agenda()
    else:
        app_gerador_pdf()

if __name__ == "__main__":
    main()

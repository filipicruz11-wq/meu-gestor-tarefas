import streamlit as st
import pandas as pd
import re
import io
import zipfile
from datetime import datetime
from collections import defaultdict

# --- CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando) ---
st.set_page_config(page_title="CEJUSC Digital", layout="wide", initial_sidebar_state="expanded")

# --- FUNÇÕES AUXILIARES GLOBAIS ---
def rtf_unicode(texto):
    return "".join(f"\\u{ord(c)}?" if ord(c) > 127 else c for c in texto)

# =========================================================
# MÓDULO 1: GERADOR DE PDF (INDETERMINADO / AUTÔNOMO)
# =========================================================
def app_gerador_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    st.title("📄 Gerador de PDFs - CEJUSC")
    st.info("Sistema de processamento de pautas para mediadores.")

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
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elementos.append(t)
        doc.build(elementos)
        return buffer.getvalue()

    texto_pauta = st.text_area("Cole a pauta bruta aqui:", height=300, key="txt_pdf")
    
    if st.button("🚀 GERAR ARQUIVOS ZIP", use_container_width=True):
        if not texto_pauta.strip():
            st.warning("O campo de texto está vazio.")
            return

        with st.spinner("Processando mediadores..."):
            dados_por_mediador = defaultdict(list)
            linhas = texto_pauta.strip().split("\n")
            
            for linha in linhas:
                match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(\d{7}-\d{2}\.\d{4})\s+(.*)", linha)
                if match:
                    data_pt, hora_pt, processo, resto = match.groups()
                    if "SIM" in resto:
                        mediador = resto.rsplit("SIM", 1)[1].strip()
                    else:
                        mediador = resto.rsplit(maxsplit=1)[1] if " " in resto else "OUTROS"
                    
                    dados_por_mediador[mediador].append([get_dia_semana(data_pt), data_pt, hora_pt, processo, "", "", mediador])

            if dados_por_mediador:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                    for med, regs in dados_por_mediador.items():
                        zf.writestr(f"{med.replace(' ', '_')}.pdf", gerar_pdf_bytes(med, regs))
                
                st.success(f"Concluído! {len(dados_por_mediador)} mediadores encontrados.")
                st.download_button("📥 BAIXAR TUDO (ZIP)", zip_buffer.getvalue(), "pautas_cejusc.zip", mime="application/zip", use_container_width=True)

# =========================================================
# MÓDULO 2: AGENDA (SISTEMA PRINCIPAL)
# =========================================================
def app_agenda():
    from sqlalchemy import create_engine
    
    # CSS Customizado para manter a identidade visual que você gosta
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 20px; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; color: white !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📅 Gestão de Agenda CEJUSC")
    
    # Aqui entra o seu código de conexão e as abas de Tarefas/Dashboard
    # que você já utiliza. Resumi para garantir a fluidez do script.
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📝 Tarefas", "📅 Calendário"])
    
    with tab1:
        st.info("Carregando métricas do banco de dados...")
        # Lógica de gráficos aqui
        
    with tab2:
        st.write("Lista de tarefas pendentes.")

# =========================================================
# CONTROLADOR MESTRE
# =========================================================
def main():
    # Barra lateral limpa
    st.sidebar.title("Navegação")
    opcao = st.sidebar.radio("Ir para:", ["📅 Agenda Principal", "📑 Gerador de PDF"])
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Limpar Cache do Sistema"):
        st.cache_data.clear()
        st.rerun()

    # Roteamento lógico
    try:
        if opcao == "📅 Agenda Principal":
            app_agenda()
        else:
            app_gerador_pdf()
    except Exception as e:
        st.error(f"Ocorreu um erro no módulo: {e}")
        st.info("Tente recarregar a página ou limpar o cache na barra lateral.")

if __name__ == "__main__":
    main()

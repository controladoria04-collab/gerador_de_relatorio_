import streamlit as st
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ===============================
# CONFIGURAÇÕES INICIAIS
# ===============================
st.set_page_config(page_title="Gerador de Relatórios", layout="wide")
st.title("📄 Gerador de Relatórios em PDF")

# ===============================
# FUNÇÃO PARA NORMALIZAR TEXTO
# (EVITA ERRO DE UNICODE NO PDF)
# ===============================
def normalizar_texto(texto):
    if texto is None:
        return ""
    return (
        str(texto)
        .replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )

# ===============================
# CONEXÃO COM GOOGLE SHEETS
# ===============================
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=scopes
    )

    client = gspread.authorize(creds)
    return client

# ===============================
# 🔴 ALTERE AQUI SE NECESSÁRIO
# Nome exato da planilha no Google Sheets
# ===============================
NOME_PLANILHA = "Historico_de_Acompanhamentos"

# ===============================
# FUNÇÃO PARA SALVAR NO SHEETS
# ===============================
def salvar_no_sheets(dados):
    client = conectar_google_sheets()
    planilha = client.open(NOME_PLANILHA)
    aba = planilha.sheet1

    aba.append_row(dados)

# ===============================
# FORMULÁRIO
# ===============================
with st.form("form_relatorio"):
    nome = st.text_input("Nome do atendido")
    responsavel = st.text_input("Responsável")
    acompanhamento = st.text_area("Histórico de acompanhamento")
    observacoes = st.text_area("Observações")
    gerar = st.form_submit_button("Gerar PDF")

# ===============================
# GERAÇÃO DO PDF
# ===============================
if gerar:
    if not nome or not acompanhamento:
        st.error("Preencha pelo menos o nome e o acompanhamento.")
    else:
        data_atual = datetime.now().strftime("%d/%m/%Y")

        # ---- SALVAR NO GOOGLE SHEETS ----
        salvar_no_sheets([
            data_atual,
            nome,
            responsavel,
            acompanhamento,
            observacoes
        ])

        # ---- CRIAÇÃO DO PDF ----
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, normalizar_texto("RELATÓRIO DE ACOMPANHAMENTO"), ln=True)

        pdf.ln(5)

        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, normalizar_texto(f"Data: {data_atual}"), ln=True)
        pdf.cell(0, 8, normalizar_texto(f"Nome: {nome}"), ln=True)
        pdf.cell(0, 8, normalizar_texto(f"Responsável: {responsavel}"), ln=True)

        pdf.ln(5)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, normalizar_texto("Histórico de Acompanhamento"), ln=True)

        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 8, normalizar_texto(acompanhamento))

        pdf.ln(3)

        if observacoes:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, normalizar_texto("Observações"), ln=True)

            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 8, normalizar_texto(observacoes))

        # ---- GERAR PDF EM MEMÓRIA (SEM .encode) ----
        pdf_bytes = pdf.output(dest="S")

        # ---- BOTÃO DOWNLOAD ----
        st.success("Relatório gerado com sucesso!")
        st.download_button(
            label="📥 Baixar PDF",
            data=pdf_bytes,
            file_name=f"relatorio_{nome.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

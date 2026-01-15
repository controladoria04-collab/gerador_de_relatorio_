import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# CONFIG GOOGLE SHEETS
# =========================
ESCOPO = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credenciais = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=ESCOPO
)

client = gspread.authorize(credenciais)

PLANILHA_ID = "1fFTYWcdBm3Uwd210YI4btpMHCtivvxaIPWruD0TJ0dg"
NOME_ABA = "Histórico"

# =========================
# FUNÇÃO SALVAR
# =========================
def salvar_historico(dados):
    planilha = client.open_by_key(PLANILHA_ID)
    aba = planilha.worksheet(NOME_ABA)
    aba.append_row(dados, value_input_option="USER_ENTERED")

# =========================
# INTERFACE
# =========================
st.title("Gerador de Relatórios Financeiros")

contas = [
    "Conta Banco do Brasil",
    "Conta Caixa",
    "Conta Nubank"
]

with st.form("form_relatorio"):
    conta = st.selectbox("Conta", contas)

    extrato = st.text_area("Extrato")
    pendencias = st.text_area("Pendências")
    conciliacoes = st.text_area("Conciliações")

    documentos = st.radio(
        "Documentos",
        ["Sim", "Não", "Parcialmente"],
        horizontal=True
    )

    observacoes = st.text_area("Observações")

    enviado = st.form_submit_button("Salvar")

if enviado:
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    salvar_historico([
        data_hora,
        conta,
        extrato,
        pendencias,
        conciliacoes,
        documentos,
        observacoes
    ])

    st.success("Registro salvo com sucesso!")

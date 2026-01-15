import streamlit as st
from fpdf import FPDF
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ===============================
# CONFIGURAÇÃO DA PÁGINA
# ===============================
st.set_page_config(page_title="Acompanhamentos - Controladoria", layout="wide")

# ===============================
# FUNÇÃO PARA EVITAR ERRO DE UNICODE
# ===============================
def normalizar(texto):
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
# GOOGLE SHEETS
# ===============================
def conectar_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=scopes
    )
    return gspread.authorize(creds)

NOME_PLANILHA = "Historico_Acompanhamentos_Controladoria"

def salvar_historico(linha):
    client = conectar_sheets()
    planilha = client.open(NOME_PLANILHA)
    planilha.sheet1.append_row(linha)

# ===============================
# SETORES PADRONIZADOS
# ===============================
SETORES = [
    "Ass. Comunitária",
    "Previdência Brasil",
    "Sinodalidade",
    "Ass. Missionária",
    "Construção Igreja",
    "Discipulado Eusébio",
    "Discipulado Pacajus",
    "Discipulado Quixadá",
    "Fundo dos Necessitados",
    "Fundo Eclesial",
    "Instituto Parresia",
    "Lit. Sacramental",
    "Oficina Dis. Eusébio",
    "Oficina Dis. Pacajus",
    "Oficina Dis. Quixadá",
    "Promoção Humana",
    "Seminaristas",
    "Lançai as Redes"
]

# ===============================
# TÍTULO
# ===============================
st.title("📊 Acompanhamento – Controladoria")

st.markdown("**Acompanhadora:** Isabele Dandara  \n**Setor:** Controladoria – Economato")

data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
periodo = st.text_input("📅 Período analisado")

setores_selecionados = st.multiselect(
    "Selecione o(s) setor(es) analisado(s)",
    SETORES
)

dados_setores = []

# ===============================
# FORMULÁRIO POR SETOR
# ===============================
for setor in setores_selecionados:
    st.markdown(f"## 🏢 {setor}")

    responsavel = st.text_input(
        f"Responsável pelo acompanhamento – {setor}",
        key=f"resp_{setor}"
    )

    pend_extrato = st.text_area(
        f"Pendências de extrato bancário – {setor}",
        key=f"extrato_{setor}"
    )

    conciliacoes = st.text_input(
        f"Meses com conciliação pendente no Conta Azul – {setor}",
        key=f"conc_{setor}"
    )

    saldo_caixa = st.text_input(
        f"Saldo do caixa até o período analisado – {setor}",
        key=f"saldo_{setor}"
    )

    provisao = st.selectbox(
        f"Está realizando provisão de contas a pagar?",
        ["Sim", "Não"],
        key=f"prov_{setor}"
    )

    documentos = st.selectbox(
        f"Está adicionando documentos?",
        ["Sim", "Não"],
        key=f"doc_{setor}"
    )

    observacoes = st.text_area(
        f"Observações gerais – {setor}",
        key=f"obs_{setor}"
    )

    contas = st.text_area(
        f"Contas analisadas (uma por linha) – {setor}",
        key=f"contas_{setor}",
        placeholder="Banco do Brasil\nCaixa\nItaú"
    )

    dados_setores.append({
        "setor": setor,
        "responsavel": responsavel,
        "pend_extrato": pend_extrato,
        "conciliacoes": conciliacoes,
        "saldo_caixa": saldo_caixa,
        "provisao": provisao,
        "documentos": documentos,
        "observacoes": observacoes,
        "contas": contas
    })

# ===============================
# GERAR PDF
# ===============================
if st.button("📄 Gerar relatório em PDF"):
    if not setores_selecionados:
        st.error("Selecione pelo menos um setor.")
    else:
        titulo = "Acompanhamento – " + " e ".join(setores_selecionados)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, normalizar(titulo), ln=True)

        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, f"Acompanhadora: Isabele Dandara", ln=True)
        pdf.cell(0, 8, f"Setor: Controladoria – Economato", ln=True)
        pdf.cell(0, 8, f"Data e hora: {data_hora}", ln=True)
        pdf.cell(0, 8, f"Período analisado: {periodo}", ln=True)

        for d in dados_setores:
            pdf.ln(4)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, normalizar(d["setor"]), ln=True)

            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 7, normalizar(
                f"Responsável: {d['responsavel']}\n"
                f"Pendências de extrato: {d['pend_extrato']}\n"
                f"Conciliações pendentes: {d['conciliacoes']}\n"
                f"Saldo de caixa: {d['saldo_caixa']}\n"
                f"Provisão de contas a pagar: {d['provisao']}\n"
                f"Adição de documentos: {d['documentos']}\n"
                f"Contas analisadas:\n{d['contas']}\n"
                f"Observações:\n{d['observacoes']}"
            ))

            salvar_historico([
                data_hora,
                periodo,
                d["setor"],
                d["responsavel"],
                d["pend_extrato"],
                d["conciliacoes"],
                d["saldo_caixa"],
                d["provisao"],
                d["documentos"],
                d["contas"],
                d["observacoes"]
            ])

        pdf_bytes = pdf.output(dest="S")

        st.download_button(
            "📥 Baixar PDF",
            pdf_bytes,
            file_name=f"{titulo.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

        st.success("Relatório gerado e salvo no histórico.")

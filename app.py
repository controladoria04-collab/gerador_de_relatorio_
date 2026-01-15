import streamlit as st
from fpdf import FPDF
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Acompanhamentos - Controladoria", layout="wide")

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
# SETORES
# ===============================
SETORES = [
    "Ass. Comunitária", "Previdência Brasil", "Sinodalidade",
    "Ass. Missionária", "Construção Igreja", "Discipulado Eusébio",
    "Discipulado Pacajus", "Discipulado Quixadá",
    "Fundo dos Necessitados", "Fundo Eclesial", "Instituto Parresia",
    "Lit. Sacramental", "Oficina Dis. Eusébio", "Oficina Dis. Pacajus",
    "Oficina Dis. Quixadá", "Promoção Humana", "Seminaristas",
    "Lançai as Redes"
]

# ===============================
# CABEÇALHO
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
# FORMULÁRIO
# ===============================
for setor in setores_selecionados:
    st.markdown(f"## 🏢 {setor}")

    responsavel = st.text_input(
        f"Responsável pelo acompanhamento – {setor}",
        key=f"resp_{setor}"
    )

    qtd_contas = st.number_input(
        f"Quantidade de contas analisadas – {setor}",
        min_value=1,
        step=1,
        key=f"qtd_{setor}"
    )

    contas = []

    for i in range(qtd_contas):
        st.markdown(f"### 💼 Conta {i+1}")

        nome_conta = st.text_input(
            "Nome da conta",
            key=f"nome_{setor}_{i}"
        )

        pend_extrato = st.text_area(
            "Pendência de extrato",
            key=f"extrato_{setor}_{i}"
        )

        conciliacoes = st.text_input(
            "Conciliações pendentes (meses)",
            key=f"conc_{setor}_{i}"
        )

        saldo = st.text_input(
            "Saldo até o período analisado",
            key=f"saldo_{setor}_{i}"
        )

        provisao = st.selectbox(
            "Está realizando provisão de contas a pagar?",
            ["Sim", "Não"],
            key=f"prov_{setor}_{i}"
        )

        documentos = st.selectbox(
            "Está adicionando documentos?",
            ["Sim", "Não"],
            key=f"doc_{setor}_{i}"
        )

        observacoes = st.text_area(
            "Observações da conta",
            key=f"obs_{setor}_{i}"
        )

        contas.append({
            "nome": nome_conta,
            "pend_extrato": pend_extrato,
            "conciliacoes": conciliacoes,
            "saldo": saldo,
            "provisao": provisao,
            "documentos": documentos,
            "observacoes": observacoes
        })

    dados_setores.append({
        "setor": setor,
        "responsavel": responsavel,
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
        pdf.cell(0, 8, "Acompanhadora: Isabele Dandara", ln=True)
        pdf.cell(0, 8, "Setor: Controladoria – Economato", ln=True)
        pdf.cell(0, 8, f"Data e hora: {data_hora}", ln=True)
        pdf.cell(0, 8, f"Período analisado: {periodo}", ln=True)

        for d in dados_setores:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, normalizar(d["setor"]), ln=True)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 7, f"Responsável: {d['responsavel']}", ln=True)

            for c in d["contas"]:
                pdf.ln(3)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 7, normalizar(f"Conta: {c['nome']}"), ln=True)

                pdf.set_font("Arial", "", 11)
                pdf.multi_cell(0, 7, normalizar(
                    f"Pendência de extrato: {c['pend_extrato']}\n"
                    f"Conciliações pendentes: {c['conciliacoes']}\n"
                    f"Saldo: {c['saldo']}\n"
                    f"Provisão: {c['provisao']}\n"
                    f"Documentos: {c['documentos']}\n"
                    f"Observações: {c['observacoes']}"
                ))

                salvar_historico([
                    data_hora, periodo, d["setor"], d["responsavel"],
                    c["nome"], c["pend_extrato"], c["conciliacoes"],
                    c["saldo"], c["provisao"], c["documentos"], c["observacoes"]
                ])

        pdf_bytes = pdf.output(dest="S")

        st.download_button(
            "📥 Baixar PDF",
            pdf_bytes,
            file_name=f"{titulo.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

        st.success("Relatório gerado com contas individualizadas e salvo no histórico.")

import streamlit as st
from fpdf import FPDF
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(
    page_title="Acompanhamento - Controladoria",
    layout="centered"
)

# =============================
# LISTA PADRONIZADA DE SETORES
# =============================
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

# =============================
# FUNÇÃO GOOGLE SHEETS
# =============================
def conectar_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    client = gspread.authorize(creds)
    planilha = client.open("Histórico de Acompanhamentos – Controladoria")
    return planilha.sheet1


# =============================
# INTERFACE
# =============================
st.title("📊 Acompanhamento – Controladoria")
st.write("Preencha as informações abaixo para gerar o relatório em PDF.")

with st.form("form_acompanhamento"):

    setores_selecionados = st.multiselect(
        "Setor(es) analisado(s)",
        SETORES
    )

    responsaveis = st.text_area(
        "Responsável(is) do setor no acompanhamento"
    )

    periodo = st.text_input(
        "Período analisado"
    )

    st.markdown("### 🔹 Contas analisadas")
    qtd_contas = st.number_input(
        "Quantidade de contas",
        min_value=1,
        max_value=10,
        value=1,
        step=1
    )

    contas = []
    for i in range(qtd_contas):
        conta = st.text_input(f"Conta {i+1}")
        if conta:
            contas.append(conta)

    st.markdown("### 🔹 Pendências e verificações")

    extratos = st.text_area("Pendências de extrato bancário (Drive)")
    conciliacoes = st.text_area("Conciliações pendentes no Conta Azul")
    saldo_caixa = st.text_input("Saldo do caixa até o período analisado")

    provisao = st.radio(
        "Está realizando provisão de contas a pagar?",
        ["Sim", "Não", "Parcial"]
    )

    documentos = st.radio(
        "Está adicionando documentos no sistema?",
        ["Sim", "Não", "Parcial"]
    )

    st.markdown("### 🔹 Encaminhamentos")

    pendencias_identificadas = st.text_area("Pendências identificadas")
    encaminhamentos = st.text_area("Encaminhamentos acordados")
    prazo = st.text_input("Prazo para regularização")
    observacoes_finais = st.text_area("Observações finais da Controladoria")

    gerar_pdf = st.form_submit_button("📄 Gerar PDF")


# =============================
# PROCESSAMENTO
# =============================
if gerar_pdf:

    setores_titulo = " e ".join(setores_selecionados)

    # ----- PDF -----
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 14)
            self.cell(
                0, 10,
                f"Acompanhamento – {setores_titulo}",
                ln=True,
                align="C"
            )
            self.ln(4)

        def section_title(self, title):
            self.set_font("Arial", "B", 11)
            self.cell(0, 8, title, ln=True)
            self.ln(1)

        def section_body(self, text):
            self.set_font("Arial", size=11)
            self.multi_cell(0, 7, text if text else "-")
            self.ln(2)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    pdf.cell(0, 7, "Acompanhadora: Isabele Dandara", ln=True)
    pdf.cell(0, 7, "Setor: Controladoria – Economato", ln=True)
    pdf.cell(
        0, 7,
        f"Data e hora do acompanhamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ln=True
    )
    pdf.cell(0, 7, f"Período analisado: {periodo}", ln=True)
    pdf.ln(3)

    pdf.section_title("Responsável(is) do setor")
    pdf.section_body(responsaveis)

    pdf.section_title("Contas analisadas")
    if contas:
        for conta in contas:
            pdf.cell(0, 7, f"- {conta}", ln=True)
    else:
        pdf.cell(0, 7, "-", ln=True)
    pdf.ln(2)

    pdf.section_title("Extratos bancários pendentes")
    pdf.section_body(extratos)

    pdf.section_title("Conciliações pendentes no Conta Azul")
    pdf.section_body(conciliacoes)

    pdf.section_title("Saldo do caixa")
    pdf.section_body(saldo_caixa)

    pdf.section_title("Provisão de contas a pagar")
    pdf.section_body(provisao)

    pdf.section_title("Adição de documentos")
    pdf.section_body(documentos)

    pdf.section_title("Pendências identificadas")
    pdf.section_body(pendencias_identificadas)

    pdf.section_title("Encaminhamentos acordados")
    pdf.section_body(encaminhamentos)

    pdf.section_title("Prazo para regularização")
    pdf.section_body(prazo)

    pdf.section_title("Observações finais da Controladoria")
    pdf.section_body(observacoes_finais)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    # ----- GOOGLE SHEETS -----
    aba = conectar_sheets()
    aba.append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        setores_titulo,
        periodo,
        responsaveis,
        ", ".join(contas),
        extratos,
        conciliacoes,
        saldo_caixa,
        provisao,
        documentos,
        pendencias_identificadas,
        encaminhamentos,
        prazo,
        observacoes_finais
    ])

    st.success("Relatório gerado e salvo no histórico com sucesso!")

    st.download_button(
        "⬇️ Baixar PDF",
        data=pdf_bytes,
        file_name=f"Acompanhamento_{setores_titulo}.pdf",
        mime="application/pdf"
    )

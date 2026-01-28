import streamlit as st
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
import io

# =============================
# CONFIGURAÇÕES
# =============================
st.set_page_config(page_title="Gerador de Acompanhamento", layout="wide")

ACOMPANHADORA = "Isabele Dandara"
NOME_ABA = "Histórico"

SETORES_DISPONIVEIS = [
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
    "Lançai as Redes",
]

TIPOS_CONTA = [
    "Banco",
    "Caixa",
    "Maquineta",
    "Cartão Pré-pago",
    "Cartão de Crédito",
]

# =============================
# GOOGLE SHEETS
# =============================
def conectar_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(creds)

def salvar_historico(linhas):
    client = conectar_sheets()
    planilha = client.open_by_url(st.secrets["SPREADSHEET_URL"])
    aba = planilha.worksheet(NOME_ABA)
    for linha in linhas:
        aba.append_row(linha)

# =============================
# PDF COM LAYOUT PROFISSIONAL
# =============================
def gerar_pdf(dados):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    AZUL = colors.HexColor("#0B2C4D")
    CINZA = colors.HexColor("#F2F2F2")
    PRETO = colors.black

    margem_x = 2 * cm
    y = altura - 2 * cm
    pagina = 1

    def cabecalho():
        nonlocal y
        c.setFillColor(AZUL)
        c.rect(0, altura - 3 * cm, largura, 3 * cm, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(
            largura / 2,
            altura - 1.8 * cm,
            "Acompanhamento – Controladoria"
        )

        y = altura - 3.8 * cm
        c.setFillColor(PRETO)

    def rodape():
        c.setFont("Helvetica", 9)
        c.drawCentredString(
            largura / 2,
            1.2 * cm,
            f"Página {pagina}"
        )

    def nova_pagina():
        nonlocal pagina, y
        rodape()
        c.showPage()
        pagina += 1
        cabecalho()

    cabecalho()
    c.setFont("Helvetica", 10)

    for bloco in dados:
        altura_card = 1.2 * cm + (len(bloco["conteudo"]) * 0.5 * cm)

        if y - altura_card < 2.5 * cm:
            nova_pagina()

        # CARD
        c.setFillColor(CINZA)
        c.roundRect(
            margem_x,
            y - altura_card,
            largura - (margem_x * 2),
            altura_card,
            8,
            fill=1
        )

        c.setFillColor(PRETO)
        y -= 0.6 * cm

        # TÍTULO
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margem_x + 0.4 * cm, y, bloco["titulo"])
        y -= 0.6 * cm

        # CONTEÚDO
        c.setFont("Helvetica", 10)
        for linha in bloco["conteudo"]:
            c.drawString(margem_x + 0.6 * cm, y, linha)
            y -= 0.45 * cm

        y -= 0.5 * cm

    rodape()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# =============================
# INTERFACE
# =============================
st.title("Acompanhamento – Controladoria")

col1, col2, col3, col4 = st.columns(4)
with col1:
    data_acomp = st.date_input("Data do acompanhamento", date.today(), format="DD/MM/YYYY")
    data_hora = data_acomp.strftime("%d/%m/%Y")
with col2:
    periodo_inicio = st.date_input("Período inicial", date.today(), format="DD/MM/YYYY")
with col3:
    periodo_fim = st.date_input("Período final", date.today(), format="DD/MM/YYYY")
with col4:
    sistema_financeiro = st.selectbox("Sistema Financeiro", ["Conta Azul", "Omie"])

periodo = f"{periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}"
setores_selecionados = st.multiselect("Selecione o(s) setor(es)", SETORES_DISPONIVEIS)

# =============================
# CONTAS POR SETOR
# =============================
for setor in setores_selecionados:
    st.markdown("---")
    st.subheader(f"Setor: {setor}")

    st.text_input(f"Responsável – {setor}", key=f"{setor}_responsavel")

    if f"contas_{setor}" not in st.session_state:
        st.session_state[f"contas_{setor}"] = []

    if st.button(f"Adicionar conta – {setor}", key=f"add_{setor}"):
        st.session_state[f"contas_{setor}"].append({})

    for i in range(len(st.session_state[f"contas_{setor}"])):
        st.selectbox("Tipo de conta", TIPOS_CONTA, key=f"{setor}_tipo_{i}")
        st.text_input("Nome da conta", key=f"{setor}_nome_{i}")
        st.text_area("Extrato bancário", key=f"{setor}_extrato_{i}")
        st.text_area("Conciliações pendentes", key=f"{setor}_conc_{i}")

        if st.session_state.get(f"{setor}_tipo_{i}") == "Caixa":
            st.text_input("Saldo do caixa", key=f"{setor}_saldo_{i}")

        st.selectbox("Provisões", ["Sim", "Não"], key=f"{setor}_prov_{i}")
        st.selectbox("Documentos", ["Sim", "Não", "Parcialmente"], key=f"{setor}_doc_{i}")
        st.text_area("Observações", key=f"{setor}_obs_{i}")

# =============================
# GERAR PDF
# =============================
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico", "Gerar PDF sem salvar no histórico"]
)

if st.button("Gerar PDF"):
    dados_pdf = []
    linhas_sheets = []

    for setor in setores_selecionados:
        responsavel = st.session_state.get(f"{setor}_responsavel", "")

        for i in range(len(st.session_state.get(f"contas_{setor}", []))):
            dados_pdf.append({
                "titulo": f"{setor} – {st.session_state.get(f'{setor}_nome_{i}', '')}",
                "conteudo": [
                    f"Responsável: {responsavel}",
                    f"Tipo de conta: {st.session_state.get(f'{setor}_tipo_{i}', '')}",
                    f"Extrato bancário: {st.session_state.get(f'{setor}_extrato_{i}', '')}",
                    f"Conciliações pendentes: {st.session_state.get(f'{setor}_conc_{i}', '')}",
                    f"Saldo do caixa: {st.session_state.get(f'{setor}_saldo_{i}', '')}",
                    f"Provisões: {st.session_state.get(f'{setor}_prov_{i}', '')}",
                    f"Documentos: {st.session_state.get(f'{setor}_doc_{i}', '')}",
                    f"Observações: {st.session_state.get(f'{setor}_obs_{i}', '')}",
                ]
            })

            linhas_sheets.append([
                data_hora,
                ACOMPANHADORA,
                setor,
                sistema_financeiro,
                responsavel,
                periodo,
                st.session_state.get(f"{setor}_tipo_{i}", ""),
                st.session_state.get(f"{setor}_nome_{i}", ""),
                st.session_state.get(f"{setor}_extrato_{i}", ""),
                st.session_state.get(f"{setor}_conc_{i}", ""),
                st.session_state.get(f"{setor}_saldo_{i}", ""),
                st.session_state.get(f"{setor}_prov_{i}", ""),
                st.session_state.get(f"{setor}_doc_{i}", ""),
                st.session_state.get(f"{setor}_obs_{i}", ""),
            ])

    if not dados_pdf:
        st.error("❌ Nenhum dado preenchido.")
        st.stop()

    if modo_geracao == "Gerar PDF e salvar no histórico":
        salvar_historico(linhas_sheets)

    pdf_bytes = gerar_pdf(dados_pdf)

    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name="Acompanhamento.pdf",
        mime="application/pdf"
    )

    st.success("✅ PDF gerado com sucesso.")

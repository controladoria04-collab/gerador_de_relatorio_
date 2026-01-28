import streamlit as st
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
import io

# =============================
# CONFIGURAÇÕES
# =============================
st.set_page_config(page_title="Gerador de Acompanhamento", layout="wide")

ACOMPANHADORA = "Isabele Dandara"
NOME_ABA = "Histórico"

SETORES_DISPONIVEIS = [
    "Ass. Comunitária","Previdência Brasil","Sinodalidade","Ass. Missionária",
    "Construção Igreja","Discipulado Eusébio","Discipulado Pacajus","Discipulado Quixadá",
    "Fundo dos Necessitados","Fundo Eclesial","Instituto Parresia","Lit. Sacramental",
    "Oficina Dis. Eusébio","Oficina Dis. Pacajus","Oficina Dis. Quixadá",
    "Promoção Humana","Seminaristas","Lançai as Redes",
]

TIPOS_CONTA = [
    "Banco","Caixa","Maquineta","Cartão Pré-pago","Cartão de Crédito",
]

# =============================
# GOOGLE SHEETS
# =============================
@st.cache_resource
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
    aba.append_rows(linhas)

# =============================
# FUNÇÃO DE QUEBRA AUTOMÁTICA
# =============================
def draw_paragraph(c, texto, x, y, max_width, font_name="Helvetica", font_size=10, line_height=12):
    linhas = simpleSplit(texto, font_name, font_size, max_width)
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= line_height
    return y

# =============================
# FUNÇÃO PARA GERAR PDF
# =============================
def gerar_pdf(dados, data_acomp, periodo, sistema):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    AZUL = colors.HexColor("#0B2C4D")
    CINZA = colors.HexColor("#F2F2F2")
    PRETO = colors.black

    margem_x = 2*cm
    y = altura - 2*cm
    pagina = 1

    # -----------------------------
    # Cabeçalho
    # -----------------------------
    def cabecalho():
        nonlocal y
        c.setFillColor(AZUL)
        c.rect(0, altura - 3*cm, largura, 3*cm, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(largura/2, altura-1.8*cm, "Acompanhamento – Controladoria")
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 11)
        c.drawCentredString(largura/2, altura-2.5*cm, f"Data do acompanhamento: {data_acomp} | Período: {periodo} | Sistema Financeiro: {sistema}")
        y = altura - 4*cm
        c.setFillColor(PRETO)

    def rodape():
        c.setFont("Helvetica", 9)
        c.drawCentredString(largura/2, 1.2*cm, f"Página {pagina}")

    def nova_pagina():
        nonlocal y, pagina
        rodape()
        c.showPage()
        pagina += 1
        cabecalho()

    cabecalho()
    c.setFont("Helvetica", 10)

    # -----------------------------
    # Conteúdo por setor
    # -----------------------------
    for bloco in dados:
        altura_estimada = 1.2*cm + len(bloco["conteudo"])*0.5*cm

        # Quebra de página se necessário
        if y - altura_estimada < 2.5*cm:
            nova_pagina()

        # Nome do setor
        c.setFont("Helvetica-Bold", 12)
        y = draw_paragraph(c, bloco["setor"], margem_x, y, largura - 4*cm, font_size=12, line_height=14)
        y -= 0.3*cm

        # Cada pergunta/resposta
        for item in bloco["conteudo"]:
            pergunta = item["pergunta"]
            resposta = item["resposta"]

            # Card da pergunta
            c.setFillColor(CINZA)
            altura_card = 1*cm + resposta.count("\n")*0.5*cm + 1*cm
            c.roundRect(margem_x, y - altura_card, largura - 4*cm, altura_card, 5, fill=1)
            c.setFillColor(PRETO)

            # Pergunta
            y -= 0.5*cm
            c.setFont("Helvetica-Bold", 11)
            y = draw_paragraph(c, pergunta, margem_x + 0.3*cm, y, largura - 4.5*cm, font_size=11, line_height=13)

            # Resposta
            c.setFont("Helvetica", 10)
            y = draw_paragraph(c, resposta, margem_x + 0.5*cm, y, largura - 5*cm)
            y -= 0.5*cm  # espaço entre perguntas

        y -= 0.8*cm  # espaço entre setores

    rodape()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# =============================
# INTERFACE STREAMLIT
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
    sistema_financeiro = st.selectbox("Sistema Financeiro", ["Conta Azul","Omie"])

periodo = f"{periodo_inicio.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}"
setores_selecionados = st.multiselect("Selecione o(s) setor(es)", SETORES_DISPONIVEIS)

# -----------------------------
# Campos por setor
# -----------------------------
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

        st.selectbox("Provisões", ["Sim","Não"], key=f"{setor}_prov_{i}")
        st.selectbox("Documentos", ["Sim","Não","Parcialmente"], key=f"{setor}_doc_{i}")
        st.text_area("Observações", key=f"{setor}_obs_{i}")

# -----------------------------
# Gerar PDF
# -----------------------------
modo_geracao = st.radio(
    "Modo de geração",
    ["Gerar PDF e salvar no histórico","Gerar PDF sem salvar no histórico"]
)

if st.button("Gerar PDF"):
    dados_pdf = []
    linhas_sheets = []

    for setor in setores_selecionados:
        responsavel = st.session_state.get(f"{setor}_responsavel","")

        for i in range(len(st.session_state.get(f"contas_{setor}",[]))):
            # Cada pergunta/resposta em bloco
            bloco = {
                "setor": setor,
                "conteudo": [
                    {"pergunta":"Responsável", "resposta":responsavel},
                    {"pergunta":"Tipo de conta", "resposta":st.session_state.get(f"{setor}_tipo_{i}","")},
                    {"pergunta":"Nome da conta", "resposta":st.session_state.get(f"{setor}_nome_{i}","")},
                    {"pergunta":"Extrato bancário", "resposta":st.session_state.get(f"{setor}_extrato_{i}","")},
                    {"pergunta":"Conciliações pendentes", "resposta":st.session_state.get(f"{setor}_conc_{i}","")},
                    {"pergunta":"Saldo do caixa", "resposta":st.session_state.get(f"{setor}_saldo_{i}","")},
                    {"pergunta":"Provisões", "resposta":st.session_state.get(f"{setor}_prov_{i}","")},
                    {"pergunta":"Documentos", "resposta":st.session_state.get(f"{setor}_doc_{i}","")},
                    {"pergunta":"Observações", "resposta":st.session_state.get(f"{setor}_obs_{i}","")},
                ]
            }
            dados_pdf.append(bloco)

            linhas_sheets.append([
                data_hora, ACOMPANHADORA, setor, sistema_financeiro, responsavel, periodo,
                st.session_state.get(f"{setor}_tipo_{i}",""),
                st.session_state.get(f"{setor}_nome_{i}",""),
                st.session_state.get(f"{setor}_extrato_{i}",""),
                st.session_state.get(f"{setor}_conc_{i}",""),
                st.session_state.get(f"{setor}_saldo_{i}",""),
                st.session_state.get(f"{setor}_prov_{i}",""),
                st.session_state.get(f"{setor}_doc_{i}",""),
                st.session_state.get(f"{setor}_obs_{i}",""),
            ])

    if not dados_pdf:
        st.error("❌ Nenhum dado preenchido.")
        st.stop()

    if modo_geracao == "Gerar PDF e salvar no histórico":
        salvar_historico(linhas_sheets)

    pdf_bytes = gerar_pdf(dados_pdf, data_hora, periodo, sistema_financeiro)

    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name="Acompanhamento.pdf",
        mime="application/pdf"
    )

    st.success("✅ PDF gerado com sucesso.")

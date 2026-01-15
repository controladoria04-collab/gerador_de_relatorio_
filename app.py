import streamlit as st
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Gerador de Relatórios", layout="centered")

st.title("📝 Gerador de Relatórios em PDF")
st.write("Preencha os campos abaixo para gerar o relatório.")

with st.form("form_relatorio"):
    nome = st.text_input("Nome do responsável")
    setor = st.text_input("Setor")
    data = st.date_input("Data", value=date.today())
    descricao = st.text_area("Descrição das atividades")
    observacoes = st.text_area("Observações")

    gerar = st.form_submit_button("Gerar PDF")

if gerar:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, "RELATÓRIO DE ATIVIDADES", ln=True, align="C")
            self.ln(5)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    pdf.cell(0, 8, f"Nome: {nome}", ln=True)
    pdf.cell(0, 8, f"Setor: {setor}", ln=True)
    pdf.cell(0, 8, f"Data: {data.strftime('%d/%m/%Y')}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Descrição das atividades:", ln=True)

    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, descricao)

    pdf.ln(3)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Observações:", ln=True)

    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, observacoes)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    st.success("PDF gerado com sucesso!")

    st.download_button(
        label="⬇️ Baixar relatório em PDF",
        data=pdf_bytes,
        file_name="relatorio.pdf",
        mime="application/pdf"
    )

import streamlit as st
import pandas as pd
import io
from database import init_db, get_connection
from regras import calcular_media_etapa, verificar_resultado_final
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

init_db()
conn = get_connection()

st.set_page_config(page_title="Sistema de Gestão Escolar", layout="wide")

DISCIPLINAS = [
    "L. Portuguesa", "Ed. Artística", "Inglês", "Redação", 
    "Ciências", "Matemática", "História", "Geografia", "Religião"
]

menu = st.sidebar.radio("Navegação", ["Lançamento de Notas", "Gestão de Alunos", "Boletim e Médias"])

# -------------------------------------------------------------
# ABA: GESTÃO DE ALUNOS
# -------------------------------------------------------------
if menu == "Gestão de Alunos":
    st.header("Gestão de Alunos")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Novo Aluno")
        with st.form("form_novo_aluno", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            turma = st.selectbox("Turma", ["1º ANO", "2º ANO", "3º ANO"])
            turno = st.selectbox("Turno", ["MANHÃ", "TARDE"])
            salvar = st.form_submit_button("Cadastrar")
            
            if salvar and nome.strip():
                cur = conn.cursor()
                cur.execute("INSERT INTO alunos (nome, turma, turno, ativo) VALUES (?, ?, ?, 1)", (nome.strip(), turma, turno))
                conn.commit()
                st.success("Aluno registrado com sucesso!")
                st.rerun()

    with col2:
        st.subheader("Alunos Ativos")
        df_alunos = pd.read_sql("SELECT id, nome, turma, turno FROM alunos WHERE ativo = 1 ORDER BY nome", conn)
        
        if not df_alunos.empty:
            for _, row in df_alunos.iterrows():
                c_nome, c_turma, c_btn = st.columns([3, 1, 1])
                c_nome.write(row["nome"])
                c_turma.write(row["turma"])
                if c_btn.button("Inativar", key=f"del_{row['id']}"):
                    cur = conn.cursor()
                    cur.execute("UPDATE alunos SET ativo = 0 WHERE id = ?", (row["id"],))
                    conn.commit()
                    st.warning(f"Aluno {row['nome']} inativado.")
                    st.rerun()
        else:
            st.info("Nenhum aluno ativo registrado.")

# -------------------------------------------------------------
# ABA: LANÇAMENTO DE NOTAS
# -------------------------------------------------------------
elif menu == "Lançamento de Notas":
    st.header("Lançamento de Notas por Etapa")
    
    c1, c2, c3 = st.columns(3)
    turma_sel = c1.selectbox("Selecione a Turma", ["1º ANO", "2º ANO", "3º ANO"])
    disciplina_sel = c2.selectbox("Disciplina", DISCIPLINAS)
    etapa_sel = c3.selectbox("Etapa", [1, 2, 3, 4])
    
    query = """
    SELECT a.id as aluno_id, a.nome, 
           COALESCE(av.trabalho, 0.0) as Trabalho, 
           COALESCE(av.vp, 0.0) as VP, 
           COALESCE(av.vg, 0.0) as VG,
           COALESCE(av.faltas, 0) as Faltas
    FROM alunos a
    LEFT JOIN avaliacoes av ON a.id = av.aluno_id AND av.disciplina = ? AND av.etapa = ?
    WHERE a.ativo = 1 AND a.turma = ?
    ORDER BY a.nome
    """
    df_notas = pd.read_sql(query, conn, params=[disciplina_sel, etapa_sel, turma_sel])
    
    if not df_notas.empty:
        st.write("Introduza as avaliações diretamente na tabela:")
        grade_editada = st.data_editor(
            df_notas,
            disabled=["aluno_id", "nome"],
            column_config={
                "aluno_id": None,
                "Trabalho": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.1),
                "VP": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.1),
                "VG": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.1),
                "Faltas": st.column_config.NumberColumn(min_value=0, max_value=100, step=1)
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("Guardar Alterações da Etapa", type="primary"):
            cur = conn.cursor()
            for _, r in grade_editada.iterrows():
                cur.execute("""
                INSERT INTO avaliacoes (aluno_id, disciplina, etapa, trabalho, vp, vg, faltas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(aluno_id, disciplina, etapa) DO UPDATE SET
                    trabalho = excluded.trabalho,
                    vp = excluded.vp,
                    vg = excluded.vg,
                    faltas = excluded.faltas
                """, (int(r["aluno_id"]), disciplina_sel, etapa_sel, float(r["Trabalho"]), float(r["VP"]), float(r["VG"]), int(r["Faltas"])))
            conn.commit()
            st.success("Notas e faltas salvas com sucesso!")
    else:
        st.info("Nenhum aluno registrado nesta turma.")

# -------------------------------------------------------------
# ABA: BOLETIM E MÉDIAS (Cálculo Automático + PDF)
# -------------------------------------------------------------
elif menu == "Boletim e Médias":
    st.header("Boletim Escolar Individual")
    
    df_alunos = pd.read_sql("SELECT id, nome, turma, turno FROM alunos WHERE ativo = 1 ORDER BY nome", conn)
    
    if df_alunos.empty:
        st.info("Nenhum aluno cadastrado.")
    else:
        opcoes_alunos = {row["nome"]: row["id"] for _, row in df_alunos.iterrows()}
        aluno_nome = st.selectbox("Selecione o Aluno", list(opcoes_alunos.keys()))
        aluno_id = opcoes_alunos[aluno_nome]
        aluno_info = df_alunos[df_alunos["id"] == aluno_id].iloc[0]
        
        # Puxa notas do aluno
        df_av = pd.read_sql("SELECT * FROM avaliacoes WHERE aluno_id = ?", conn, params=[aluno_id])
        
        dados_tabela = []
        for disc in DISCIPLINAS:
            medias_etapas = []
            for et in range(1, 5):
                reg = df_av[(df_av["disciplina"] == disc) & (df_av["etapa"] == et)]
                if not reg.empty:
                    m = calcular_media_etapa(
                        reg.iloc[0]["trabalho"],
                        reg.iloc[0]["vp"],
                        reg.iloc[0]["vg"],
                        reg.iloc[0]["recuperacao"]
                    )
                    medias_etapas.append(m)
                else:
                    medias_etapas.append(None)
            
            # Cálculo dos totais
            notas_validas = [m for m in medias_etapas if m is not None]
            total_pontos = sum(notas_validas) if notas_validas else 0.0
            media_anual = round(total_pontos / len(notas_validas), 1) if notas_validas else 0.0
            
            # Aplica regra de 5.75 a 5.9 na média anual também
            if 5.75 <= round(media_anual, 2) < 6.0:
                media_anual = 6.0
                
            status = "APROVADO" if media_anual >= 6.0 else "RECUPERAÇÃO"
            if len(notas_validas) < 4:
                status = "EM ANDAMENTO"
                
            dados_tabela.append({
                "Disciplina": disc,
                "1ª Etapa": medias_etapas[0] if medias_etapas[0] is not None else "-",
                "2ª Etapa": medias_etapas[1] if medias_etapas[1] is not None else "-",
                "3ª Etapa": medias_etapas[2] if medias_etapas[2] is not None else "-",
                "4ª Etapa": medias_etapas[3] if medias_etapas[3] is not None else "-",
                "Total Pontos": round(total_pontos, 1),
                "Média Anual": media_anual,
                "Situação": status
            })
            
        df_boletim = pd.DataFrame(dados_tabela)
        st.dataframe(df_boletim, use_container_width=True, hide_index=True)
        
        # Função para gerar PDF
        def gerar_pdf():
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elementos = []
            estilos = getSampleStyleSheet()
            
            titulo_estilo = ParagraphStyle(
                'Titulo',
                parent=estilos['Heading1'],
                alignment=1,
                fontSize=16,
                spaceAfter=12
            )
            subtitulo_estilo = ParagraphStyle(
                'Sub',
                parent=estilos['Normal'],
                alignment=1,
                fontSize=10,
                textColor=colors.gray,
                spaceAfter=15
            )
            
            elementos.append(Paragraph("<b>BOLETIM ESCOLAR</b>", titulo_estilo))
            elementos.append(Paragraph(f"<b>Aluno:</b> {aluno_info['nome']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Turma:</b> {aluno_info['turma']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Turno:</b> {aluno_info['turno']}", subtitulo_estilo))
            
            # Montar dados para tabela ReportLab
            cabecalho = ["Disciplina", "1ª Et.", "2ª Et.", "3ª Et.", "4ª Et.", "Total", "Média", "Situação"]
            linhas = [cabecalho]
            for _, r in df_boletim.iterrows():
                linhas.append([
                    str(r["Disciplina"]),
                    str(r["1ª Etapa"]),
                    str(r["2ª Etapa"]),
                    str(r["3ª Etapa"]),
                    str(r["4ª Etapa"]),
                    str(r["Total Pontos"]),
                    str(r["Média Anual"]),
                    str(r["Situação"])
                ])
                
            tabela = Table(linhas, colWidths=[130, 50, 50, 50, 50, 55, 55, 90])
            tabela.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            elementos.append(tabela)
            
            doc.build(elementos)
            buffer.seek(0)
            return buffer
            
        pdf_bytes = gerar_pdf()
        st.download_button(
            label="📄 Baixar Boletim em PDF",
            data=pdf_bytes,
            file_name=f"Boletim_{aluno_info['nome'].replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary"
        )
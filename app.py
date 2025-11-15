from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import io
import os
import json
import math
from datetime import datetime, timedelta
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

app = Flask(__name__)
# Caminho do banco de dados para o Render
DB_NAME = "/data/empresas.db" 

# --- CONFIGURAÇÕES ---
PDF_MODELO = "Formulário_Modelo.pdf" 
ARQUIVO_ASSINATURA = "assinatura.png"
VALOR_HORA_CHEIA = 759.86
PRECO_BLOCO_30MIN = VALOR_HORA_CHEIA / 2

# --- BANCO DE DADOS ---
def init_db():
    # Verifica se o diretório /data existe (para rodar no Render)
    if os.path.exists("/data"):
        db_path = "/data/empresas.db"
    else:
        # Se não, usa um arquivo local (para você testar no seu PC)
        db_path = "empresas.db"
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razao_social TEXT NOT NULL,
            cnpj TEXT NOT NULL UNIQUE,
            endereco TEXT,
            telefone TEXT,
            email_financeiro TEXT,
            solicitante_padrao TEXT,
            email_solicitante_padrao TEXT,
            piloto_padrao TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- LÓGICA DE CÁLCULO (FINANCEIRO - BLOCOS DE 30 MIN) ---
def calcular_timeline(inicio_main, fim_main, lista_concorrentes):
    fmt = "%H:%M"
    t_inicio = datetime.strptime(inicio_main, fmt)
    t_fim = datetime.strptime(fim_main, fmt)
    
    if t_fim < t_inicio:
        t_fim += timedelta(days=1)

    duracao_total = (t_fim - t_inicio).total_seconds() / 60
    qtd_blocos = math.ceil(duracao_total / 30)
    
    custo_total = 0
    detalhes_blocos = []

    for i in range(qtd_blocos):
        bloco_inicio = t_inicio + timedelta(minutes=i*30)
        bloco_fim = bloco_inicio + timedelta(minutes=30)
        
        concorrentes_no_bloco = 0
        
        for conc in lista_concorrentes:
            c_inicio = datetime.strptime(conc['inicio'], fmt)
            c_fim = datetime.strptime(conc['fim'], fmt)
            if c_fim < c_inicio: c_fim += timedelta(days=1)
            
            if (bloco_inicio < c_fim) and (c_inicio < bloco_fim):
                concorrentes_no_bloco += 1
        
        total_aeronaves = 1 + concorrentes_no_bloco
        custo_do_bloco = PRECO_BLOCO_30MIN / total_aeronaves
        custo_total += custo_do_bloco
        
        detalhes_blocos.append({
            "bloco": i+1,
            "horario": f"{bloco_inicio.strftime('%H:%M')} - {bloco_fim.strftime('%H:%M')}",
            "aeronaves_pagantes": total_aeronaves,
            "valor": custo_do_bloco
        })

    return {
        "valor_final": custo_total,
        "qtd_blocos": qtd_blocos,
        "horas_visuais": qtd_blocos * 0.5,
        "minutos_cobrados": int(qtd_blocos * 30),
        "detalhes": detalhes_blocos
    }

# --- LÓGICA AUXILIAR: INTERSEÇÃO DE HORÁRIOS (VISUAL) ---
def calcular_interseccao_visual(main_ini, main_fim, lista_concorrentes):
    fmt = "%H:%M"
    t_main_ini = datetime.strptime(main_ini, fmt)
    t_main_fim = datetime.strptime(main_fim, fmt)
    if t_main_fim < t_main_ini: t_main_fim += timedelta(days=1)
    
    intervalos_overlap = []

    for conc in lista_concorrentes:
        c_ini = datetime.strptime(conc['inicio'], fmt)
        c_fim = datetime.strptime(conc['fim'], fmt)
        if c_fim < c_ini: c_fim += timedelta(days=1)

        overlap_ini = max(t_main_ini, c_ini)
        overlap_fim = min(t_main_fim, c_fim)

        if overlap_ini < overlap_fim:
            txt = f"{overlap_ini.strftime('%H:%M')} - {overlap_fim.strftime('%H:%M')}"
            if txt not in intervalos_overlap:
                intervalos_overlap.append(txt)
            
    return ", ".join(intervalos_overlap)

# --- GERAÇÃO DO ANEXO (PLATYPUS) ---
def gerar_pagina_anexo(dados_principais, lista_concorrentes, detalhe_calculo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=inch, bottomMargin=inch, leftMargin=inch, rightMargin=inch)
    elements = []
    styles = getSampleStyleSheet()

    title_style = styles['Title']
    title_style.fontSize = 18
    title_style.textColor = colors.HexColor("#003366")
    
    elements.append(Paragraph("<b>Demonstrativo de Rateio e Cálculo</b>", title_style))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"<b>Aeronave Principal (Pagante):</b> {dados_principais['aeronave']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data do Voo:</b> {dados_principais['data']}", styles['Normal']))
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("<b>1. Aeronaves Envolvidas no Período</b>", styles['Heading3']))
    dados_tabela = [['Matrícula', 'Tipo', 'Início', 'Fim']]
    dados_tabela.append([dados_principais['aeronave'], 'Principal (Pagante)', dados_principais['inicio'], dados_principais['fim']])
    for c in lista_concorrentes:
        dados_tabela.append([c['matricula'], 'Rateio', c['inicio'], c['fim']])

    t = Table(dados_tabela, colWidths=[100, 150, 80, 80])
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#003366")),
        
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E0E8F0")), 
    ]))
    
    for i in range(2, len(dados_tabela)):
        if i % 2 == 0:
             t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F0F5FA"))]))

    elements.append(t)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("<b>2. Memória de Cálculo (Blocos de 30 min)</b>", styles['Heading3']))
    dados_calc = [['Bloco', 'Horário', 'Qtd. Aeronaves', 'Valor Rateado (p/ Aeronave)']]
    for d in detalhe_calculo['detalhes']:
        dados_calc.append([
            str(d['bloco']),
            d['horario'],
            str(d['aeronaves_pagantes']),
            f"R$ {d['valor']:.2f}"
        ])
    
    dados_calc.append(['TOTAL COBRADO', '', '', f"R$ {detalhe_calculo['valor_final']:.2f}"])

    t2 = Table(dados_calc, colWidths=[60, 120, 100, 180])
    
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#333333")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),

        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 1, colors.darkgrey),
    ]))

    for i in range(1, len(dados_calc) -1):
        if i % 2 != 0:
             t2.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F4F4F4"))]))
    
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (0, -1), (2, -1), 'RIGHT'),
        ('ALIGN', (3, -1), (3, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ]))

    elements.append(t2)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- ROTAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/empresas', methods=['GET', 'POST'])
def gerenciar_empresas():
    # Caminho do banco (local ou servidor)
    db_path = "/data/empresas.db" if os.path.exists("/data") else "empresas.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        try:
            # Esta é a seção (Linha ~227) que o Render indicou como quebrada.
            # Esta versão está sintaticamente correta.
            cursor.execute('''
                INSERT INTO empresas (razao_social, cnpj, endereco, telefone, email_financeiro, solicitante_padrao, email_solicitante_padrao, piloto_padrao) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('razao'), 
                data.get('cnpj'), 
                data.get('endereco'), 
                data.get('telefone'), 
                data.get('email_financeiro'), 
                data.get('solicitante'), 
                data.get('email_solicitante'), 
                data.get('piloto')
            ))
            conn.commit()
            return jsonify({"msg": "Salvo!"}), 201
        except Exception as e:
            return jsonify({"msg": str(e)}), 400
        finally:
            conn.close()
    else:
        cursor.execute('SELECT * FROM empresas')
        rows = cursor.fetchall()
        # Corrigido "email_colicitante" para "email_solicitante_padrao"
        empresas = [{"id":r[0], "razao":r[1], "cnpj":r[2], "endereco":r[3], "telefone":r[4], "email_financeiro":r[5], "solicitante":r[6], "email_solicitante_padrao":r[7], "piloto":r[8]} for r in rows]
        conn.close()
        return jsonify(empresas)

@app.route('/api/gerar_pdf', methods=['POST'])
def gerar_pdf():
    dados = request.form
    arquivo_anexo_email = request.files.get('anexo')
    lista_concorrentes = json.loads(dados.get('concorrentes_json', '[]'))
    observacoes = dados.get('observacoes', '')
    
    # Pega os dados da empresa do formulário
    email_financeiro = dados.get('empresa_email', '') 
    telefone_cobranca = dados.get('empresa_telefone', '') # O mesmo número
    
    # 1. Cálculo
    resultado = calcular_timeline(dados['inicio'], dados['fim'], lista_concorrentes)
    
    # 2. Overlay PDF
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica", 10)
    
    # DNB
    can.drawString(110, 700, "IMPERATRIZ-MA") 

    # Coordenadas Pessoais (Solicitante, Piloto)
    can.drawString(150, 645, dados['solicitante'])
    can.drawString(150, 624, dados['email_solicitante'])
    can.drawString(150, 602, dados['piloto'])
    
    # Telefone Solicitante
    can.drawString(400, 622, telefone_cobranca)
    
    # Coordenadas Faturamento (Empresa)
    can.drawString(150, 530, dados['empresa_razao'])
    can.drawString(150, 510, dados['empresa_cnpj'])
    
    # Endereço (com quebra de linha)
    endereco_texto = dados.get('empresa_endereco', '')
    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleN.fontName = "Helvetica"
    styleN.fontSize = 10
    styleN.leading = 12 
    p_endereco = Paragraph(endereco_texto, styleN)
    caixa_largura = 400 
    caixa_altura = 42
    w, h = p_endereco.wrap(caixa_largura, caixa_altura)
    y_desenho = 486 - h
    p_endereco.drawOn(can, 150, y_desenho)

    # Email (Abaixo do Endereço)
    can.drawString(250, 424, email_financeiro) 
    
    # Telefone Cobrança (Abaixo do Email)
    can.drawString(100, 444, telefone_cobranca) 
    
    y_tab = 300 
    
    # Escreve Aeronave Principal
    can.setFont("Helvetica", 10)
    can.drawString(80, y_tab, dados['aeronave']) 
    
    # Lógica Concorrentes e Horário de Rateio
    if len(lista_concorrentes) > 0:
        matriculas = [c['matricula'] for c in lista_concorrentes]
        
        if len(lista_concorrentes) <= 5:
            texto_extra = f"{', '.join(matriculas)}"
            gera_anexo_tabela = True 
        else:
            texto_extra = f"+ {len(lista_concorrentes)} aeronaves (Ver Anexo)"
            gera_anexo_tabela = True

        can.setFont("Helvetica", 8)
        can.drawString(110, y_tab - 74, texto_extra) 
        
        texto_horario_rateio = calcular_interseccao_visual(dados['inicio'], dados['fim'], lista_concorrentes)
        
        if texto_horario_rateio:
            can.drawString(320, y_tab - 74, f" {texto_horario_rateio}")
        
        can.setFont("Helvetica", 10)
    else:
        gera_anexo_tabela = False

    # Obs
    if observacoes:
        can.setFont("Helvetica", 9)
        can.drawString(80, y_tab - 95, f"Obs: {observacoes}")
        can.setFont("Helvetica", 10)

    # Dados da Principal
    can.drawString(140, y_tab, dados['data'])
    can.drawString(220, y_tab, dados['inicio'])
    can.drawString(290, y_tab, dados['fim'])
    
    # Minutos Cobrados
    can.drawString(350, y_tab, f"{resultado['minutos_cobrados']} min")
    
    can.drawString(420, y_tab, f"R$ {VALOR_HORA_CHEIA:.2f}")
    can.drawString(490, y_tab, f"R$ {resultado['valor_final']:.2f}")
    
    # Checkbox
    if len(lista_concorrentes) > 0:
        can.drawString(182, 272, "X") # Sim
    else:
        can.drawString(250, 268, "X") # Não

    # Assinatura
    if os.path.exists(ARQUIVO_ASSINATURA):
        can.drawImage(ARQUIVO_ASSINATURA, 350, 100, width=100, height=30, mask='auto')

    can.save()
    packet.seek(0)
    
    # 3. Montagem Final
    output_writer = PdfWriter()
    
    # Pág 1
    if os.path.exists(PDF_MODELO):
        overlay_pdf = PdfReader(packet)
        modelo_pdf = PdfReader(open(PDF_MODELO, "rb"))
        pagina_1 = modelo_pdf.pages[0]
        pagina_1.merge_page(overlay_pdf.pages[0])
        output_writer.add_page(pagina_1)
    
    # Pág 2
    if gera_anexo_tabela:
        pdf_tabela = gerar_pagina_anexo(dados, lista_concorrentes, resultado)
        reader_tabela = PdfReader(pdf_tabela)
        output_writer.add_page(reader_tabela.pages[0])
        
    # Pág 3
    if arquivo_anexo_email:
        anexo_reader = PdfReader(arquivo_anexo_email)
        output_writer.append_pages_from_reader(anexo_reader)
    
    pdf_output = io.BytesIO()
    output_writer.write(pdf_output)
    pdf_output.seek(0)
    
    filename = f"Fatura_{dados['aeronave']}.pdf"
    return send_file(pdf_output, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == '__main__':
    # Verifica o ambiente antes de iniciar o DB
    if not os.path.exists("/data"):
        print("Aviso: Diretório /data não encontrado. Rodando em modo local.")
    init_db()
    
    # Define a porta para o Render (ou 5000 para local)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

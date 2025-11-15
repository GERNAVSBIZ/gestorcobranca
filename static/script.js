// --- NAVEGAÇÃO ---
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    if (window.event && window.event.target) window.event.target.classList.add('active');
}

// --- FUNÇÕES DE CONCORRENTES ---
function addConcorrente() {
    const tbody = document.querySelector('#tbConcorrentes tbody');
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="conc-mat" placeholder="PT-XYZ" style="width: 70px; margin:0;"></td>
        <td><input type="time" class="conc-ini" style="margin:0;"></td>
        <td><input type="time" class="conc-fim" style="margin:0;"></td>
        <td><button type="button" onclick="this.parentElement.parentElement.remove()" style="color:red; border:none; background:none; cursor:pointer;">X</button></td>
    `;
    tbody.appendChild(tr);
}

function getConcorrentes() {
    const linhas = document.querySelectorAll('#tbConcorrentes tbody tr');
    const lista = [];
    linhas.forEach(tr => {
        const mat = tr.querySelector('.conc-mat').value;
        const ini = tr.querySelector('.conc-ini').value;
        const fim = tr.querySelector('.conc-fim').value;
        if(mat && ini && fim) {
            lista.push({ matricula: mat, inicio: ini, fim: fim });
        }
    });
    return JSON.stringify(lista);
}

// --- EMPRESAS ---
async function carregarEmpresas() {
    try {
        const res = await fetch('/api/empresas');
        const empresas = await res.json();
        const select = document.getElementById('selectEmpresa');
        const lista = document.getElementById('listaEmpresas');
        
        select.innerHTML = '<option value="">-- Selecione --</option>';
        lista.innerHTML = '';
    
        empresas.forEach(emp => {
            const opt = document.createElement('option');
            opt.value = JSON.stringify(emp); // O objeto JSON com todos os dados
            opt.textContent = emp.razao;
            select.appendChild(opt);
    
            const li = document.createElement('li');
            li.textContent = `${emp.razao} (${emp.cnpj})`;
            lista.appendChild(li);
        });
    } catch (e) { console.log("Erro api"); }
}

function preencherEmpresa() {
    const select = document.getElementById('selectEmpresa');
    if (!select.value) return; // Não faz nada se o valor for vazio

    const emp = JSON.parse(select.value); 
    
    document.getElementById('f_razao').value = emp.razao || "";
    document.getElementById('f_cnpj').value = emp.cnpj || "";
    document.getElementById('f_endereco').value = emp.endereco || "";
    document.getElementById('f_telefone').value = emp.telefone || "";
    document.getElementById('f_email_financeiro').value = emp.email_financeiro || ""; 
    
    // Preenche dados operacionais
    document.getElementById('f_solicitante').value = emp.solicitante || "";
    // CORREÇÃO: Pega o nome de propriedade correto do JSON
    document.getElementById('f_email_solicitante').value = emp.email_solicitante_padrao || ""; 
    document.getElementById('f_piloto').value = emp.piloto || "";
}

// --- SALVAR EMPRESA ---
async function salvarEmpresa() {
    const dados = {
        razao: document.getElementById('c_razao').value,
        cnpj: document.getElementById('c_cnpj').value,
        endereco: document.getElementById('c_endereco').value,
        telefone: document.getElementById('c_telefone').value,
        email_financeiro: document.getElementById('c_email_financeiro').value,
        solicitante: document.getElementById('c_solicitante').value,
        email_solicitante: document.getElementById('c_email_solicitante').value,
        piloto: document.getElementById('c_piloto').value
    };
    if (!dados.razao) return alert("Preencha a Razão Social.");
    
    await fetch('/api/empresas', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(dados)
    });
    alert("Salvo!");
    carregarEmpresas();
}

// --- CONSULTAR CNPJ (Versão com Diagnóstico e Email) ---
async function consultarReceita() {
    console.log("Iniciando consulta...");

    const cnpjInput = document.getElementById('c_cnpj');
    const cnpj = cnpjInput.value.replace(/\D/g, '');
    
    if(cnpj.length !== 14) {
        return alert("CNPJ inválido (digite 14 números)");
    }

    cnpjInput.style.background = "#e8f0fe"; 
    
    try {
        const res = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${cnpj}`);
        if(!res.ok) throw new Error("API não respondeu OK");
        
        const d = await res.json();
        console.log("DADOS COMPLETOS RECEBIDOS DA API:", d);

        // Preenchimento
        document.getElementById('c_razao').value = d.razao_social;
        document.getElementById('c_endereco').value = `${d.logradouro}, ${d.numero} ${d.complemento || ''} - ${d.bairro}, ${d.municipio}-${d.uf}`;
        document.getElementById('c_telefone').value = d.ddd_telefone_1;

        const emailField = document.getElementById('c_email_financeiro');
        if (!emailField) {
            console.error("ERRO CRÍTICO: Não achei o campo 'c_email_financeiro' no HTML.");
        } else {
            emailField.value = d.email || ""; 
            console.log("Preenchimento do email concluído.");
        }

    } catch(e) {
        console.error("Falha na consulta:", e);
        alert("Erro ao consultar CNPJ. Verifique o console (F12).");
    } finally {
        cnpjInput.style.background = "white"; 
    }
}


// --- GERAR PDF ---
async function gerarPDF(e) {
    e.preventDefault();
    const formData = new FormData();

    // Campos Texto
    formData.append('empresa_razao', document.getElementById('f_razao').value);
    formData.append('empresa_cnpj', document.getElementById('f_cnpj').value);
    formData.append('empresa_endereco', document.getElementById('f_endereco').value);
    formData.append('empresa_telefone', document.getElementById('f_telefone').value);
    formData.append('empresa_email', document.getElementById('f_email_financeiro').value); 
    
    formData.append('solicitante', document.getElementById('f_solicitante').value);
    formData.append('email_solicitante', document.getElementById('f_email_solicitante').value);
    formData.append('piloto', document.getElementById('f_piloto').value);
    
    formData.append('aeronave', document.getElementById('f_aeronave').value);
    
    // Formata a data do tipo 'date' para 'DD/MM/YYYY'
    const dataInput = document.getElementById('f_data').value; // Pega 'YYYY-MM-DD'
    const [ano, mes, dia] = dataInput.split('-');
    const dataFormatada = `${dia}/${mes}/${ano}`;
    formData.append('data', dataFormatada); // Envia 'DD/MM/YYYY'
    
    formData.append('inicio', document.getElementById('f_inicio').value);
    formData.append('fim', document.getElementById('f_fim').value);
    
    formData.append('observacoes', document.getElementById('f_observacoes').value);

    // LISTA DE CONCORRENTES (JSON)
    formData.append('concorrentes_json', getConcorrentes());

    // Arquivo
    const fileInput = document.getElementById('f_anexo');
    if (fileInput.files.length > 0) {
        formData.append('anexo', fileInput.files[0]);
    }

    const res = await fetch('/api/gerar_pdf', { method: 'POST', body: formData });
    
    if(res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Fatura_${document.getElementById('f_aeronave').value}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    } else {
        alert("Erro ao gerar PDF.");
    }
}

window.onload = carregarEmpresas;
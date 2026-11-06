// Publica o código de maestro/ no bloco PARSE_dados de um Maestro existente no Desk Manager.
// Por padrão só SIMULA. Use --apply para gravar.
//
//   node scripts/publicar_maestro.mjs --versao 12            # simulação (versão que você espera encontrar)
//   node scripts/publicar_maestro.mjs --versao 12 --apply    # grava
//
// A versão do Maestro funciona como trava otimista: se alguém editou no Desk depois de você,
// o script aborta em vez de sobrescrever.
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const raiz = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '..');
const apply = process.argv.includes('--apply');
const i = process.argv.indexOf('--versao');
const VERSAO_ESPERADA = i > 0 ? Number(process.argv[i + 1]) : NaN;
if (!Number.isInteger(VERSAO_ESPERADA)) { console.error('Informe --versao <número da versão atual do Maestro>'); process.exit(1); }

const env = Object.fromEntries(fs.readFileSync(path.join(raiz, '.env'), 'utf8').split(/\r?\n/)
  .filter(l => l.includes('=') && !l.startsWith('#'))
  .map(l => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1).trim().replace(/^"|"$/g, '')]));
for (const k of ['DESK_OPERATOR_KEY', 'DESK_PUBLIC_KEY', 'DESK_PORTAL_HOST', 'MAESTRO_COD']) if (!env[k]) { console.error(`Falta ${k} no .env`); process.exit(1); }

const falha = m => { console.error('ABORTADO:', m); process.exit(1); };
const curl = (args, body) => {
  const tmp = path.join(raiz, '.req.tmp');
  if (body !== undefined) fs.writeFileSync(tmp, body);
  try { return execFileSync('curl', ['-sS', '--ssl-no-revoke', '-m', '120', ...args, ...(body !== undefined ? ['--data-binary', '@' + tmp] : [])], { maxBuffer: 80e6 }).toString('utf8'); }
  finally { fs.rmSync(tmp, { force: true }); }
};
const login = () => curl(['-X', 'POST', 'https://api.desk.ms/Login/autenticar', '-H', 'Authorization: ' + env.DESK_OPERATOR_KEY, '-H', 'Content-Type: application/json'],
  JSON.stringify({ PublicKey: env.DESK_PUBLIC_KEY })).replace(/"/g, '');
const ler = tk => {
  const dados = encodeURIComponent(JSON.stringify({ Chave: env.MAESTRO_COD }));
  const j = JSON.parse(curl(['-X', 'POST', `https://${env.DESK_PORTAL_HOST}/Maestro`, '-H', 'Authorization: ' + tk, '-H', 'Content-Type: application/x-www-form-urlencoded'],
    `Dados=${dados}&Origem=Construtor&App=Panel`));
  const m = j.TMaestro || j; let f = m.Fluxo; if (typeof f === 'string') f = JSON.parse(f);
  return { versao: Number(m.Versao), fluxo: f };
};
const gz64 = t => zlib.gzipSync(Buffer.from(t, 'utf8'), { level: 9 }).toString('base64');

// 1) monta o Python final (preenche os marcadores com o HTML compactado)
let py = fs.readFileSync(path.join(raiz, 'maestro/parse_dados.py'), 'utf8');
const preenche = (marcador, arquivo) => {
  if (py.split(marcador).length !== 2) falha(`marcador ${marcador} deve aparecer exatamente 1 vez`);
  py = py.replace(marcador, () => gz64(fs.readFileSync(path.join(raiz, arquivo), 'utf8')));
};
preenche('__EMBED_B64__', 'maestro/embed.html');
preenche('__DOC_B64__', 'maestro/documento_termo.html');
if (/SUA_CHAVE_DE_OPERADOR|SUA_PUBLIC_KEY|SEU_TOKEN/.test(py)) {
  console.log('Aviso: os valores de exemplo (SUA_CHAVE_DE_OPERADOR, SUA_PUBLIC_KEY, SEU_TOKEN...) continuam no código.');
  console.log('       Prefira informá-los na memória do Maestro (CST_ChaveOperador, CST_PublicKey, CST_Webhook, CST_MaestroCod, CST_CampoCPF).');
}
let validou = false;
for (const exe of ['python3', 'python']) {
  try { execFileSync(exe, ['-c', 'import ast,sys;ast.parse(sys.stdin.read())'], { input: py, stdio: ['pipe', 'pipe', 'pipe'] }); validou = true; console.log('Python: sintaxe OK'); break; }
  catch (e) { if (e.code === 'ENOENT' || /n.o foi encontrado|not found/i.test(String(e.stderr))) continue; falha('Python inválido: ' + String(e.stderr || e.message).slice(0, 300)); }
}
if (!validou) console.log('Aviso: python não encontrado, sintaxe do Python não validada.');

// 2) lê o Maestro atual e confere a versão
let tk = login();
const { versao, fluxo } = ler(tk);
if (versao !== VERSAO_ESPERADA) falha(`a versão do Maestro agora é ${versao} (esperado ${VERSAO_ESPERADA}): alguém alterou. Revise antes de gravar.`);
const original = JSON.parse(JSON.stringify(fluxo));
const bloco = fluxo.config.find(x => x.name === 'PARSE_dados');
if (!bloco) falha('bloco PARSE_dados não encontrado no Maestro');
bloco.jsonata = py;

// 3) codifica o fluxo (JSON -> escape mínimo de % e + -> base64) e confere o tamanho
const json = JSON.stringify(fluxo);
const pc = String.fromCharCode(37);
const fluxoB64 = Buffer.from(json.split(pc).join(pc + '25').split('+').join(pc + '2B'), 'utf8').toString('base64');
const corpo = 'Dados=' + encodeURIComponent(JSON.stringify({ TMaestro: { Chave: env.MAESTRO_COD, Fluxo: fluxoB64, Panel: 'FluxoMConstrutor' } })) + '&Menu=FluxoMConstrutor&App=Ticket';
console.log(`corpo do PUT: ${corpo.length} bytes (o Desk recusa por volta de 131.000)`);
if (corpo.length > 130000) falha('corpo do PUT perto do limite: enxugue o código (por exemplo, comentários do Python)');
if (!apply) { console.log('(simulação: nada foi enviado)'); process.exit(0); }

// 4) grava e confere
tk = login();
if (ler(tk).versao !== VERSAO_ESPERADA) falha('a versão mudou durante a preparação');
console.log('resposta do PUT:', curl(['-X', 'PUT', `https://${env.DESK_PORTAL_HOST}/Maestro`, '-H', 'Authorization: ' + tk, '-H', 'Content-Type: application/x-www-form-urlencoded'], corpo).slice(0, 120));
tk = login();
const dep = ler(tk);
const outros = original.config.map(x => x.name).filter(n => n !== 'PARSE_dados');
console.log('Versão depois:', dep.versao);
console.log('demais blocos iguais:', outros.filter(n => JSON.stringify(dep.fluxo.config.find(x => x.name === n)) === JSON.stringify(original.config.find(x => x.name === n))).length + '/' + outros.length);
console.log('PARSE_dados gravado = enviado:', dep.fluxo.config.find(x => x.name === 'PARSE_dados').jsonata === py);

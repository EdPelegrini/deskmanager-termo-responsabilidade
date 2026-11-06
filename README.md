# Termo de Responsabilidade digital dentro do Desk Manager

Emissão, assinatura eletrônica e arquivamento de **Termos de Responsabilidade de equipamentos**, tudo dentro do
Desk Manager usando **Embed + Maestro**, sem ferramenta externa de assinatura.

> Todos os dados deste repositório são **fictícios** (empresa "Empresa Exemplo S.A.", endereço, logo, chaves e
> webhook de exemplo). Este é um projeto pessoal de exemplo e não tem vínculo oficial com o Desk Manager.

## O problema

O termo era assinado em uma ferramenta externa. Depois, alguém precisava baixar o PDF e anexar manualmente no
cadastro do equipamento (IC) no CMDB: trabalho manual, sujeito a esquecimento e difícil de rastrear.

## A solução

Tudo no próprio Desk Manager:

1. **Emissão** (tela Embed): o responsável de TI escolhe o solicitante e os equipamentos (IC), informa o número do
   chamado (obrigatório), acessórios e estado de conservação, e assina.
2. **Aviso**: o solicitante recebe uma notificação com o link do termo (válido por 10 dias).
3. **Assinatura**: o solicitante lê as cláusulas, desenha a assinatura e confirma. O documento registra data, hora,
   IP e hash de integridade.
4. **Arquivamento**: o PDF assinado é anexado automaticamente na aba **Anexos** do IC.
5. **Rastreio**: cada termo tem número único (`TR-AAAA-NNNN`), data, responsável de TI e número do chamado.

Recursos da tela de emissão:

- busca do equipamento por **nome, número de série, IMEI ou número da linha**;
- acessório padrão "Fonte / Carregador" e estado de conservação do equipamento;
- número do chamado obrigatório (validado na tela e no servidor);
- aba com os termos já emitidos e o status de cada um.

## Arquitetura

```
 Embed (HTML) ──┐
                ├──►  Maestro (webhook)  ──►  bloco PARSE_dados (Python)
 Link do termo ─┘            │                    │
                             │                    ├─► Table (termos emitidos)
                             │                    ├─► Notificação ao solicitante
                             │                    └─► Anexo do PDF no IC (files API)
                             └─ Storage: termo_<token>
```

O fluxo do Maestro tem poucos blocos (`BEGIN_init`, `PARSE_dados`, `IF_rota`, `PARSE_html`, `PARSE_json` e as
rotas). Quase toda a lógica está no `PARSE_dados`, um script Python com a função `run(memoria)`.

## Estrutura do repositório

| Caminho | O que é |
|---|---|
| `maestro/parse_dados.py` | Código do bloco `PARSE_dados` (Python). Os HTML entram por marcadores. |
| `maestro/embed.html` | Tela de emissão e lista de termos (HTML + JS). |
| `maestro/documento_termo.html` | Modelo do termo com cláusulas, assinatura e evidências. |
| `scripts/publicar_maestro.mjs` | Compacta os HTML (gzip + base64) e grava no Maestro, com trava de versão. |
| `.env.example` | Variáveis necessárias para o script (copie para `.env`). |

## Como usar

Pré-requisitos: Node.js 18+, `curl`, `python3` (só para validar a sintaxe) e um Maestro já criado no seu Desk Manager
com o bloco `PARSE_dados`.

1. Copie `.env.example` para `.env` e preencha (o `.env` está no `.gitignore`).
2. No Maestro, guarde na **memória** os valores de configuração, em vez de deixá-los no código:
   `CST_ChaveOperador`, `CST_PublicKey`, `CST_Webhook`, `CST_MaestroCod`, `CST_CampoCPF`, `CST_RazaoSocial`
   (e, opcionalmente, `CST_SeqPiso` para iniciar a numeração a partir de um valor).
3. Ajuste os textos de `maestro/documento_termo.html` com as cláusulas aprovadas **pelo jurídico da sua empresa**
   (as cláusulas deste repositório são só um exemplo).
4. Simule e depois grave:

```bash
node scripts/publicar_maestro.mjs --versao 12            # simulação
node scripts/publicar_maestro.mjs --versao 12 --apply    # grava
```

Substitua `12` pela versão atual do Maestro. O script só grava se a versão for exatamente essa e confere o
resultado depois (os demais blocos precisam ficar idênticos).

## Cuidados

- **Nunca** coloque chaves, tokens ou URLs de webhook no repositório. Os valores `SUA_...` e `SEU_...` são
  marcadores.
- **Restrinja o acesso** ao Embed à equipe de TI (permissão de menu/grupo no Desk Manager). Quem abre a tela pode
  emitir termos.
- **Edição concorrente**: se alguém editar o Maestro pelo painel do Desk, as suas alterações podem ser
  sobrescritas. Por isso a trava de versão do script e a recomendação de editar sempre a partir da versão mais
  recente.
- **Tamanho**: o corpo da requisição de gravação do Maestro tem um limite (cerca de 131.000 bytes). O script avisa
  quando chega perto; remover comentários do Python é a forma mais simples de ganhar espaço.
- A numeração `TR-AAAA-NNNN` usa o maior número existente na Table + 1. Se linhas forem apagadas, números podem
  se repetir.

## Limitações conhecidas

- O campo do IC que indica "termo assinado" ainda não é atualizado automaticamente.
- O PDF anexado ao IC é gerado em Python (biblioteca `fpdf`) com texto resumido das cláusulas; o documento HTML tem
  o texto completo.

## Licença

Defina a licença antes de publicar (por exemplo, MIT).

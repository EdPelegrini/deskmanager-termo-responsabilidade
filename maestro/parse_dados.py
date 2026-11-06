#python,saida!
def run(memoria):
    import gzip, base64, json, requests, hashlib, random
    from datetime import datetime, timedelta
    _EMBED_B64 = "__EMBED_B64__"
    _DOC_B64 = "__DOC_B64__"
    def _unz(x):
        return gzip.decompress(base64.b64decode(x)).decode("utf-8")
    API = "https://api.desk.ms"
    TABLE = "000005"
    CO = str(memoria.get("CST_ChaveOperador", "") or "").strip() or "SUA_CHAVE_DE_OPERADOR"
    CA = str(memoria.get("CST_PublicKey", "") or "").strip() or "SUA_PUBLIC_KEY"
    WEBHOOK = str(memoria.get("CST_Webhook", "") or "").strip() or "https://SEU-WEBHOOK.lambda-url.us-east-1.on.aws/?token=SEU_TOKEN"
    MAESTRO_COD = str(memoria.get("CST_MaestroCod", "") or "").strip() or "COD_DO_MAESTRO"

    b = memoria.get("BEGIN_init", {}) or {}
    par = b.get("MAESTRO_PARAMS") or {}
    def g(k, d=""):
        v = b.get(k)
        if v is None or v == "":
            v = par.get(k, d)
        return v if v is not None else d
    case = str(g("case", "")).strip().lower()
    is_get = str(g("get", "")).strip().lower() in ("true", "1", "s", "sim")

    def ip_servidor():
        try:
            hdr = b.get("MAESTRO_HEADERS") or {}
            xff = str(hdr.get("x-forwarded-for") or hdr.get("X-Forwarded-For") or "").strip()
            return xff.split(",")[0].strip() if xff else ""
        except Exception:
            return ""

    def auth():
        try:
            r = requests.post(API + "/Login/autenticar",
                headers={"Authorization": CO, "Content-Type": "application/json", "JsonPath": "true"},
                json={"PublicKey": CA}, timeout=60)
            return str(r.json().get("access_token", "")).strip()
        except Exception:
            return ""
    TK = auth()
    Hj = {"Authorization": TK, "Content-Type": "application/json", "JsonPath": "true"}

    def esc(s):
        s = "" if s is None else str(s)
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _stg():
        try:
            import storage
            return storage.Storage(MAESTRO_COD)
        except Exception:
            return None
    def stg_save(token, obj):
        s = _stg()
        if s is None:
            return False
        try:
            s.key = "termo_" + token
            s.value = json.dumps(obj, ensure_ascii=False)
            s.Save()
            return True
        except Exception:
            return False
    def stg_get(token):
        s = _stg()
        if s is None:
            return {}
        try:
            s.key = "termo_" + token
            raw = s.Get()
            if isinstance(raw, dict):
                for c in ("value", "Value", "valor", "data"):
                    if raw.get(c):
                        raw = raw.get(c); break
            if raw and not isinstance(raw, str):
                raw = str(raw)
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def stg_raw_get(key):
        s = _stg()
        if s is None:
            return ""
        try:
            s.key = key
            raw = s.Get()
            if isinstance(raw, dict):
                for c in ("value", "Value", "valor", "data"):
                    if raw.get(c):
                        raw = raw.get(c); break
            return "" if raw is None else str(raw)
        except Exception:
            return ""
    def stg_raw_set(key, val):
        s = _stg()
        if s is None:
            return False
        try:
            s.key = key
            s.value = str(val)
            s.Save()
            return True
        except Exception:
            return False

    def _max_table_num(pref):
        mx = 0
        for row in tbl_list():
            nt = str(row.get("Campo27", "") or "")
            if nt.startswith(pref):
                try:
                    nn = int(nt.split("-")[-1])
                    if nn > mx:
                        mx = nn
                except Exception:
                    pass
        return mx
    def proximo_numero(ano):
        pref = "TR-" + ano + "-"
        key = "seq_" + ano
        try:
            seq_atual = int(str(stg_raw_get(key) or "0").strip() or "0")
        except Exception:
            seq_atual = 0
        try:
            piso = int(str(memoria.get("CST_SeqPiso", "") or "0").strip() or "0")
        except Exception:
            piso = 0
        base = max(seq_atual, _max_table_num(pref), piso)
        novo = base + 1
        stg_raw_set(key, novo)
        return pref + str(novo).zfill(4)

    TAB = "TablesMaestro" + TABLE
    _FORM_CT = "application/x-www-form-urlencoded; charset=UTF-8"
    def _form_body(dados_obj, menu):
        import urllib.parse as _up
        return "Dados=" + _up.quote(json.dumps(dados_obj, ensure_ascii=False)) + "&Menu=" + menu + "&App=Panel"
    def tbl_list():
        body = _form_body({"Pesquisa": "", "Ativo": "S", "Limit": "5000", "Ordem": []}, TAB)
        try:
            r = maestroutils.apiDeskManager(spath=TAB + "/lista", smethod="POST",
                sbody=body, sContentType=_FORM_CT, sauth=TK)
            rj = r.get("responsejson", {}) if isinstance(r, dict) else {}
            if isinstance(rj, dict) and "root" in rj:
                return rj.get("root", [])
        except Exception:
            pass
        return []
    def tbl_put(campos):
        body = _form_body({"TTableMaestro": campos}, TAB)
        try:
            r = maestroutils.apiDeskManager(spath=TAB, smethod="PUT",
                sbody=body, sContentType=_FORM_CT, sauth=TK)
            rj = r.get("responsejson", r) if isinstance(r, dict) else r
            return "MU:" + (json.dumps(rj) if not isinstance(rj, str) else rj)[:200]
        except Exception as e:
            return "EXC:" + str(e)[:150]

    def ics_lista():
        try:
            r = requests.post(API + "/ICs/lista", headers=Hj, json={
                "Ativo": "S",
                "Colunas": {"Chave": "on", "Nome": "on", "SerialNum": "on", "TermoResp": "on", "TipodeAtivo": "on"},
                "Ordem": [{"Coluna": "Nome", "Direcao": "true"}]}, timeout=60)
            d = r.json()
            return d.get("root", []) if isinstance(d, dict) else []
        except Exception:
            return []
    def ic_dados(cod):
        try:
            return requests.post(API + "/ICs", headers=Hj, json={"Chave": str(cod)}, timeout=60).json().get("TIc", {}) or {}
        except Exception:
            return {}
    def usuarios():
        try:
            return requests.post(API + "/Usuarios/lista", headers=Hj,
                json={"Pesquisa": "", "Ativo": "1", "Ordem": [], "Limit": "5000"}, timeout=60).json().get("root", [])
        except Exception:
            return []
    def operadores():
        try:
            return requests.post(API + "/Operadores/lista", headers=Hj,
                json={"Pesquisa": "", "Ativo": "1", "Ordem": [{"Coluna": "Nome", "Direcao": "true"}]}, timeout=60).json().get("root", [])
        except Exception:
            return []

    def html_resp(html, externo=False):
        if not html.lstrip().lower().startswith("<!doctype"):
            html = "<!DOCTYPE htm>" + html
        html = html.replace("<!DOCTYPE html>", "<!DOCTYPE htm>", 1)
        return {"html_pronto": html, "is_html": "1" if externo else "0",
                "payload": json.dumps({"type": "text/html", "base64": base64.b64encode(html.encode("utf-8")).decode("ascii")}, ensure_ascii=False)}
    def json_resp(obj):
        return {"html_pronto": "", "is_html": "0", "payload": json.dumps(obj, ensure_ascii=False)}

    _LOGO_B64 = ""
    def termo_pdf_bytes(st):
        from fpdf import FPDF
        import tempfile, os as _os
        MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        def _dtext(iso):
            try:
                d = datetime.strptime(str(iso)[:19], "%Y-%m-%d %H:%M:%S")
                return str(d.day) + " de " + MESES[d.month] + " de " + str(d.year) + " " + d.strftime("%H:%M:%S")
            except Exception:
                return str(iso or "")
        def L(s):
            return ("" if s is None else str(s)).encode("latin-1", "replace").decode("latin-1")
        def _png_tmp(datauri):
            try:
                ext = ".png"
                head = datauri[:30].lower()
                if "jpeg" in head or "jpg" in head: ext = ".jpg"
                elif "gif" in head: ext = ".gif"
                b = datauri.split(",", 1)[1] if "," in datauri else datauri
                raw = base64.b64decode(b)
                fd, p = tempfile.mkstemp(suffix=ext); _os.write(fd, raw); _os.close(fd)
                return p
            except Exception:
                return ""
        PRIM = (232, 99, 10)  # laranja da marca
        pdf = FPDF(format="A4"); pdf.set_auto_page_break(True, margin=16); pdf.add_page()
        LM = pdf.l_margin
        W = pdf.w - pdf.l_margin - pdf.r_margin
        def X():
            pdf.set_x(LM)
        if _LOGO_B64:
            lp = _png_tmp(_LOGO_B64)
            if lp:
                try: pdf.image(lp, x=LM, y=12, h=11)
                except Exception: pass
                try: _os.remove(lp)
                except Exception: pass
        pdf.set_draw_color(*PRIM); pdf.set_line_width(1.0)
        pdf.line(LM, 26, LM + W, 26)
        pdf.set_xy(LM, 29); pdf.set_text_color(26, 35, 50); pdf.set_font("Helvetica", "B", 15)
        pdf.cell(W, 8, L("Termo de Responsabilidade e Entrega de Equipamentos"), ln=1, align="C")
        X(); pdf.set_font("Helvetica", "", 9); pdf.set_text_color(90, 102, 120)
        pdf.cell(W, 5, L("No " + st.get("numero", "") + "  -  Emitido em " + st.get("data", "") +
                         "  -  Empresa Exemplo S.A."), ln=1, align="C")
        pdf.ln(4)
        def sectitle(t):
            X(); pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(*PRIM)
            pdf.cell(W, 6, L(t), ln=1); pdf.set_text_color(40, 46, 58)
        def kv(k, v):
            X(); pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(120, 128, 140)
            pdf.cell(38, 5.5, L(k), ln=0)
            pdf.set_font("Helvetica", "", 10); pdf.set_text_color(26, 35, 50)
            pdf.multi_cell(W - 38, 5.5, L(v))
        solic = st.get("solic", {}); ti = st.get("ti", {})
        ics = st.get("ics") or ([st.get("ic", {})] if st.get("ic", {}).get("chave") else [])
        status = st.get("status", "")
        sectitle("Beneficiario / Solicitante")
        kv("Nome", solic.get("nome", "")); kv("E-mail", solic.get("email", ""))
        kv("Empresa", solic.get("empresa", "")); kv("Emissao", st.get("data", ""))
        pdf.ln(1)
        sectitle("Equipamentos / Itens de Configuracao")
        c1, c2, c3, c4 = 10.0, 80.0, 45.0, W - 135.0
        X(); pdf.set_font("Helvetica", "B", 8); pdf.set_fill_color(250, 243, 236); pdf.set_text_color(120, 128, 140)
        pdf.cell(c1, 6.5, "#", fill=True); pdf.cell(c2, 6.5, L("Equipamento / IC"), fill=True)
        pdf.cell(c3, 6.5, L("No de Serie"), fill=True); pdf.cell(c4, 6.5, L("Patrimonio"), fill=True, ln=1)
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(26, 35, 50)
        for i, it in enumerate(ics):
            X()
            pdf.cell(c1, 6.5, str(i + 1), border="B")
            pdf.cell(c2, 6.5, L(it.get("nome", ""))[:46], border="B")
            pdf.cell(c3, 6.5, L(it.get("serial", "") or "-"), border="B")
            pdf.cell(c4, 6.5, L(it.get("patrimonio", "") or "-"), border="B", ln=1)
        pdf.ln(2)
        acess = (st.get("acessorios", "") or "").strip()
        if acess:
            sectitle("Perifericos e acessorios entregues")
            X(); pdf.set_font("Helvetica", "", 10); pdf.multi_cell(W, 5.5, L(acess))
        cond = (st.get("estado", "") or "").strip()
        if cond:
            sectitle("Condicao do equipamento")
            X(); pdf.set_font("Helvetica", "", 10); pdf.multi_cell(W, 5.5, L(cond))
        pdf.ln(1)
        sectitle("Clausulas e Condicoes")
        pdf.set_font("Helvetica", "", 8.5); pdf.set_text_color(60, 68, 82)
        for c in [
            "Declaro ser responsavel pela guarda e bom uso dos equipamentos recebidos, utilizando-os exclusivamente para fins profissionais e conforme as normas da Empresa. Login e senha sao de uso pessoal e intransferivel; comunicarei a TI qualquer uso indevido ou quebra de sigilo.",
            "Comprometo-me a nao instalar softwares nao homologados e a nao utilizar licencas da Empresa em equipamentos particulares, zelando pela conservacao do equipamento.",
            "Em caso de rescisao do contrato de trabalho, devolverei imediatamente os bens da Empresa Exemplo S.A., sob pena de desconto do valor de mercado de cada item deste termo.",
            "Caso os equipamentos estejam danificados por mau uso ou extraviados, reconheco a obrigacao de ressarcimento (art. 462 da CLT), podendo ser descontado de forma parcelada.",
            "No ato da rescisao do contrato de trabalho, os dispositivos deverao ser devolvidos ao departamento de Recursos Humanos.",
        ]:
            X(); pdf.multi_cell(W, 4.4, L(c))
        X(); pdf.set_font("Helvetica", "", 6.5); pdf.set_text_color(130, 120, 110)
        pdf.multi_cell(W, 3.6, L("LGPD (Lei 13.709/2018): a EMPRESA EXEMPLO S.A. declara que os dados aqui "
                               "solicitados sao estritamente necessarios para a execucao legal deste termo."))
        pdf.ln(2)
        sectitle("Assinaturas")
        colw = W / 2.0; y0 = pdf.get_y() + 1
        def assina(x, titulo, nome, cpf, org, img, dt_iso, tid):
            pdf.set_xy(x, y0); pdf.set_font("Helvetica", "B", 7.5); pdf.set_text_color(120, 128, 140)
            pdf.cell(colw - 8, 4, L(titulo), ln=2)
            pdf.set_x(x); pdf.set_font("Helvetica", "", 6.5); pdf.set_text_color(140, 150, 165)
            pdf.cell(colw - 8, 3.5, L("Assinado por:"), ln=2)
            ytop = pdf.get_y()
            if img:
                p = _png_tmp(img)
                if p:
                    try: pdf.image(p, x=x + 2, y=ytop, w=34, h=12)
                    except Exception: pass
                    try: _os.remove(p)
                    except Exception: pass
            yln = ytop + 13
            pdf.set_draw_color(180, 190, 205); pdf.set_line_width(0.2); pdf.line(x, yln, x + colw - 12, yln)
            if tid:
                pdf.set_xy(x, yln + 0.5); pdf.set_font("Helvetica", "", 6); pdf.set_text_color(150, 160, 175)
                pdf.cell(colw - 8, 3, L("ID: " + tid), ln=2)
            pdf.set_x(x); pdf.set_font("Helvetica", "B", 8.5); pdf.set_text_color(26, 35, 50)
            pdf.cell(colw - 8, 4.5, L(nome), ln=2)
            if org:
                pdf.set_x(x); pdf.set_font("Helvetica", "", 7.5); pdf.set_text_color(60, 68, 82)
                pdf.multi_cell(colw - 8, 3.8, L(org))
            if cpf:
                pdf.set_x(x); pdf.set_font("Helvetica", "", 7.5); pdf.set_text_color(60, 68, 82)
                pdf.cell(colw - 8, 4, L("CPF: " + cpf), ln=2)
            if dt_iso:
                pdf.set_x(x); pdf.set_font("Helvetica", "", 6.5); pdf.set_text_color(120, 128, 140)
                pdf.cell(colw - 8, 3.6, L("Assinado em " + _dtext(dt_iso)), ln=2)
        _razao = str(memoria.get("CST_RazaoSocial", "") or "").strip() or "Empresa Exemplo S.A."
        assina(LM, "Responsavel de TI (Emissor)", _razao, ti.get("cpf", ""),
               "Representada por " + ti.get("nome", ""),
               st.get("sig_ti", ""), st.get("sig_ti_dt", ""), st.get("sig_ti_tid", ""))
        assina(LM + colw, "Beneficiario / Solicitante", solic.get("nome", ""), solic.get("cpf", ""), "",
               st.get("sig_solic", ""), st.get("sig_solic_dt", ""), st.get("sig_solic_tid", ""))
        pdf.set_y(y0 + 44)
        if status == "concluido":
            sectitle("Evidencias da assinatura eletronica")
            yev = pdf.get_y()
            def _ev(x, tit, papel, nome):
                pdf.set_xy(x, yev)
                pdf.set_font("Helvetica", "B", 7); pdf.set_text_color(120, 128, 140)
                pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L(tit))
                pdf.set_font("Helvetica", "", 6.5); pdf.set_text_color(90, 102, 120)
                pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L(nome))
                dt = st.get("sig_" + papel + "_dt", "")
                if dt:
                    pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L("Assinado em " + _dtext(dt)))
                ac = st.get("sig_" + papel + "_aceite_dt", "")
                if ac:
                    pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L("Aceite: " + _dtext(ac)))
                ip = st.get("sig_" + papel + "_ip", "")
                if ip:
                    pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L("IP: " + str(ip)))
                ua = st.get("sig_" + papel + "_ua", "")
                if ua:
                    pdf.set_x(x); pdf.multi_cell(colw - 6, 3.6, L("Dispositivo: " + str(ua)[:90]))
                return pdf.get_y()
            y1 = _ev(LM, "Responsavel de TI (Emissor)", "ti", ti.get("nome", ""))
            y2 = _ev(LM + colw, "Beneficiario / Solicitante", "solic", solic.get("nome", ""))
            pdf.set_y(max(y1, y2) + 1)
            email_dest = solic.get("email", "")
            if email_dest:
                X(); pdf.set_font("Helvetica", "", 6.5); pdf.set_text_color(90, 102, 120)
                pdf.multi_cell(W, 3.6, L("Link de assinatura enviado para: " + email_dest))
            X(); pdf.set_font("Helvetica", "", 6.5); pdf.multi_cell(W, 3.6, L("Integridade do documento (hash): " + st.get("hash", "")))
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)

    def doc_html(st, modo):
        tmpl = _unz(_DOC_B64)
        MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        def dt_extenso(iso):
            try:
                d = datetime.strptime(str(iso)[:19], "%Y-%m-%d %H:%M:%S")
                return str(d.day) + " de " + MESES[d.month] + " de " + str(d.year) + " " + d.strftime("%H:%M:%S")
            except Exception:
                return esc(str(iso or ""))
        def sign_caption(nome, dt_iso):
            if not dt_iso:
                return '<div class="sign-caption">' + esc(nome) + '</div>'
            return ('<div class="sign-caption">' + esc(nome) +
                    '<span class="meta">Assinado em ' + dt_extenso(dt_iso) + '</span></div>')
        def ds_bloco(titulo_topo, representante, cpf, img, dt_iso, tid):
            tid_html = '<span class="ds-tid">' + ('ID: ' + esc(tid) if tid else '') + '</span>'
            dados = '<div class="nm">' + esc(titulo_topo) + '</div>'
            if representante:
                dados += '<div class="org">Representada por: <b>' + esc(representante) + '</b></div>'
            if cpf:
                dados += '<div class="kv">CPF: <b>' + esc(cpf) + '</b></div>'
            if dt_iso:
                dados += '<div class="kv" style="margin-top:3px"><span class="meta">Assinado em ' + dt_extenso(dt_iso) + '</span></div>'
            return ('<div class="ds-sig"><div class="ds-label">Assinado por:</div>'
                    '<div class="ds-frame"><img class="sign-img" src="' + img + '">' + tid_html + '</div>'
                    '<div class="ds-data">' + dados + '</div></div>')
        ic = st.get("ic", {}); solic = st.get("solic", {}); ti = st.get("ti", {})
        ics = st.get("ics") or ([ic] if ic.get("chave") else [])
        linhas_ic = ""
        for i, it in enumerate(ics):
            linhas_ic += ('<tr><td class="ic-n">' + str(i + 1) + '</td>'
                '<td><b>' + esc(it.get("nome", "")) + '</b> <span class="tag">IC #' + esc(it.get("chave", "")) + '</span></td>'
                '<td><span class="tag">' + esc(it.get("serial", "") or "-") + '</span></td>'
                '<td>' + esc(it.get("patrimonio", "") or "-") + '</td></tr>')
        ic_lista = ('<table class="ic-table"><thead><tr><th style="width:36px">#</th><th>Equipamento / IC</th>'
                    '<th>Nº de Série</th><th>Patrimônio</th></tr></thead><tbody>' + linhas_ic + '</tbody></table>')
        sig_ti = st.get("sig_ti", ""); sig_solic = st.get("sig_solic", "")
        status = st.get("status", "")
        badge = "Concluido" if status == "concluido" else "Aguardando assinatura"
        aviso = ""
        if modo == "ti":
            aviso = '<div class="aviso">Assine abaixo como responsavel de TI. Ao confirmar, o solicitante recebe o link por e-mail.</div>'
        elif modo == "solic":
            aviso = '<div class="aviso">Confira o equipamento e os dados. Desenhe sua assinatura e confirme o recebimento.</div>'
        if sig_ti:
            _razao = str(memoria.get("CST_RazaoSocial", "") or "").strip() or "Empresa Exemplo S.A."
            area_ti = ds_bloco(_razao, ti.get("nome", ""), ti.get("cpf", ""),
                               sig_ti, st.get("sig_ti_dt", ""), st.get("sig_ti_tid", ""))
        elif modo == "ti":
            area_ti = '<div class="canvas-wrap"><canvas id="cnv_ti"></canvas></div><div class="sign-tools"><button type="button" class="btn btn-ghost" onclick="limpar(\'ti\')">Limpar</button></div>'
        else:
            area_ti = '<div style="color:#999;font-size:12px;padding:20px;text-align:center;border:1px dashed #ddd;border-radius:6px">Aguardando assinatura</div>'
        if sig_solic:
            area_solic = ds_bloco(solic.get("nome", ""), "", solic.get("cpf", ""),
                                  sig_solic, st.get("sig_solic_dt", ""), st.get("sig_solic_tid", ""))
        elif modo == "solic":
            area_solic = '<div class="canvas-wrap"><canvas id="cnv_solic"></canvas></div><div class="sign-tools"><button type="button" class="btn btn-ghost" onclick="limpar(\'solic\')">Limpar</button></div>'
        else:
            area_solic = '<div style="color:#999;font-size:12px;padding:20px;text-align:center;border:1px dashed #ddd;border-radius:6px">Aguardando assinatura</div>'
        if modo in ("ti", "solic"):
            action = '<div class="action-bar"><button class="btn btn-ghost" onclick="gerarPDF()">Gerar PDF</button><button class="btn btn-primary" id="btnAssinar" onclick="assinar()">Confirmar assinatura</button></div>'
        else:
            action = '<div class="action-bar"><button class="btn btn-ghost" onclick="gerarPDF()">Gerar PDF</button></div>'
        aceite_html = ""
        if modo in ("ti", "solic"):
            aceite_html = ('<div class="aceite"><input type="checkbox" id="chkAceite" onclick="toggleAceite()">'
                '<label for="chkAceite">Declaro que <b>li e concordo</b> com as cláusulas e condições deste Termo de '
                'Responsabilidade e confirmo, por minha assinatura eletrônica, o seu aceite.</label></div>')
        evidencias_html = ""
        if status == "concluido":
            def _ev(titulo, papel):
                nome = ti.get("nome", "") if papel == "ti" else solic.get("nome", "")
                dt = st.get("sig_" + papel + "_dt", "")
                ip = st.get("sig_" + papel + "_ip", "")
                ua = st.get("sig_" + papel + "_ua", "")
                aceite_dt = st.get("sig_" + papel + "_aceite_dt", "")
                partes = ('<div class="ev"><b>' + esc(titulo) + '</b>'
                    + esc(nome)
                    + ('<br>Assinado em ' + dt_extenso(dt) if dt else "")
                    + ('<br>Aceite das cláusulas: ' + dt_extenso(aceite_dt) if aceite_dt else "")
                    + ('<br>IP: <span class="mono">' + esc(ip) + '</span>' if ip else "")
                    + ('<br>Dispositivo: <span class="mono">' + esc(ua) + '</span>' if ua else "")
                    + '</div>')
                return partes
            email_dest = solic.get("email", "")
            evidencias_html = ('<div class="evidencias"><h4>Evidências da assinatura eletrônica</h4>'
                '<div class="ev-grid">'
                + _ev("Responsável de TI (Emissor)", "ti")
                + _ev("Beneficiário / Solicitante", "solic")
                + '</div>'
                + ('<div class="ev" style="margin-top:10px">Link de assinatura enviado para: <span class="mono">' + esc(email_dest) + '</span></div>' if email_dest else "")
                + '<div class="ev" style="margin-top:6px">Integridade do documento (hash): <span class="mono">' + esc(st.get("hash", "")) + '</span></div>'
                '</div>')
        acessorios_box = ""
        _acess_raw = st.get("acessorios", "") or ""
        _acess_itens = [a.strip() for a in str(_acess_raw).split(",") if a.strip()]
        if _acess_itens:
            _chips = "".join(['<span>' + esc(a) + '</span>' for a in _acess_itens])
            acessorios_box = ('<div class="box" style="margin-bottom:22px">'
                '<h3>Periféricos e acessórios entregues</h3>'
                '<div class="acess">' + _chips + '</div></div>')
        rep = {
            "{{NUMERO_TERMO}}": esc(st.get("numero", "")), "{{DATA_EMISSAO}}": esc(st.get("data", "")),
            "{{STATUS_BADGE}}": esc(badge), "{{AVISO_HTML}}": aviso,
            "{{SOLIC_NOME}}": esc(solic.get("nome", "")), "{{SOLIC_EMAIL}}": esc(solic.get("email", "")),
            "{{CLIENTE_NOME}}": esc(solic.get("empresa", "")), "{{IC_NOME}}": esc(ic.get("nome", "")),
            "{{IC_LISTA}}": ic_lista,
            "{{ACESSORIOS_BOX}}": acessorios_box,
            "{{IC_CHAVE}}": esc(ic.get("chave", "")), "{{IC_SERIAL}}": esc(ic.get("serial", "")),
            "{{IC_PATRIMONIO}}": esc(ic.get("patrimonio", "")), "{{TI_NOME}}": esc(ti.get("nome", "")),
            "{{SIGN_TI_AREA}}": area_ti, "{{SIGN_SOLIC_AREA}}": area_solic,
            "{{SOLIC_ORG_HTML}}": ('<span class="who-org">' + esc(solic.get("empresa", "")) + '</span>') if solic.get("empresa", "") else "",
            "{{ACEITE_HTML}}": aceite_html, "{{EVIDENCIAS_HTML}}": evidencias_html,
            "{{HASH}}": esc(st.get("hash", "")), "{{ACTION_BAR}}": action,
            "{{WEBHOOK}}": WEBHOOK, "{{MODO}}": modo, "{{TOKEN_SIG}}": esc(st.get("token", "")),
        }
        for k, v in rep.items():
            tmpl = tmpl.replace(k, v)
        return tmpl

    if case in ("", "carregar"):
        ics_map = {}; opts_ic = []
        for it in ics_lista():
            ch = str(it.get("Chave", "")); nome = it.get("Nome", "") or ""
            tipo = ""
            ta = it.get("TipodeAtivo")
            if isinstance(ta, list) and len(ta) > 0 and isinstance(ta[0], dict):
                tipo = str(ta[0].get("text", "") or "")
            ics_map[ch] = {"nome": nome, "serial": it.get("SerialNum", "") or "", "termo": it.get("TermoResp", "N") or "N", "status": "", "prop": "", "tipo": tipo}
            opts_ic.append('<option value="' + esc(ch) + '">' + esc(ch + " - " + nome) + '</option>')
        solics_map = {}; opts_sol = []
        for u in usuarios():
            uid = str(u.get("Chave", "")); nome = (str(u.get("Nome", "")) + " " + str(u.get("Sobrenome", ""))).strip()
            email = u.get("Email", "") or ""; emp = str(u.get("Cliente", "") or "")
            solics_map[uid] = {"nome": nome, "email": email, "empresa": emp}
            opts_sol.append('<option value="' + esc(uid) + '">' + esc(nome + " (" + email + ")") + '</option>')
        emiss = []
        for row in tbl_list():
            emiss.append({"numero": row.get("Campo27", ""), "data": row.get("Campo28", ""),
                "cod_ic": row.get("Campo26", ""), "ic_nome": row.get("Campo33", ""),
                "signatarios": row.get("Campo30", ""), "status": row.get("Campo31", ""),
                "num_chamado": row.get("Campo34", ""),
                "acessorios": row.get("Campo35", ""),
                "observacoes": row.get("Campo36", ""),
                "condicao": row.get("Campo37", ""),
                "termo_url": row.get("Campo29", "")})
        emiss.reverse()
        ops_map = {}; opts_op = []
        for op in operadores():
            oid = str(op.get("Chave", "")); onome = (str(op.get("Nome", "")) + " " + str(op.get("Sobrenome", ""))).strip()
            if not onome:
                continue
            ops_map[oid] = {"nome": onome, "email": op.get("Email", "") or ""}
            opts_op.append('<option value="' + esc(oid) + '">' + esc(onome) + '</option>')
        op_id = str(g("operador_cod", "") or g("operador_id", "")).strip()
        op_nome = ""
        if op_id and op_id in ops_map:
            op_nome = ops_map[op_id]["nome"]
        if not op_nome:
            op_nome = str(g("operador_nome", "")).strip() or "Operador"
        html = _unz(_EMBED_B64)
        html = html.replace("{{WEBHOOK}}", WEBHOOK).replace("{{OPERADOR_ID}}", esc(op_id)).replace("{{OPERADOR_NOME}}", esc(op_nome))
        html = html.replace("{{IC_OPTS}}", "".join(opts_ic)).replace("{{SOLIC_OPTS}}", "".join(opts_sol))
        html = html.replace("{{OP_OPTS}}", "".join(opts_op))
        html = html.replace("{{ICS_JSON}}", json.dumps(ics_map, ensure_ascii=False))
        html = html.replace("{{SOLICS_JSON}}", json.dumps(solics_map, ensure_ascii=False))
        html = html.replace("{{OPS_JSON}}", json.dumps(ops_map, ensure_ascii=False))
        html = html.replace("{{EMISSOES_JSON}}", json.dumps(emiss, ensure_ascii=False))
        return html_resp(html)

    if case == "reset_seq":
        ano = str(g("ano", "")).strip() or str((datetime.now() - timedelta(hours=3)).year)
        try:
            valor = int(str(g("valor", "0")).strip() or "0")
        except Exception:
            valor = 0
        ok = stg_raw_set("seq_" + ano, valor)
        atual = stg_raw_get("seq_" + ano)
        return json_resp({"ok": bool(ok), "ano": ano, "seq_agora": atual,
                          "proximo_estimado": "TR-" + ano + "-" + str(int(atual or 0) + 1).zfill(4)})

    if case == "emitir":
        cod_ics_raw = str(g("cod_ics", "")).strip() or str(g("cod_ic", "")).strip()
        cod_ic_list = [c.strip() for c in cod_ics_raw.split(",") if c.strip()]
        solic_id = str(g("solicitante_id", "")).strip()
        op_id = str(g("operador_id", "")).strip(); op_nome = str(g("operador_nome", "")).strip() or "Responsavel TI"
        estado = str(g("estado", "")); acess = str(g("acessorios", "")); sig_ti = str(g("sig_ti", ""))
        num_chamado = str(g("num_chamado", "")).strip()
        observacoes = str(g("observacoes", "")).strip()
        if not cod_ic_list or not solic_id:
            return json_resp({"ok": False, "mensagem": "Selecione ao menos um equipamento e o solicitante."})
        if not num_chamado:
            return json_resp({"ok": False, "mensagem": "Informe o numero do chamado (Desk Manager)."})
        ics = []
        prop = ""
        for cic in cod_ic_list:
            tic = ic_dados(cic)
            if not prop:
                pc0 = tic.get("ProprietarioCliente") or []
                if pc0 and isinstance(pc0, list):
                    prop = pc0[0].get("text", "")
            ics.append({"chave": cic, "nome": tic.get("Nome", "") or ("IC " + cic),
                        "serial": tic.get("SerialNum", "") or "", "patrimonio": tic.get("Patrimonio", "") or ""})
        s_nome, s_email, s_emp, s_cpf = "", "", prop, ""
        for u in usuarios():
            if str(u.get("Chave", "")) == solic_id:
                s_nome = (str(u.get("Nome", "")) + " " + str(u.get("Sobrenome", ""))).strip()
                s_email = u.get("Email", "") or ""; s_emp = str(u.get("Cliente", "") or prop); break
        _cpf_key = str(memoria.get("CST_CampoCPF", "") or "").strip() or "ID_DO_CAMPO_CPF"
        try:
            du = requests.post(API + "/Usuarios", headers=Hj, json={"Chave": str(solic_id)}, timeout=60).json()
            ceg = (du.get("TCampoExtraGeral", {}) or {}) if isinstance(du, dict) else {}
            s_cpf = str(ceg.get("_" + _cpf_key, "") or ceg.get(_cpf_key, "") or "")
        except Exception:
            pass
        ano = str((datetime.now() - timedelta(hours=3)).year)
        numero = proximo_numero(ano)
        agora = datetime.now() - timedelta(hours=3)
        data_em = agora.strftime("%d-%m-%Y"); expira = (agora + timedelta(days=10)).strftime("%d-%m-%Y")
        token = hashlib.sha256((numero + str(random.random()) + str(agora.timestamp())).encode("utf-8")).hexdigest()[:40]
        codigos_join = ",".join([i["chave"] for i in ics])
        nomes_join = " | ".join([i["nome"] for i in ics])
        h = hashlib.sha256((numero + "|" + codigos_join + "|" + solic_id + "|" + data_em).encode("utf-8")).hexdigest()[:16]
        signat = op_nome + " (TI) | " + s_nome + " (Solicitante)"
        ic_primeiro = ics[0] if ics else {"chave": "", "nome": "", "serial": "", "patrimonio": ""}
        _agora_ti = agora.strftime("%Y-%m-%d %H:%M:%S")
        _tid_ti = hashlib.sha256((token + "|ti|" + _agora_ti).encode("utf-8")).hexdigest()[:16].upper() if sig_ti else ""
        estado_obj = {"numero": numero, "data": data_em, "status": "aguardando_usuario",
            "token": token, "hash": h, "expira": expira,
            "ics": ics, "ic": ic_primeiro,
            "solic": {"id": solic_id, "nome": s_nome, "email": s_email, "empresa": s_emp, "cpf": s_cpf},
            "ti": {"id": op_id, "nome": op_nome, "cpf": ""}, "sig_ti": sig_ti, "sig_solic": "",
            "sig_ti_dt": (_agora_ti if sig_ti else ""), "sig_solic_dt": "",
            "sig_ti_tid": _tid_ti,
            "sig_ti_ip": (ip_servidor() if sig_ti else ""),
            "sig_ti_ua": (str(g("ua", ""))[:300] if sig_ti else ""),
            "sig_ti_aceite_dt": (agora.strftime("%Y-%m-%d %H:%M:%S") if sig_ti else ""),
            "acessorios": acess, "estado": estado, "num_chamado": num_chamado,
            "observacoes": observacoes}
        stg_save(token, estado_obj)
        tbl_put({"Chave": "", "Campo26": codigos_join, "Campo27": numero, "Campo28": data_em,
            "Campo29": "", "Campo30": signat, "Campo31": "aguardando_usuario",
            "Campo32": token, "Campo33": nomes_join, "Campo34": num_chamado,
            "Campo35": acess, "Campo36": observacoes, "Campo37": estado})
        sep = "&" if "?" in WEBHOOK else "?"
        link_ext = WEBHOOK + sep + "get=true&case=ver&token_sig=" + token
        qtd_txt = (str(len(ics)) + " equipamentos") if len(ics) != 1 else ("1 equipamento (" + esc(nomes_join) + ")")
        email_status = "sem_email"
        if s_email:
            try:
                corpo = ("<p>Ola " + esc(s_nome) + ",</p><p>Foi emitido o Termo de Responsabilidade <b>" + numero +
                    "</b> referente a <b>" + qtd_txt + "</b>.</p>"
                    "<p>Para revisar e <b>assinar</b>, copie e cole o endereco abaixo no seu navegador (valido por 10 dias):</p>"
                    "<p style='margin:14px 0;padding:12px;background:#f4f6f9;border:1px solid #e1e4e8;border-radius:6px;word-break:break-all;font-size:13px'>" + link_ext + "</p>"
                    "<p style='text-align:center;margin:16px 0'><a href='" + link_ext + "' style='background:#e8630a;color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:600'>Assinar Termo</a></p>"
                    "<p style='font-size:12px;color:#888'>Desk Manager - Empresa Exemplo S.A.</p>")
                nt = {"TNotificacao": {"Chave": "", "Assunto": "Assinatura do Termo " + numero,
                    "Conteudo": corpo, "DataInicial": data_em, "HoraInicial": "00:00", "EnviarEmail": "on",
                    "DataFinal": expira, "HoraFinal": "23:59", "CodUsuario": [solic_id]}}
                ch_not = ""
                try:
                    import urllib.parse as _upn
                    body_nt = "Dados=" + _upn.quote(json.dumps(nt, ensure_ascii=False)) + "&Menu=Notificacoes&App=Ticket"
                    rc = maestroutils.apiDeskManager(spath="Notificacoes", smethod="PUT",
                        sbody=body_nt, sContentType="application/x-www-form-urlencoded; charset=UTF-8", sauth=TK)
                    rj = rc.get("responsejson", rc) if isinstance(rc, dict) else rc
                    ch_not = str(rj).strip().strip('"') if not isinstance(rj, dict) else str(rj.get("root", rj)).strip().strip('"')
                except Exception as e:
                    ch_not = ""; email_status = "erro_criar:" + str(e)[:80]
                if ch_not and ch_not.isdigit():
                    try:
                        rc2 = maestroutils.apiDeskManager(spath="Notificacoes/enviaragora", smethod="PUT",
                            sbody="Chave=" + ch_not + "&App=Ticket",
                            sContentType="application/x-www-form-urlencoded; charset=UTF-8", sauth=TK)
                        email_status = "enviado:" + ch_not
                    except Exception:
                        email_status = "criado:" + ch_not
                elif not email_status or email_status == "sem_email":
                    email_status = "falha_criar:" + str(ch_not)[:80]
            except Exception as e:
                email_status = "erro:" + str(e)[:60]
        return json_resp({"ok": True, "numero_termo": numero, "email": s_email, "email_status": email_status, "link": link_ext,
            "emissao": {"numero": numero, "data": data_em, "cod_ic": codigos_join, "ic_nome": nomes_join,
                "signatarios": signat, "status": "aguardando_usuario", "num_chamado": num_chamado, "termo_url": ""}})

    if case == "consultar":
        emiss = []
        for row in tbl_list():
            emiss.append({"numero": row.get("Campo27", ""), "data": row.get("Campo28", ""),
                "cod_ic": row.get("Campo26", ""), "ic_nome": row.get("Campo33", ""),
                "signatarios": row.get("Campo30", ""), "status": row.get("Campo31", ""),
                "num_chamado": row.get("Campo34", ""),
                "acessorios": row.get("Campo35", ""),
                "observacoes": row.get("Campo36", ""),
                "condicao": row.get("Campo37", ""),
                "termo_url": row.get("Campo29", "")})
        emiss.reverse()
        return json_resp({"ok": True, "emissoes": emiss})

    if case == "ver":
        token = str(g("token_sig", "")).strip()
        st = stg_get(token) if token else {}
        if not st:
            return html_resp("<!DOCTYPE htm><meta charset=utf-8><body style='font-family:Inter,Arial;padding:40px;text-align:center'><h2>Link invalido ou expirado</h2><p>Termo nao encontrado.</p></body>", externo=True)
        if st.get("status") == "concluido":
            return html_resp(doc_html(st, "view"), externo=True)
        return html_resp(doc_html(st, "solic"), externo=True)

    if case == "assinar":
        token = str(g("token_sig", "")).strip()
        papel = str(g("papel", "solic")).strip().lower()
        assinatura = str(g("assinatura", ""))
        ua_cli = str(g("ua", ""))[:300]
        ip_cli = (ip_servidor() or str(g("ip_cli", "")))[:60]
        aceite = str(g("aceite", "")).strip().lower() in ("1", "true", "s", "sim", "on")
        st = stg_get(token) if token else {}
        if not st:
            return json_resp({"ok": False, "mensagem": "Termo nao encontrado."})
        if st.get("status") == "concluido":
            return json_resp({"ok": True, "mensagem": "Este termo ja esta concluido."})
        agora_sig = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        _tid = hashlib.sha256((token + "|" + papel + "|" + agora_sig).encode("utf-8")).hexdigest()[:16].upper()
        if papel == "ti":
            st["sig_ti"] = assinatura
            st["sig_ti_dt"] = agora_sig
            st["sig_ti_ip"] = ip_cli
            st["sig_ti_ua"] = ua_cli
            st["sig_ti_tid"] = _tid
            if aceite:
                st["sig_ti_aceite_dt"] = agora_sig
        else:
            st["sig_solic"] = assinatura
            st["sig_solic_dt"] = agora_sig
            st["sig_solic_ip"] = ip_cli
            st["sig_solic_ua"] = ua_cli
            st["sig_solic_tid"] = _tid
            if aceite:
                st["sig_solic_aceite_dt"] = agora_sig
        finalizou = bool(st.get("sig_ti")) and bool(st.get("sig_solic"))
        termo_url = ""
        rowchave = ""
        for row in tbl_list():
            if str(row.get("Campo32", "")) == token:
                rowchave = str(row.get("Chave", "")); break
        if finalizou:
            st["status"] = "concluido"
            doc = doc_html(st, "view")
            try:
                termo_url = maestroutils.base64toURLForceExt(base64.b64encode(doc.encode("utf-8")).decode("ascii"), "html", "html")
            except Exception:
                try:
                    termo_url = maestroutils.base64toURL(base64.b64encode(doc.encode("utf-8")).decode("ascii"))
                except Exception:
                    termo_url = ""
            st["termo_url"] = termo_url
            _termo_pdf_b64 = ""
            try:
                _termo_pdf_b64 = base64.b64encode(termo_pdf_bytes(st)).decode("ascii")
                st["pdf_ok"] = "bytes:" + str(len(_termo_pdf_b64))
            except Exception as _epdf:
                _termo_pdf_b64 = ""
                st["pdf_ok"] = "erro:" + str(_epdf)[:120]
            ics_grava = st.get("ics") or ([st.get("ic", {})] if st.get("ic", {}).get("chave") else [])
            solic_id_termo = str(st.get("solic", {}).get("id", "") or "").strip()
            grav_res = []
            for _icitem in ics_grava:
                cod_ic = str(_icitem.get("chave", "") or "").strip()
                if not cod_ic:
                    continue
                tic = ic_dados(cod_ic)
                attrs = []
                for a in (tic.get("Atributo") or []):
                    nome = a.get("id", "")
                    if nome == "Termo de Responsabilidade": continue
                    attrs.append({"Chave": "", "Nome": nome, "Valor": a.get("text", ""), "Ex": ""})
                attrs.append({"Chave": "", "Nome": "Termo de Responsabilidade", "Valor": termo_url, "Ex": ""})
                tp = {"Chave": str(cod_ic), "Nome": tic.get("Nome", ""), "SerialNum": tic.get("SerialNum", ""),
                      "TermoResp": "S"}
                ta = tic.get("TipodeAtivo") or []
                if ta: tp["TipodeAtivo"] = ta[0].get("id", "")
                pc = tic.get("ProprietarioCliente") or []
                ps = tic.get("ProprietarioSolicitante") or []
                pa = tic.get("ProprietarioArea") or []
                if pc: tp["ProprietarioCliente"] = pc[0].get("id", "")
                elif ps: tp["ProprietarioSolicitante"] = ps[0].get("id", "")
                elif pa: tp["ProprietarioArea"] = pa[0].get("id", "")
                if solic_id_termo:
                    tp["AlocadoSolicitante"] = solic_id_termo
                else:
                    ac = tic.get("AlocadoCliente") or []
                    asl = tic.get("AlocadoSolicitante") or []
                    aa = tic.get("AlocadoArea") or []
                    if ac: tp["AlocadoCliente"] = ac[0].get("id", "")
                    elif asl: tp["AlocadoSolicitante"] = asl[0].get("id", "")
                    elif aa: tp["AlocadoArea"] = aa[0].get("id", "")
                try:
                    _ric = requests.put(API + "/ICs", headers=Hj, json={"TIc": tp, "TAtributos": attrs}, timeout=60)
                    grav_res.append(cod_ic + ":" + _ric.text[:40])
                except Exception as _e:
                    try:
                        _ric = maestroutils.apiDeskManager(spath="ICs", smethod="PUT",
                            sbody=json.dumps({"TIc": tp, "TAtributos": attrs}),
                            sContentType="application/json", sauth=TK)
                        grav_res.append(cod_ic + ":MU:" + ((str(_ric.get("responsejson", _ric)) if isinstance(_ric, dict) else str(_ric))[:40]))
                    except Exception as _e2:
                        grav_res.append(cod_ic + ":exc:" + str(_e2)[:40])
                try:
                    if _termo_pdf_b64:
                        _anic = requests.put("https://files.desk.ms/v1/enviar",
                            headers={"Authorization": TK, "Content-Type": "application/json"},
                            json={"codic": str(cod_ic), "base64": _termo_pdf_b64,
                                  "type": "application/pdf", "name": st.get("numero", "termo") + ".pdf"},
                            timeout=90)
                    else:
                        _anic = requests.put("https://files.desk.ms/v1/enviar",
                            headers={"Authorization": TK, "Content-Type": "application/json"},
                            json={"codic": str(cod_ic), "base64": base64.b64encode(doc.encode("utf-8")).decode("ascii"),
                                  "type": "text/html", "name": st.get("numero", "termo") + ".html"},
                            timeout=90)
                    grav_res.append(cod_ic + ":anexoIC:" + _anic.text[:50])
                except Exception as _e:
                    grav_res.append(cod_ic + ":anexoIC_exc:" + str(_e)[:50])
            st["ic_grav"] = " | ".join(grav_res)
            if rowchave:
                try:
                    if _termo_pdf_b64:
                        _raw = base64.b64decode(_termo_pdf_b64)
                        _anx = requests.put("https://files.desk.ms/v1/enviar",
                            headers={"Authorization": TK, "Content-Type": "application/json"},
                            json={"codtable": str(rowchave), "tables": "TablesMaestro" + TABLE,
                                  "base64": _termo_pdf_b64,
                                  "type": "application/pdf", "name": st.get("numero", "termo") + ".pdf",
                                  "size": str(len(_raw))}, timeout=60)
                    else:
                        _anx = requests.put("https://files.desk.ms/v1/enviar",
                            headers={"Authorization": TK, "Content-Type": "application/json"},
                            json={"codtable": str(rowchave), "tables": "TablesMaestro" + TABLE,
                                  "base64": base64.b64encode(doc.encode("utf-8")).decode("ascii"),
                                  "type": "text/html", "name": st.get("numero", "termo") + ".html",
                                  "size": str(len(doc.encode("utf-8")))}, timeout=60)
                    st["anexo"] = _anx.text[:80]
                except Exception as _e:
                    st["anexo"] = "exc:" + str(_e)[:60]
        stg_save(token, st)
        if rowchave:
            upd = {"Chave": rowchave, "Campo31": st.get("status", "aguardando_usuario")}
            if finalizou:
                upd["Campo29"] = termo_url
            tbl_put(upd)
        if finalizou:
            fim = ("<!DOCTYPE htm><meta charset=utf-8><body style='font-family:Inter,Arial;padding:40px;text-align:center;background:#f4f6f9'>"
                   "<div style='max-width:520px;margin:40px auto;background:#fff;border:1px solid #e1e4e8;border-radius:12px;padding:36px'>"
                   "<div style='width:56px;height:56px;background:#ecfdf5;border:1px solid #a7f3d0;color:#198754;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 18px;font-size:28px'>&#10003;</div>"
                   "<h2 style='color:#7a3405'>Termo assinado com sucesso!</h2>"
                   "<p style='color:#555'>O Termo <b>" + esc(st.get("numero", "")) + "</b> foi concluido e registrado no equipamento no CMDB.</p>"
                   + ("<p style='margin-top:18px'><a href='" + termo_url + "' style='background:#e8630a;color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:600'>Abrir termo assinado</a></p>" if termo_url else "")
                   + "</div></body>")
            return json_resp({"ok": True, "sucesso": True, "finalizou": True, "mensagem": "Termo assinado e concluido!",
                    "termo_url": termo_url, "base64": base64.b64encode(fim.encode("utf-8")).decode("ascii")})
        return json_resp({"ok": True, "sucesso": True, "finalizou": False, "mensagem": "Assinatura registrada. Aguardando o solicitante."})

    return json_resp({"ok": False, "mensagem": "Caso nao reconhecido: " + case})

saida = run(memoria)

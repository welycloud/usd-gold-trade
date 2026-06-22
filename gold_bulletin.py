#!/usr/bin/env python3
import os, sys, subprocess, tempfile
from datetime import datetime
import pytz
from ddgs import DDGS
from groq import Groq

NTFY_URL = "https://ntfy.sh/USD-GOLD"
MODEL    = "llama-3.3-70b-versatile"
TZ_ET    = pytz.timezone("America/New_York")
TZ_CL    = pytz.timezone("America/Santiago")

DIAS_ES  = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]

PROMPT = """Actua como analista financiero especializado en ORO (XAU/USD).
Tienes datos frescos de la web. Usa SOLO esos datos, no inventes precios.
La fecha de HOY viene en los datos como HOY ES: — usala exactamente, no la cambies ni corrijas.

Redacta el boletin:
1) RESUMEN PRE-APERTURA (sesiones, DXY, bonos, sentiment).
2) CATALIZADORES DEL DIA (evento - hora Santiago - impacto - sesgo).
3) ANALISIS TECNICO (tendencia, soportes/resistencias, momentum).
4) PLAN OPERATIVO (COMPRA/VENTA/ESPERAR; entrada; SL; TP1; TP2; R:R; confianza; invalidacion).
5) ESCENARIO ALTERNATIVO.
6) NOTA DE RIESGO (SL obligatorio, max 1pct capital).
7) FUENTES: lista 3-5 URLs de los datos recibidos.

Formato para celular:
BOLETIN ORO - [fecha de HOY ES exacta] | 1h antes apertura NY
PRE-APERTURA: [...]
CATALIZADORES: [...]
TECNICO: Tendencia [..] | S [..] / R [..]
PLAN:
> [COMPRA/VENTA/ESPERAR] Entrada [..] SL [..] TP1 [..] TP2 [..]
> R:R [..] | Confianza [..] | Invalida si [..]
ALTERNATIVO: [..]
FUENTES:
- [titulo]: [URL]
- [titulo]: [URL]
- [titulo]: [URL]
Solo analisis, no asesoria.

DEVUELVE UNICAMENTE EL BOLETIN. DATOS:
{market_data}"""

def check_schedule():
    now = datetime.now(TZ_ET)
    if now.weekday() >= 5 or now.hour != 8:
        print(f"[SKIP] {now.strftime('%A %H:%M')} ET"); return False
    return True

def get_fecha_hoy():
    now = datetime.now(TZ_CL)
    return f"{DIAS_ES[now.weekday()]} {now.day} de {MESES_ES[now.month-1]} de {now.year}"

def search_ddg(q, n=3):
    try:
        results = DDGS().text(q, max_results=n)
        return "\n".join(f"[{r['href']}] {r['title']}: {r['body']}" for r in results)
    except Exception as e:
        return f"[error: {e}]"

def gather_data():
    now_et = datetime.now(TZ_ET).strftime("%Y-%m-%d %H:%M ET")
    fecha  = get_fecha_hoy()
    print(f"[INFO] Fecha Santiago: {fecha}")
    print("[INFO] Buscando datos...")
    parts = [f"=== HOY ES: {fecha} | {now_et} ==="]
    for label, q in [
        ("PRECIO XAU/USD", "XAU USD gold spot price today"),
        ("TECNICO",        "gold XAU USD technical analysis support resistance today"),
        ("DXY/BONOS",      "DXY dollar index US 10yr yield today"),
        ("CALENDARIO",     "economic calendar high impact events today forex"),
    ]:
        print(f"  -> {label}")
        parts.append(f"--- {label} ---\n{search_ddg(q)}")
    return "\n".join(parts)

def generate(data):
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    print(f"[INFO] Llamando {MODEL}...")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT.format(market_data=data)}],
        max_tokens=2048,
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()

def send_ntfy(text):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text); tmp = f.name
    try:
        r = subprocess.run(
            ["curl","-s","-w","\nHTTP:%{http_code}",
             "-H","Title: Boletin ORO","-H","Priority: high","-H","Tags: moneybag",
             "--data-binary",f"@{tmp}", NTFY_URL],
            capture_output=True, text=True, timeout=30)
        code = next((l.split(":")[1] for l in r.stdout.splitlines() if l.startswith("HTTP:")), "?")
        print(f"[ntfy] HTTP {code}"); return code == "200"
    finally:
        os.unlink(tmp)

def main():
    print(f"=== Boletin ORO | UTC {datetime.utcnow():%Y-%m-%d %H:%M} ===")
    # PRUEBA
    # if not check_schedule(): sys.exit(0)
    data = gather_data()
    bulletin = generate(data)
    if not bulletin: print("[ERROR] Sin respuesta"); sys.exit(1)
    print(bulletin[:300])
    if not send_ntfy(bulletin): sys.exit(1)
    print("[OK] Boletin enviado.")

if __name__ == "__main__": main()

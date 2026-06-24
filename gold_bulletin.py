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

PROMPT = """Eres un analista financiero y trader profesional que redacta un BOLETIN EJECUTIVO para XAU/USD.
Tu lector es inteligente pero tiene poco tiempo: debe entender la idea en 15 segundos.
Eres riguroso y prefieres decir "sin senal clara" antes que forzar un setup.

Tienes datos frescos de busquedas web que incluyen precio actual, analisis tecnico en multiples temporalidades,
nivel del dolar (DXY), rendimiento de bonos, noticias macro y calendario economico.
Usa SOLO esos datos. No inventes precios ni niveles.
La fecha exacta de hoy viene en los datos como HOY ES: — usala tal cual.

FORMATO DE SALIDA — respeta esta estructura y orden exactos:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOLETIN XAU/USD · [fecha de HOY ES exacta] · 8:30 AM ET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESUMEN EJECUTIVO (TL;DR)
Una sola frase con el veredicto. Ej: "Sesgo alcista en marcos mayores; se busca compra en retroceso hacia [nivel]."

SEMAFORO
Direccion:   COMPRA / VENTA / NO OPERAR
Confianza:   Alta / Media / Baja
Confluencia: Las temporalidades apuntan al mismo lado? Si / Parcial / No

LECTURA POR TEMPORALIDAD
Marco | Tendencia | Nota clave (1 linea)
  Semanal | Alza/Baja/Lateral | ...
  Diario  | Alza/Baja/Lateral | ...
  4H      | Alza/Baja/Lateral | ...
  1H      | Alza/Baja/Lateral | ...
"Lo mayor manda el sesgo; lo menor afina la entrada."

PLAN OPERATIVO
  Direccion:   COMPRA / VENTA
  Entrada:     [precio o rango] — motivo tecnico
  Stop Loss:   [nivel] — que lo invalida
  Take Profit: TP1 [nivel] / TP2 [nivel]
  Ratio R/B:   1:X
  Invalidacion: que tendria que pasar para descartar la idea

CONTEXTO DE MERCADO
2-3 puntos con el driver del momento (macro, datos, eventos).
Cada punto termina con la fuente citada entre parentesis con URL.

PARA SEGUIR LEYENDO
3-4 enlaces relevantes y actuales:
  - [Titulo] — que aporta — URL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analisis tecnico, no asesoria financiera. Sin garantia de resultado.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGLAS ESTRICTAS:
- Si las temporalidades se contradicen sin sesgo dominante: NO OPERAR y explica que confirmacion esperarias.
- Numeros concretos, nada de generalidades.
- Cada afirmacion de contexto debe tener fuente con URL real de los datos recibidos.
- No excedas una pantalla: el lector debe poder leerlo de corrido en el celular.
- DEVUELVE UNICAMENTE EL BOLETIN, sin texto previo ni posterior.

DATOS:
{market_data}"""

def check_schedule():
    now = datetime.now(TZ_ET)
    if now.weekday() >= 5:
        print(f"[SKIP] Fin de semana {now.strftime('%A')} ET"); return False
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
        ("PRECIO XAU/USD",    "XAU USD gold spot price today"),
        ("TECNICO MULTI-TF",  "gold XAU USD technical analysis weekly daily 4H 1H support resistance trend today"),
        ("DXY/BONOS",         "DXY dollar index US 10yr treasury yield today"),
        ("MACRO/NOTICIAS",    "gold price news macro drivers federal reserve inflation today"),
        ("CALENDARIO",        "economic calendar high impact events today USD gold forex"),
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
    if not check_schedule(): sys.exit(0)
    data = gather_data()
    bulletin = generate(data)
    if not bulletin: print("[ERROR] Sin respuesta"); sys.exit(1)
    print(bulletin[:300])
    if not send_ntfy(bulletin): sys.exit(1)
    print("[OK] Boletin enviado.")

if __name__ == "__main__": main()

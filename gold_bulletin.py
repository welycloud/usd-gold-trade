#!/usr/bin/env python3
"""
🟡 Boletín Diario ORO (XAU/USD)
Rutina autónoma — corre en GitHub Actions, sin PC encendido.
Verifica ventana 08:00-09:00 ET (lunes-viernes), genera análisis
con Gemini + Google Search grounding y lo envía vía ntfy.sh.
100% gratuito (Google AI Studio free tier).
"""

import os
import sys
import subprocess
import tempfile
from datetime import datetime

import pytz
import google.generativeai as genai

# ── Configuración ────────────────────────────────────────────────────────────
NTFY_URL     = "https://ntfy.sh/oro-fran-7k4xq2"
MODEL        = "gemini-2.0-flash"
TZ_ET        = pytz.timezone("America/New_York")

# ── Prompt completo ──────────────────────────────────────────────────────────
PROMPT = """
Actúa como analista financiero y trader profesional especializado en ORO (XAU/USD).
Corres como una rutina programada y autónoma; nadie supervisa.
Completa todo de principio a fin y devuelve SOLO el boletín formateado al final.

PASO 0 — VERIFICACIÓN DE HORARIO (a prueba de cambios de hora)
Consulta la hora actual real en America/New_York. Solo continúa si es un día
hábil (lunes a viernes) y estás dentro de la ventana 08:00–09:00 ET (la meta
es publicar ~1 hora antes de la apertura de la NYSE, que abre 09:30 ET).
Si es fin de semana o estás fuera de esa ventana, responde EXACTAMENTE con
la palabra: FUERA_DE_VENTANA — nada más.

PASO 1 — DATOS (búsqueda web)
Cada ejecución es independiente y sin memoria: busca datos frescos en la web.
Reúne:
- precio actual de XAU/USD y cierre/rango de la sesión previa;
- niveles publicados (soportes, resistencias, pivotes);
- DXY y bono EE.UU. a 10 años;
- calendario económico del día con eventos de alto impacto.
Fuentes confiables: Investing.com, FXStreet, DailyFX, Kitco, Forex Factory.
Anota hora y fuente de cada dato.
NUNCA inventes precios; si algo no está disponible, decláralo y baja la confianza.

PASO 2 — ANÁLISIS Y BOLETÍN
Redacta el boletín con esta estructura exacta:

1) RESUMEN PRE-APERTURA (sesiones asiática/europea, DXY, bonos, risk-on/off).
2) CATALIZADORES DEL DÍA (evento — hora Santiago — impacto alto/medio — sesgo;
   prioriza NFP, CPI/PCE, Fed/FOMC, PMIs, geopolítica).
3) ANÁLISIS TÉCNICO (tendencia/estructura; acción de precio reciente; niveles;
   momentum).
4) PLAN OPERATIVO (dirección COMPRA/VENTA o ESPERAR; entrada con su lógica; SL;
   TP1 y TP2; R:R mínimo 1:1.5 o esperar; confianza alta/media/baja; condición
   de invalidación).
5) ESCENARIO ALTERNATIVO (qué invalida el plan y plan B).
6) NOTA DE RIESGO (es análisis, no garantía; operar con SL y máx. 1% del capital
   por operación).

Formato de salida (para celular, respeta emojis y saltos de línea):
🟡 BOLETÍN ORO — [fecha]
🕒 1h antes de apertura NY
📊 PRE-APERTURA: [...]
📰 CATALIZADORES: [...]
📈 TÉCNICO: Tendencia [..] | Niveles: S [..] / R [..]
🚦 PLAN:
▸ [COMPRA/VENTA/ESPERAR]
▸ Entrada [..]
▸ SL [..] | TP1 [..] | TP2 [..]
▸ R:R [..] | Confianza [..]
▸ Invalidación [..]
🅱️ Alternativo: [..]
📍 Datos: [fuente + hora] · ⚠️ Análisis, no asesoría.

PASO 3 — ENTREGA
Devuelve ÚNICAMENTE el boletín formateado. Cero texto fuera del boletín.
Si en el PASO 0 determinaste FUERA_DE_VENTANA, devuelve solo esa palabra.
"""


# ── Funciones ────────────────────────────────────────────────────────────────

def check_schedule():
    """Verifica ventana 08:00-09:00 ET, lunes-viernes."""
    now = datetime.now(TZ_ET)
    day_name = now.strftime("%A")
    time_str = now.strftime("%H:%M")

    if now.weekday() >= 5:
        print(f"[SKIP] Fin de semana: {day_name} {time_str} ET")
        return False

    if now.hour != 8:
        print(f"[SKIP] Fuera de ventana: {time_str} ET (se requiere 08:xx)")
        return False

    print(f"[OK] Horario válido: {day_name} {time_str} ET")
    return True


def generate_bulletin():
    """Llama a Gemini con Google Search grounding y retorna el boletín."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    print(f"[INFO] Llamando {MODEL} con Google Search grounding…")

    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(
        PROMPT,
        tools="google_search_retrieval",
    )

    bulletin = response.text.strip() if response.text else ""
    print(f"[INFO] Respuesta recibida: {len(bulletin)} caracteres")
    return bulletin


def send_to_ntfy(text):
    """Guarda el boletín en archivo temporal y lo envía a ntfy.sh con curl."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-w", "\nHTTP_STATUS:%{http_code}",
                "-H", "Title: Boletin ORO",
                "-H", "Priority: high",
                "-H", "Tags: moneybag",
                "--data-binary", f"@{tmp_path}",
                NTFY_URL,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout.strip()
        http_code = "???"
        for line in output.splitlines():
            if line.startswith("HTTP_STATUS:"):
                http_code = line.split(":")[1]

        print(f"[ntfy] HTTP {http_code}")

        if http_code != "200":
            print(f"[ntfy] Respuesta completa: {output}")
            return False
        return True

    finally:
        os.unlink(tmp_path)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🟡 Boletín ORO — inicio de rutina (Gemini, free tier)")
    print(f"   UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not check_schedule():
        print("[FIN] Rutina terminada sin enviar.")
        sys.exit(0)

    bulletin = generate_bulletin()

    if not bulletin:
        print("[ERROR] Gemini no devolvió contenido.")
        sys.exit(1)

    if "FUERA_DE_VENTANA" in bulletin:
        print("[SKIP] Gemini confirmó estar fuera de ventana horaria.")
        sys.exit(0)

    preview = "\n".join(bulletin.splitlines()[:3])
    print(f"[INFO] Preview:\n{preview}\n…")

    ok = send_to_ntfy(bulletin)

    if ok:
        print("[OK] ✅ Boletín enviado correctamente a ntfy.")
    else:
        print("[ERROR] ❌ Falló el envío a ntfy.")
        sys.exit(1)

    print("=" * 60)
    print("🟡 Rutina completada exitosamente.")
    print("=" * 60)


if __name__ == "__main__":
    main()

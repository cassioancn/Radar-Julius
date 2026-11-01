import os
import sys
import time
import re

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

URLS = [
    "https://radar-julius-c6w8h7d9iv2uge3rgphuj4.streamlit.app",
    "https://evolucao-saude-cmx3ay3lqw2ndcbvsqc76d.streamlit.app"
]

SLEEP_REGEX = re.compile(r"gone to sleep|zzzz", re.IGNORECASE)
WAKE_REGEX = re.compile(r"get this app back up|wake it back up|wake up", re.IGNORECASE)

def write_github_summary(lines):
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            print(f"Aviso ao escrever resumo: {e}")

def main():
    print("=" * 60)
    print("Iniciando rotina de verificacao e despertar dos apps Streamlit")
    print("=" * 60)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        for url in URLS:
            print(f"\n--> Verificando: {url}")
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(6)

                body_text = ""
                for f in page.frames:
                    try:
                        body_text += " " + f.locator("body").inner_text()
                    except Exception:
                        pass

                is_asleep = bool(SLEEP_REGEX.search(body_text))

                if not is_asleep:
                    print("  STATUS: O aplicativo ja esta acordado e 100% operacional!")
                    results.append((url, "🟢 Acordado (Online)"))
                    continue

                print("  STATUS: Tela de sono detectada! Procurando botao de despertar...")
                btn = None
                for f in page.frames:
                    try:
                        candidate = f.locator('button, a, [role="button"]').filter(has_text=WAKE_REGEX).first
                        if candidate.count() > 0:
                            btn = candidate
                            break
                    except Exception:
                        pass

                if not btn:
                    print("  Tentando busca ampla por botao...")
                    for f in page.frames:
                        all_btns = f.locator("button").all()
                        for b in all_btns:
                            try:
                                t = b.inner_text()
                                if WAKE_REGEX.search(t):
                                    btn = b
                                    break
                            except Exception:
                                pass
                        if btn:
                            break

                if not btn:
                    print("  AVISO: Tela de repouso detectada, mas botao de despertar nao foi encontrado.")
                    results.append((url, "⚠️ Repouso (Botao nao encontrado)"))
                    continue

                print("  Clicando no botao de despertar ('Yes, get this app back up!')...")
                btn.click()
                print("  Aguardando container do Streamlit Cloud inicializar...")

                woke_up = False
                for attempt in range(12):
                    time.sleep(5)
                    check_text = ""
                    for f in page.frames:
                        try:
                            check_text += " " + f.locator("body").inner_text()
                        except Exception:
                            pass
                    if not SLEEP_REGEX.search(check_text) and len(check_text.strip()) > 30:
                        print(f"  SUCESSO: Aplicativo acordou e carregou a interface em {(attempt + 1) * 5}s!")
                        woke_up = True
                        break

                if woke_up:
                    results.append((url, "⚡ Despertado com Sucesso"))
                else:
                    print("  Clique enviado; container esta iniciando em segundo plano.")
                    results.append((url, "⏳ Em Inicializacao"))

            except Exception as e:
                print(f"  Erro ao acessar {url}: {e}")
                results.append((url, f"❌ Erro: {str(e)[:60]}"))
            finally:
                page.close()
                context.close()

        browser.close()

    summary_lines = [
        "### 🤖 Status do Auto-Wake (Streamlit Apps)",
        "",
        "| Aplicativo | Status |",
        "| :--- | :--- |"
    ]
    for u, status in results:
        summary_lines.append(f"| [{u}]({u}) | {status} |")

    write_github_summary(summary_lines)
    print("\n" + "\n".join(summary_lines))
    print("\nRotina finalizada com sucesso!")

if __name__ == "__main__":
    main()

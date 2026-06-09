import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AFIP Facturacion Scraper")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    cuit: str
    clave: str


class FacturacionResponse(BaseModel):
    success: bool
    monto: str | None = None
    error: str | None = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/scrape", response_model=FacturacionResponse)
async def scrape_facturacion(req: LoginRequest):
    cuit = req.cuit.strip().replace("-", "").replace(".", "")
    if not cuit.isdigit() or len(cuit) != 11:
        raise HTTPException(status_code=400, detail="CUIT inválido. Debe tener 11 dígitos.")
    if not req.clave or len(req.clave) < 1:
        raise HTTPException(status_code=400, detail="Clave no puede estar vacía.")

    try:
        monto = await run_scraper(cuit, req.clave)
        return FacturacionResponse(success=True, monto=monto)
    except PlaywrightTimeout as e:
        logger.error(f"Timeout durante scraping: {e}")
        return FacturacionResponse(success=False, error="Tiempo de espera agotado. El sitio de AFIP puede estar lento.")
    except ValueError as e:
        return FacturacionResponse(success=False, error=str(e))
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return FacturacionResponse(success=False, error=f"Error interno: {str(e)}")


async def run_scraper(cuit: str, clave: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            # ── 1. Login AFIP ──────────────────────────────────────────────
            logger.info("Navegando a login AFIP...")
            await page.goto("https://auth.afip.gob.ar/contribuyente_/login.xhtml", timeout=30000)

            # Ingresar CUIT
            await page.wait_for_selector("#F1\\:username", timeout=15000)
            await page.fill("#F1\\:username", cuit)
            logger.info("CUIT ingresado.")

            # Click "Siguiente"
            await page.click("#F1\\:btnSiguiente")
            await page.wait_for_selector("#F1\\:password", timeout=15000)
            logger.info("Pantalla de clave cargada.")

            # Ingresar clave
            await page.fill("#F1\\:password", clave)

            # Click "Ingresar"
            await page.click("#F1\\:btnIngresar")

            # Esperar que cargue el portal (buscador)
            await page.wait_for_selector("#buscadorInput", timeout=20000)
            logger.info("Sesión iniciada correctamente.")

            # ── 2. Buscar Monotributo ──────────────────────────────────────
            await page.fill("#buscadorInput", "Monotributo")
            await asyncio.sleep(1.5)  # Esperar resultados del autocomplete

            # Click en el resultado "Monotributo"
            monotributo_div = page.locator("div.small.text-muted p.small.text-muted", has_text="Monotributo").first
            await monotributo_div.wait_for(timeout=10000)
            logger.info("Resultado Monotributo encontrado.")

            # Abrir nueva pestaña al hacer click
            async with context.expect_page() as new_page_info:
                await monotributo_div.click()

            new_page = await new_page_info.value
            await new_page.wait_for_load_state("networkidle", timeout=30000)
            logger.info(f"Nueva pestaña abierta: {new_page.url}")

            # ── 3. Obtener monto facturado ─────────────────────────────────
            await new_page.wait_for_selector("#spanFacturometroMonto", timeout=20000)
            monto_raw = await new_page.inner_text("#spanFacturometroMonto")
            monto = monto_raw.strip()
            logger.info(f"Monto obtenido: {monto}")

            if not monto:
                raise ValueError("No se encontró el monto facturado en la página.")

            return monto

        except PlaywrightTimeout:
            # Verificar si fue error de credenciales
            if page.url and "login" in page.url:
                error_visible = await page.is_visible(".alert-danger, .msg-error", timeout=2000)
                if error_visible:
                    raise ValueError("CUIT o clave incorrectos.")
            raise
        finally:
            await browser.close()

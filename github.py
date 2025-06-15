import asyncio
import os
import pickle
import random
from pathlib import Path

# from playwright.async_api import async_playwright
from patchright.async_api import async_playwright
# from patchright.patchright import Patchright
from browserforge.fingerprints import FingerprintGenerator, Screen
from browserforge.injectors.playwright import AsyncNewContext
# from browserforge import BrowserForge
# from browserforge.fingerprints import generate_fingerprint

USER_DATA_DIR = "/media/disk/main_480/0xSCRIPT/sh_web3/Playwright/user_data/github"
EXT_DIR = "/media/disk/main_480/0xSCRIPT/sh_web3/Playwright/EXT_DIR"
PROFILES_PKL = os.path.join(USER_DATA_DIR, "github_profiles.pkl")

CHROME_VERSIONS = [str(v) for v in range(120, 138)]
WEBGL_VENDORS = [
    "NVIDIA Corporation", "NVIDIA", "NVIDIA (NVIDIA Corporation)", "NVIDIA-OpenGL"
]
WEBGL_RENDERERS = [
    "NVIDIA GeForce GTX 1080/PCIe/SSE2",
    "NVIDIA GeForce RTX 3070/PCIe/SSE2",
    "NVIDIA GeForce RTX 2080 Ti/PCIe/SSE2"
]
ACCEPT_LANGUAGES = ["en-US", "en-GB", "en"]
PLATFORMS = ["Linux x86_64", "Linux i686"]
TIMEZONES = ["Europe/London", "America/New_York", "Asia/Singapore", "UTC"]
SCREEN_RESOLUTIONS = [(1920, 1080), (1366, 768), (2560, 1440), (3840, 2160)]
CPU_CORES = [2, 4, 6, 8, 12, 16]
DEVICE_MEMORY = [4, 8, 16, 32]
FONT_SETS = [
    ["Arial", "Tahoma", "Verdana", "Ubuntu", "Liberation Sans"],
    ["Helvetica", "Arial", "Ubuntu Mono", "Liberation Mono"],
    ["Cascadia Code", "Fira Mono", "Liberation Serif", "Ubuntu"]
]

def random_extension_subset(ext_dir):
    all_exts = [str(p) for p in Path(ext_dir).iterdir() if p.is_dir()]
    if not all_exts:
        return []
    return random.sample(all_exts, k=random.randint(1, min(len(all_exts), 3)))

def get_profile_path(profile_id):
    return os.path.join(USER_DATA_DIR, profile_id)

def save_profiles(profiles):
    with open(PROFILES_PKL, "wb") as f:
        pickle.dump(profiles, f)

def load_profiles():
    if not os.path.exists(PROFILES_PKL):
        return {}
    with open(PROFILES_PKL, "rb") as f:
        return pickle.load(f)

async def create_profile(profile_id):
    print(f"Создаю новый профиль: {profile_id}")
    profile_path = get_profile_path(profile_id)
    os.makedirs(profile_path, exist_ok=True)

    user_agent = f"Mozilla/5.0 (X11; {random.choice(PLATFORMS)}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.choice(CHROME_VERSIONS)}.0.0.0 Safari/537.36"
    screen_width, screen_height = random.choice(SCREEN_RESOLUTIONS)
    screen = Screen(width=screen_width, height=screen_height)
    timezone = random.choice(TIMEZONES)
    accept_language = random.choice(ACCEPT_LANGUAGES)
    geolocation = {
        "latitude": random.uniform(-90, 90),
        "longitude": random.uniform(-180, 180),
        "accuracy": random.uniform(10, 100)
    }
    webgl_vendor = random.choice(WEBGL_VENDORS)
    webgl_renderer = random.choice(WEBGL_RENDERERS)
    cpu_cores = random.choice(CPU_CORES)
    device_memory = random.choice(DEVICE_MEMORY)
    fonts = random.choice(FONT_SETS)
    extensions = random_extension_subset(EXT_DIR)

    # генерируем отпечаток через browserforge
    fingerprint = FingerprintGenerator().generate(
        os='linux',
        browser='chrome',
        userAgent=user_agent,
        screen=screen,
        language=accept_language,
        timezone=timezone,
        webglVendor=webgl_vendor,
        webglRenderer=webgl_renderer,
        cpuCores=cpu_cores,
        deviceMemory=device_memory,
        fonts=fonts
    )

    # сохраняем профиль
    profile_info = {
        "profile_id": profile_id,
        "profile_path": profile_path,
        "user_agent": user_agent,
        "screen": {"width": screen_width, "height": screen_height},
        "timezone": timezone,
        "accept_language": accept_language,
        "geolocation": geolocation,
        "webgl_vendor": webgl_vendor,
        "webgl_renderer": webgl_renderer,
        "cpu_cores": cpu_cores,
        "device_memory": device_memory,
        "fonts": fonts,
        "extensions": extensions,
        "fingerprint": fingerprint
    }
    profiles = load_profiles()
    profiles[profile_id] = profile_info
    save_profiles(profiles)
    print(f"Профиль {profile_id} создан и сохранён.")
    return profile_info

async def launch_with_profile(profile_id):
    profiles = load_profiles()
    if profile_id not in profiles:
        print(f"Профиль {profile_id} не найден. Сначала создайте профиль.")
        return

    profile = profiles[profile_id]
    profile_path = profile["profile_path"]
    extensions = profile["extensions"]

    print(f"Запуск профиля: {profile_id}")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                *(["--load-extension=" + ",".join(extensions)] if extensions else [])
            ]
        )

        async def patch_page(page):
            # Скрытие Automation
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            # WebGL vendor/renderer
            vendor = profile["fingerprint"].videoCard.vendor
            renderer = profile["fingerprint"].videoCard.renderer
            await page.add_init_script(f"""
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) {{ return "{vendor}"; }}
                    if (parameter === 37446) {{ return "{renderer}"; }}
                    return getParameter.call(this, parameter);
                }};
            """)
            # HardwareConcurrency, deviceMemory
            hc = profile["fingerprint"].navigator.hardwareConcurrency
            dm = profile["fingerprint"].navigator.deviceMemory
            await page.add_init_script(f"""
                Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {hc}}});
                Object.defineProperty(navigator, 'deviceMemory', {{get: () => {dm}}});
            """)
            # Язык
            lang = profile["fingerprint"].navigator.language
            langs = profile["fingerprint"].navigator.languages
            await page.add_init_script(f"""
                Object.defineProperty(navigator, 'language', {{get: () => "{lang}"}});
                Object.defineProperty(navigator, 'languages', {{get: () => {langs}}});
            """)
            # User-Agent
            ua = profile["fingerprint"].navigator.userAgent
            await page.set_user_agent(ua)
            # Экран
            screen = profile["fingerprint"].screen
            await page.set_viewport_size({"width": screen.width, "height": screen.height})

        # Патчим уже открытые страницы
        for page in browser.pages:
            await patch_page(page)

        # Патчим новые страницы автоматически
        browser.on("page", lambda page: asyncio.create_task(patch_page(page)))

        page = await browser.new_page()
        await patch_page(page)
        await page.goto("https://fingerprint.com/demo/")

        print("Браузер запущен. Для выхода закройте все вкладки.")
        await browser.wait_for_event("close")
        await browser.close()

async def apply_stealth_settings(page, profile):
    await page.set_user_agent(profile["user_agent"])
    await page.set_viewport_size(profile["screen"])
    await page.emulate_media(timezone_id=profile["timezone"])
    await page.set_extra_http_headers({
        "Accept-Language": profile["accept_language"]
    })
    # Геолокация
    await page.context.grant_permissions(["geolocation"])
    await page.context.set_geolocation(profile["geolocation"])
    # WebRTC
    await page.add_init_script("""
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => %d});
        Object.defineProperty(navigator, 'deviceMemory', {get: () => %d});
    """ % (profile["cpu_cores"], profile["device_memory"]))
    # WebGL
    await page.add_init_script("""
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) { return '%s'; }
            if (parameter === 37446) { return '%s'; }
            return getParameter.call(this, parameter);
        };
    """ % (profile["webgl_vendor"], profile["webgl_renderer"]))
    # Fonts
    await page.add_init_script("""
        document.fonts.forEach(font => { font.family = '%s'; });
    """ % (random.choice(profile["fonts"])))
    # Canvas fingerprint, AudioContext и прочее (обфускация)
    # ... можно добавить кастомные скрипты или использовать patchright/browserforge

async def main():
    print("1. Создать новый профиль")
    print("2. Запустить существующий профиль")
    choice = input("Выберите действие (1/2): ")
    if choice == "1":
        profile_id = input("Введите имя нового профиля: ")
        await create_profile(profile_id)
    elif choice == "2":
        profiles = load_profiles()
        if not profiles:
            print("Нет сохранённых профилей.")
            return
        print("Доступные профили:", ", ".join(profiles.keys()))
        profile_id = input("Введите имя профиля для запуска: ")
        await launch_with_profile(profile_id)
    else:
        print("Неверный выбор.")

if __name__ == "__main__":
    asyncio.run(main())

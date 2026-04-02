#!/usr/bin/env python3
"""
WorldPosta Knowledge Base Scraper
===================================
Scrapes all 50 pages from worldposta.com using Selenium,
extracts clean text content, and outputs:

  pages/
    cloudedge/     — 14 individual .md files
    posta/         — 14 individual .md files
    cloudspace/    —  5 individual .md files
    general/       — 18 individual .md files
  consolidated/
    cloudedge_complete.md
    posta_complete.md
    cloudspace_complete.md
    general_complete.md

Usage:
    python worldposta_scraper.py --headless
    python worldposta_scraper.py --headless --no-fail
"""

import os, re, sys, json, time, subprocess, argparse
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL          = "https://www.worldposta.com"
PAGE_LOAD_TIMEOUT = 60
RENDER_WAIT       = 6       # seconds after load for Angular to finish rendering
OUTPUT_DIR        = "output"
JSON_REPORT       = "scrape_report.json"

# Tags to strip — pure noise
STRIP_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "img",
    "nav", "footer", "header", "cookie", "aside",
    "app-navbar", "app-footer", "app-header", "app-cookie",
]

# CSS selectors to remove — site-specific boilerplate
STRIP_SELECTORS = [
    "nav", "footer", "header",
    ".navbar", ".nav", ".footer", ".cookie", ".cookie-banner",
    ".breadcrumb", ".pagination", ".social-links", ".social-media",
    "[class*='cookie']", "[class*='navbar']", "[class*='footer']",
    "[class*='header']", "[class*='nav-']",
]

# ─────────────────────────────────────────────────────────────────────────────
# PAGE MANIFEST
# ─────────────────────────────────────────────────────────────────────────────

# (page_name, path, group, filename_slug)
PAGES = [
    # ── CloudEdge ─────────────────────────────────────────────────────────────
    ("CloudEdge Main",                   "/cloudedge",                              "cloudedge", "cloudedge_main"),
    ("Cloud Plan",                       "/CloudPlan",                              "cloudedge", "cloud_plan"),
    ("Cloud Resource Optimization",      "/cloud-resource-optimization",            "cloudedge", "cloud_resource_optimization"),
    ("Dedicated Compute Instances",      "/dedicated-compute-instances",            "cloudedge", "dedicated_compute_instances"),
    ("Cloud Ransomware Protection",      "/cloud-ransomware-protection",            "cloudedge", "cloud_ransomware_protection"),
    ("Comprehensive Cloud Security",     "/comprehensive-cloud-security-solutions", "cloudedge", "comprehensive_cloud_security"),
    ("VDC vs Traditional VMs",           "/virtual-data-centre-vs-traditional-vms","cloudedge", "vdc_vs_traditional_vms"),
    ("Virtual Data Center Solutions",    "/virtual-data-center-solutions",          "cloudedge", "virtual_data_center_solutions"),
    ("GPU Instances",                    "/gpu-instances",                          "cloudedge", "gpu_instances"),
    ("Cloud Firewall",                   "/cloud-firewall",                         "cloudedge", "cloud_firewall"),
    ("GPU Instance Pro",                 "/gpu-instance-pro",                       "cloudedge", "gpu_instance_pro"),
    ("CloudEdge Pricing",                "/cloudedge-pricing",                      "cloudedge", "cloudedge_pricing"),
    ("CloudEdge Portal",                 "/cloudedge-portal",                       "cloudedge", "cloudedge_portal"),
    ("CloudEdge Support",                "/cloudedge-support",                      "cloudedge", "cloudedge_support"),
    # ── Posta ─────────────────────────────────────────────────────────────────
    ("Posta Main",                       "/posta",                                  "posta", "posta_main"),
    ("Office 365 with Posta",            "/office-365-with-posta",                  "posta", "office_365_with_posta"),
    ("Posta Hybrid",                     "/posta-hybrid",                           "posta", "posta_hybrid"),
    ("Posta Gate",                       "/posta-gate",                             "posta", "posta_gate"),
    ("Posta Gate Comparison",            "/posta-gate-comparison",                  "posta", "posta_gate_comparison"),
    ("Posta Gate Security",              "/posta-gate-security",                    "posta", "posta_gate_security"),
    ("Email Security Test",              "/email-security-test",                    "posta", "email_security_test"),
    ("Posta Pricing",                    "/posta-pricing",                          "posta", "posta_pricing"),
    ("Posta Portal",                     "/posta-portal",                           "posta", "posta_portal"),
    ("WP Support",                       "/wp-support",                             "posta", "wp_support"),
    ("One SLA",                          "/one-sla",                                "posta", "one_sla"),
    ("Email Migration",                  "/email-migration",                        "posta", "email_migration"),
    ("Seamless Migration",               "/seamless-migration",                     "posta", "seamless_migration"),
    # ── CloudSpace ────────────────────────────────────────────────────────────
    ("CloudSpace Main",                  "/cloudspace",                             "cloudspace", "cloudspace_main"),
    ("CloudSpace Support",               "/cloudspace-support",                     "cloudspace", "cloudspace_support"),
    ("Cloud Backup",                     "/cloud-backup",                           "cloudspace", "cloud_backup"),
    ("Mission Critical Data Backup",     "/mission-critical-data-backup",           "cloudspace", "mission_critical_data_backup"),
    ("Veeam Cloud Connect",              "/veeam-cloud-connect",                    "cloudspace", "veeam_cloud_connect"),
    # ── General ───────────────────────────────────────────────────────────────
    ("Home",                             "/",                                        "general", "home"),
    ("WPSYS IT Solutions",               "/wpsys-it-solutions",                     "general", "wpsys_it_solutions"),
    ("IT Software Automation Tools",     "/it-software-automation-tools",           "general", "it_software_automation_tools"),
    ("Cloud Based SOC Solutions",        "/cloud-based-soc-solutions",              "general", "cloud_based_soc_solutions"),
    ("SAP Cloud Operations",             "/sap-cloud-operations",                   "general", "sap_cloud_operations"),
    ("Cloud Security Solutions",         "/cloud-security-solutions",               "general", "cloud_security_solutions"),
    ("Cloud Solutions for SAP Partners", "/cloud-solutions-for-sap-partners",       "general", "cloud_solutions_for_sap_partners"),
    ("Contact Us",                       "/contact-us",                             "general", "contact_us"),
    ("Knowledge Base",                   "/knowledge-base",                         "general", "knowledge_base"),
    ("Become a Partner",                 "/become-a-partner",                       "general", "become_a_partner"),
    ("About WorldPosta",                 "/about-worldposta",                       "general", "about_worldposta"),
    ("Terms",                            "/terms",                                  "general", "terms"),
    ("Free Trial",                       "/free-trial",                             "general", "free_trial"),
    ("IT Excellence",                    "/It-excellence",                          "general", "it_excellence"),
    ("One SLA",                          "/one-sla",                                "general", "one_sla"),
    ("Privacy Policy",                   "/privacy-policy",                         "general", "privacy_policy"),
    ("Blogs",                            "/blogs",                                  "general", "blogs"),
    ("E-Books",                          "/e-books",                                "general", "e_books"),
    ("UAE Home",                         "/uae-home",                               "general", "uae_home"),
]

GROUP_LABELS = {
    "cloudedge":  "CloudEdge",
    "posta":      "Posta",
    "cloudspace": "CloudSpace",
    "general":    "General",
}

# ─────────────────────────────────────────────────────────────────────────────
# CHROME DRIVER
# ─────────────────────────────────────────────────────────────────────────────

def get_chrome_path():
    import platform
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Google\Chrome\Application\chrome.exe"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None
    return "/usr/bin/google-chrome"


def get_chrome_major():
    try:
        chrome = get_chrome_path()
        if not chrome:
            return None
        out = subprocess.check_output([chrome, "--version"]).decode()
        m   = re.search(r"(\d+)\.", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def make_driver(headless: bool = True):
    print("🌐 Launching Chrome...")
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    if headless:
        options.add_argument("--headless=new")

    chrome_path  = get_chrome_path()
    chrome_major = get_chrome_major()
    print(f"   Chrome path  : {chrome_path or 'auto-detect'}")
    print(f"   Chrome major : {chrome_major or 'auto-detect'}")

    driver = uc.Chrome(
        options=options,
        browser_executable_path=chrome_path,
        version_main=chrome_major,
        driver_executable_path=None,
        use_subprocess=True,
    )
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    print("✅ Chrome launched\n")
    return driver


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def clean_html(raw_html: str) -> str:
    """Strip boilerplate, return clean readable text."""
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove noisy tags
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Remove noisy selectors
    for sel in STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    # Remove empty tags
    for tag in soup.find_all():
        if not tag.get_text(strip=True):
            tag.decompose()

    return soup


def extract_text(soup) -> str:
    """Convert cleaned soup to readable plain text."""
    lines = []

    # First pass: headings with markers
    for el in soup.find_all(["h1","h2","h3","h4","h5","h6"]):
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 3:
            continue
        level = int(el.name[1])
        lines.append(f"\n{'#' * level} {text}\n")

    # Second pass: paragraphs and list items (most Angular content)
    for el in soup.find_all(["p","li","td","th","blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 20:
            continue
        lines.append(text)

    # Third pass: divs and spans ONLY if they have substantial direct text
    # (not just wrapping other elements) — avoids duplicating nested content
    for el in soup.find_all(["div","span","section","article"]):
        # Only take text if element has no block children (it's a leaf node)
        children = [c for c in el.children if hasattr(c, 'name') and c.name in
                    ["p","li","div","section","h1","h2","h3","h4","h5","h6","ul","ol","table"]]
        if children:
            continue
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 30:
            continue
        lines.append(text)

    # Deduplicate
    seen  = set()
    clean = []
    for line in lines:
        key = re.sub(r"\s+", " ", line.strip())
        if key and key not in seen:
            seen.add(key)
            clean.append(line)

    return "\n".join(clean).strip()


def get_page_title(soup) -> str:
    t = soup.find("title")
    if t:
        return t.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


MAX_RETRIES = 3
RETRY_WAIT  = 6     # seconds between retries


def scrape_page(driver, name: str, path: str) -> dict:
    """Load one page, extract content. Retries up to MAX_RETRIES times."""
    url = BASE_URL.rstrip("/") + path

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                print(f"  🔄 Retry {attempt}/{MAX_RETRIES}: {name}")
                time.sleep(RETRY_WAIT)

            driver.get(url)

            # Wait for Angular — use JS readyState then fixed buffer
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass
            time.sleep(RENDER_WAIT)   # buffer for Angular component rendering

            raw_html = driver.page_source
            soup_raw = BeautifulSoup(raw_html, "html.parser")
            title    = get_page_title(soup_raw)
            soup     = clean_html(raw_html)
            text     = extract_text(soup)
            words    = len(text.split())

            print(f"  ✅ {name:45s} {words:>5} words")
            return {
                "status":     "ok",
                "page_name":  name,
                "path":       path,
                "url":        url,
                "title":      title,
                "content":    text,
                "word_count": words,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error":      None,
            }

        except TimeoutException:
            print(f"  ⚠️ TIMEOUT attempt {attempt}/{MAX_RETRIES}: {name}")
            if attempt == MAX_RETRIES:
                print(f"  ❌ FAILED after {MAX_RETRIES} attempts: {name}")
                return {
                    "status": "timeout", "page_name": name, "path": path,
                    "url": url, "title": "", "content": "", "word_count": 0,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": f"Timeout after {MAX_RETRIES} attempts",
                }

        except Exception as e:
            print(f"  ⚠️ ERROR attempt {attempt}/{MAX_RETRIES}: {name} — {e}")
            if attempt == MAX_RETRIES:
                print(f"  ❌ FAILED after {MAX_RETRIES} attempts: {name}")
                return {
                    "status": "error", "page_name": name, "path": path,
                    "url": url, "title": "", "content": "", "word_count": 0,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e)[:200],
                }


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_page_md(result: dict) -> str:
    """Build markdown for a single page."""
    lines = [
        f"# {result['page_name']}",
        f"",
        f"**URL:** {result['url']}  ",
        f"**Scraped:** {result['scraped_at']}  ",
        f"**Word count:** {result['word_count']}  ",
        f"",
        "---",
        "",
    ]
    if result["status"] == "ok" and result["content"]:
        lines.append(result["content"])
    else:
        lines.append(f"> ⚠️ Could not scrape this page: {result.get('error', 'unknown error')}")
    return "\n".join(lines)


def build_consolidated_md(group: str, results: list[dict]) -> str:
    """Build one merged markdown file for a product group."""
    label   = GROUP_LABELS.get(group, group.title())
    ok      = [r for r in results if r["status"] == "ok"]
    total_w = sum(r["word_count"] for r in ok)

    lines = [
        f"# WorldPosta — {label} Knowledge Base",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Pages:** {len(results)}  ",
        f"**Total words:** {total_w:,}  ",
        f"",
        "---",
        "",
        "## Table of Contents",
        "",
    ]

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r['page_name']}](#{r['page_name'].lower().replace(' ', '-').replace('/', '')})")

    lines.append("")
    lines.append("---")
    lines.append("")

    for r in results:
        lines.append(f"## {r['page_name']}")
        lines.append(f"")
        lines.append(f"**URL:** {r['url']}  ")
        lines.append(f"**Word count:** {r['word_count']}  ")
        lines.append(f"")
        if r["status"] == "ok" and r["content"]:
            lines.append(r["content"])
        else:
            lines.append(f"> ⚠️ Could not scrape: {r.get('error', 'unknown error')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# FILE WRITERS
# ─────────────────────────────────────────────────────────────────────────────

def setup_dirs():
    for group in ("cloudedge", "posta", "cloudspace", "general"):
        os.makedirs(os.path.join(OUTPUT_DIR, "pages", group), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "consolidated"), exist_ok=True)


def write_page_md(result: dict, slug: str, group: str):
    path = os.path.join(OUTPUT_DIR, "pages", group, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_page_md(result))


def write_consolidated(group: str, results: list[dict]):
    path = os.path.join(OUTPUT_DIR, "consolidated", f"{group}_complete.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_consolidated_md(group, results))
    words = sum(r["word_count"] for r in results if r["status"] == "ok")
    print(f"  📄 {group}_complete.md — {len(results)} pages, {words:,} words")


def write_report(all_results: list[dict]):
    ok      = sum(1 for r in all_results if r["status"] == "ok")
    failed  = sum(1 for r in all_results if r["status"] != "ok")
    total_w = sum(r["word_count"] for r in all_results)

    report = {
        "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_pages":   len(all_results),
        "ok":            ok,
        "failed":        failed,
        "total_words":   total_w,
        "pages":         all_results,
    }
    with open(JSON_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  📋 JSON report → {JSON_REPORT}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WorldPosta Knowledge Base Scraper")
    parser.add_argument("--headless", action="store_true",
                        help="Run Chrome headless (required for GitHub Actions)")
    parser.add_argument("--no-fail",  action="store_true",
                        help="Always exit 0 even if some pages failed")
    args = parser.parse_args()

    print("=" * 60)
    print("📚  WORLDPOSTA KNOWLEDGE BASE SCRAPER")
    print("=" * 60)
    print(f"  Pages   : {len(PAGES)}")
    print(f"  Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()

    setup_dirs()

    driver      = make_driver(headless=args.headless)
    all_results = []
    by_group    = {"cloudedge": [], "posta": [], "cloudspace": [], "general": []}

    try:
        for i, (name, path, group, slug) in enumerate(PAGES, 1):
            print(f"[{i:02d}/{len(PAGES)}]", end=" ")
            result = scrape_page(driver, name, path)
            all_results.append(result)
            by_group[group].append(result)
            write_page_md(result, slug, group)

    finally:
        try:
            driver.quit()
            print("\n✅ Browser closed")
        except Exception:
            pass

    # Write consolidated files
    print(f"\n{'='*60}")
    print("📄  WRITING CONSOLIDATED FILES")
    print(f"{'='*60}")
    for group in ("cloudedge", "posta", "cloudspace", "general"):
        write_consolidated(group, by_group[group])

    # Write JSON report
    write_report(all_results)

    # Summary
    ok     = sum(1 for r in all_results if r["status"] == "ok")
    failed = sum(1 for r in all_results if r["status"] != "ok")
    total_w = sum(r["word_count"] for r in all_results)

    print(f"\n{'='*60}")
    print("📊  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"  ✅ Scraped successfully : {ok}/{len(PAGES)}")
    print(f"  ❌ Failed               : {failed}")
    print(f"  📝 Total words          : {total_w:,}")
    print(f"\n  Output → {OUTPUT_DIR}/")
    print(f"    pages/cloudedge/   — {len(by_group['cloudedge'])} files")
    print(f"    pages/posta/       — {len(by_group['posta'])} files")
    print(f"    pages/cloudspace/  — {len(by_group['cloudspace'])} files")
    print(f"    pages/general/     — {len(by_group['general'])} files")
    print(f"    consolidated/      — 4 merged files")

    if failed:
        print(f"\n::warning::Scraper: {failed} page(s) failed. Check {JSON_REPORT}")

    print("\n===== BEGIN_SCRAPER_JSON =====")
    print(json.dumps({
        "total_pages":  len(PAGES),
        "ok":           ok,
        "failed":       failed,
        "total_words":  total_w,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))
    print("===== END_SCRAPER_JSON =====")

    sys.exit(0 if (args.no_fail or failed == 0) else 1)


if __name__ == "__main__":
    main()
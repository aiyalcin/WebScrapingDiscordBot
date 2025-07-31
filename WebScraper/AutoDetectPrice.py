import sys
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import platform
import json
from urllib.parse import urlparse

def is_grey_color(color_str):
    color_str = color_str.strip().lower()
    if color_str in ['grey', 'gray']:
        return True
    rgb_match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color_str)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
    elif color_str.startswith('#'):
        hex_val = color_str.lstrip('#')
        if len(hex_val) == 3:
            r, g, b = [int(hex_val[i]*2, 16) for i in range(3)]
        elif len(hex_val) == 6:
            r, g, b = [int(hex_val[i:i+2], 16) for i in (0, 2, 4)]
        else:
            return False
    else:
        return False
    if max(abs(r-g), abs(r-b), abs(g-b)) < 15 and 80 <= r <= 200:
        return True
    return False

if platform.system() == "Windows":
    GECKODRIVER_PATH = r"C:\Coding\Github\WebScrapingDiscordBot\WebScraper\bin\geckodriver\geckodriver.exe"
else:
    GECKODRIVER_PATH = "/usr/bin/geckodriver"

def fetch_html(url, use_js=False):
    if not use_js:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    options = webdriver.FirefoxOptions()
    options.add_argument('--headless')
    service = Service(GECKODRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=options)
    driver.get(url)
    html = driver.page_source
    driver.quit()
    return html

def get_domain(url):
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def clean_price_text(price_text):
    return re.sub(r'[$€£¥₹USD|EUR|GBP|CAD|AUD|CHF|RUB|kr|PLN|CZK|SEK|NOK|DKK\s]+', '', price_text, flags=re.I)

def try_known_selectors(url, html, domain):
    try:
        with open('selector_data.json', 'r') as f:
            selector_data = json.load(f)
    except Exception:
        return None, None
    selectors = selector_data.get(domain)
    if not selectors:
        return None, None
    soup = BeautifulSoup(html, 'lxml')
    for selector in selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            text = el.get_text(strip=True)
            fraction = None
            for child in el.find_all(recursive=False):
                if child.has_attr('class') and any('fraction' in c for c in child['class']):
                    fraction = child.get_text(strip=True)
                    break
            combined_text = text
            if fraction:
                if not (',' in text or '.' in text):
                    combined_text = f"{text},{fraction}"
                else:
                    combined_text = f"{text}{fraction}"
            cleaned = clean_price_text(combined_text)
            return cleaned, selector
    return None, None

def find_price_candidates(soup):
    price_regex = re.compile(r'(\$|€|£|¥|₹|USD|EUR|GBP|CAD|AUD|CHF|RUB|\bkr\b|\bPLN\b|\bCZK\b|\bSEK\b|\bNOK\b|\bDKK\b)?\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?\s?(USD|EUR|GBP|CAD|AUD|CHF|RUB|kr|PLN|CZK|SEK|NOK|DKK|€|£|¥|₹)?', re.I)
    candidates = []
    for el in soup.find_all(string=True):
        text = el.strip()
        if not text:
            continue
        if price_regex.search(text):
            parent = el.parent
            if parent.name in ['s', 'strike', 'del']:
                continue
            style = parent.get('style', '')
            if 'line-through' in style or 'text-decoration:line-through' in style:
                continue
            color_match = re.search(r'color\s*:\s*([^;]+)', style)
            if color_match and is_grey_color(color_match.group(1)):
                continue
            ancestor = parent
            crossed_out = False
            while ancestor:
                if ancestor.name in ['s', 'strike', 'del']:
                    crossed_out = True
                    break
                style = ancestor.get('style', '')
                if 'line-through' in style or 'text-decoration:line-through' in style:
                    crossed_out = True
                    break
                if ancestor.has_attr('data-a-strike') and ancestor['data-a-strike'] == 'true':
                    crossed_out = True
                    break
                color_match = re.search(r'color\s*:\s*([^;]+)', style)
                if color_match and is_grey_color(color_match.group(1)):
                    crossed_out = True
                    break
                ancestor = ancestor.parent if hasattr(ancestor, 'parent') else None
            if crossed_out:
                continue
            selector = get_css_selector(parent)
            font_size = None
            if 'font-size' in style:
                match = re.search(r'font-size\s*:\s*([\d.]+)px', style)
                if match:
                    font_size = float(match.group(1))
            candidates.append((parent, selector, text, font_size))
    return candidates

def get_css_selector(element):
    path = []
    while element and element.name != '[document]':
        selector = element.name
        if element.get('id'):
            selector += f"#{element['id']}"
            path.insert(0, selector)
            break
        elif element.get('class'):
            selector += '.' + '.'.join(element['class'])
        siblings = element.find_previous_siblings(element.name)
        if siblings:
            selector += f":nth-child({len(siblings)+1})"
        path.insert(0, selector)
        if element.get('class') and not siblings:
            break
        element = element.parent
    return ' > '.join(path)

def score_candidate(el, selector, text, font_size=None):
    score = 0
    if re.search(r'price|amount|cost|total', selector, re.I):
        score += 5
    if len(text) < 20:
        score += 2
    if re.match(r'^\s*[$€£¥₹]?', text) and re.search(r'\d', text):
        score += 2
    if el.name in ['span', 'div', 'p', 'b', 'strong']:
        score += 1
    if el.name in ['script', 'style']:
        score -= 10
    if font_size:
        score += min(15, font_size / 2)
    if re.search(r'[$€£¥₹]', text):
        score += 4
    if el.has_attr('class') and 'promo-price' in el['class']:
        score += 8
    if el.has_attr('data-test') and el['data-test'] == 'price':
        score += 8
    if hasattr(el, 'sourceline') and el.sourceline:
        score += max(0, 10 - (el.sourceline // 100))
    return score

def auto_detect_price(url):
    html = fetch_html(url, use_js=False)
    domain = get_domain(url)
    known_price, known_selector = try_known_selectors(url, html, domain)
    if known_price:
        return known_price
    soup = BeautifulSoup(html, 'lxml')
    candidates = find_price_candidates(soup)
    if not candidates:
        html = fetch_html(url, use_js=True)
        known_price, known_selector = try_known_selectors(url, html, domain)
        if known_price:
            return known_price
        soup = BeautifulSoup(html, 'lxml')
        candidates = find_price_candidates(soup)
        if not candidates:
            return None
    scored = [(score_candidate(el, sel, txt, font_size), el, sel, txt) for el, sel, txt, font_size in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None
    best = scored[0]
    cleaned_best = clean_price_text(best[1].get_text(strip=True))
    return cleaned_best

if __name__ == "__main__":
    while True:
        url = input("enter url here:")
        price = auto_detect_price(url)
        if price:
            print(f"Most likely price: {price}")
        else:
            print("Price not found.")

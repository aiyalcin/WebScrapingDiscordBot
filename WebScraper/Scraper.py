from bs4 import BeautifulSoup
import requests


def addTracker(url):
    html_text = requests.get(url).text
    soup = BeautifulSoup(html_text, "lxml")
    print(html_text)
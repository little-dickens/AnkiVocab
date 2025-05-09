import ast
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

def get_soup(target_word: str) -> BeautifulSoup:
    url = f"https://www.wordreference.com/fren/{target_word}"

    soup = BeautifulSoup(requests.get(url).content, "html.parser")

    # Get article head (entry, pronunciation, audio, etc.)
    article_head = soup.find("div", id="articleHead")

    return soup

data = get_soup('pomme')

print(type(data))
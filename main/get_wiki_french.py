import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

def flatten_list(lst):
    return [item for sublist in lst for item in sublist]

target = 'secrétaire'
url = f"https://fr.wiktionary.org/wiki/{target}"
soup = BeautifulSoup(requests.get(url).content, "html.parser")

main_content = soup.find('div', class_='mw-content-ltr mw-parser-output')

# Pronunciation and Gender
pronunciations = []
genders = []

p_all = main_content.find_all('p')

# Not all p tags contain both the pronunciation and gender; filter if missing
if p_all:
    p_pron = []
    for p in p_all:
        children = p.children
        values = flatten_list([c.attrs.values() for c in children if isinstance(c, Tag)])
        if values == ['/wiki/Annexe:Prononciation/fran%C3%A7ais', 'Annexe:Prononciation/français', ['ligne-de-forme']]:
            p_pron.append(p)
    if p_pron:
        for p in p_pron:
            pronunciation_span = p.find('span', title="Prononciation API")
            if pronunciation_span:
                pronunciation = f"[{pronunciation_span.text[1:-1]}]"
                pronunciations.append(pronunciation)
            gender_span = p.find('span', class_="ligne-de-forme")
            if gender_span:
                gender_dict = {
                    'féminin': '(nf)',
                    'masculin': '(nm)',
                    'masculin et féminin identiques': '(nmf)',
                }
                gender = gender_dict[gender_span.text]
                genders.append(gender)

# Definitions
mw_headings = soup.find_all('div', class_='mw-heading')
for h in mw_headings:
    print(h.find_next())

# print(pronunciations)
# print(genders)


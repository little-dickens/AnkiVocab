import ast
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

def get_wr_french(some_target):
    url = f"https://www.wordreference.com/fren/{some_target}"

    soup = BeautifulSoup(requests.get(url).content, "html.parser")

    # Get article head (entry, pronunciation, audio, etc.)
    article_head = soup.find("div", id="articleHead")

    # Get all data tables from WordReference
    tables_all = soup.find_all("table", class_="WRD")

    # Filter out the "Formes composées"
    tables_definitions = [table for table in tables_all
                        if len(table.find_all("td", attrs={"title": "Principal Translations"})) != 0
                        or len(table.find_all("td", attrs={"title": "Additional Translations"})) != 0
                    ]

    ## Extract data
    # Head
    headerWordh1 = article_head.find('h1', class_='headerWord')
    if headerWordh1:
        headerWord = headerWordh1.text
    else:
        headerWord = ""
    # Pronunciation
    pronunciation_span = article_head.find('span', class_='pronWR')
    if pronunciation_span:
        pronunciation = pronunciation_span.text
    else:
        pronunciation = ""
    # Audio files
    audio_scripts = [script.string for script in article_head.find_all('script') if "var audioFiles" in script.string]
    audio_files = []
    for script_str in audio_scripts:
        # Extract the array part
        start = script_str.find('[')
        end = script_str.find('];') + 1
        array_str = script_str[start:end]

        # Convert to Python list
        audio_file = ast.literal_eval(array_str)
        for file in audio_file:
            head = 'https://www.wordreference.com'
            audio_file = f'{head}{file}'
            if audio_file not in audio_files:
                audio_files.append(audio_file)
    # Inflections
    inflections = {}
    inflections_div = soup.find('div', class_="inflectionsSection")
    if inflections_div:
        inflections_dl = inflections_div.find('dl')
        if inflections_dl:
            inflections_children = inflections_dl.children
            infinitive = ""
            inflection = ""
            conjugations = []
            for child in inflections_children:
                # verb = child.a
                a = child.find('a')
                b = child.find('b')

                if isinstance(a, Tag):
                    infinitive += a.text
                if isinstance(b, Tag):
                    inflection_str = ''.join(child for child in b.contents if isinstance(child, str))
                    if inflection_str:
                        inflection = inflection_str
                elif child.name == 'dd':
                    if inflection == some_target:
                        conjugations.append(child.text)
                elif child == '--------------':
                    if infinitive and conjugations:
                        inflections[infinitive] = conjugations
                    infinitive = ""
                    inflection = ""
                    conjugations = []
                if infinitive and conjugations:
                    inflections[infinitive] = conjugations

    # Get word definitions
    def_dict = {}
    trs = []
    # Definitions are contained in <td> class="ToWrd" within <td> lines with class="even" or "odd". 
    # Some definitions have supplementary notes in <td> class="To2"
    for table in tables_definitions:
        trs.extend([tr for tr in table.find_all('tr') if any(x in tr.attrs['class'] for x in ('even', 'odd'))])
    # Group tr lines by definition id
    tr_dict = {}
    id = ""
    for tr in trs:
        if 'id' in tr.attrs.keys():
            id = tr.attrs['id']
            if tr.attrs['id'] not in tr_dict:
                tr_dict[tr.attrs['id']] = []
                tr_dict[tr.attrs['id']].append(tr)
        else:
            tr_dict[id].append(tr)
    for id, tr_list in tr_dict.items():
        frWrd = ""
        pos = ""
        definitions = []
        for tr in tr_list:
            to2 = ""
            toWrd = ""
            tds = tr.find_all('td')
            for td in tds:
                if td.attrs:
                    if 'FrWrd' in td['class']:
                        frWrd += td.strong.text.replace('⇒', '')
                        pos += td.em.text
                    if "To2" in td['class']:
                        to2 += f"({td.i.string})"
                    if "ToWrd" in td['class']:
                        toWrd += td.contents[0].strip()
            definition = f"{to2} {toWrd}"
            definition = definition.strip()
            if definition:
                definitions.append(definition)
        # Make sure the definition matches the target
        if frWrd == some_target:
            entry = f'{frWrd} ({pos})'
            if entry not in def_dict:
                def_dict[entry] = [definitions]
            else:
                def_dict[entry].append(definitions)

    # Build the result dictionary
    if def_dict or inflections:
        result = {
            "entry": headerWord,
            "pronunciation": pronunciation,
            "audio": audio_files,
            "definitions": def_dict,
            "inflections": inflections
        }
        return result
    else:
        return None
    

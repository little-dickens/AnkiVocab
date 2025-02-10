import ast
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from dataclasses import dataclass
from itertools import chain
import pprint

@dataclass
class WordReference:
    # target_word is the word that we want to define 
    target_word: str

    def __post_init__(self):
        self.soup = self._get_soup()
        self.article_head = self._get_article_head()
        self.tr_dict = self._get_tr_dict()

    def _get_soup(self) -> BeautifulSoup:
        """Fetches the webpage for the target word and returns a BeautifulSoup object."""
        url = f"https://www.wordreference.com/fren/{self.target_word}"
        self.soup = BeautifulSoup(requests.get(url).content, "html.parser")
        return self.soup
    
    def _get_article_head(self) -> Tag:
        """Fetches the articleHead for the target word and returns a Tag object."""
        return self.soup.find("div", id="articleHead") if self.soup else None

    def _get_tr_dict(self) -> dict[str, list[Tag]]:
        """Fetches the data tables for the target word and returns a dict mapping strings to lists of Tags."""
        tables_all = self.soup.find_all("table", class_="WRD")

        # Filter out the "Formes composées"
        tables_definitions = [table for table in tables_all
                            if len(table.find_all("td", attrs={"title": "Principal Translations"})) != 0
                            or len(table.find_all("td", attrs={"title": "Additional Translations"})) != 0
                        ]

        # Get word definitions
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
        return tr_dict

    def get_pronunciations(self) -> str:
        '''Fetches pronunciations from WordReference'''
        if not self.article_head:
            return None
        pronunciation_span = self.article_head.find('span', class_='pronWR')
        return pronunciation_span.text if pronunciation_span.text else None

    def get_inflections(self) -> dict[str, list[str]]:
        '''Fetches inflections (primarily conjugations but listed in the html as inflections) from WordReference'''
        '''and returns a dict mapping the infinitive str to a list of conjugation descriptions'''
        inflections = {}
        inflections_div = self.soup.find('div', class_="inflectionsSection")
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
                        if inflection == self.target_word:
                            conjugations.append(child.text)
                    elif child == '--------------':
                        if infinitive and conjugations:
                            inflections[infinitive] = conjugations
                        infinitive = ""
                        inflection = ""
                        conjugations = []
                    if infinitive and conjugations:
                        inflections[infinitive] = conjugations
        return inflections

    def get_audio(self) -> list[str]:
        '''Fetches list of audio url strs from WordReference'''
        audio_scripts = [script.string for script in self.article_head.find_all('script') if "var audioFiles" in script.string]
        audio_files = []
        for script_str in audio_scripts:
            # Extract the array part
            start = script_str.find('[')
            end = script_str.find('];') + 1
            array_str = script_str[start:end]
            # Convert to Python list
            audio_file = ast.literal_eval(array_str)
            for file in audio_file:
                full_audio_file = f'''https://www.wordreference.com{file}'''
                if full_audio_file not in audio_files:
                    audio_files.append(full_audio_file)
        return audio_files

    def get_definitions(self) -> dict[str, str]:
        '''Fetches definitions from WordReference, returns dict mapping target_word str to enumerated definition strings'''
        def_dict = {}

        for tr_list in self.tr_dict.values():
            frWrd = ""
            pos = ""
            definitions = []
            for tr in tr_list:
                to2 = ""
                toWrd = ""
                tds = tr.find_all('td')
                for td in tds:
                    if 'FrWrd' in td.get('class', []):
                        frWrd += td.strong.text.replace('⇒', '')
                        pos += td.em.text     
                    if 'To2' in td.get('class', []):
                        to2 += f"({td.i.string})"
                    if 'ToWrd' in td.get('class', []):   
                        toWrd += td.contents[0].strip()   
                definition = f"{to2} {toWrd}"
                definition = definition.strip()
                if definition:
                    definitions.append(definition)
            # Make sure the definition matches the target
            if frWrd == self.target_word:
                entry = f'{frWrd} ({pos})'
                if entry not in def_dict:
                    def_dict[entry] = [definitions]
                else:
                    def_dict[entry].append(definitions)
        def_dict_enum = {}
        for target_word, list_of_defs in def_dict.items():
            def_str = ""
            for idx, definition in enumerate(list_of_defs, start=1):
                def_str += f'''{idx}. {", ".join(definition)}'''
                if idx < len(list_of_defs):
                    def_str += '; '
            if target_word not in def_dict_enum:
                def_dict_enum[target_word] = def_str
            else:
                def_dict_enum[target_word].append(def_str)

        return def_dict_enum
    
    def get_examples(self) -> list[str]:
        '''Fetches example sentences from WordReference, returns a list of strings'''
        example_sentences = []

        for tr_list in self.tr_dict.values():
            for tr in tr_list:
                tds = tr.find_all('td')
                for td in tds:
                    if 'FrEx' in td.get('class', []):   
                        example_sentences.append(td.get_text())  
        return example_sentences
    
    def to_dict(self) -> dict:
        '''Aggregate all collected data into a dictionary'''
        inflections = self.get_inflections()
        examples = self.get_examples()
        audio = self.get_audio()
        pronunciations = self.get_pronunciations()
        definitions = self.get_definitions()

        # Aggregate all collected data into a dictionary
        return {
            "target_word": self.target_word,
            "definitions": definitions,
            "pronunciations": pronunciations,
            "inflections": inflections,
            "examples": examples,
            "audio": audio
        }

@dataclass
class Wiktionnaire:
    # target_word is the word that we want to define 
    target_word: str

    def __post_init__(self):
        self.soup = self._get_soup()
        self.article_head = self._get_article_head()
        self.p_pron = self._get_p_pron()

    def _get_soup(self) -> BeautifulSoup:
        url = f"https://fr.wiktionary.org/wiki/{self.target_word}"
        self.soup = BeautifulSoup(requests.get(url).content, "html.parser")
        return self.soup
    
    def _get_article_head(self) -> Tag:
        """Fetches the articleHead for the target word and returns a Tag object."""
        return self.soup.find('div', class_='mw-content-ltr mw-parser-output') if self.soup else None
    
    def _get_p_pron(self) -> list[Tag]:
        """Fetches the p_pron spans, returns a list of bs4 Tags."""
        p_all = self.article_head.find_all('p')
        # Not all p tags contain both the pronunciation and gender; filter if missing
        if p_all:
            p_pron = []
            for p in p_all:
                children = p.children
                values = list(chain(*([c.attrs.values() for c in children if isinstance(c, Tag)])))
                if values == ['/wiki/Annexe:Prononciation/fran%C3%A7ais', 'Annexe:Prononciation/français', ['ligne-de-forme']]:
                    p_pron.append(p)
        return p_pron

    def get_pronunciations(self) -> list:
        """Fetches the pronunciations."""
        # Pronunciation
        pronunciations = []

        if self.p_pron:
            for p in self.p_pron:
                pronunciation_span = p.find('span', title="Prononciation API")
                if pronunciation_span:
                    pronunciation = f"[{pronunciation_span.text[1:-1].replace('.','')}]"
                    if pronunciation not in pronunciations:
                        pronunciations.append(pronunciation)
        return pronunciations

    def get_genders(self) -> list:
        """Fetches the genders."""
        # Pronunciation and Gender
        genders = []

        if self.p_pron:
            for p in self.p_pron:
                gender_span = p.find('span', class_="ligne-de-forme")
                if gender_span:
                    gender_dict = {
                        'féminin': '(nf)',
                        'masculin': '(nm)',
                        'masculin et féminin identiques': '(nmf)',
                    }
                    gender = gender_dict[gender_span.text]
                    if gender not in genders:
                        genders.append(gender)
        return genders

    def get_definitions(self) -> list:
        # Definitions
        for h in self.article_head:
            print(h.find_next())



pp = pprint.PrettyPrinter(indent=4)
pendule = Wiktionnaire('pendule')
pp.pprint(pendule.get_definitions())

# target = 'pomme'
# soup = get_soup(target)
# # data = get_wr_french(soup)
# inflections = get_wr_inflections(soup, target)
# audio = get_wr_audio(soup)


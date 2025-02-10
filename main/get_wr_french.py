import ast
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from dataclasses import dataclass
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

    def get_wr_pronunciations(self) -> str:
        '''Fetches pronunciations from WordReference'''
        pronunciation_span = self.article_head.find('span', class_='pronWR')
        return pronunciation_span.text if pronunciation_span.text else None

    def get_wr_inflections(self) -> dict[str, list[str]]:
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

    def get_wr_audio(self) -> list[str]:
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
                head = 'https://www.wordreference.com'
                audio_file = f'{head}{file}'
                if audio_file not in audio_files:
                    audio_files.append(audio_file)
        
        return audio_files

    def get_wr_definitions(self) -> dict[str, str]:
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
    
    def get_wr_example_sentences(self) -> list[str]:
        '''Fetches example sentences from WordReference, returns a list of strings'''
        example_sentences = []

        for tr_list in self.tr_dict.values():
            for tr in tr_list:
                tds = tr.find_all('td')
                for td in tds:
                    if td.attrs:
                        if "FrEx" in td['class']:
                            example_sentences.append(td.get_text())
        return example_sentences
    
    def to_dict(self) -> dict:
        '''Aggregate all collected data into a dictionary'''
        inflections = self.get_wr_inflections()
        examples = self.get_wr_example_sentences()
        audio = self.get_wr_audio()
        pronunciations = self.get_wr_pronunciations()
        definitions = self.get_wr_definitions()

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
        self.tr_dict = self._get_tr_dict()


pp = pprint.PrettyPrinter(indent=4)
pomme = WordReference('pomme')
pp.pprint(pomme.to_dict())

# target = 'pomme'
# soup = get_soup(target)
# # data = get_wr_french(soup)
# inflections = get_wr_inflections(soup, target)
# audio = get_wr_audio(soup)


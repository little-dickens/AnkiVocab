import ast
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString
from dataclasses import dataclass
from itertools import chain
import pprint
import json

class DefinitionNotFoundError(Exception):
    """Raised when no definition can be found for the target word."""
    pass

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
        result = self.soup.find("div", id="articleHead") if self.soup else None
        if result is None:
            raise DefinitionNotFoundError("Definition does not exist")
        return result

    def _get_tr_dict(self) -> dict[str, list[Tag]]:
        """Fetches the data tables for the target word and returns a dict mapping strings to lists of Tags."""
        tables_all = self.soup.find_all("table", class_="WRD")
        if len(tables_all) == 0:
            raise DefinitionNotFoundError("Definition does not exist")
        
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
            return ""
        pronunciation_span = self.article_head.find('span', class_='pronWR')
        if pronunciation_span is None:
            return ""
        else: 
            return pronunciation_span.text

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

    # def get_definitions(self) -> dict[str, list[str]]:
    #     '''Fetches definitions from WordReference, returns dict mapping target_word str to enumerated definition strings'''
    #     def_dict = {}

    #     for tr_list in self.tr_dict.values():
    #         frWrd = ""
    #         pos = ""
    #         definitions = []
    #         for tr in tr_list:
    #             to2 = ""
    #             toWrd = ""
    #             tds = tr.find_all('td')
    #             for td in tds:
    #                 if 'FrWrd' in td.get('class', []):
    #                     frWrd += td.strong.text.replace('⇒', '')
    #                     pos += td.em.text
    #                 if td.span:
    #                     if 'dsense' in td.span.get('class', []):
    #                         to2 += td.span.get_text()
    #                 if 'ToWrd' in td.get('class', []):   
    #                     toWrd += td.contents[0].strip()
    #             definition = f"{to2} {toWrd}"
    #             print(definition)
    #             definition = definition.strip()
    #             if definition:
    #                 definitions.append(definition)
    #             # Make sure the definition matches the target
    #             if frWrd == self.target_word:
    #                 entry = f'{frWrd} ({pos})'
    #                 if entry not in def_dict:
    #                     def_dict[entry] = [definitions]
    #                 else:
    #                     def_dict[entry].append(definitions)
    #     # Now we want to enumerate the definitions by each word group
    #     def_dict_enum = {}
    #     for target_word, list_of_defs in def_dict.items():
    #         def_str = ""
    #         for idx, definition in enumerate(list_of_defs, start=1):
    #             def_str += f'''{idx}. {", ".join(definition)}'''
    #             if idx < len(list_of_defs):
    #                 def_str += '; '
    #         if target_word not in def_dict_enum:
    #             def_dict_enum[target_word] = def_str
    #         else:
    #             def_dict_enum[target_word].append(def_str)

    #     return def_dict

    # def get_definitions(self) -> dict[str, str]:
    #     raw_defs: dict[str, list[str]] = {}

    #     for tr_list in self.tr_dict.values():
    #         # Build the key from the first row: "word (pos)"
    #         first = tr_list[0]
    #         fr_td = first.find("td", class_="FrWrd")
    #         if not fr_td or not fr_td.strong or not fr_td.em:
    #             continue
    #         key = f"{fr_td.strong.text.strip()} ({fr_td.em.text.strip()})"
    #         raw_defs.setdefault(key, [])

    #         # Extract each sense/gloss
    #         for tr in tr_list:
    #             tds = tr.find_all("td")
    #             if len(tds) < 3:
    #                 continue

    #             # Only look in the *middle* cell for a dsense
    #             dsense_span = tds[1].find("span", class_="dsense")
    #             if dsense_span:
    #                 sense = dsense_span.get_text(strip=True).strip("()")
    #                 prefix = f"({sense}) "
    #             else:
    #                 prefix = ""

    #             # Grab the very first text node from the 3rd cell
    #             gloss = None
    #             for node in tds[2].contents:
    #                 if isinstance(node, NavigableString) and node.strip():
    #                     gloss = node.strip()
    #                     break
    #             if not gloss:
    #                 continue

    #             # Remove any trailing ⇒
    #             if "⇒" in gloss:
    #                 gloss = gloss.split("⇒", 1)[0].strip()

    #             raw_defs[key].append(f"{prefix}{gloss}")

    #     if not raw_defs:
    #         raise DefinitionNotFoundError("Definition does not exist")

    #     # Dedupe and enumerate
    #     final_defs: dict[str, str] = {}
    #     for key, senses in raw_defs.items():
    #         seen = []
    #         for s in senses:
    #             if s not in seen:
    #                 seen.append(s)
    #         enumerated = "; ".join(f"{i+1}. {s}" for i, s in enumerate(seen))
    #         final_defs[key] = enumerated

    #     return final_defs

    def get_definitions(self) -> dict[str, str] | str:
        """
        If there are real definitions, returns a dict mapping
        “word (pos)” → enumerated senses.
        If the page is only an inflection (e.g. “eusse”), returns "".
        Otherwise raises DefinitionNotFoundError.
        """
        # detect an inflection‐only page
        is_inflection_only = bool(self.soup.find("div", class_="otherWRD"))

        # 1) scrape all the <tr> groups into raw_defs
        raw_defs: dict[str, list[str]] = {}
        for tr_list in self.tr_dict.values():
            first = tr_list[0]
            fr_td = first.find("td", class_="FrWrd")
            if not fr_td or not fr_td.strong or not fr_td.em:
                continue
            key = f"{fr_td.strong.text.strip()} ({fr_td.em.text.strip()})"
            raw_defs.setdefault(key, [])

            for tr in tr_list:
                tds = tr.find_all("td")
                if len(tds) < 3:
                    continue

                dsense = tds[1].find("span", class_="dsense")
                prefix = f"({dsense.get_text(strip=True).strip('()')}) " if dsense else ""

                # first real text node in the English cell
                gloss = None
                for node in tds[2].contents:
                    if isinstance(node, NavigableString) and node.strip():
                        gloss = node.strip()
                        break
                if not gloss:
                    continue

                if "⇒" in gloss:
                    gloss = gloss.split("⇒", 1)[0].strip()

                raw_defs[key].append(f"{prefix}{gloss}")

        # 2) if we found nothing at all…
        if not raw_defs:
            if is_inflection_only:
                # e.g. “eusse”-only pages
                return ""
            raise DefinitionNotFoundError("Definition does not exist")

        # 3) dedupe & enumerate the ones we did find
        final_defs: dict[str, str] = {}
        for key, senses in raw_defs.items():
            seen: list[str] = []
            for s in senses:
                if s not in seen:
                    seen.append(s)
            enumerated = "; ".join(f"{i+1}. {s}" for i, s in enumerate(seen))
            final_defs[key] = enumerated

        return final_defs


    def get_examples(self) -> list[str]:
        '''Fetches example sentences from WordReference, returns a list of strings'''
        example_sentences = []

        for tr_list in self.tr_dict.values():
            for tr in tr_list:
                tds = tr.find_all('td')
                for td in tds:
                    if 'FrEx' in td.get('class', []): 
                        if td.get_text() not in example_sentences:
                            # if self.target_word in td.get_text():
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
        result = self.soup.find('div', class_='mw-content-ltr mw-parser-output') if self.soup else None
        if result is None:
            raise DefinitionNotFoundError("Definition does not exist")
        return result
        
        # return self.soup.find('div', class_='mw-content-ltr mw-parser-output') if self.soup else None
    
    def _get_p_pron(self) -> list[str]:
        """Fetches the p_pron spans and parses pronunciation, returning as a list of strs"""
        p_all = self.article_head.find_all('p')
        # Not all p tags contain both the pronunciation and gender; filter if missing
        if p_all:
            p_pron = []
            for p in p_all:
                p_pron.append(p)
        return p_pron

    def get_pronunciations(self) -> list[str]:
        """Fetches the pronunciations."""
        # Pronunciation
        pronunciations = []

        if self.p_pron:
            for p in self.p_pron:
                ipas = [span.get_text().strip('\\') for span in p.select('span.API')]
                for ipa in ipas:
                    if ipa not in pronunciations:
                        pronunciations.append(ipa)
                # children = p.children
                # values = list(chain(*([c.attrs.values() for c in children if isinstance(c, Tag)])))
                # # print(values)
                # tag = p.find("a", {"data-mw": True})
                # print(tag)
                # raw = tag["data-mw"]
                # mw = json.loads(raw)
                # params = mw["parts"][0]["template"]["params"]
                # ipa = params.get("1", {}).get("wt")
                # pronunciations.append(ipa)
                # print(ipa)
                # for v in values:
                    
                #     if isinstance(v, set):
                #         print(v)
                # parts = values[-1]
                # parts_json = json.loads(parts)
                # params = parts_json['parts'][0]['template']['params']
                # if '1' in params:
                #     pronunciations.append(params['1']['wt'])
        return pronunciations

    def get_genders(self) -> list[str]:
        """Fetches the genders."""
        # Pronunciation and Gender
        genders = []
        if self.p_pron:
            for p in self.p_pron:
                gender_span = p.find('span', class_="ligne-de-forme")
                if gender_span:
                    gender_typeof = gender_span.find('i').get_text()

                    gender_dict = {
                        'féminin': '(nf)',
                        'masculin': '(nm)',
                        'masculin et féminin identiques': '(nmf)',
                    }
                    if gender_typeof in gender_dict:
                        gender = gender_dict[gender_span.find('i').get_text()]
                        if gender not in genders:
                            genders.append(gender)
        return genders
    
    def get_audio(self) -> list[str]:
        '''Fetches list of audio url strs from Wiktionnaire'''
        # audio_elements = self.soup.find_all('span', class_='audio-file')
        audio_elements = self.soup.find_all('audio', class_='mw-file-element')

        audio_files = []

        for audio_element in audio_elements:
            link = audio_element['resource']
            while link.startswith('/'):
                link = link[1:]
            audio_files.append(link)
        return audio_files

    def get_definitions(self) -> dict[str, list[str]]:   
        '''Fetches the definitions'''
        def_dict = {}
        ''' 
        <ol> is the master tag for definitions, but also supplemental info like translations, composite forms, etc.
        We only want the definitions of each word, whose <ol> tags appear at the top. 
        Normally, we'd just take the first <ol> tag, but some words like 'pendule' have different genders and thus different meanings (lets call these 'word groups').
        So, get the length of the genders list and then use that to splice the ol_all list.
        '''
        genders = self.get_genders()
        definition_group_count = len(genders)
        ol_all = self.article_head.find_all('ol')[:definition_group_count]
        list_of_li_groups = []
        '''
        We want to group the <li> tags by their <ol> parent, each occurence of which should be a unique word group (i.e. [<tags> for 'pendule (nm)', <tags> for 'pendule (nf)'])
        That way, we can keep the definitions of each word separate
        '''
        for ol in ol_all:
            list_of_li_groups.append(ol.find_all('li'))
        for li_list_idx, li_list in enumerate(list_of_li_groups):
            def_list = []
            for li in li_list:
                def_str = ""
                li_contents = li.contents
                for item in li_contents:
                    # Filter out the example sentences (contained in <span> and <ul> tags)
                    if item.name is None or item.name not in ('span', 'ul'):
                        if isinstance(item, Tag):
                            def_str += item.get_text().replace('\n',' ')
                        else:
                            def_str += item.replace('\n',' ')
                if def_str:
                    def_list.append(def_str.strip())
            def_dict[f'''{self.target_word} {genders[li_list_idx]}'''] = def_list
        # Now we want to enumerate the definitions by each word group
        def_dict_enum = {}
        for target_word, list_of_defs in def_dict.items():
            def_str = ''
            for idx, definition in enumerate(list_of_defs, start=1):
                def_str += f'''{idx}. {definition}'''
                if idx < len(list_of_defs):
                    def_str = def_str[:-1] + '; '
                def_dict_enum[target_word] = def_str
        return def_dict

    def get_examples(self) -> dict[str, list[str]]:   
        '''Fetches the definitions'''
        example_dict = {}
        ''' 
        <ol> is the master tag for definitions, but also supplemental info like translations, composite forms, etc.
        We only want the definitions of each word, whose <ol> tags appear at the top. 
        Normally, we'd just take the first <ol> tag, but some words like 'pendule' have different genders and thus different meanings (lets call these 'word groups').
        So, get the length of the genders list and then use that to splice the ol_all list.
        '''
        genders = self.get_genders()
        definition_group_count = len(genders)
        ol_all = self.article_head.find_all('ol')[:definition_group_count]
        list_of_li_groups = []
        '''
        We want to group the <li> tags by their <ol> parent, each occurence of which should be a unique word group (i.e. [<tags> for 'pendule (nm)', <tags> for 'pendule (nf)'])
        That way, we can keep the definitions of each word separate
        '''
        for ol in ol_all:
            list_of_li_groups.append(ol.find_all('li'))
        for li_list_idx, li_list in enumerate(list_of_li_groups):
            example_list = []
            for li in li_list:
                example_str = ""
                li_contents = li.contents
                for item in li_contents:
                    # Filter out the example sentences (contained in <span> and <ul> tags)
                    if item.name in ('span', 'ul'):
                        example_str += item.get_text().replace('\xa0','')
                if example_str:
                    example_list.append(example_str.strip())
            example_dict[f'''{self.target_word} {genders[li_list_idx]}'''] = example_list
        # Now we want to enumerate the definitions by each word group
        example_dict_enum = {}
        for target_word, list_of_defs in example_dict.items():
            example_str = ''
            for idx, definition in enumerate(list_of_defs, start=1):
                example_str += f'''{idx}. {definition}'''
                if idx < len(list_of_defs):
                    example_str = example_str[:-1] + '; '
                example_dict_enum[target_word] = example_str
        return example_dict
    
    def to_dict(self) -> dict:
        '''Aggregate all collected data into a dictionary'''
        # inflections = self.get_inflections()
        examples = self.get_examples()
        audio = self.get_audio()
        pronunciations = self.get_pronunciations()
        definitions = self.get_definitions()

        # Aggregate all collected data into a dictionary
        return {
            "target_word": self.target_word,
            "definitions": definitions,
            "pronunciations": pronunciations,
            # "inflections": inflections,
            "examples": examples,
            "audio": audio
        }

pp = pprint.PrettyPrinter(indent=4)

pendule_wr = Wiktionnaire('pendule')
pp.pprint(pendule_wr.to_dict())

# pomme = WordReference('pendule')
# pp.pprint(pomme.to_dict())
# pomme.to_dict()

# target = 'pomme'
# soup = get_soup(target)
# # data = get_wr_french(soup)
# inflections = get_wr_inflections(soup, target)
# audio = get_wr_audio(soup)


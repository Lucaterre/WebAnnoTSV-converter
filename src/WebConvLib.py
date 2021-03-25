# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""Main Class and Functions in WebAnnoTSV-converter
to read a Web anno TSV v3 format.

NOTES :
- The code adapted from web-anno-tsv Python package | https://pypi.org/project/web-anno-tsv/
- Entity-fishing Python client use for find Wikipedia page ID

"""
# Licence : MIT

from dataclasses import dataclass, field
from typing import List, Dict, Union, Tuple, Generator, Optional, TextIO
from itertools import groupby
import uuid
import re
from collections import defaultdict
import traceback

from nerd import nerd_client


class ReadException(Exception):
    pass

@dataclass
class Annotation:
    label: str
    text: str
    start: int
    stop: int
    length: int
    wikiname: str
    wikidata_id: str
    wikipedia_id: str
    id: Optional[str] = None


@dataclass
class Span:
    text: str
    start: int
    stop: int
    length: int
    wikiname: Optional[str]
    wikidata_id: Optional[str]
    wikipedia_id: Optional[str]
    is_token: bool = False
    id: Optional[str] = None


@dataclass
class SpanAnnotation:
    span: Span
    annotations: Dict[str, str] = field(default_factory={})


@dataclass
class AnnotatedSentence:
    text: str
    tokens: []
    annotations: List[Annotation]


def escape_text(text: str) -> str:
    """The Inception doc is wrong about what it is really escaped
    """
    text = text.replace('\\', '\\\\')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    return text


def un_escape_text(text: str) -> str:
    """The Inception doc is wrong about what it is really escaped
    """
    text = re.sub(r'(?<=\\)\\r', '\r', text)
    text = re.sub(r'(?<=\\)\\t', '\t', text)
    return text

def fetch_wikipedia_prefferedterm_page_id(concept_wikidata: str, api_base: str, language: str) -> str:
    # Fetch Wikipedia term and Wikipedia page id with Entity-Fishing API
    client = nerd_client.NerdClient(apiBase=api_base)
    client.api_base = api_base
    content, response = client.get_concept(concept_wikidata, lang=language)

    if language == "en":
        wikiname = content['preferredTerm']
        wikipedia_page = content['wikipediaExternalRef']
    else:
        # other language (de, fr, es, it)
        for i in content['multilingual']:
            if i['lang'] == language:
                wikiname = i['term']
                wikipedia_page = i['page_id']

    return wikipedia_page, wikiname



class IndexMapper:
    """To deal with special Inception string offsets. Cf Appendix B: WebAnno TSV 3.2 File format
    """
    def __init__(self, text):
        self.map: List[Tuple[int, int]] = []
        self.inverse: List[Tuple[int, int]] = []

        for i, char in enumerate(text):
            char_java_length = len(char.encode('utf-16-le')) // 2  # le (little indian) to avoid BOM mark
            if i == 0:
                start = 0
            else:
                start = self.map[-1][1]
            stop = start + char_java_length
            self.map.append((start, stop))

            for _ in range(char_java_length):
                self.inverse.append((i, i+ 1))

    @staticmethod
    def utf16_blocks(text: str):
        return len(text.encode('utf-16-le')) // 2

    def true_offsets(self, start: int, stop: int) -> Tuple[int, int]:
        return self.inverse[start][0], self.inverse[stop - 1][1]

    def java_offsets(self, start: int, stop: int) -> Tuple[int, int]:
        return self.map[start][0], self.map[stop - 1][1]


class Reader:
    def __init__(self, file_path: str, api_base: str, language: str):
        self.file_path = file_path

        self.api_base = api_base
        self.language = language


        self.header: str = ''
        with open(self.file_path, encoding='utf-8') as f:
            header = []
            for line in f:
                line = line.strip()
                if line == '':
                    self.header_size = len(header)
                    self.header = "\n".join(header)
                    break
                header.append(line)

        self.f: Optional[TextIO] = None

    def read(self) -> Generator[AnnotatedSentence, None, None]:
        if not self.f:
            self.open()

        sentence_index: int = 0
        lines: List[str] = []
        n: int = 0

        while True:
            line = self.f.readline()
            n += 1
            if n > self.header_size + 2:
                if line == '\n' or line == "":
                    # A sentence block has stop
                    annotated_sentence = Reader.get_annotated_sentence(lines, sentence_index, self.api_base, self.language)
                    yield annotated_sentence
                    lines = []
                    sentence_index += 1
                else:
                    # Remove \n at the stop of the line.
                    # We don't use strip() to preserve other whitespaces if any
                    lines.append(line[0:-1])

            # End of file
            if line == '':
                break

        self.close()

    @staticmethod
    def sentence_part(line) -> Optional[str]:
        """
        :param line: sentence
        :return:    "text" -> for text block
                    token_index -> for tokens and associated sub-tokens (token and sub-tokens are grouped)
        """
        if line.startswith('#Text='):
            return 'text'
        elif line == '':
            return None
        else:
            return re.sub(r"\.[0-9]+", '', line[line.index('-') + 1: line.index('\t')])

    @staticmethod
    def get_annotated_sentence(lines: List[str], sentence_index: int, api_base: str, language: str) -> AnnotatedSentence:
        sentence = ''
        try:
            spans: Union[List[Span], Span] = []
            annotations = defaultdict(list)
            labels = {}
            for group_index, (group_id, group) in enumerate(groupby(lines, key=lambda l: Reader.sentence_part(l))):
                group = list(group)
                if group_id == 'text':
                    # Extract sentence
                    sentence = "\n".join([un_escape_text(line[6:]) for line in group])

                else:
                    # Extract annotations
                    for j, line in enumerate(group):
                        if line != '':
                            # # Read the token line
                            span_annotation = Reader.read_token_line(line, api_base, language)
                            span = span_annotation.span

                            # Register span
                            spans.append(span)

                            # Annotations
                            for label_id, label in span_annotation.annotations.items():
                                if annotations[label_id] and span.start == annotations[label_id][-1].start:
                                    # In Inception, for some strange reasons,
                                    # The entire token inherits label from the the first sub-word,
                                    # if this sub-word is at the beginning of the token.
                                    # We remove it.
                                    annotations[label_id] = annotations[label_id][:-1]
                                labels[label_id] = label
                                annotations[label_id].append(span)

            # 3 things:
            # - Offsets correction [Cf Appstopix B: WebAnno TSV 3.2 File format]
            # - Make offsets relative to sentence
            # - Validation of the offsets calculation
            mapper: IndexMapper = IndexMapper(sentence)
            first_span_start: Optional[int] = None
            for i, span in enumerate(spans):
                if i == 0:
                    first_span_start = span.start
                span.start, span.stop = mapper.true_offsets(span.start - first_span_start, span.stop - first_span_start)

                error = f"Bad offsets ({span.start}, {span.stop}) for span `{span.text}`"
                assert sentence[span.start: span.stop] == span.text, error

            # Compact annotation
            compacted_annotations = []
            for annotation_id, annotation_parts in annotations.items():
                if len(annotation_parts) > 1:
                    # Check that annotations are compact
                    for p1, p2 in zip(annotation_parts, annotation_parts[1:]):
                        space = sentence[p1.stop: p2.start]
                        error = f"Annotation is not compact between {p1} and {p2}"
                        assert sentence[p1.stop: p2.start].isspace() or not space, error

                    # Compacts
                    start = annotation_parts[0].start
                    stop = annotation_parts[-1].stop
                    wiki_name = annotation_parts[0].wikiname
                    wikidata = annotation_parts[0].wikidata_id
                    wikipedia = annotation_parts[0].wikipedia_id
                else:
                    start = annotation_parts[0].start
                    stop = annotation_parts[0].stop
                    wiki_name = annotation_parts[0].wikiname
                    wikidata = annotation_parts[0].wikidata_id
                    wikipedia = annotation_parts[0].wikipedia_id

                compacted_annotations.append(Annotation(
                    label=labels[annotation_id],
                    text=sentence[start: stop],
                    wikiname=wiki_name,
                    wikidata_id=wikidata,
                    wikipedia_id=wikipedia,
                    length=stop - start,
                    start=start,
                    stop=stop))

            # Extract tokens
            tokens = [span for span in spans if span.is_token]

            # Sort annotations
            compacted_annotations.sort(key=lambda a: (a.start, -a.stop, a.label))

            return AnnotatedSentence(sentence, tokens, compacted_annotations)
        except Exception as e:
            tb = traceback.format_exc()
            tb_str = str(tb)
            message = f'Sentence {sentence_index}: `{sentence}` ' + tb_str
            raise ReadException(message)

    @staticmethod
    def read_token_line(line, api_base: str, language: str):
        columns = line.split('\t')

        # Id
        span_id = columns[0]

        # Offsets
        start, stop = map(int, columns[1].split('-'))

        # Span text
        span_text = un_escape_text(columns[2])

        # Annotations
        annotations = {}
        if columns[4] != '_':
            for part in columns[4].split('|'):
                res = re.search(r'([^[]*)(\[(\d*)\])*$', part)
                label = res.group(1)
                label_id = res.group(3)
                if not label_id:
                    label_id = str(uuid.uuid4())
                annotations[label_id] = label

        # Wikidata ID, Wikipedia page ID and Wikiname
        span_wikidata_id = columns[5]
        if span_wikidata_id == "_":
            wikidata_id = "null"
            wikipedia_page_id = -1
            wiki_name = "null"
        else:
            wikidata_id = re.sub(r'http.+/(Q\d+)\[?.*\]?', r'\1', span_wikidata_id)
            wikipedia_page_id, wiki_name = fetch_wikipedia_prefferedterm_page_id(str(wikidata_id), api_base, language)

        return SpanAnnotation(
            span=Span(
                id=span_id,
                start=start,
                stop=stop,
                length=stop - start,
                wikiname=wiki_name,
                wikidata_id=wikidata_id,
                wikipedia_id=wikipedia_page_id,
                text=span_text,
                is_token="." not in span_id
            ),
            annotations=annotations
        )

    def open(self):
        self.f = open(self.file_path, encoding='utf-8')

    def close(self):
        if self.f:
            self.f.close()
            self.f = None

    def __iter__(self):
        return self.read()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def open_web_anno_tsv(file_path: str, api_base, language, mode: str = 'r'):
    if mode == 'r':
        return Reader(file_path, api_base, language)
    else:
        raise ValueError(f'Invalid mode {mode}')


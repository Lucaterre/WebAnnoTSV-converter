# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""CLI Control WebAnnoTSV-converter
"""
# Licence : MIT

import os
import re
import time
import datetime

import click
import pyfiglet

from src._export_utils import to_csv, to_xml
from src._utils import _report_log, _timing
from src.WebConvLib import open_web_anno_tsv


ASCII_LOGO = pyfiglet.figlet_format("| WebAnnoTSV Converter |")
date = datetime.datetime.now()

@click.command()
@click.argument('file',
                nargs=1)
@click.argument('output',
                nargs=1)
@click.option('-od',
              '--output_dir',
              default="./out/",
              show_default=True,
              type=str,
              required=False,
              help='You can indicate the output '
                   'directory of your file.')
@click.option('-pn',
              '--project_name',
              default='my_project',
              show_default=True,
              required=False,
              help='If you choose xml format, you can indicate a name '
                   'project for root tag, possibility to change after.')
@click.option('-v', '--verbose',
              default=False,
              show_default=True,
              type=click.BOOL,
              required=False,
              help='Indicate if you want logs during process.')
@click.option('-api',
              '--api_base',
              default="http://nerd.huma-num.fr/nerd/service/",
              show_default=True,
              type=str,
              required=False,
              help='If you have a local instance of Entity-Fishing to recognize identifiers as'
                   'Wikipage ID or Wikidata ID, you can indicate'
                   'here your used service.')
@click.option('-l',
              '--language',
              default="fr",
              show_default=True,
              type=str,
              required=False,
              help='If you use a specific language as fr, en, de, it, es, indicate here.')

@_timing
def main(file: str,
         verbose: bool,
         output: str,
         output_dir: str,
         project_name: str,
         api_base: str,
         language: str):
    """
    WebAnnoTSV-converter\b\n
    2021\b\n
    -----------------------\b\n
    A tool that helps you transform your WebAnno TSV 3.2
    annotated files (FILE: relative or absolute path) from the Inception platform
    into (OUTPUT: "csv" / "xml") CSV format for read-only or into XML
    compatible with Entity-fishing for evaluate or training NER & NED.\b\n
    A tool use Entity-fishing (API) Python client with "Concept look-up" service to find Wikipedia page ID.
    """

    print(ASCII_LOGO)
    print(f'{date.strftime("%Y-%m-%d %H:%M:%S")}\n')
    _report_log(f"Start process with file : {file} | type output :  {output} | verbose : {verbose}", type_log="V")
    time.sleep(3)

    filename = os.path.basename(file)
    filename = re.sub(r'\.tsv', '', filename)

    data = []

    with open_web_anno_tsv(file, api_base, language) as f:
        for i, sentence in enumerate(f):
            sentence_text = sentence.text
            index_sentence = i
            if verbose:
                print(f"Sentence {index_sentence}: ", sentence_text)
            for j, annotation in enumerate(sentence.annotations):
                index_annot = j
                text = annotation.text
                label = annotation.label
                offset_start = annotation.start
                offset_end = annotation.stop
                length = annotation.length
                wikiname = annotation.wikiname
                wikidata_id = annotation.wikidata_id
                wikipedia_page_id = annotation.wikipedia_id
                if verbose:
                    print(f'\tAnnotation {index_annot}:')
                    print('\t\tText :', text)
                    print("\t\tLabel :", label)
                    print("\t\tOffset Start : ", f"{offset_start}")
                    print("\t\tOffset End : ", f"{offset_end}")
                    print("\t\tTotal length : ", length)
                    print("\t\tWikiName : ", wikiname)
                    print("\t\tWikidata ID : ", wikidata_id)
                    print("\t\tWikipedia page ID : ", wikipedia_page_id)
                data.append((index_sentence,
                             sentence_text,
                             index_annot,
                             text,
                             label,
                             offset_start,
                             offset_end,
                             length,
                             wikiname,
                             wikidata_id,
                             wikipedia_page_id))

    try:
        if output.lower() == "csv":
            to_csv(data,
                   filename,
                   out_dirname=output_dir)
            _report_log(f"Finish with success find your document in out/ directory",
                        type_log="S")
        if output.lower() == "xml":
            to_xml(data,
                   filename,
                   out_dirname=output_dir,
                   project_name=project_name)
            _report_log(f"Finish with success find your document in out/ directory",
                        type_log="S")
    except AttributeError:
        _report_log(f"you did not specify an output format: 'csv' or 'xml' for {filename} file", type_log='E')


if __name__ == '__main__':
    main()

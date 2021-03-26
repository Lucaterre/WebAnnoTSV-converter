# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""Export functions code for WebAnnoTSV-converter
"""
# Licence : MIT

import csv
import lxml.etree as ET


def to_csv(data, file_name, out_dirname):
    file = open(out_dirname + file_name + ".csv", "w")
    writer = csv.writer(file)
    writer.writerow(('Index_sentence',
                     'Sentence',
                     'Index_annotation',
                     'Entity',
                     'Label',
                     'Offset_Start',
                     'Offset_End',
                     'Length',
                     'Wikipedia_name',
                     'Wikidata_ID',
                     'Wikipedia_page_ID'
                     ))

    for line in data:
        writer.writerow(line)

    file.close()


def to_xml(data, file_name, out_dirname, project_name="my_project"):
    root = ET.Element(f'{project_name}.entityAnnotation')
    document = ET.SubElement(root, 'document')
    document.set('docName', f'{file_name}.txt')

    for line in data:
        mention_name = line[3]
        wikiname = line[8]
        wikidataid = line[9]
        wikipediaid = line[10]
        offset_start = line[5]
        length = line[7]

        annotation_tag = ET.SubElement(document, 'annotation')

        mention = ET.SubElement(annotation_tag, 'mention')
        mention.text = str(mention_name)
        wiki_name = ET.SubElement(annotation_tag, 'wikiName')
        wiki_name.text = str(wikiname)
        wikidata_id = ET.SubElement(annotation_tag, 'wikidataId')
        wikidata_id.text = str(wikidataid)
        wikipedia_id = ET.SubElement(annotation_tag, 'wikipediaId')
        wikipedia_id.text = str(wikipediaid)
        offset = ET.SubElement(annotation_tag, 'offset')
        offset.text = str(offset_start)
        l = ET.SubElement(annotation_tag, 'length')
        l.text = str(length)

    b_xml = ET.tostring(root, pretty_print=True, encoding='utf-8')

    with open(out_dirname + project_name + ".xml", "wb") as f:
        f.write(b_xml)


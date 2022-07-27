import argparse
import csv
import json
import sqlite3

"""
Add lemmas with difficulty value converted from the Excel file of the paper
"Estimating the prevalence and diversity of words in written language" by
Johns, B. T., Dye, M., & Jones, M. N.
http://btjohns.com/pubs/JDJ_QJEP_2020.pdf
http://btjohns.com/JDJ_Prev_supp.xlsx
"""

parser = argparse.ArgumentParser()
parser.add_argument("csv_path", help="path of CSV file exported from Excel.")
parser.add_argument("klld", help="path of kll.en.en.klld file.")
args = parser.parse_args()


# Convert the semantic diversity-author prevalence(SD-AP) value to difficulty
def sd_ap_to_difficulty(sd_ap: float) -> int:
    if sd_ap >= 4:
        return 5
    elif sd_ap >= 3:
        return 4
    elif sd_ap >= 2:
        return 3
    elif sd_ap >= 1:
        return 2
    else:
        return 1


words_dict = {}
simple_words = set()
with open(args.csv_path, newline="") as f:
    for row in csv.reader(f):
        word = row[0]
        sd_ap = row[-1]
        if not word or not sd_ap:
            continue
        sd_ap = float(sd_ap)
        if sd_ap >= 5:
            simple_words.add(word)
            continue
        words_dict[word] = sd_ap_to_difficulty(sd_ap)

with open("lemmas.json", encoding="utf-8") as f:
    lemmas_dict = json.load(f)

klld_conn = sqlite3.connect(args.klld)

for lemma, sense_id, pos_type in klld_conn.execute(
    'SELECT lemma, senses.id, pos_type FROM lemmas JOIN senses ON lemmas.id = display_lemma_id WHERE (full_def IS NOT NULL OR short_def IS NOT NULL) AND lemma NOT like "-%" ORDER BY lemma'
):
    if lemma.lower() in words_dict:
        if lemma not in lemmas_dict:
            lemmas_dict[lemma] = [words_dict[lemma.lower()], sense_id, pos_type]
        elif lemmas_dict[lemma][0] < words_dict[lemma.lower()]:
            lemmas_dict[lemma][0] = words_dict[lemma.lower()]
    elif lemma.lower() in simple_words:
        del lemmas_dict[lemma]

klld_conn.close()
with open("lemmas.json", "w", encoding="utf-8") as f:
    json.dump(lemmas_dict, f, indent=2, sort_keys=True, ensure_ascii=False)

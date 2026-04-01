import xml.etree.ElementTree as ET
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD


INPUT = Path("data/raw/rgo/latest/rg5.xml")
OUTPUT = Path("data/raw/rgo/rg5.ttl")

BASE = "https://example.org/rg/"
EX = Namespace("https://example.org/ontology/")
RG = Namespace(BASE)


# N. \t N. --> N. N.
def normalize_whitespace(text: str) -> str:
    return " ".join(text.split()) if text else ""


def inner_text(elem: ET.Element) -> str:
    """
    Return the textual content of an element without tags, including nested texts
    """
    return normalize_whitespace("".join(elem.itertext()))


# 123 456 --> ["123", "456"]
def split_lemma_ids(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split() if part.strip()]


def add_literal_if_present(g: Graph, subject: URIRef, predicate: URIRef, value: str, datatype=None):
    """
    Add a literal to the graph if the value is not empty after normalization, else do nothing.
    """
    if value is None:
        return
    value = normalize_whitespace(value)
    if not value:
        return
    if datatype:
        g.add((subject, predicate, Literal(value, datatype=datatype)))
    else:
        g.add((subject, predicate, Literal(value)))


def lemma_uri(lemma_id: str) -> URIRef:
    return RG[f"lemma/{lemma_id}"]


def sublemma_uri(lemma_id: str, idx: int) -> URIRef:
    return RG[f"sublemma/{lemma_id}-{idx}"]


def person_uri(person_id: str) -> URIRef:
    return RG[f"person/{person_id}"]


def place_uri(place_id: str) -> URIRef:
    return RG[f"ort/{place_id}"]


def head_date_uri(lemma_id: str, idx: int) -> URIRef:
    return RG[f"date/{lemma_id}-head-{idx}"]


def subentry_date_uri(lemma_id: str, idx: int) -> URIRef:
    return RG[f"date/{lemma_id}-{idx}"]


def head_fund_uri(lemma_id: str, idx: int) -> URIRef:
    return RG[f"fund/{lemma_id}-head-{idx}"]


def fund_uri(lemma_id: str, sub_idx: int, fund_idx: int) -> URIRef:
    return RG[f"fund/{lemma_id}-{sub_idx}-{fund_idx}"]


def build_graph() -> Graph:
    tree = ET.parse(INPUT)
    root = tree.getroot()
    root_vol = root.get("vol")

    g = Graph()
    g.bind("ex", EX)
    g.bind("rg", RG)
    g.bind("rdfs", RDFS)

    # If the file root is a single <lemma>, support that.
    # If it contains many <lemma> elements, support that too.
    if root.tag == "lemma":
        lemma_elements = [root]
    else:
        lemma_elements = root.findall(".//lemma")

    for lemma in lemma_elements:
        lid = lemma.get("id")
        if not lid:
            continue

        lemma_node = lemma_uri(lid)
        g.add((lemma_node, RDF.type, EX.RegestEntry))
        g.add((lemma_node, EX.sourceId, Literal(lid))) # redundant with URI but can be useful for querying without IRIs
        add_literal_if_present(g, lemma_node, EX.volume, root_vol)

        sp_start = lemma.get("spStart")
        sp_end = lemma.get("spEnd")
        add_literal_if_present(g, lemma_node, EX.spStart, sp_start)
        add_literal_if_present(g, lemma_node, EX.spEnd, sp_end)

        reg = lemma.find("reg")
        if reg is not None:
            head = reg.find("head")
            if head is not None:
                add_literal_if_present(g, lemma_node, EX.headText, inner_text(head))

                head_dates = head.findall("date")
                for head_date_idx, date_el in enumerate(head_dates, start=1):
                    d_node = head_date_uri(lid, head_date_idx)
                    g.add((d_node, RDF.type, EX.DateInfo))
                    g.add((lemma_node, EX.hasDate, d_node))

                    add_literal_if_present(g, d_node, EX.dateText, inner_text(date_el))
                    add_literal_if_present(g, d_node, EX.dateISO, date_el.get("iso"))
                    add_literal_if_present(g, d_node, EX.dateYear, date_el.get("year"))

                    iso = (date_el.get("iso") or "").strip()

                    if len(iso) == 8 and iso.isdigit():
                        year = iso[0:4]
                        month = iso[4:6]
                        day = iso[6:8]

                        if month != "00" and day != "00":
                            iso_date = f"{year}-{month}-{day}"
                            g.add((d_node, EX.dateValue, Literal(iso_date, datatype=XSD.date)))
                        elif month != "00" and day == "00":
                            iso_year_month = f"{year}-{month}"
                            g.add((d_node, EX.dateValue, Literal(iso_year_month, datatype=XSD.gYearMonth)))
                        elif month == "00" and day == "00":
                            g.add((d_node, EX.dateValue, Literal(year, datatype=XSD.gYear)))
                    elif len(iso) == 4 and iso.isdigit():
                        g.add((d_node, EX.dateValue, Literal(iso, datatype=XSD.gYear)))

                head_funds = head.findall("fund")
                for head_fund_idx, fund_el in enumerate(head_funds, start=1):
                    f_node = head_fund_uri(lid, head_fund_idx)
                    g.add((f_node, RDF.type, EX.SourceReference))
                    g.add((lemma_node, EX.hasSourceReference, f_node))

                    add_literal_if_present(g, f_node, EX.referenceText, inner_text(fund_el))
                    add_literal_if_present(g, f_node, EX.referenceCode, fund_el.get("iso"))
                    add_literal_if_present(g, f_node, EX.referencePart1, fund_el.get("l1"))
                    add_literal_if_present(g, f_node, EX.referencePart2, fund_el.get("l2"))
                    add_literal_if_present(g, f_node, EX.referencePart3, fund_el.get("l3"))

            sublemmata = reg.findall("sublemma")
            for idx, sub in enumerate(sublemmata, start=1):
                sub_node = sublemma_uri(lid, idx)
                g.add((sub_node, RDF.type, EX.SubEntry))
                g.add((lemma_node, EX.hasSubEntry, sub_node)) # Lemma hasSubEntry Sublemma
                g.add((sub_node, EX.partOfLemma, lemma_node)) # Sublemma partOfLemma Lemma

                vol = sub.get("vol")
                add_literal_if_present(g, sub_node, EX.volume, vol)

                sub_text = inner_text(sub)
                add_literal_if_present(g, sub_node, EX.text, sub_text)

                date_el = sub.find("date")
                if date_el is not None:
                    d_node = subentry_date_uri(lid, idx)
                    g.add((d_node, RDF.type, EX.DateInfo))
                    g.add((sub_node, EX.hasDate, d_node)) # Extra node since date has multiple properties like text, iso, year

                    add_literal_if_present(g, d_node, EX.dateText, inner_text(date_el))
                    add_literal_if_present(g, d_node, EX.dateISO, date_el.get("iso"))
                    add_literal_if_present(g, d_node, EX.dateYear, date_el.get("year"))

                    # Handle ISO date parsing for different levels of precision (YYYY, YYYY-MM, YYYY-MM-DD)
                    iso = (date_el.get("iso") or "").strip()

                    if len(iso) == 8 and iso.isdigit():
                        year = iso[0:4]
                        month = iso[4:6]
                        day = iso[6:8]

                        if month != "00" and day != "00":
                            # full date
                            iso_date = f"{year}-{month}-{day}"
                            g.add((d_node, EX.dateValue, Literal(iso_date, datatype=XSD.date))) # rdf syntax for typified literal value (e.g. date)

                        elif month != "00" and day == "00":
                            # year + month only
                            iso_year_month = f"{year}-{month}"
                            g.add((d_node, EX.dateValue, Literal(iso_year_month, datatype=XSD.gYearMonth)))

                        elif month == "00" and day == "00":
                            # year only
                            g.add((d_node, EX.dateValue, Literal(year, datatype=XSD.gYear)))

                        else:
                            # malformed partial date like YYYY00DD -> keep only raw ISO string
                            pass

                    elif len(iso) == 4 and iso.isdigit():
                        g.add((d_node, EX.dateValue, Literal(iso, datatype=XSD.gYear)))

                fund_elements = sub.findall("fund")
                for fund_idx, fund_el in enumerate(fund_elements, start=1):
                    f_node = fund_uri(lid, idx, fund_idx)
                    g.add((f_node, RDF.type, EX.SourceReference))
                    g.add((sub_node, EX.hasSourceReference, f_node))

                    add_literal_if_present(g, f_node, EX.referenceText, inner_text(fund_el))
                    add_literal_if_present(g, f_node, EX.referenceCode, fund_el.get("iso"))
                    add_literal_if_present(g, f_node, EX.referencePart1, fund_el.get("l1"))
                    add_literal_if_present(g, f_node, EX.referencePart2, fund_el.get("l2"))
                    add_literal_if_present(g, f_node, EX.referencePart3, fund_el.get("l3"))

        personenindex = lemma.find("personenindex")
        if personenindex is not None:
            for person in personenindex.findall("person"):
                pid = person.get("id")
                if not pid:
                    continue

                person_node = person_uri(pid)
                g.add((person_node, RDF.type, EX.Person))
                g.add((person_node, EX.sourceId, Literal(pid)))

                name_el = person.find("name")
                if name_el is not None:
                    add_literal_if_present(g, person_node, EX.name, inner_text(name_el))

                # sometimes a surname with synonyms, other times an ordinal like III. 
                beiname_el = person.find("beiname")
                if beiname_el is not None:
                    add_literal_if_present(g, person_node, EX.byName, inner_text(beiname_el))

                # create bidirectional links between current lemma and person
                g.add((person_node, EX.appearsInLemma, lemma_node))
                g.add((lemma_node, EX.mentionsPerson, person_node))

        ortsindex = lemma.find("ortsindex")
        if ortsindex is not None:
            for place in ortsindex.findall("ort"):
                oid = place.get("id")
                if not oid:
                    continue

                place_node = place_uri(oid)
                g.add((place_node, RDF.type, EX.Ort))
                g.add((place_node, EX.sourceId, Literal(oid)))

                name_el = place.find("name")
                if name_el is not None:
                    add_literal_if_present(g, place_node, EX.preferredName, inner_text(name_el))

                # create bidirectional links between current lemma and place
                g.add((place_node, EX.appearsInLemma, lemma_node))
                g.add((lemma_node, EX.mentionsPlace, place_node))

    return g


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    graph = build_graph()
    graph.serialize(destination=OUTPUT, format="turtle")
    print(f"Saved RDF to {OUTPUT}")
    print(f"Triples: {len(graph)}")


if __name__ == "__main__":
    main()
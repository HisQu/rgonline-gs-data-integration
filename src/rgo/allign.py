from pathlib import Path

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF


INPUT = Path("data/raw/rgo/rg5.ttl")
OUTPUT = Path("data/raw/rgo/full.ttl")

RGO = Namespace("https://rg-online.dhi-roma.it/ontology/")
GNDO = Namespace("https://d-nb.info/standards/elementset/gnd#")


def copy_all(g_in: Graph, g_out: Graph, subject, predicate):
    for obj in g_in.objects(subject, predicate):
        g_out.add((subject, predicate, obj))


def first_literal(graph: Graph, subject, predicate):
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, Literal):
            return obj
    return None


def all_literals(graph: Graph, subject, predicate):
    return [obj for obj in graph.objects(subject, predicate) if isinstance(obj, Literal)]


def split_byname_values(value: str) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in value.split(",")]
    return [part for part in parts if part]


def main() -> None:
    g_in = Graph()
    g_in.parse(INPUT, format="turtle")

    g_out = Graph()
    g_out.bind("rgo", RGO)
    g_out.bind("gndo", GNDO)

    # --- Regest entries ---
    for lemma in g_in.subjects(RDF.type, RGO.RegestEntry):
        g_out.add((lemma, RDF.type, RGO.RegestEntry))

        for pred in [
            RGO.sourceId,
            RGO.volume,
            RGO.headText,
            RGO.spStart,
            RGO.spEnd,
            RGO.hasSubEntry,
            RGO.dateValue,
            RGO.fundReferencePart1,
            RGO.fundReferencePart2,
            RGO.fundReferencePart3,
            RGO.mentionsPerson,
            RGO.mentionsPlace,
        ]:
            copy_all(g_in, g_out, lemma, pred)

        for sub in g_in.objects(lemma, RGO.hasSubEntry):
            g_out.add((lemma, RGO.hasSubEntry, sub))

        for date_node in g_in.objects(lemma, RGO.hasDate):
            date_value = first_literal(g_in, date_node, RGO.dateValue)
            if date_value is not None:
                g_out.add((lemma, RGO.dateValue, date_value))

        for fund_node in g_in.objects(lemma, RGO.hasSourceReference):
            part1 = first_literal(g_in, fund_node, RGO.referencePart1)
            part2 = first_literal(g_in, fund_node, RGO.referencePart2)
            part3 = first_literal(g_in, fund_node, RGO.referencePart3)

            if part1 is not None:
                g_out.add((lemma, RGO.fundReferencePart1, part1))
            if part2 is not None:
                g_out.add((lemma, RGO.fundReferencePart2, part2))
            if part3 is not None:
                g_out.add((lemma, RGO.fundReferencePart3, part3))

    # --- Subentries ---
    for sub in g_in.subjects(RDF.type, RGO.SubEntry):
        g_out.add((sub, RDF.type, RGO.SubEntry))

        for pred in [
            RGO.partOfLemma,
            RGO.volume,
            RGO.text,
            RGO.dateValue,
            RGO.fundReferencePart1,
            RGO.fundReferencePart2,
            RGO.fundReferencePart3,
            RGO.mentionsPerson,
            RGO.mentionsPlace,
        ]:
            copy_all(g_in, g_out, sub, pred)

        for date_node in g_in.objects(sub, RGO.hasDate):
            date_value = first_literal(g_in, date_node, RGO.dateValue)
            if date_value is not None:
                g_out.add((sub, RGO.dateValue, date_value))

        for fund_node in g_in.objects(sub, RGO.hasSourceReference):
            part1 = first_literal(g_in, fund_node, RGO.referencePart1)
            part2 = first_literal(g_in, fund_node, RGO.referencePart2)
            part3 = first_literal(g_in, fund_node, RGO.referencePart3)

            if part1 is not None:
                g_out.add((sub, RGO.fundReferencePart1, part1))
            if part2 is not None:
                g_out.add((sub, RGO.fundReferencePart2, part2))
            if part3 is not None:
                g_out.add((sub, RGO.fundReferencePart3, part3))

    # --- Persons ---
    for person in g_in.subjects(RDF.type, RGO.Person):
        g_out.add((person, RDF.type, GNDO.DifferentiatedPerson))

        copy_all(g_in, g_out, person, RGO.sourceId)
        copy_all(g_in, g_out, person, RGO.appearsInLemma)

        # rgo:name -> gnd:preferredNameForThePerson
        for obj in g_in.objects(person, RGO.name):
            g_out.add((person, GNDO.preferredNameForThePerson, obj))

        byname_literals = []
        byname_literals.extend(all_literals(g_in, person, RGO.byName))
        byname_literals.extend(all_literals(g_in, person, RGO.beiname))
        for lit in byname_literals:
            for part in split_byname_values(str(lit)):
                g_out.add((person, GNDO.variantNameForThePerson, Literal(part)))

    # --- Places ---
    for place in g_in.subjects(RDF.type, RGO.PlaceOrInstitution):
        g_out.add((place, RDF.type, GNDO.PlaceOrGeographicName))

        copy_all(g_in, g_out, place, RGO.sourceId)
        copy_all(g_in, g_out, place, RGO.appearsInLemma)

        # rgo:preferredName -> gnd:preferredNameForThePlaceOrGeographicName
        for obj in g_in.objects(place, RGO.preferredName):
            g_out.add((place, GNDO.preferredNameForThePlaceOrGeographicName, obj))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    g_out.serialize(destination=OUTPUT, format="turtle")

    print(f"Saved aligned RDF to {OUTPUT}")
    print(f"Triples: {len(g_out)}")


if __name__ == "__main__":
    main()
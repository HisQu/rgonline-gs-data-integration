from pathlib import Path

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF


INPUT = Path("data/raw/rgo/rg5.ttl")
OUTPUT = Path("data/raw/rgo/rg5_simplified.ttl")

EX = Namespace("https://example.org/ontology/")


def split_byname_values(value: str) -> list[str]:
    """
    Split a serialized byName/beiname string into multiple values.
    This is heuristic and currently assumes comma-separated variants.
    """
    if not value:
        return []

    parts = [part.strip() for part in value.split(",")]
    return [part for part in parts if part]


def first_literal(graph: Graph, subject, predicate):
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, Literal):
            return obj
    return None


def all_literals(graph: Graph, subject, predicate):
    return [obj for obj in graph.objects(subject, predicate) if isinstance(obj, Literal)]


def main() -> None:
    g_in = Graph()
    g_in.parse(INPUT, format="turtle")

    g_out = Graph()
    g_out.bind("ex", EX)

    # --- Lemmata ---
    for lemma in g_in.subjects(RDF.type, EX.RegestEntry):
        g_out.add((lemma, RDF.type, EX.RegestEntry))

        for pred in [
            EX.sourceId, EX.volume, EX.headText, EX.spStart, EX.spEnd,
            EX.mentionsPerson, EX.mentionsPlace
        ]:
            for obj in g_in.objects(lemma, pred):
                g_out.add((lemma, pred, obj))

        for sub in g_in.objects(lemma, EX.hasSubEntry):
            g_out.add((lemma, EX.hasSubEntry, sub))

        # dates from head directly attached to lemma
        for date_node in g_in.objects(lemma, EX.hasDate):
            date_value = first_literal(g_in, date_node, EX.dateValue)
            if date_value is not None:
                g_out.add((lemma, EX.dateValue, date_value))

        # source refs from head directly attached to lemma
        for fund_node in g_in.objects(lemma, EX.hasSourceReference):
            part1 = first_literal(g_in, fund_node, EX.referencePart1)
            part2 = first_literal(g_in, fund_node, EX.referencePart2)
            part3 = first_literal(g_in, fund_node, EX.referencePart3)

            if part1 is not None:
                g_out.add((lemma, EX.fundReferencePart1, part1))
            if part2 is not None:
                g_out.add((lemma, EX.fundReferencePart2, part2))
            if part3 is not None:
                g_out.add((lemma, EX.fundReferencePart3, part3))

    # --- Subentries ---
    for sub in g_in.subjects(RDF.type, EX.SubEntry):
        g_out.add((sub, RDF.type, EX.SubEntry))

        for pred in [EX.partOfLemma, EX.volume, EX.text]:
            for obj in g_in.objects(sub, pred):
                g_out.add((sub, pred, obj))

        for date_node in g_in.objects(sub, EX.hasDate):
            date_value = first_literal(g_in, date_node, EX.dateValue)
            if date_value is not None:
                g_out.add((sub, EX.dateValue, date_value))

        for fund_node in g_in.objects(sub, EX.hasSourceReference):
            part1 = first_literal(g_in, fund_node, EX.referencePart1)
            part2 = first_literal(g_in, fund_node, EX.referencePart2)
            part3 = first_literal(g_in, fund_node, EX.referencePart3)

            if part1 is not None:
                g_out.add((sub, EX.fundReferencePart1, part1))
            if part2 is not None:
                g_out.add((sub, EX.fundReferencePart2, part2))
            if part3 is not None:
                g_out.add((sub, EX.fundReferencePart3, part3))

    # --- Persons ---
    for person in g_in.subjects(RDF.type, EX.Person):
        g_out.add((person, RDF.type, EX.Person))

        for pred in [EX.sourceId, EX.name, EX.appearsInLemma]:
            for obj in g_in.objects(person, pred):
                g_out.add((person, pred, obj))

        # support both old EX.byName and future EX.beiname
        byname_literals = []
        byname_literals.extend(all_literals(g_in, person, EX.byName))
        byname_literals.extend(all_literals(g_in, person, EX.beiname))

        for lit in byname_literals:
            for part in split_byname_values(str(lit)):
                g_out.add((person, EX.beiname, Literal(part)))

    # --- Places ---
    for place in g_in.subjects(RDF.type, EX.Ort):
        g_out.add((place, RDF.type, EX.Ort))

        for pred in [EX.sourceId, EX.preferredName, EX.appearsInLemma]:
            for obj in g_in.objects(place, pred):
                g_out.add((place, pred, obj))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    g_out.serialize(destination=OUTPUT, format="turtle")

    print(f"Saved simplified RDF to {OUTPUT}")
    print(f"Triples: {len(g_out)}")


if __name__ == "__main__":
    main()
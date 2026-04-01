from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, XSD


INPUT = Path("data/raw/rgo/rg5_simplified.ttl")
OUTPUT = Path("data/raw/rgo/rg5_aligned.ttl")

EX = Namespace("https://example.org/ontology/")
GND = Namespace("https://d-nb.info/standards/elementset/gnd#")


def copy_all(g_in: Graph, g_out: Graph, subject, predicate):
    for obj in g_in.objects(subject, predicate):
        g_out.add((subject, predicate, obj))


def main() -> None:
    g_in = Graph()
    g_in.parse(INPUT, format="turtle")

    g_out = Graph()
    g_out.bind("ex", EX)
    g_out.bind("gnd", GND)
    g_out.bind("xsd", XSD)

    # --- Regest entries ---
    for lemma in g_in.subjects(RDF.type, EX.RegestEntry):
        # keep project-specific class
        g_out.add((lemma, RDF.type, EX.RegestEntry))

        for pred in [
            EX.sourceId,
            EX.volume,
            EX.headText,
            EX.spStart,
            EX.spEnd,
            EX.hasSubEntry,
            EX.dateValue,
            EX.fundReferencePart1,
            EX.fundReferencePart2,
            EX.fundReferencePart3,
            EX.mentionsPerson,
            EX.mentionsPlace,
        ]:
            copy_all(g_in, g_out, lemma, pred)

    # --- Subentries ---
    for sub in g_in.subjects(RDF.type, EX.SubEntry):
        # keep project-specific class
        g_out.add((sub, RDF.type, EX.SubEntry))

        for pred in [
            EX.partOfLemma,
            EX.volume,
            EX.text,
            EX.dateValue,
            EX.fundReferencePart1,
            EX.fundReferencePart2,
            EX.fundReferencePart3,
            EX.mentionsPerson,
            EX.mentionsPlace,
        ]:
            copy_all(g_in, g_out, sub, pred)

    # --- Persons ---
    for person in g_in.subjects(RDF.type, EX.Person):
        g_out.add((person, RDF.type, GND.DifferentiatedPerson))

        copy_all(g_in, g_out, person, EX.sourceId)
        copy_all(g_in, g_out, person, EX.appearsInLemma)

        # ex:name -> gnd:preferredNameForThePerson
        for obj in g_in.objects(person, EX.name):
            g_out.add((person, GND.preferredNameForThePerson, obj))

        # ex:beiname -> gnd:variantNameForThePerson
        # maybe change to epithetGenericNameTitleOrTerritory?
        for obj in g_in.objects(person, EX.beiname):
            g_out.add((person, GND.variantNameForThePerson, obj))

    # --- Places ---
    for place in g_in.subjects(RDF.type, EX.Ort):
        g_out.add((place, RDF.type, GND.PlaceOrGeographicName))

        copy_all(g_in, g_out, place, EX.sourceId)
        copy_all(g_in, g_out, place, EX.appearsInLemma)

        # ex:preferredName -> gnd:preferredNameForThePlaceOrGeographicName
        for obj in g_in.objects(place, EX.preferredName):
            g_out.add((place, GND.preferredNameForThePlaceOrGeographicName, obj))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    g_out.serialize(destination=OUTPUT, format="turtle")

    print(f"Saved aligned RDF to {OUTPUT}")
    print(f"Triples: {len(g_out)}")


if __name__ == "__main__":
    main()
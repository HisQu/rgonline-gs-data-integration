import re
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Set

import pandas as pd
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[2]
DNB_FILE = ROOT / "data" / "raw" / "dnb" / "example.ttl"
GS_FILE = ROOT / "data" / "raw" / "gs" / "example.ttl"
RGO_FILE = ROOT / "data" / "raw" / "rgo" / "full.ttl"

GNDO = Namespace("https://d-nb.info/standards/elementset/gnd#")
SCHEMA = Namespace("http://schema.org/")
PART = Namespace("http://purl.org/vocab/participation/schema#")
ORG = Namespace("http://www.w3.org/ns/org#")
RGO = Namespace("https://rg-online.dhi-roma.it/ontology/")

# Target schema for the first matching profile
COMMON_COLUMNS = [
    "entity_id",
    "source",
    "preferred_name",
    "variant_names",
    "birth_year",
    "death_year",
    "activity_start",
    "activity_end",
    "mention_start",
    "mention_end",
    "places",
    "gnd_id",
    "wikidata_id",
]

YEAR_COLUMNS = [
    "birth_year",
    "death_year",
    "activity_start",
    "activity_end",
    "mention_start",
    "mention_end",
]

LIST_COLUMNS = ["variant_names", "places"]

# Helpers
YEAR_RE = re.compile(r"(?<!\d)(-?\d{3,4})(?!\d)")


def load_rdf(file_path: str, rdf_format: Optional[str] = None) -> Graph:
    """
    Load one RDF/Turtle file into an rdflib Graph.
    """
    graph = Graph()
    try:
        graph.parse(str(file_path), format=rdf_format)
    except Exception as exc:
        raise ValueError(f"Could not parse RDF file: {file_path}") from exc
    return graph


def clean_text(value: Any) -> str:
    """Normalize whitespace and convert RDF values to plain strings."""
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def unique_list(values: Iterable[Any]) -> list[str]:
    """Deduplicate while preserving order; ignore empty values."""
    seen: Set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def extract_year(value: Any) -> Optional[int]:
    """
    Extract a year from:
    - xsd:gYear            -> 1463
    - xsd:date             -> 1463-02-14 -> 1463
    - xsd:gYearMonth       -> 1437-03 -> 1437
    - fuzzy strings        -> 'um 1385', 'circa 1500' -> 1385 / 1500
    """
    if value is None:
        return None

    text = clean_text(value)
    if not text:
        return None

    match = YEAR_RE.search(text)
    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def first_year(values: Iterable[Any]) -> Optional[int]:
    """Return the first parsable year in an iterable."""
    for value in values:
        year = extract_year(value)
        if year is not None:
            return year
    return None


def min_year(values: Iterable[Any]) -> Optional[int]:
    """Return the minimum parsable year from an iterable."""
    years = [extract_year(v) for v in values]
    years = [y for y in years if y is not None]
    return min(years) if years else None


def max_year(values: Iterable[Any]) -> Optional[int]:
    """Return the maximum parsable year from an iterable."""
    years = [extract_year(v) for v in values]
    years = [y for y in years if y is not None]
    return max(years) if years else None


def first_literal(graph: Graph, subject: Any, predicate: URIRef) -> Optional[str]:
    """Return the first object value for a given subject/predicate as plain string."""
    for obj in graph.objects(subject, predicate):
        text = clean_text(obj)
        if text:
            return text
    return None


def all_literals(graph: Graph, subject: Any, predicate: URIRef) -> list[str]:
    """Return all object values for a given subject/predicate as strings."""
    return unique_list(graph.objects(subject, predicate))


def strip_fragment(uri: Any) -> str:
    """Strip the #fragment from a URI string."""
    text = clean_text(uri)
    return text.split("#", 1)[0]


def extract_gnd_id_from_uri(uri: Any) -> Optional[str]:
    text = clean_text(uri)
    if "/gnd/" not in text:
        return None
    return text.rsplit("/gnd/", 1)[-1].strip("/") or None


def extract_wikidata_id_from_uri(uri: Any) -> Optional[str]:
    text = clean_text(uri)
    match = re.search(r"/entity/(Q\d+)$", text)
    return match.group(1) if match else None



def empty_common_record() -> dict[str, Any]:
    """Create one empty row in the target schema."""
    return {
        "entity_id": None,
        "source": None,
        "preferred_name": None,
        "variant_names": [],
        "birth_year": None,
        "death_year": None,
        "activity_start": None,
        "activity_end": None,
        "mention_start": None,
        "mention_end": None,
        "places": [],
        "gnd_id": None,
        "wikidata_id": None,
    }


def finalize_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert list of dicts to DataFrame, enforce schema order, and normalize dtypes.
    """
    df = pd.DataFrame(records)

    # Add missing columns if necessary
    for col in COMMON_COLUMNS:
        if col not in df.columns:
            if col in LIST_COLUMNS:
                df[col] = [[] for _ in range(len(df))]
            else:
                df[col] = pd.NA

    # Ensure list columns are always Python lists
    for col in LIST_COLUMNS:
        def _normalize_list(v: Any) -> list[str]:
            if isinstance(v, list):
                return unique_list(v)
            if v is None or pd.isna(v):
                return []
            return unique_list([v])

        df[col] = df[col].apply(_normalize_list)

    # Normalize year columns to pandas nullable integer dtype
    for col in YEAR_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Order columns exactly as defined
    return df[COMMON_COLUMNS]


def concatenate_source_frames(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """
    Stack source-specific frames into one unified long-format profile table.
    One row = one source-specific person profile.
    """
    if not frames:
        return finalize_dataframe([])

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = finalize_dataframe(combined.to_dict(orient="records"))
    return combined


# DNB
# ---------------------------------------------------------------------------
def iter_dnb_persons(graph: Graph) -> list[URIRef]:
    """
    Iterate DNB person resources.
    In DNB, gndo:preferredNameForThePerson is a reliable indicator for persons.
    """
    persons = set(graph.subjects(GNDO.preferredNameForThePerson, None))
    return [p for p in persons if isinstance(p, URIRef)]


def extract_dnb_columns(graph: Graph, person: URIRef) -> dict[str, Any]:
    """Extract one DNB person into the target schema."""
    record = empty_common_record()
    record["entity_id"] = clean_text(person)
    record["source"] = "dnb"

    preferred_name = first_literal(graph, person, GNDO.preferredNameForThePerson)
    variant_names = all_literals(graph, person, GNDO.variantNameForThePerson)
    if preferred_name:
        variant_names = [v for v in variant_names if v != preferred_name]

    birth_year = first_year(graph.objects(person, GNDO.dateOfBirth))
    death_year = first_year(graph.objects(person, GNDO.dateOfDeath))

    place_uris = unique_list(
        list(graph.objects(person, GNDO.placeOfActivity))
        + list(graph.objects(person, GNDO.placeOfDeath))
    )

    gnd_id = first_literal(graph, person, GNDO.gndIdentifier)
    if not gnd_id:
        gnd_id = extract_gnd_id_from_uri(person)

    wikidata_id = None
    for same_as in graph.objects(person, OWL.sameAs):
        wikidata_id = extract_wikidata_id_from_uri(same_as)
        if wikidata_id:
            break

    record.update(
        {
            "preferred_name": preferred_name,
            "variant_names": variant_names,
            "birth_year": birth_year,
            "death_year": death_year,
            "activity_start": None,
            "activity_end": None,
            "mention_start": None,
            "mention_end": None,
            "places": place_uris,
            "gnd_id": gnd_id,
            "wikidata_id": wikidata_id,
        }
    )
    return record


def build_dnb_dataframe(file_path: str, rdf_format: Optional[str] = None) -> pd.DataFrame:
    graph = load_rdf(file_path, rdf_format=rdf_format)
    records = [extract_dnb_columns(graph, person) for person in iter_dnb_persons(graph)]
    return finalize_dataframe(records)


# GS
# ---------------------------------------------------------------------------
def iter_gs_persons(graph: Graph) -> list[Any]:
    """
    Iterate GS persons.
    The excerpt uses blank nodes and rdf:type as string-literal in places,
    so we do not rely on rdf:type alone.
    Robust criteria:
    - has schema:givenName and/or schema:familyName
    - or has part:holder_of
    """
    persons = set(graph.subjects(SCHEMA.givenName, None))
    persons.update(graph.subjects(SCHEMA.familyName, None))
    persons.update(graph.subjects(PART.holder_of, None))
    return list(persons)


def derive_gs_entity_id(graph: Graph, person: Any) -> str:
    """
    Derive a stable GS entity_id.
    Preferred strategy:
    1) base URI of part:holder_of resources (strip #amt-...)
    2) GS owl:sameAs URI (strip fragment if present)
    3) blank-node fallback
    """
    holder_of_bases = unique_list(
        strip_fragment(obj)
        for obj in graph.objects(person, PART.holder_of)
        if isinstance(obj, URIRef)
    )
    if holder_of_bases:
        return holder_of_bases[0]

    gs_sameas = unique_list(
        strip_fragment(obj)
        for obj in graph.objects(person, OWL.sameAs)
        if "personendatenbank.germania-sacra.de" in clean_text(obj)
    )
    if gs_sameas:
        return gs_sameas[0]

    if isinstance(person, BNode):
        return f"_:{clean_text(person)}"

    return clean_text(person)


def extract_gs_gnd_id(graph: Graph, person: Any) -> Optional[str]:
    """Extract GND id from GS owl:sameAs links to DNB."""
    for same_as in graph.objects(person, OWL.sameAs):
        gnd_id = extract_gnd_id_from_uri(same_as)
        if gnd_id:
            return gnd_id
    return None


def extract_gs_activity_interval(graph: Graph, person: Any) -> dict[str, Optional[int]]:
    """
    Aggregate activity_start / activity_end from all Amtsdaten linked via part:holder_of.
    """
    amt_nodes = list(graph.objects(person, PART.holder_of))
    start_values: list[Any] = []
    end_values: list[Any] = []

    for amt in amt_nodes:
        start_values.extend(graph.objects(amt, PART.startDate))
        end_values.extend(graph.objects(amt, PART.endDate))

    return {
        "activity_start": min_year(start_values),
        "activity_end": max_year(end_values),
    }


def extract_gs_columns(graph: Graph, person: Any) -> dict[str, Any]:
    """Extract one GS person into the target schema."""
    record = empty_common_record()
    record["entity_id"] = derive_gs_entity_id(graph, person)
    record["source"] = "gs"

    given_name = first_literal(graph, person, SCHEMA.givenName)
    family_name = first_literal(graph, person, SCHEMA.familyName)
    preferred_name = " ".join([part for part in [given_name, family_name] if part]).strip() or None

    birth_year = first_year(graph.objects(person, SCHEMA.birthDate))
    death_year = first_year(graph.objects(person, SCHEMA.deathDate))

    activity = extract_gs_activity_interval(graph, person)
    gnd_id = extract_gs_gnd_id(graph, person)

    record.update(
        {
            "preferred_name": preferred_name,
            "variant_names": [],      # no reliable variant-name property in the given GS excerpt
            "birth_year": birth_year,
            "death_year": death_year,
            "activity_start": activity["activity_start"],
            "activity_end": activity["activity_end"],
            "mention_start": None,
            "mention_end": None,
            "places": [],             # intentionally empty in first pass
            "gnd_id": gnd_id,
            "wikidata_id": None,
        }
    )
    return record


def build_gs_dataframe(file_path: str, rdf_format: Optional[str] = None) -> pd.DataFrame:
    graph = load_rdf(file_path, rdf_format=rdf_format)
    records = [extract_gs_columns(graph, person) for person in iter_gs_persons(graph)]
    return finalize_dataframe(records)


# RGO
# ---------------------------------------------------------------------------
def iter_rgo_persons(graph: Graph) -> list[URIRef]:
    """
    Iterate RGO person resources.
    Preferred name is a reliable indicator in the current model.
    """
    persons = set(graph.subjects(GNDO.preferredNameForThePerson, None))
    return [p for p in persons if isinstance(p, URIRef)]


def get_rgo_place_label(graph: Graph, place: Any) -> Optional[str]:
    """
    Return the human-readable place label.
    Per your note, RGO place text should be available, so we prefer labels only.
    """
    for predicate in (
        GNDO.preferredNameForThePlaceOrGeographicName,
        RDFS.label,
        FOAF.name,
    ):
        label = first_literal(graph, place, predicate)
        if label:
            return label
    return None



def aggregate_rgo_context(graph: Graph, person: URIRef) -> dict[str, Any]:
    """
    Aggregate RGO mention dates and places from the l+ocal graph context.

    Included paths:
    - person -> rgo:appearsInLemma -> lemma
    - lemma -> rgo:mentionsPerson -> person

    mention_start / mention_end:
    - aggregate all rgo:dateValue values found on linked subentries
    - also include lemma-level rgo:dateValue if present

    places:
    - gather all places linked from those lemmas via rgo:mentionsPlace
    - store place labels
    """
    lemmas: Set[Any] = set()

    # direct: person -> lemma
    lemmas.update(graph.objects(person, RGO.appearsInLemma))

    # inverse: lemma -> person
    lemmas.update(graph.subjects(RGO.mentionsPerson, person))

    date_values: list[Any] = []
    place_labels: list[str] = []

    for lemma in lemmas:
        # optional lemma-level date
        date_values.extend(graph.objects(lemma, RGO.dateValue))

        # subentries in both directions, to stay robust
        subentries: Set[Any] = set()
        subentries.update(graph.objects(lemma, RGO.hasSubEntry))
        subentries.update(graph.subjects(RGO.partOfLemma, lemma))

        for subentry in subentries:
            date_values.extend(graph.objects(subentry, RGO.dateValue))

        for place in graph.objects(lemma, RGO.mentionsPlace):
            label = get_rgo_place_label(graph, place)
            if label:
                place_labels.append(label)

    return {
        "mention_start": min_year(date_values),
        "mention_end": max_year(date_values),
        "places": unique_list(place_labels),
    }


def extract_rgo_columns(graph: Graph, person: URIRef) -> dict[str, Any]:
    """Extract one RGO person into the target schema."""
    record = empty_common_record()
    record["entity_id"] = clean_text(person)
    record["source"] = "rgo"

    preferred_name = first_literal(graph, person, GNDO.preferredNameForThePerson)
    variant_names = all_literals(graph, person, GNDO.variantNameForThePerson)
    if preferred_name:
        variant_names = [v for v in variant_names if v != preferred_name]

    context = aggregate_rgo_context(graph, person)

    record.update(
        {
            "preferred_name": preferred_name,
            "variant_names": variant_names,
            "birth_year": None,
            "death_year": None,
            "activity_start": None,
            "activity_end": None,
            "mention_start": context["mention_start"],
            "mention_end": context["mention_end"],
            "places": context["places"],
            "gnd_id": None,
            "wikidata_id": None,
        }
    )
    return record

def build_rgo_dataframe(file_path: str, rdf_format: Optional[str] = None) -> pd.DataFrame:
    graph = load_rdf(file_path, rdf_format=rdf_format)
    records = [extract_rgo_columns(graph, person) for person in iter_rgo_persons(graph)]
    return finalize_dataframe(records)


def add_all_names_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optional convenience function.
    'all_names' is not part of the minimal first-pass schema, but can be derived.
    """
    df = df.copy()

    def _build_all_names(row: pd.Series) -> list[str]:
        names = []
        if pd.notna(row["preferred_name"]) and row["preferred_name"]:
            names.append(row["preferred_name"])
        names.extend(row["variant_names"] or [])
        return unique_list(names)

    df["all_names"] = df.apply(_build_all_names, axis=1)
    return df

# Usage
if __name__ == "__main__":
    # Build one DataFrame per source
    dnb_df = build_dnb_dataframe(DNB_FILE)
    gs_df = build_gs_dataframe(GS_FILE)
    rgo_df = build_rgo_dataframe(RGO_FILE)

    # Unify into one common long-format profile table
    common_profiles_df = concatenate_source_frames([dnb_df, gs_df, rgo_df])

    #  materialize derived all_names
    common_profiles_with_all_names_df = add_all_names_column(common_profiles_df)

    print("DNB rows:", len(dnb_df))
    print("GS rows:", len(gs_df))
    print("RGO rows:", len(rgo_df))
    print("Combined rows:", len(common_profiles_df))
    print()

    print("Combined schema:")
    print(common_profiles_df.dtypes)
    print()

    print(common_profiles_df.head())

    common_profiles_df.to_csv("data/tabular/common_profiles.csv", index=False)
    common_profiles_df.to_pickle("data/tabular/common_profiles.pkl")
"""Tests for DNB source data preparation and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GNDO = Namespace("https://d-nb.info/standards/elementset/gnd#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


@pytest.fixture
def sample_graph() -> Graph:
    g = Graph()
    g.parse(FIXTURES_DIR / "source-dnb-sample.nt", format="nt")
    return g


class TestSampleFixtureParsing:
    def test_fixture_parses_without_error(self, sample_graph: Graph) -> None:
        assert len(sample_graph) > 0

    def test_contains_expected_persons(self, sample_graph: Graph) -> None:
        persons = set(sample_graph.subjects(RDF.type, GNDO.Person))
        assert URIRef("https://d-nb.info/gnd/118514768") in persons
        assert URIRef("https://d-nb.info/gnd/100086721") in persons

    def test_person_count(self, sample_graph: Graph) -> None:
        persons = set(sample_graph.subjects(RDF.type, GNDO.Person))
        assert len(persons) == 2


class TestPropertyCoverage:
    def test_preferred_names_present(self, sample_graph: Graph) -> None:
        names = list(sample_graph.objects(
            URIRef("https://d-nb.info/gnd/118514768"),
            GNDO.preferredNameForThePerson,
        ))
        assert len(names) == 1
        assert "Bonifatius" in str(names[0])

    def test_dates_present(self, sample_graph: Graph) -> None:
        person = URIRef("https://d-nb.info/gnd/118514768")
        births = list(sample_graph.objects(person, GNDO.dateOfBirth))
        deaths = list(sample_graph.objects(person, GNDO.dateOfDeath))
        assert len(births) == 1
        assert len(deaths) == 1

    def test_occupation_linked(self, sample_graph: Graph) -> None:
        person = URIRef("https://d-nb.info/gnd/118514768")
        occupations = list(sample_graph.objects(person, GNDO.professionOrOccupation))
        assert len(occupations) >= 1

        # Check that the occupation has a label
        occ_labels = list(sample_graph.objects(
            occupations[0], GNDO.preferredNameForTheSubjectHeading
        ))
        assert len(occ_labels) == 1
        assert "Erzbischof" in str(occ_labels[0])

    def test_place_of_death_linked(self, sample_graph: Graph) -> None:
        person = URIRef("https://d-nb.info/gnd/118514768")
        places = list(sample_graph.objects(person, GNDO.placeOfDeath))
        assert len(places) == 1

        labels = list(sample_graph.objects(
            places[0], GNDO.preferredNameForThePlaceOrGeographicName
        ))
        assert len(labels) == 1
        assert "Dokkum" in str(labels[0])

    def test_structured_name_node(self, sample_graph: Graph) -> None:
        person = URIRef("https://d-nb.info/gnd/118514768")
        name_nodes = list(sample_graph.objects(
            person, GNDO.preferredNameEntityForThePerson
        ))
        assert len(name_nodes) == 1

        personal_names = list(sample_graph.objects(name_nodes[0], GNDO.personalName))
        assert len(personal_names) == 1
        assert "Bonifatius" in str(personal_names[0])

    def test_variant_names(self, sample_graph: Graph) -> None:
        person = URIRef("https://d-nb.info/gnd/118514768")
        variants = list(sample_graph.objects(person, GNDO.variantNameForThePerson))
        assert len(variants) == 2

# RG Online XML Technical Specifications

> **Access note:** The upstream repository is private. Reproducing the fetch step therefore
> requires authenticated access to the HisQu GitHub repository, e.g. via a
> Personal Access Token (PAT) with permission to read repository contents.

## Fetching the XML source file

The RG Online source data is fetched from the private GitHub repository
`HisQu/RG_data`, currently from the file:

- `rg_xml/rg5.xml`

The scripted acquisition resolves a fixed commit and downloads the XML file via
the GitHub Contents API.

```http request
GET [https://api.github.com/repos/HisQu/RG_data/contents/rg_xml/rg5.xml?ref=](https://api.github.com/repos/HisQu/RG_data/contents/rg_xml/rg5.xml?ref=)<COMMIT_SHA>
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

The raw XML is preserved unchanged in the raw-data layer. Subsequent processing
steps operate on this immutable snapshot.

## Source Structure

The fetched RG Online data is an XML corpus of regest entries. The central unit
is a <lemma> element identified by a stable internal ID.
A typical entry contains:

* a root `<lemma id="...">`
* a ``<reg>`` element with the regest text
* a ``<head>`` element
* one or more ``<sublemma>`` elements
* embedded structured elements such as: ``<date iso="..." year="...">, <fund ...>``
* a ``<personenindex>`` with one or more ``<person>`` entries
* an ``<ortsindex>`` with one or more ``<ort>`` entries

Example skeleton:

```xml
<lemma id="10500001">
  <reg>
    <head>...</head>
    <sublemma vol="5">... <date ...>...</date> <fund ...>...</fund></sublemma>
    <sublemma vol="5">... <date ...>...</date> <fund ...>...</fund></sublemma>
  </reg>
  <personenindex>
    <person id="...">
      <name>...</name>
      <beiname>...</beiname>
      <lemmaID>...</lemmaID>
    </person>
  </personenindex>
  <ortsindex>
    <ort id="...">
      <name>...</name>
      <lemmaID>...</lemmaID>
    </ort>
  </ortsindex>
</lemma>
```

## Interpretation of the XML Structure

The XML is not a flat person table. It is a regest-oriented source structure with
editorially indexed entities.

1. **Lemma as the primary source unit**
Each <lemma> represents a regest entry, not a canonical person record. The
lemma is therefore the primary source object for ingestion and later RDF
materialization.

2. **Sublemmata as statement-bearing segments**
A lemma may contain multiple <sublemma> elements. These subentries often carry
their own date, source reference, and contextual content. They should therefore
be preserved as separate informational units during conversion.

3. **Indexed persons and places**
<personenindex> and <ortsindex> contain editorially extracted entities
associated with the lemma. These are not necessarily disambiguated external
identities, but rather source-internal index entities.

4. **Meaning of lemmaID**
The lemmaID field in <person> and <ort> entries is interpreted as a list of
lemma IDs in which the indexed entity occurs. It should therefore be treated as
an occurrence or mention relation, not as a “main entry” or biography link.

For example:

```xml
<person id="10500323">
  <name>Albertus</name>
  <beiname>Ponghen ...</beiname>
  <lemmaID>10500327 10500001 10504531 10505473 10508051</lemmaID>
</person>
```

means that the indexed person 10500323 occurs in the listed lemma entries.

## Known Structural Characteristics Relevant for RDF Conversion

The raw XML is already partially structured, but it is not yet an RDF-ready
entity graph. Several characteristics must be taken into account during
conversion.

1. **Mixed text and markup in regest content**
The regest text is not plain text. It contains inline editorial markup such as
abbreviation tags and annotation markers: <abk720>solv.</abk720>, <ka/>...<kz/>.
These structures must be preserved or normalized carefully. A naive text extract
would lose editorial information.

2. **Dates occur as both text and normalized attributes**
Date elements contain a human-readable string and normalized attributes:
<date iso="14450407" year="1445">7. apr. 1445</date>.
This is useful for RDF conversion because both the original textual form and a
machine-readable normalized form can be retained.

3. **Fund/source references are internally structured**
Source references are not only free text. They include an iso attribute and
further structured components:
```xml
<fund iso="P1:microf. p.:311" l1="Paris, Q. A. 1" l2="microf. p." l3="311">
  Paris, Q. A. 1 microf. p. 311
</fund>
```
These should be preserved as structured source-reference data in RDF.

4. **Persons and places are source-internal indexed entities**
The <person> and <ort> entries already have stable internal IDs, names, and
cross-references to lemmas. This makes them suitable as source-local RDF
resources, but they should not yet be treated as globally resolved entities.

5. **Names and place strings are not fully normalized**
Names and place labels often contain abbreviations, variant spellings, and
editorial markup, for example:
<beiname><ka/>de<kz/> Speg<ka/>h<kz/>elberg...</beiname>
<name>Traiect. Leod. dioc: s. Servatii <ka/>colleg. eccl.<kz/></name>
These values should be retained in raw or lightly normalized form before any
strong normalization or entity resolution is applied.

6. **Uncertainty and editorial intervention are encoded in the source**
The XML may contain uncertainty markers or reconstructed text, for example via
bracketing, inline markers, or punctuation such as ?. This information is part
of the source semantics and should not be discarded in early-stage conversion.

## Consequences for the RDF Conversion Step

The RG Online XML should first be transformed into a source-faithful RDF graph
with minimal information loss.
The initial RDF conversion should therefore model at least:

* each <lemma> as a regest entry resource
* each <sublemma> as a subentry resource linked to its parent lemma
* each indexed <person> as a source-local person resource
* each indexed <ort> as a source-local place or place/institution resource
* dates as structured temporal information
* fund references as structured source-reference resources
* occurrence relations between indexed entities and lemmas

A minimal target pattern is:

```turtle
@prefix rg: <https://rg-online.dhi-roma.it/rg/> .
@prefix rgo: <https://rg-online.dhi-roma.it/ontology/> .
@prefix gndo: <https://d-nb.info/standards/elementset/gnd#> .

rg:lemma/10500001 a rgo:RegestEntry ;
    rgo:sourceId "10500001" ;
    rgo:hasSubEntry rg:sublemma/10500001-1 ;
    rgo:hasSubEntry rg:sublemma/10500001-2 .

rg:sublemma/10500001-1 a rgo:SubEntry ;
    rgo:dateValue rg:date/10500001-1 ;
    rgo:fundReferencePart1 rg:fund/10500001-1 .

rg:person/10513906 a gndo:DifferentiatedPerson ;
    gndo:preferredNameForThePerson "Mauritius" ;
    rgo:appearsInLemma rg:lemma/10500001 .

rg:place/10519882 a gndo:PlaceOrGeographicName ;
    gndo:preferredNameForThePlaceOrGeographicName "Traiect. Leod. dioc: s. Servatii colleg. eccl." ;
    rgo:appearsInLemma rg:lemma/10500001 .
```
## Licensing

No explicit licensing information is currently available to us from the source
repository metadata. The upstream repository is private and access-restricted.
Reuse, redistribution, and publication rights must therefore be clarified with
the repository owner / data provider (HisQu) before further distribution of the
raw data or derived data products.

## Update Frequency

There is no automatic update schedule. The dataset is ingested manually from a
fixed repository snapshot (commit-pinned fetch). Updates only occur when a new
snapshot is deliberately fetched and stored.

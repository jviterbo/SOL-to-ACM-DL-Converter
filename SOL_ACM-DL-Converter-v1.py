# -*- coding: utf-8 -*-
"""
SOL to ACM-DL Converter
Scrapes proceedings data from SOL (SBC Open Library) and generates
the XML files required for import into the ACM Digital Library.

@author: Viterbo, J.
"""

import requests
import time
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOL_BASE_URL = "https://sol.sbc.org.br/index.php"

PROC_TYPES = [
    "acmconferences",
    "acmotherconferences",
    "dlproceedings",
    "guideproceedings",
    "sbcconferences",
]

BOOK_TYPES = [
    "ACM Conferences",
    "ACM Other Conferences",
    "DL Proceedings",
    "Guide Proceedings",
    "SBC Conferences",
]

SECTION_MAP = {
    "Artigos Curtos": "short-paper",
}
DEFAULT_SECTION = "research-article"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> bytes | None:
    """
    Makes an HTTP GET request to *url* and returns the raw content if the
    response is a successful HTML/XML page, or None otherwise.
    """
    try:
        session = requests.Session()
        response = session.get(
            url,
            headers={"Accept-Language": "en"},
            cookies={"from-my": "browser"},
            stream=True,
        )
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code == 200 and "html" in content_type:
            return response.content
        return None
    except RequestException as exc:
        print(f"[ERROR] Request failed for {url}: {exc}")
        return None


def parse_html(url: str) -> BeautifulSoup:
    """Fetches *url* and returns a BeautifulSoup object."""
    html = fetch_html(url)
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# HTML encoding
# ---------------------------------------------------------------------------

def html_escape(text: str) -> str:
    """Escapes the characters &, ", <, > for safe embedding in XML."""
    return (
        text
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# SOL scraping
# ---------------------------------------------------------------------------

def get_issue_paper_ids(proc_path: str, proc_id: str) -> tuple[list, list, str]:
    """
    Fetches the issue index page and returns:
      - list of article submission IDs
      - list of page ranges (one per article)
      - publication date string
    """
    issue_url = f"{SOL_BASE_URL}/{proc_path}/issue/view/{proc_id}"
    print(f"Fetching issue index: {issue_url}")

    soup = parse_html(issue_url)

    date_pub = (
        soup.find("div", class_="published")
        .find("span", class_="value")
        .string
    )

    paper_ids, page_ranges = [], []

    for article_div in soup.find_all("div", class_="obj_article_summary"):
        title_div = article_div.find("div", class_="title")
        pages_div = article_div.find("div", class_="pages")

        if title_div:
            href = title_div.find_all("a")[0]["href"]
            submission_id = href.rstrip("/").split("/")[-1]
            paper_ids.append(submission_id)
            page_ranges.append(
                pages_div.string.strip() if pages_div else "no page number"
            )

    print(f"Found {len(paper_ids)} articles. Published: {date_pub}")
    return paper_ids, page_ranges, date_pub


def scrape_article(proc_path: str, submission_id: str, pages: str) -> dict:
    """
    Visits the SOL article page for *submission_id* and returns a dict with
    all metadata needed to build the ACM-DL XML files.
    """
    url = f"{SOL_BASE_URL}/{proc_path}/article/view/{submission_id}"
    print(f"  Scraping: {url}")

    soup = parse_html(url)

    meta = {
        "id": submission_id,
        "pages": pages.strip(),
        "authors_list": [],
        "affils_list": [],
        "orcids_list": [],
        "refs": "",
        "kwds": "",
        "abstract": "",
        "abstract_alt": "",
        "title_alt": "",
        "doi": None,
        "url": None,
    }
    section_raw = ""

    for tag in soup.find_all("meta"):
        name = tag.get("name")
        content = tag.get("content", "")

        if name == "DC.Language":
            meta["lang"] = content
        elif name == "DC.Type.articleType":
            section_raw = content
        elif name == "DC.Title":
            meta["title"] = content
        elif name == "DC.Title.Alternative":
            meta["title_alt"] = content
        elif name == "DC.Identifier.DOI":
            meta["doi"] = content
        elif name == "DC.Description":
            if tag.get("xml:lang") == "en":
                meta["abstract"] = content
            elif tag.get("xml:lang") == "pt":
                meta["abstract_alt"] = content
        elif name in ("citation_date", "DC.Date.created"):
            meta["pub_date"] = content
            meta["pub_year"] = content[:4]
        elif name == "citation_author":
            meta["authors_list"].append(content)
        elif name == "citation_author_institution":
            meta["affils_list"].append(content)
        elif name == "citation_firstpage":
            meta["first_page"] = content
        elif name == "citation_lastpage":
            meta["last_page"] = content
        elif name == "citation_pdf_url":
            meta["url"] = content

    meta["section"] = SECTION_MAP.get(section_raw.strip(), DEFAULT_SECTION)
    meta["title"] = meta.get("title", "").strip()
    meta["title_alt"] = meta["title_alt"].strip()
    meta["abstract"] = meta["abstract"].strip()
    meta["abstract_alt"] = meta["abstract_alt"].strip()
    if meta["doi"]:
        meta["doi"] = meta["doi"].strip()

    ref_div = soup.find("div", class_="item references")
    if ref_div:
        val_div = ref_div.find("div", class_="value")
        if val_div:
            meta["refs"] = val_div.text

    kwd_div = soup.find("div", class_="item keywords")
    if kwd_div:
        val_span = kwd_div.find("span", class_="value")
        if val_span:
            meta["kwds"] = val_span.text

    orc_div = soup.find("div", class_="main_entry")
    if orc_div:
        orc_ul = orc_div.find("ul", class_="item authors")
        if orc_ul:
            auts = orc_ul.find_all("li")
            if auts:
                for aut in auts:
                    if aut:
                        orc = aut.find("span", class_="orcid")
                        if orc:
                            orc_a = orc.find("a")
                            if orc_a:
                                orcid_aut = orc_a.text.strip()
                                meta["orcids_list"].append(orcid_aut)
                    else:
                        meta["orcids_list"].append("")

    return meta


# ---------------------------------------------------------------------------
# Params file
# ---------------------------------------------------------------------------

def load_params(filepath: str = "params.txt") -> dict:
    """
    Reads key=value pairs from *filepath* (one per line) and returns them as
    a dict.  The separator is the first '=' on each line so that values may
    contain '=' characters.
    """
    params = {}
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                key, _, value = line.partition("=")
                params[key.strip()] = value.rstrip("\n").strip()
    return params


# ---------------------------------------------------------------------------
# XML writers
# ---------------------------------------------------------------------------

class XmlWriter:
    """
    Writes the BITS XML files required by the ACM Digital Library.

    Parameters
    ----------
    params : dict
        Configuration loaded from params.txt.
    root_path : str
        Base output directory.
    index_path : str
        Directory for the main book XML file.
    """

    def __init__(self, params: dict, root_path: str, index_path: str):
        self.params = params
        self.root_path = root_path
        self.index_path = index_path
        self._type_id = int(params["type_ID"])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_collection_meta(self, fh):
        p = self.params
        fh.write('\t<collection-meta collection-type="book-series">\n')
        fh.write(f'\t\t<collection-id collection-id-type="doi">10.1145/{PROC_TYPES[self._type_id]}</collection-id>\n')
        fh.write('\t\t<title-group>\n')
        fh.write('\t\t\t<title>SBC Conferences</title>\n')
        fh.write('\t\t</title-group>\n')
        fh.write('\t</collection-meta>\n')

    def _write_keywords(self, fh, paper: dict):
        fh.write('\t\t\t<kwd-group>\n')
        for kwd in paper["kwds"].split(","):
            fh.write(f'\t\t\t\t<kwd>{kwd.strip()}</kwd>\n')
        fh.write('\t\t\t</kwd-group>\n')

    def _write_references(self, fh, paper: dict):
        fh.write('\t\t<back>\n')
        fh.write('\t\t\t<ref-list specific-use="unparsed">\n')
        seq = 1
        for line in paper["refs"].splitlines():
            line = line.replace("[link]", "").strip()
            if line:
                ref_id = str(seq).zfill(5)
                fh.write(f'\t\t\t\t<ref id="ref-{ref_id}">\n')
                fh.write(f'\t\t\t\t\t<mixed-citation>{html_escape(line)}</mixed-citation>\n')
                fh.write('\t\t\t\t</ref>\n')
                seq += 1
        fh.write('\t\t\t</ref-list>\n')
        fh.write('\t\t</back>\n')

    def _write_authors(self, fh, paper: dict):
        fh.write('\t\t\t<contrib-group>\n')
        for seq, (full_name, affil, orc) in enumerate(
            zip(paper["authors_list"], paper["affils_list"], paper["orcids_list"]), start=1
        ):
            name_parts = full_name.split()
            surname = name_parts[-1]
            given_names = " ".join(name_parts[:-1])
            contrib_id = str(seq).zfill(5)
            fh.write(f'\t\t\t\t<contrib contrib-type="author" corresp="no" id="artseq-{contrib_id}">\n')
            if orc != '':
                fh.write(f'\t\t\t\t\t<contrib-id contrib-id-type="orcid">{orc}</contrib-id>\n')
            fh.write('\t\t\t\t\t<name>\n')
            fh.write(f'\t\t\t\t\t\t<surname>{surname}</surname>\n')
            fh.write(f'\t\t\t\t\t\t<given-names>{given_names}</given-names>\n')
            fh.write('\t\t\t\t\t</name>\n')
            fh.write(f'\t\t\t\t\t<aff>{affil}</aff>\n')
            fh.write('\t\t\t\t\t<role>Author</role>\n')
            fh.write('\t\t\t\t</contrib>\n')
        fh.write('\t\t\t</contrib-group>\n')

    def _write_pub_date(self, fh, date_str: str, indent: str = "\t\t"):
        day, month, year = date_str.split("-")
        fh.write(f'{indent}<pub-date date-type="publication">\n')
        fh.write(f'{indent}\t<day>{day.strip()}</day>\n')
        fh.write(f'{indent}\t<month>{month.strip()}</month>\n')
        fh.write(f'{indent}\t<year>{year.strip()}</year>\n')
        fh.write(f'{indent}</pub-date>\n')

    # ------------------------------------------------------------------
    # Per-paper XML
    # ------------------------------------------------------------------

    def write_paper_file(self, paper: dict, date_pub: str):
        """Writes the BITS XML file for a single article."""
        p = self.params
        doi_suffix = paper["doi"].split("/")[1]
        paper_dir = Path(self.root_path) / doi_suffix
        paper_dir.mkdir(parents=True, exist_ok=True)

        output_file = paper_dir / f"{doi_suffix}.xml"
        date_parts = paper["pub_date"].split("-")

        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
            fh.write('<!DOCTYPE book-part-wrapper PUBLIC "-//NLM//DTD BITS Book Interchange DTD with OASIS and XHTML Tables v2.0 20151225//EN" "BITS-book-oasis2.dtd">\n')
            fh.write(f'<book-part-wrapper dtd-version="2.0" xml:lang="en" content-type="{paper["section"]}" xmlns:xlink="http://www.w3.org/1999/xlink">\n')

            self._write_collection_meta(fh)

            fh.write('\t<book-meta>\n')
            fh.write(f'\t\t<book-id book-id-type="acm-id">{p["object_ID"]}</book-id>\n')
            fh.write(f'\t\t<book-id book-id-type="doi">10.5753/{p["proc_path"]}.{p["proc_year"]}</book-id>\n')
            fh.write('\t\t<book-title-group>\n')
            fh.write(f'\t\t\t<book-title>{p["issue_title"]}</book-title>\n')
            fh.write(f'\t\t\t<alt-title alt-title-type="acronym">{p["proc_acron"]} {p["proc_year"]}</alt-title>\n')
            fh.write('\t\t</book-title-group>\n')
            fh.write('\t</book-meta>\n')

            fh.write('\t<book-part book-part-type="chapter" xml:lang="en">\n')
            fh.write('\t\t<book-part-meta>\n')
            fh.write(f'\t\t\t<book-part-id book-part-id-type="acm-id">{p["object_ID"]}</book-part-id>\n')
            fh.write(f'\t\t\t<book-part-id book-part-id-type="doi">10.5753/{doi_suffix}</book-part-id>\n')
            fh.write('\t\t\t<title-group>\n')
            fh.write(f'\t\t\t\t<title>{paper["title"]}</title>\n')
            fh.write('\t\t\t</title-group>\n')

            self._write_authors(fh, paper)

            # Publication date (YYYY-MM-DD → day/month/year)
            fh.write('\t\t\t<pub-date date-type="publication">\n')
            fh.write(f'\t\t\t\t<day>{date_parts[2]}</day>\n')
            fh.write(f'\t\t\t\t<month>{date_parts[1]}</month>\n')
            fh.write(f'\t\t\t\t<year>{date_parts[0]}</year>\n')
            fh.write('\t\t\t</pub-date>\n')

            fh.write(f'\t\t\t<fpage>{paper["first_page"]}</fpage>\n')
            fh.write(f'\t\t\t<lpage>{paper["last_page"]}</lpage>\n')

            fh.write('\t\t\t<permissions>\n')
            fh.write(f'\t\t\t\t<copyright-year>{date_parts[0]}</copyright-year>\n')
            fh.write('\t\t\t\t<copyright-holder>Copyright held by the owner/author(s).</copyright-holder>\n')
            fh.write('\t\t\t\t<license license-type="open-access" xlink:href="https://creativecommons.org/licenses/by/4.0/">\n')
            fh.write('\t\t\t\t\t<license-p>This work is licensed under <ext-link ext-link-type="uri" xlink:href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution International 4.0</ext-link>.</license-p>\n')
            fh.write('\t\t\t\t\t<ali:license_ref xmlns:ali="http://www.niso.org/schemas/ali/1.0/">https://creativecommons.org/licenses/by/4.0/legalcode</ali:license_ref>\n')
            fh.write('\t\t\t\t</license>\n')
            fh.write('\t\t\t</permissions>\n')

            fh.write('\t\t\t<abstract>\n')
            fh.write(f'\t\t\t\t<p>{paper["abstract"]}</p>\n')
            fh.write('\t\t\t</abstract>\n')

            self._write_keywords(fh, paper)

            fh.write('\t\t</book-part-meta>\n')
            self._write_references(fh, paper)
            fh.write('\t</book-part>\n')
            fh.write('</book-part-wrapper>\n')

    # ------------------------------------------------------------------
    # Front matter (TOC) — written inline into the main file
    # ------------------------------------------------------------------

    def _write_front_matter(self, fh, papers: list[dict], date_pub: str):
        fh.write('\t<front-matter>\n')
        fh.write('\t\t<toc>\n')
        for paper in papers:
            if paper["title"] == "Front Matter":
                continue
            fh.write('\t\t\t<toc-entry>\n')
            fh.write(f'\t\t\t\t<title>{paper["title"]}</title>\n')
            fh.write('\t\t\t\t<nav-pointer-group>\n')
            fh.write('\t\t\t\t\t<nav-pointer>\n')
            fh.write(f'\t\t\t\t\t\t<ext-link ext-link-type="doi">{paper["doi"]}</ext-link>\n')
            fh.write('\t\t\t\t\t</nav-pointer>\n')
            fh.write(f'\t\t\t\t\t<nav-pointer content-type="label" specific-use="pages">{paper["pages"]}</nav-pointer>\n')
            fh.write('\t\t\t\t</nav-pointer-group>\n')
            fh.write('\t\t\t</toc-entry>\n')
            self.write_paper_file(paper, date_pub)
        fh.write('\t\t</toc>\n')
        fh.write('\t</front-matter>\n')

    def _write_contributors(self, fh, contributors_str: str):
        fh.write('\t\t<contrib-group>\n')
        for seq, contributor in enumerate(contributors_str.split(";"), start=1):
            parts = contributor.split(",")
            role, given_name, surname, affil, email = parts
            contrib_id = str(seq).zfill(5)
            fh.write(f'\t\t\t<contrib contrib-type="other" id="bkseq-{contrib_id}">\n')
            fh.write('\t\t\t\t<name>\n')
            fh.write(f'\t\t\t\t\t<surname>{surname}</surname>\n')
            fh.write(f'\t\t\t\t\t<given-names>{given_name}</given-names>\n')
            fh.write('\t\t\t\t</name>\n')
            fh.write(f'\t\t\t\t<aff>{affil}</aff>\n')
            if email:
                fh.write(f'\t\t\t\t<email>{email}</email>\n')
            fh.write(f'\t\t\t\t<role>{role}</role>\n')
            fh.write('\t\t\t</contrib>\n')
        fh.write('\t\t</contrib-group>\n')

    # ------------------------------------------------------------------
    # Main book XML
    # ------------------------------------------------------------------

    def write_main_file(self, papers: list[dict], date_pub: str):
        """Writes the top-level book XML file that references all articles."""
        p = self.params
        output_file = Path(self.index_path) / f"{p['object_ID']}.xml"

        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
            fh.write('<!DOCTYPE book PUBLIC "-//NLM//DTD BITS Book Interchange DTD with OASIS and XHTML Tables v2.0 20151225//EN" "BITS-book-oasis2.dtd">\n')
            fh.write(f'<book dtd-version="2.0" xml:lang="en" book-type="{BOOK_TYPES[self._type_id]}" xmlns:xlink="http://www.w3.org/1999/xlink">\n')

            self._write_collection_meta(fh)

            fh.write('\t<book-meta>\n')
            fh.write(f'\t\t<book-id book-id-type="acm-id">{p["object_ID"]}</book-id>\n')
            fh.write(f'\t\t<book-id book-id-type="doi">10.5753/{p["proc_path"]}.{p["proc_year"]}</book-id>\n')

            # Conference collections
            fh.write('\t\t<subj-group subj-group-type="conference-collections">\n')
            fh.write('\t\t\t<compound-subject>\n')
            fh.write(f'\t\t\t\t<compound-subject-part content-type="code">{p["proc_path"]}-mtg</compound-subject-part>\n')
            fh.write(f'\t\t\t\t<compound-subject-part content-type="text">{p["proc_acron"]}: {p["proc_title"]}</compound-subject-part>\n')
            fh.write('\t\t\t</compound-subject>\n')
            fh.write('\t\t</subj-group>\n')

            # Acceptance rates
            fh.write('\t\t<subj-group subj-group-type="acceptance-rates">\n')
            fh.write('\t\t\t<compound-subject>\n')
            fh.write(f'\t\t\t\t<compound-subject-part content-type="tract_type">{p["tract_type"]}</compound-subject-part>\n')
            fh.write(f'\t\t\t\t<compound-subject-part content-type="total_submitted">{p["total_submitted"]}</compound-subject-part>\n')
            fh.write(f'\t\t\t\t<compound-subject-part content-type="total_accepted">{p["total_accepted"]}</compound-subject-part>\n')
            fh.write('\t\t\t</compound-subject>\n')
            fh.write('\t\t</subj-group>\n')

            # Book title
            fh.write('\t\t<book-title-group>\n')
            fh.write(f'\t\t\t<book-title>{p["issue_title"]}</book-title>\n')
            fh.write(f'\t\t\t<alt-title alt-title-type="acronym">{p["proc_acron"]} {p["proc_year"]}</alt-title>\n')
            fh.write('\t\t</book-title-group>\n')

            self._write_contributors(fh, p["contributors"])

            # Publication date (format from params: DD/MM/YYYY)
            day, month, year = date_pub.split("/")
            fh.write('\t\t<pub-date date-type="publication">\n')
            fh.write(f'\t\t\t<day>{day.strip()}</day>\n')
            fh.write(f'\t\t\t<month>{month.strip()}</month>\n')
            fh.write(f'\t\t\t<year>{year.strip()}</year>\n')
            fh.write('\t\t</pub-date>\n')

            fh.write('\t\t<publisher>\n')
            fh.write('\t\t\t<publisher-name>SBC - Brazilian Computer Society</publisher-name>\n')
            fh.write('\t\t\t<publisher-name specific-use="publisher-id db-only">PUB6784</publisher-name>\n')
            fh.write('\t\t\t<publisher-loc>Porto Alegre, RS, Brazil</publisher-loc>\n')
            fh.write('\t\t</publisher>\n')

            fh.write('\t\t<permissions>\n')
            fh.write(f'\t\t\t<copyright-year>{p["proc_year"]}</copyright-year>\n')
            fh.write('\t\t</permissions>\n')

            if p.get("has_FM") == "yes":
                fh.write(f'\t\t<self-uri content-type="fm-pdf" xlink:href="{p["object_ID"]}.fm.pdf">Front matter (Title page, Contents, Welcome, Author index)</self-uri>\n')
            if p.get("has_Full") == "yes":
                fh.write(f'\t\t<self-uri content-type="pdf" xlink:href="{p["object_ID"]}.pdf">{p["proc_acron"]} {p["proc_year"]}</self-uri>\n')

            fh.write('\t\t<abstract>\n')
            fh.write(f'\t\t\t<p>{p["proc_abstract"]}</p>\n')
            fh.write('\t\t</abstract>\n')

            # Conference info
            conf_date = f'{p["start_year"]}-{p["start_month"]}-{p["start_day"]}'
            fh.write('\t\t<conference>\n')
            fh.write(f'\t\t\t<conf-date iso-8601-date="{conf_date}">\n')
            fh.write(f'\t\t\t\t<day content-type="start-day">{p["start_day"]}</day>\n')
            fh.write(f'\t\t\t\t<month content-type="start-month">{p["start_month"]}</month>\n')
            fh.write(f'\t\t\t\t<year content-type="start-year">{p["start_year"]}</year>\n')
            fh.write(f'\t\t\t\t<day content-type="end-day">{p["end_day"]}</day>\n')
            fh.write(f'\t\t\t\t<month content-type="end-month">{p["end_month"]}</month>\n')
            fh.write(f'\t\t\t\t<year content-type="end-year">{p["end_year"]}</year>\n')
            fh.write('\t\t\t</conf-date>\n')
            fh.write(f'\t\t\t<conf-name><ext-link ext-link-type="url" xlink:href="{p["conf_site"]}">{p["proc_acron"]} {p["proc_year"]}</ext-link>: {p["conf_name"]}</conf-name>\n')
            fh.write('\t\t\t<conf-loc>\n')
            fh.write(f'\t\t\t\t<institution>{p["conf_inst"]}</institution>\n')
            fh.write(f'\t\t\t\t<city>{p["conf_city"]}</city>\n')
            fh.write(f'\t\t\t\t<country>{p["conf_country"]}</country>\n')
            fh.write('\t\t\t</conf-loc>\n')
            fh.write(f'\t\t\t<conf-acronym>{p["proc_acron"]} {p["proc_year"]}</conf-acronym>\n')
            fh.write('\t\t</conference>\n')

            fh.write(f'\t\t<counts><book-page-count count="{p["proc_pages"]}" /></counts>\n')
            fh.write('\t</book-meta>\n')

            self._write_front_matter(fh, papers, date_pub)

            fh.write('</book>\n')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    params = load_params("params.txt")
    datestamp = datetime.now().strftime("%Y%m%d")

    type_id = int(params["type_ID"])
    root_path = f"{PROC_TYPES[type_id]}_{params['object_ID']}_{datestamp}/{params['object_ID']}"
    index_path = f"{root_path}/{params['object_ID']}"

    Path(root_path).mkdir(parents=True, exist_ok=True)
    Path(index_path).mkdir(parents=True, exist_ok=True)

    paper_ids, page_ranges, date_pub = get_issue_paper_ids(
        params["proc_path"], params["proc_ID"]
    )

    papers = []
    for submission_id, pages in zip(paper_ids, page_ranges):
        paper = scrape_article(params["proc_path"], submission_id, pages)
        papers.append(paper)
        time.sleep(2.5)

    print(f"\n{len(papers)} article(s) collected.")

    writer = XmlWriter(params, root_path, index_path)
    writer.write_main_file(papers, date_pub)
    print("Done. XML files written to:", root_path)


if __name__ == "__main__":
    main()

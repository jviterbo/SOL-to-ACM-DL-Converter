# -*- coding: utf-8 -*-
"""
Created on Mon Apr 19 22:54:04 2026

@author: Viterbo, J.

       
"""

import requests
#from requests import Session
from requests.exceptions import RequestException
#from contextlib import closing
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime





def simple_get(url):
    """
    Attempts to get the content at `url` by making an HTTP GET request.
    If the content-type of response is some kind of HTML/XML, return the
    text content, otherwise return None.
    """
    try:
        s = requests.Session()
        resp = s.get(url, headers = {"Accept-Language": "en"}, cookies={'from-my': 'browser'}, stream=True)
        if is_good_response(resp):
            return resp.content
        else:
            return None

    except RequestException as e:
        log_error('Error during requests to {0} : {1}'.format(url, str(e)))
        return None

def is_good_response(resp):
    """
    Returns True if the response seems to be HTML, False otherwise.
    """
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200 
            and content_type is not None 
            and content_type.find('html') > -1)

def log_error(e):
    """
    It is always a good idea to log errors. 
    This function just prints them, but you can
    make it do anything.
    """
    print(e)

def getart(link):
    """
    Attempts to get the content at `url` that corresponds to an article
    page.
    """
    html = simple_get(link)
    return BeautifulSoup(html,"html.parser")

def htmlspecialchars(text):
    return (
        text.replace("&", "&amp;").
        replace('"', "&quot;").
        replace("<", "&lt;").
        replace(">", "&gt;")
    )


def check_article(proc, id_submission, pages):
    link = "https://sol.sbc.org.br/index.php/"+proc+"/article/view/"+id_submission
    print(link)
    html = simple_get(link)
    res = BeautifulSoup(html,"html.parser")
    title = None
    title_alt = None
    abstract = None
    lang = None
    doi = None
    author_list=[]
    affil_list=[]
    k_author = 0
    metas = res.findAll('meta')
    for meta in metas:
        meta_name = meta.get("name", None)
        if meta_name == "DC.Language":
            lang = meta.get("content", None)
        if meta_name == "DC.Type.articleType":
            section = meta.get("content", None)
        if meta_name == "DC.Title":
            title = meta.get("content", None)
        if meta_name == "DC.Title.Alternative":
            title_alt = meta.get("content", None)
        if meta_name == "DC.Identifier.DOI":
            doi = meta.get("content", None)
        if meta_name == "DC.Description":
            abs_lang = meta.get("xml:lang", None)
            if abs_lang == "en":
                abstract = meta.get("content", None)
            if abs_lang == "pt":
                abstract_alt = meta.get("content", None)
        if meta_name == "citation_date":
            pub_date = meta.get("content", None)
            pub_year = pub_date[0:4]
        if meta_name == "citation_author":
            author = meta.get("content", None)
            #print(author)
            author_list.append(author)
            k_author = k_author + 1
        if meta_name == "citation_author_institution":
            affil = meta.get("content", None)
            #print(affil)
            affil_list.append(affil)
        if meta_name == "citation_firstpage":
            first_page = meta.get("content", None)
        if meta_name == "citation_lastpage":
            last_page = meta.get("content", None)
        if meta_name == "DC.Date.created":
            pub_date = meta.get("content", None)
            
            
    section = section.strip()
    
    if section == "Artigos Curtos":
        section = "short-paper"
    else:
        section = "research-article"
    
    paper_meta = {}
    paper_meta["id"] = id_submission
    paper_meta["section"] = section
    paper_meta["title"] = title.strip()
    paper_meta["title_alt"] = title_alt.strip()
    paper_meta["abstract"] = abstract.strip()
    paper_meta["abstract_alt"] = abstract_alt.strip()
    if doi is not None:
        paper_meta["doi"] = doi.strip()
    paper_meta["pub_year"] = pub_year.strip()
    paper_meta["pages"] = pages.strip()
    paper_meta["num_authors"] = k_author
    paper_meta["authors_list"] = author_list
    paper_meta["affils_list"] = affil_list
    paper_meta["first_page"] = first_page
    paper_meta["last_page"] = last_page
    paper_meta["pub_date"] = pub_date
    
    paper_meta["refs"] = ""
    div_ref = res.find('div', class_= 'item references')  
    if div_ref is not None:
        div_ref_val = div_ref.find('div', class_= 'value')        
        if div_ref_val is not None:
            paper_meta["refs"] = div_ref_val.text

    paper_meta["kwds"] = ""
    div_kwd = res.find('div', class_= 'item keywords')  
    if div_kwd is not None:
        div_kwd_val = div_kwd.find('span', class_= 'value')
        if div_kwd_val is not None:
            paper_meta["kwds"] = div_kwd_val.text

    
    return paper_meta
            
    # if lang == "en":
    #     return id_submission, title, abstract, pub_year, k_author, author_list, affil_list
    # else:
    #     return id_submission, title_alt, abstract_alt, pub_year, k_author, author_list, affil_list

def get_paper_links_in_volume(link):

    """ 
    Getting the content of the volume index page 
    """
    html = simple_get(link)
    
    res = BeautifulSoup(html,"html.parser")
    
    #print("Vai contar o número de artigos em "+link)
    hrefpapers_vet = []
    
    numpapers = 0
    divs = res.findAll('div', class_= 'obj_article_summary')
    for div in divs:
        #print(str(div))
        divs2 = div.findAll('div', class_= 'title')        
        for div2 in divs2:
            a_hrefs = div2.findAll('a')
            href = a_hrefs[0]
            #print(str(href['href']))
            numpapers = numpapers + 1
            hrefpapers_vet.append(href['href'])

    return hrefpapers_vet
    
def get_paper_ids_in_volume(link):

    """ 
    Getting the content of the volume index page 
    """
    html = simple_get(link)
        
    res = BeautifulSoup(html,"html.parser")
    
    #print("Vai contar o número de artigos em "+link)
    hrefpapers_vet = []
    pagepapers_vet = []
    
    numpapers = 0
    div_pub = res.find('div', class_= 'published')
    date_pub = div_pub.find('span', class_= 'value').string
    divs = res.findAll('div', class_= 'obj_article_summary')
    for div in divs:
        #print(str(div))
        div2 = div.find('div', class_= 'title')        
        div3 = div.find('div', class_= 'pages')        
        if div2 is not None:
            a_hrefs = div2.findAll('a')
            href = a_hrefs[0]
            #print(str(href['href']))
            numpapers = numpapers + 1
            link_paper = href['href']
            link_list = link_paper.split("/")
            id_submission = link_list[len(link_list)-1]
            hrefpapers_vet.append(id_submission)
            
        if div3 is not None:
            pagepapers_vet.append(div3.string.strip())
        else:
            pagepapers_vet.append("no page number")
            
    print(hrefpapers_vet)
    return hrefpapers_vet, pagepapers_vet, date_pub
    
    


def get_params():
    
    param_dict = {}
    
    with open('params.txt','r',encoding='utf-8') as fin:
        lines = fin.readlines()
        
    for line in lines:
        line = line.replace('=', '\=')
        params = line.split('\=',1)
        key = params[0]
        val = params[1].rstrip('\n').replace('\=', '=')
        param_dict[key] = val
        #print(key+': '+val)
        
    return param_dict

def output_paper_keywords(fout, params, date_pub, paper_meta_vet, i):

    fout.write("\t\t\t<kwd-group>\n")
        
    kwd_list = paper_meta_vet[i]["kwds"].split(',')

    for kwd in kwd_list:
        kwd = kwd.strip()
        fout.write("\t\t\t\t<kwd>"+kwd+"</kwd>\n")
    
    fout.write("\t\t\t</kwd-group>\n")


def output_paper_references(fout, params, date_pub, paper_meta_vet, i):
    
    fout.write("\t\t<back>\n")
    fout.write("\t\t\t<ref-list specific-use=\"unparsed\">\n")
    
    seq = 1
    
    if paper_meta_vet[i]["refs"] is not None:
        refs_list = paper_meta_vet[i]["refs"].splitlines()

        for line in refs_list:
            line = line.replace("[link]", '')
            line = line.strip()
            if line != '':
                fout.write("\t\t\t\t<ref id=\"ref-"+str(seq).zfill(5)+"\">\n")
                fout.write("\t\t\t\t\t<mixed-citation>"+htmlspecialchars(line)+"</mixed-citation>\n")
                fout.write("\t\t\t\t</ref>\n")
                seq = seq + 1

    fout.write("\t\t\t</ref-list>\n")
    fout.write("\t\t</back>\n")
    



def output_paper_authors(fout, params, date_pub, paper_meta_vet, i):

    fout.write("\t\t\t<contrib-group>\n")
    
    seq = 1
        
    for k in range(len(paper_meta_vet[i]["authors_list"])):
        
        name_parts = paper_meta_vet[i]["authors_list"][k].split()
        surname = name_parts[len(name_parts)-1]
        del name_parts[len(name_parts)-1]
            
        given_names = ''
        
        for part in name_parts:
            given_names = given_names + part + ' '
        
        given_names = given_names.strip()


        fout.write("\t\t\t\t<contrib contrib-type=\"author\" corresp=\"no\" id=\"artseq-"+str(seq).zfill(5)+"\">\n")
        fout.write("\t\t\t\t\t<name>\n")
        fout.write("\t\t\t\t\t\t<surname>"+surname+"</surname>\n")
        fout.write("\t\t\t\t\t\t<given-names>"+given_names+"</given-names>\n")
        fout.write("\t\t\t\t\t</name>\n")
        fout.write("\t\t\t\t\t<aff>"+paper_meta_vet[i]["affils_list"][k]+"</aff>\n")
        fout.write("\t\t\t\t\t<role>Author</role>\n")
        fout.write("\t\t\t\t</contrib>\n")
        seq = seq + 1

    fout.write("\t\t\t</contrib-group>\n")


def output_paper_file(params, date_pub, paper_meta_vet, i):
    
    doi_parts = paper_meta_vet[i]["doi"].split('/')
    doi_ext = doi_parts[1]
    
    paper_path = root_path+"/"+doi_ext    
    Path(paper_path).mkdir(parents=True, exist_ok=True)

    fout = open(paper_path+"/"+doi_ext+".xml", "w", encoding = "utf-8")

    fout.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
    fout.write("<!DOCTYPE book-part-wrapper PUBLIC \"-//NLM//DTD BITS Book Interchange DTD with OASIS and XHTML Tables v2.0 20151225//EN\" \"BITS-book-oasis2.dtd\">\n")
    fout.write("<book-part-wrapper dtd-version=\"2.0\" xml:lang=\"en\" content-type=\""+paper_meta_vet[i]["section"]+"\" xmlns:xlink=\"http://www.w3.org/1999/xlink\">\n")
    fout.write("\t<collection-meta collection-type=\"book-series\">\n")
    fout.write("\t\t<collection-id collection-id-type=\"doi\">10.1145/"+proc_type[int(params["type_ID"])]+"</collection-id>\n")
    fout.write("\t\t<title-group>\n")
    fout.write("\t\t\t<title>SBC Conferences</title>\n")
    fout.write("\t\t</title-group>\n")
    fout.write("\t</collection-meta>\n")
    fout.write("\t<book-meta>\n")
    fout.write("\t\t<book-id book-id-type=\"acm-id\">"+params["object_ID"]+"</book-id>\n")
    fout.write("\t\t<book-id book-id-type=\"doi\">10.5753/"+params["proc_path"]+"."+params["proc_year"]+"</book-id>\n")

    # Book title
    fout.write("\t\t<book-title-group>\n")
    fout.write("\t\t\t<book-title>"+params["issue_title"]+"</book-title>\n")
    fout.write("\t\t\t<alt-title alt-title-type=\"acronym\">"+params["proc_acron"]+" "+params["proc_year"]+"</alt-title>\n")
    fout.write("\t\t</book-title-group>\n")
    fout.write("\t</book-meta>\n")

    # Paper metadata
    fout.write("\t<book-part book-part-type=\"chapter\" xml:lang=\"en\">\n")
    fout.write("\t\t<book-part-meta>\n")
    fout.write("\t\t\t<book-part-id book-part-id-type=\"acm-id\">"+params["object_ID"]+"</book-part-id>\n")
    fout.write("\t\t\t<book-part-id book-part-id-type=\"doi\">10.5753/"+doi_ext+"</book-part-id>\n")

    # Paper title
    fout.write("\t\t\t<title-group>\n")
    fout.write("\t\t\t\t<title>"+paper_meta_vet[i]["title"]+"</title>\n")
    fout.write("\t\t\t</title-group>\n")

    # Paper authors
    output_paper_authors(fout, params, date_pub, paper_meta_vet, i)

    # Paper dates
    date_parts = paper_meta_vet[i]["pub_date"].split('-')
    
    fout.write("\t\t\t<pub-date date-type=\"publication\">\n")
    fout.write("\t\t\t\t<day>"+date_parts[2]+"</day>\n")
    fout.write("\t\t\t\t<month>"+date_parts[1]+"</month>\n")
    fout.write("\t\t\t\t<year>"+date_parts[0]+"</year>\n")
    fout.write("\t\t\t</pub-date>\n")
    
    # Paper pages
    fout.write("\t\t\t<fpage>"+paper_meta_vet[i]["first_page"]+"</fpage>\n")
    fout.write("\t\t\t<lpage>"+paper_meta_vet[i]["last_page"]+"</lpage>\n")

    # Paper permissions
    fout.write("\t\t\t<permissions>\n")
    fout.write("\t\t\t\t<copyright-year>"+date_parts[0]+"</copyright-year>\n")
    fout.write("\t\t\t\t<copyright-holder>Copyright held by the owner/author(s).</copyright-holder>\n")
    fout.write("\t\t\t\t<license license-type=\"open-access\" xlink:href=\"https://creativecommons.org/licenses/by/4.0/\">\n")
    fout.write("\t\t\t\t\t<license-p>This work is licensed under <ext-link ext-link-type=\"uri\" xlink:href=\"https://creativecommons.org/licenses/by/4.0/\">Creative Commons Attribution International 4.0</ext-link>.</license-p>\n")
    fout.write("\t\t\t\t\t<ali:license_ref xmlns:ali=\"http://www.niso.org/schemas/ali/1.0/\">https://creativecommons.org/licenses/by/4.0/legalcode</ali:license_ref>\n")
    fout.write("\t\t\t\t</license>\n")
    fout.write("\t\t\t</permissions>\n")

    # Paper PDF file

    # Paper abstract
    fout.write("\t\t\t<abstract>\n")
    fout.write("\t\t\t\t<p>"+paper_meta_vet[i]["abstract"]+"</p>\n")
    fout.write("\t\t\t</abstract>\n")

    # Paper keywords
    output_paper_keywords(fout, params, date_pub, paper_meta_vet, i)
    
    fout.write("\t\t</book-part-meta>\n")
    
    # Paper references
    output_paper_references(fout, params, date_pub, paper_meta_vet, i)
    

    fout.write("\t</book-part>\n")
    fout.write("</book-part-wrapper>\n")
    fout.close()


def output_frontmatter(fout, paper_meta_vet, params):

    fout.write("\t<front-matter>\n")
    fout.write("\t\t<toc>\n")
    
    for i in range(len(paper_meta_vet)):
        if paper_meta_vet[i]["title"] != "Front Matter":
            fout.write("\t\t\t<toc-entry>\n")
            fout.write("\t\t\t\t<title>"+paper_meta_vet[i]["title"]+"</title>\n")
            fout.write("\t\t\t\t<nav-pointer-group>\n")
            fout.write("\t\t\t\t\t<nav-pointer>\n")
            fout.write("\t\t\t\t\t\t<ext-link ext-link-type=\"doi\">"+paper_meta_vet[i]["doi"]+"</ext-link>\n")

            fout.write("\t\t\t\t\t</nav-pointer>\n")
            fout.write("\t\t\t\t\t<nav-pointer content-type=\"label\" specific-use=\"pages\">"+paper_meta_vet[i]["pages"]+"</nav-pointer>\n")
            fout.write("\t\t\t\t</nav-pointer-group>\n")
            fout.write("\t\t\t</toc-entry>\n")
            
            output_paper_file(params, date_pub, paper_meta_vet, i)

    fout.write("\t\t</toc>\n")
    fout.write("\t</front-matter>\n")

def output_dates(fout,date):

    fout.write("\t\t<pub-date date-type=\"publication\">\n")
    fout.write("\t\t\t<day>"+date[0].strip()+"</day>\n")
    fout.write("\t\t\t<month>"+date[1].strip()+"</month>\n")
    fout.write("\t\t\t<year>"+date[2].strip()+"</year>\n")
    fout.write("\t\t</pub-date>\n")

def output_contributors(fout,contributors):
    
    fout.write("\t\t<contrib-group>\n")
    
    seq = 1
    
    for contributor in contributors:
        parts = contributor.split(',')
        role = parts[0]
        givenname = parts[1]
        surname = parts[2]
        affil = parts[3]
        email = parts[4]
        
        fout.write("\t\t\t<contrib contrib-type=\"other\" id=\"bkseq-"+str(seq).zfill(5)+"\">\n")
        fout.write("\t\t\t\t<name>\n")
        fout.write("\t\t\t\t\t<surname>"+surname+"</surname>\n")
        fout.write("\t\t\t\t\t<given-names>"+givenname+"</given-names>\n")
        fout.write("\t\t\t\t</name>\n")
        fout.write("\t\t\t\t<aff>"+affil+"</aff>\n")
        if email != '':
            fout.write("\t\t\t\t<email>"+email+"</email>\n")
        fout.write("\t\t\t\t<role>"+role+"</role>\n")

        fout.write("\t\t\t</contrib>\n")
        seq = seq + 1
        
    fout.write("\t\t</contrib-group>\n")
    

def output_main_file(params, date_pub, paper_meta_vet):
    
    fout = open(index_path+"/"+params["object_ID"]+".xml", "w", encoding = "utf-8")
    
    fout.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
    fout.write("<!DOCTYPE book PUBLIC \"-//NLM//DTD BITS Book Interchange DTD with OASIS and XHTML Tables v2.0 20151225//EN\" \"BITS-book-oasis2.dtd\">\n")
    fout.write("<book dtd-version=\"2.0\" xml:lang=\"en\" book-type=\""+book_type[int(params["type_ID"])]+"\" xmlns:xlink=\"http://www.w3.org/1999/xlink\">\n")
    fout.write("\t<collection-meta collection-type=\"book-series\">\n")
    fout.write("\t\t<collection-id collection-id-type=\"doi\">10.1145/"+proc_type[int(params["type_ID"])]+"</collection-id>\n")
    fout.write("\t\t<title-group>\n")
    fout.write("\t\t\t<title>SBC Conferences</title>\n")
    fout.write("\t\t</title-group>\n")
    fout.write("\t</collection-meta>\n")
    fout.write("\t<book-meta>\n")
    fout.write("\t\t<book-id book-id-type=\"acm-id\">"+params["object_ID"]+"</book-id>\n")
    fout.write("\t\t<book-id book-id-type=\"doi\">10.5753/"+params["proc_path"]+"."+params["proc_year"]+"</book-id>\n")
    fout.write("\t\t<subj-group subj-group-type=\"conference-collections\">\n")
    fout.write("\t\t\t<compound-subject>\n")
    fout.write("\t\t\t\t<compound-subject-part content-type=\"code\">"+params["proc_path"]+"-mtg"+"</compound-subject-part>\n")
    fout.write("\t\t\t\t<compound-subject-part content-type=\"text\">"+params["proc_acron"]+": "+params["proc_title"]+"</compound-subject-part>\n")
    fout.write("\t\t\t</compound-subject>\n")
    fout.write("\t\t</subj-group>\n")
    
    # Acceptance rates
    fout.write("\t\t<subj-group subj-group-type=\"acceptance-rates\">\n")
    fout.write("\t\t\t<compound-subject>\n")
    fout.write("\t\t\t\t<compound-subject-part content-type=\"tract_type\">"+params["tract_type"]+"</compound-subject-part>\n")
    fout.write("\t\t\t\t<compound-subject-part content-type=\"total_submitted\">"+params["total_submitted"]+"</compound-subject-part>\n")
    fout.write("\t\t\t\t<compound-subject-part content-type=\"total_accepted\">"+params["total_accepted"]+"</compound-subject-part>\n")
    fout.write("\t\t\t</compound-subject>\n")
    fout.write("\t\t</subj-group>\n")

    # Book title
    fout.write("\t\t<book-title-group>\n")
    fout.write("\t\t\t<book-title>"+params["issue_title"]+"</book-title>\n")
    fout.write("\t\t\t<alt-title alt-title-type=\"acronym\">"+params["proc_acron"]+" "+params["proc_year"]+"</alt-title>\n")
    fout.write("\t\t</book-title-group>\n")
    
    output_contributors(fout,params["contributors"].split(';'))
    output_dates(fout,date_pub.split('/'))
    
    fout.write("\t\t<publisher>\n")
    fout.write("\t\t\t<publisher-name>SBC - Brazilian Computer Society</publisher-name>\n")
    fout.write("\t\t\t<publisher-name specific-use=\"publisher-id db-only\">PUB6784</publisher-name>\n")
    fout.write("\t\t\t<publisher-loc>Porto Alegre, RS, Brazil</publisher-loc>\n")
    fout.write("\t\t</publisher>\n")
    fout.write("\t\t<permissions>\n")
    fout.write("\t\t\t<copyright-year>"+params["proc_year"]+"</copyright-year>\n")
    fout.write("\t\t</permissions>\n")
    if params["has_FM"] == "yes":
        fout.write("\t\t<self-uri content-type=\"fm-pdf\" xlink:href=\""+params["object_ID"]+".fm.pdf\">Front matter (Title page, Contents, Welcome, Author index)</self-uri>\n")    
    if params["has_Full"] == "yes":
        fout.write("\t\t<self-uri content-type=\"pdf\" xlink:href=\""+params["object_ID"]+".pdf\">"+params["proc_acron"]+" "+params["proc_year"]+"</self-uri>\n")    
    fout.write("\t\t<abstract>\n")
    fout.write("\t\t\t<p>"+params["proc_abstract"]+"</p>\n")
    fout.write("\t\t</abstract>\n")

    fout.write("\t\t<conference>\n")
    conf_date = params["start_year"]+"-"+params["start_month"]+"-"+params["start_day"]
    fout.write("\t\t\t<conf-date iso-8601-date=\""+conf_date+"\">\n")
    fout.write("\t\t\t\t<day content-type=\"start-day\">"+params["start_day"]+"</day>\n")
    fout.write("\t\t\t\t<month content-type=\"start-month\">"+params["start_month"]+"</month>\n")
    fout.write("\t\t\t\t<year content-type=\"start-year\">"+params["start_year"]+"</year>\n")
    fout.write("\t\t\t\t<day content-type=\"end-day\">"+params["end_day"]+"</day>\n")
    fout.write("\t\t\t\t<month content-type=\"end-month\">"+params["end_month"]+"</month>\n")
    fout.write("\t\t\t\t<year content-type=\"end-year\">"+params["end_year"]+"</year>\n")
    fout.write("\t\t\t</conf-date>\n")
    fout.write("\t\t\t<conf-name><ext-link ext-link-type=\"url\" xlink:href=\""+params["conf_site"]+"\">"+params["proc_acron"]+" "+params["proc_year"]+"</ext-link>: "+params["conf_name"]+"</conf-name>\n")
    fout.write("\t\t\t<conf-loc>\n")
    fout.write("\t\t\t\t<institution>"+params["conf_inst"]+"</institution>\n")
    fout.write("\t\t\t\t<city>"+params["conf_city"]+"</city>\n")
    fout.write("\t\t\t\t<country>"+params["conf_country"]+"</country>\n")
    fout.write("\t\t\t</conf-loc>\n")
    fout.write("\t\t\t<conf-acronym>"+params["proc_acron"]+" "+params["proc_year"]+"</conf-acronym>\n")

    fout.write("\t\t</conference>\n")
    
    fout.write("\t\t<counts><book-page-count count=\""+params["proc_pages"]+"\" /></counts>\n")

    fout.write("\t</book-meta>\n")
    
    output_frontmatter(fout, paper_meta_vet, params)
        
    fout.write("</book>\n")
    fout.close()
    

proc_type = ["acmconferences", "acmotherconferences", "dlproceedings", "guideproceedings", "sbcconferences"]
book_type = ["ACM Conferences", "ACM Other Conferences", "DL Proceedings", "Guide Proceedings", "SBC Conferences"]

params = get_params()

datestamp = datetime.now().strftime("%Y%m%d")

root_path = proc_type[int(params["type_ID"])] + "_" + params["object_ID"] + "_" + datestamp + "/" + params["object_ID"]
index_path = root_path+"/"+params["object_ID"]

Path(root_path).mkdir(parents=True, exist_ok=True)
Path(index_path).mkdir(parents=True, exist_ok=True)


paper_ids = []
paper_pgs = []

base__link = "https://sol.sbc.org.br/index.php/"+params["proc_path"]
issue_link = base__link+"/issue/view/"+params["proc_ID"]

papers_vet, pages_vet, date_pub = get_paper_ids_in_volume(issue_link)
print("href: " + issue_link)
print("publicado em: " + date_pub)
paper_ids.extend(papers_vet)
paper_pgs.extend(pages_vet)

paper_meta_vet = []

k_paper = 0
for i in range(len(paper_ids)):
    paper_meta = check_article(params["proc_path"], paper_ids[i], paper_pgs[i])
    paper_meta_vet.append(paper_meta)
    k_paper = k_paper + 1
    
print(str(k_paper) + " artigos localizados")

print("Tamanho de vetor é "+str(len(paper_meta_vet)))

Path(root_path).mkdir(parents=True, exist_ok=True)

output_main_file(params, date_pub, paper_meta_vet)


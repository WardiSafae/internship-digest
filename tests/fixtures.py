"""Small hand-written copies of what each source returns.
Used by the unit tests; no network needed."""
import json

REMOTIVE = json.dumps({"jobs": [
    {"title": "Data Science Intern", "company_name": "Acme",
     "candidate_required_location": "Worldwide",
     "description": "<p>Work on <strong>NLP</strong>\n  models &amp; pipelines.</p>",
     "url": "https://remotive.com/job/1", "tags": ["python", "nlp"],
     "publication_date": "2026-10-20T10:00:00"},
    {"title": "ML Intern", "company_name": "Beta", "description": "",
     "url": "https://remotive.com/job/2", "tags": [],
     "publication_date": "2026-10-21T10:00:00"},
]})

ARBEITNOW = json.dumps({"data": [
    {"title": "Software Engineering Intern (Full-Stack)", "company_name": "Sanovio",
     "location": "Munich", "description": "<p>Build things</p>",
     "url": "https://www.arbeitnow.com/jobs/a", "tags": ["engineering"],
     "created_at": 1761000000, "remote": False},
    {"title": "Senior Backend Engineer", "company_name": "Nope", "location": "Berlin",
     "description": "x", "url": "https://www.arbeitnow.com/jobs/b", "tags": [],
     "created_at": 1761000001, "remote": False},
]})

REMOTEOK = json.dumps([
    {"last_updated": 1, "legal": "API terms"},
    {"position": "Junior Data Analyst", "company": "Gamma", "location": "",
     "description": "<p>SQL</p>", "url": "https://remoteok.com/remote-jobs/1",
     "tags": ["Analyst", "SQL"], "date": "2026-10-07T16:00:05+00:00"},
    {"position": "Head of Operations", "company": "Delta", "description": "",
     "url": "https://remoteok.com/remote-jobs/2", "tags": ["exec"], "date": "x"},
    {"position": "Backend Engineer", "company": "Eps", "description": "",
     "url": "https://remoteok.com/remote-jobs/3", "tags": ["intern"], "date": "y"},
])

JOBICY = json.dumps({"jobs": [
    {"jobTitle": "Marketing Intern", "companyName": "Zeta", "jobGeo": "Anywhere",
     "jobExcerpt": "Help us grow", "url": "https://jobicy.com/jobs/1",
     "pubDate": "2026-10-01 10:00:00"},
    {"jobTitle": "CFO", "companyName": "Eta", "url": "https://jobicy.com/jobs/2"},
]})

HIMALAYAS = json.dumps({"jobs": [
    {"title": "Graduate Software Engineer", "companyName": "Theta",
     "location": "Europe", "description": "<p>Go</p>",
     "applicationLink": "https://himalayas.app/jobs/1", "categories": ["engineering"],
     "pubDate": 1761000000},
]})

WORKING_NOMADS = json.dumps([
    {"title": "Trainee Recruiter", "company_name": "Iota", "location": "Remote",
     "description": "People", "url": "https://www.workingnomads.com/jobs/1",
     "tags": ["hr"], "pub_date": "2026-10-02T00:00:00"},
    {"title": "VP Sales", "company_name": "Kappa", "url": "https://www.workingnomads.com/jobs/2"},
])

HN_SEARCH = json.dumps({"hits": [{"objectID": "424242"}]})
HN_THREAD = json.dumps({"children": [
    {"id": 1001, "text": "Acme | ML Intern | REMOTE<p>We build <i>models</i> &amp; tools"},
    {"id": 1002, "text": "Corp | Staff Engineer | NYC<p>Senior role"},
    {"id": 1003, "text": None},
]})

JOBSPRESSO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Jobspresso</title>
<item><title>Product Intern</title><link>https://jobspresso.co/job/1</link>
<pubDate>Mon, 20 Oct 2026 09:00:00 +0000</pubDate>
<description><![CDATA[<p>Join <b>us</b></p>]]></description></item>
</channel></rss>"""

WWR_EMPTY = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Senior DevOps</title><link>https://weworkremotely.com/jobs/0</link>
<description>x</description></item></channel></rss>"""
WWR_FALLBACK = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Junior Designer</title><link>https://weworkremotely.com/jobs/1</link>
<author>Lambda</author><pubDate>Tue, 21 Oct 2026 09:00:00 +0000</pubDate>
<description>Design things</description></item></channel></rss>"""

REKRUTE = """<html><body><ul>
<li class="post-id"><h2><a href="/offre-emploi-stage-data-casablanca-1.html">Stage Data Analyst | Casablanca (Maroc)</a></h2>
  <div class="info">Stage PFE en data science &amp; BI pour étudiants</div><em class="location">Casablanca (Maroc)</em></li>
<li class="post-id"><h2><a href="/offre-emploi-conseiller-client-rabat-2.html">Conseiller Client (F/H) - Service client - Rabat</a></h2>
  <div class="info">Poste CDI à Rabat</div></li>
<li class="post-id"><h2><a href="/offre-emploi-senior-3.html">Ingénieur Senior Confirmé Data</a></h2><div class="info">Confirmé</div></li>
<li class="post-id"><h2><a href="/x.html">Lancer 4K</a></h2></li>
<li class="post-id"><h2><a href="/short.html">Court</a></h2></li>
</ul></body></html>"""

REKRUTE_NO_CLASS = """<html><body><ul>
<li><h2><a href="/offre-emploi-4.html">Stage Développeur Web Fès</a></h2><div class="info">Stage 6 mois à Fès</div></li>
</ul></body></html>"""

# hrefs on the real site are RELATIVE and have no leading slash
MAROCANNONCES = """<html><body><div class="cat-items"><ul>
<li><a href="categorie/309/Offres-emploi/annonce/10467862/Charge-de-Paie-Berrechid.html">Charge(é) de Paie /BerrechidBerrechid</a><b>RH Services</b></li>
<li><a href="categorie/309/Offres-emploi/annonce/10454926/Agent-Administratif.html">Agent(e) Administratif(ve) et ComptableCasablanca</a></li>
<li><a href="categorie/309/Offres-emploi/annonce/1/x.html">ok</a></li>
<li><a href="/maroc/autre.html">Menu Emploi</a></li>
</ul></div></body></html>"""
MAROCANNONCES_EMPTY = "<html><body><p>nothing</p></body></html>"

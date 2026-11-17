"""Bounded metadata search against the public arXiv API."""
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def search_papers(query, year=None):
    stopwords = {'i', 'want', 'to', 'build', 'create', 'a', 'an', 'the', 'for', 'my', 'project', 'papers', 'research', 'on', 'about', 'using', 'with', 'and', 'of', 'in'}
    terms = [term for term in re.findall(r'[\w-]+', query.lower(), re.UNICODE) if term not in stopwords][:12]
    if not terms:
        return []
    search = ' AND '.join('all:' + term for term in terms)
    if year:
        search += f' AND submittedDate:[{year}01010000 TO 210012312359]'
    params = urllib.parse.urlencode({'search_query':search, 'start':0, 'max_results':8, 'sortBy':'relevance'})
    request = urllib.request.Request('https://export.arxiv.org/api/query?' + params, headers={'User-Agent':'ResearchWorkspace/1.0'})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read(2_000_000))
    namespace = {'a':'http://www.w3.org/2005/Atom'}
    results=[]
    for entry in root.findall('a:entry', namespace):
        identifier=entry.findtext('a:id','',namespace)
        if not re.match(r'https?://arxiv.org/abs/[\w./-]+$', identifier):
            continue
        results.append({'title':' '.join(entry.findtext('a:title','',namespace).split()),'summary':' '.join(entry.findtext('a:summary','',namespace).split()), 'published':entry.findtext('a:published','',namespace),'authors':[a.findtext('a:name','',namespace) for a in entry.findall('a:author',namespace)],'url':identifier.replace('http:','https:')})
    return results

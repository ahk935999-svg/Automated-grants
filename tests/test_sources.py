from core.sources import extract_relevant_links

def test_extract_relevant_links_filters_and_deduplicates():
    html='''
    <html><body>
      <a href="/masters/biomedical">Biomedical Engineering Master</a>
      <a href="/about">About us</a>
      <a href="mailto:apply@example.org">Apply by email</a>
      <a href="/masters/biomedical#details">Biomedical Engineering Master</a>
      <a href="https://external.example.org/fellowship">Fellowship Programme</a>
    </body></html>
    '''
    links=extract_relevant_links(html,'https://official.example.org/opportunities',max_links=10)
    urls=[url for url,_ in links]
    assert 'https://official.example.org/masters/biomedical' in urls
    assert 'https://external.example.org/fellowship' in urls
    assert 'https://official.example.org/about' not in urls
    assert len(urls)==2
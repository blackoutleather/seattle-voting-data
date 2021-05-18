import streamlit as st
import os
import re

CODE = """<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-V17PE0WYHB"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-V17PE0WYHB');
</script>"""

META_TAGS= """
<meta property = "og:image" content = "http://seattlevoterdata-env.eba-e42natez.us-east-2.elasticbeanstalk.com/media/eb91ae4b3efdf403bb5c59913940d6ceaa2b566bbc4cfddb4921816a.jpeg"/>

<meta property = "og:title" content = "I SEA ELECTION DATA"/>

<meta property = "og:description" content = "I see Seattle election data and now you can too"/>

<meta property = "og:image:width" content = "1200"/>

<meta property = "og:image:height" content = "630"/> 

"""

def setup_analytics():
    a=os.path.dirname(st.__file__)+'/static/index.html'
    with open(a, 'r') as f:
        data=f.read()
        if len(re.findall('UA-', data))==0:
            with open(a, 'w') as ff:
                newdata=re.sub('<head>','<head>'+CODE,data)
                ff.write(newdata)

def add_metdata_tags():
    a=os.path.dirname(st.__file__)+'/static/index.html'
    with open(a, 'r') as f:
        data=f.read()
    with open(a, 'w') as ff:
        newdata = re.sub('<head>', '<head>' + META_TAGS, data)
        ff.write(newdata)




if __name__ == "__main__":
    add_metdata_tags()
    setup_analytics()
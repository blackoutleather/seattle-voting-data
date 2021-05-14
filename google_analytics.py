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


def setup_analytics():
    a=os.path.dirname(st.__file__)+'/static/index.html'
    with open(a, 'r') as f:
        data=f.read()
        if len(re.findall('UA-', data))==0:
            with open(a, 'w') as ff:
                newdata=re.sub('<head>','<head>'+CODE,data)
                ff.write(newdata)

if __name__ == "__main__":
    setup_analytics()
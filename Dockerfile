# base image
FROM continuumio/miniconda3

# exposing default port for streamlit
EXPOSE 8501

# making directory of app
WORKDIR /app

# Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml

#[s3]\n\
#bucket = \"s3://com.climate.production.users"\n\
#keyPrefix = \"/team/science/people/devin.wilkinson\"\n\

# Congigure streamlit
RUN mkdir -p /root/.streamlit
RUN bash -c 'echo -e "\
[general]\n\
email = \"\"\n\
" > /root/.streamlit/credentials.toml'

RUN bash -c 'echo -e "\
[server]\n\
enableCORS = false\n\
" >> /root/.streamlit/config.toml'

RUN bash -c "conda init"

## Make RUN commands use the new environment:
#SHELL ["conda", "run", "-n", "myenv", "/bin/bash", "-c"]

# copying all files over
COPY . /app

#run script to setup analytics
RUN bash -c "conda run -n app python google_analytics.py"

#The code to run when container is started:
ENTRYPOINT ["conda", "run", "-n", "app", "streamlit", "run", "main.py"]
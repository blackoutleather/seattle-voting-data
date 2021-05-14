# base image
FROM continuumio/miniconda3

# exposing default port for streamlit
EXPOSE 8501

# making directory of app
WORKDIR /app

# Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml

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

# copying all files over
COPY . /app

#run script to setup analytics
RUN bash -c "conda run -n vote_data python google_analytics.py"

#The code to run when container is started:
ENTRYPOINT ["conda", "run", "-n", "vote_data", "streamlit", "run", "main.py"]
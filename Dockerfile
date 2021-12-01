# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.7

EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY . .
RUN python -m pip install -r requirements.txt

WORKDIR /src/

CMD python app.py

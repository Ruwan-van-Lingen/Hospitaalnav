# Bou die toepassing met: docker compose up --build -d
FROM python:3.12-slim

# Skakel bytekodelêers en uitvoerbuffering af. Matplotlib se kas is skryfbaar.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

# Stel die werkgids binne die houer in.
WORKDIR /app

# Hou afhanklikhede in 'n aparte boulaag om Docker se kas te benut.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Die toepassing loop as 'n gebruiker sonder administrateurregte.
RUN addgroup --system appgroep \
    && adduser --system --ingroup appgroep appgebruiker
COPY --chown=appgebruiker:appgroep . .

# Die benoemde Compose-volume erf hierdie gids se eienaarskap by eerste gebruik.
RUN mkdir -p /app/data \
    && chown appgebruiker:appgroep /app /app/data
USER appgebruiker

# Verklaar die poort waarop Uvicorn luister. Dit publiseer nie die poort
# outomaties nie — dit dien as dokumentasie en word deur docker-compose.yml
# se "ports"-afdeling gebruik.
EXPOSE 8000

# Die gesondheidstatus wys verbindingsfoute; dit herbegin nie self die houer nie.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" || exit 1

# Luister op alle koppelvlakke sodat Docker se poortdeurleiding werk.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

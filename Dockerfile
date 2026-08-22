# ==========================================================================
# Dockerfile
# ===========
# Bou 'n produksie-gereed Docker-beeld vir die Hospitaal Navigasiestelsel.
#
# Commands:
# -------
#   docker compose up --build -d    # Bou en begin via docker-compose.yml
#   docker build -t hospitaalnav .  # Bou die beeld direk (sonder Compose)
#   docker run -p 8000:8000 hospitaalnav
#
# Boustrategie
# -------------
# • python:3.12-slim word gebruik as basisbeeld — klein voetspoor, geen
#   onnodige bou-instrumente nie, maar steeds geskik vir Matplotlib se Agg-
#   agterkant (wat geen GUI-biblioteke benodig nie).
# • Afhanklikhede word voor die bronkode gekopieer sodat Docker se laagkas
#   hergebruik word wanneer slegs die bronkode verander — pip hoef dan nie
#   elke keer herhaal te word nie.
# • Die toepassing loop as 'n onbevoorregte stelselgebruiker (appgebruiker)
#   in plaas van root, wat die aanvalsoppervlak verminder.
#
# Sekuriteit
# -----------
# Stel ADMIN_WAGWOORD, ADMIN_GEBRUIKERSNAAM en SESSIE_GEHEIM via
# docker-compose.yml se "environment"-afdeling. Moenie die verstekwaardes
# in produksie gebruik nie.
# ==========================================================================

# Basisbeeld: Python 3.12 slanke variant — minimale OS-voetspoor.
FROM python:3.12-slim

# Omgewingsveranderlikes vir Python en Matplotlib:
#   PYTHONDONTWRITEBYTECODE — verhoed dat .pyc-lêers in die beeld gestoor word.
#   PYTHONUNBUFFERED        — verseker dat logs dadelik na stdout geskryf word
#                             (belangrik vir docker logs en log-aggregators).
#   MPLCONFIGDIR            — wys Matplotlib na /tmp sodat dit sonder
#                             tuisgidspermissies kan werk wanneer die
#                             onbevoorregte gebruiker dit gebruik.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

# Stel die werkgids in binne die container.
WORKDIR /app

# Kopieer slegs requirements.txt eers om Docker se laagkas te benut:
# as die bronkode verander maar requirements.txt dieselfde bly, hoef
# pip nie weer geinstalleer te word nie.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Skep 'n onbevoorregte stelselgroep en -gebruiker.
# Die toepassing loop nooit as root nie — dit beperk die skade wat 'n
# moontlike kwesbaarheid in FastAPI of Uvicorn kan aanrig.
RUN addgroup --system appgroep \
    && adduser --system --ingroup appgroep appgebruiker

# Kopieer die bronkode met die korrekte eienaarskap sodat appgebruiker
# die lêers kan lees sonder dat root-voorregte nodig is.
COPY --chown=appgebruiker:appgroep . .
RUN chown appgebruiker:appgroep /app

# Skakel oor na die onbevoorregte gebruiker vir alle verdere instruksies
# en die looptydproses.
USER appgebruiker

# Verklaar die poort waarop Uvicorn luister. Dit publiseer nie die poort
# outomaties nie — dit dien as dokumentasie en word deur docker-compose.yml
# se "ports"-afdeling gebruik.
EXPOSE 8000

# Gesondheidskontroleer die toepassing elke 30 sekondes deur die tuisblad
# te bereik. Docker merk die container as "unhealthy" na 3 opeenvolgende
# mislukkings, waarna Compose dit kan herbegin.
#   --interval    : Tyd tussen kontroles.
#   --timeout     : Maksimum tyd om op 'n antwoord te wag.
#   --start-period: Genadietyd na container-opstart voordat mislukkings tel.
#   --retries     : Aantal mislukkings voordat die status "unhealthy" word.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" || exit 1

# Begin die FastAPI-toepassing via Uvicorn.
#   --host 0.0.0.0  — luister op alle koppelvlakke sodat Docker se
#                     poortdeurleiding werk (127.0.0.1 sou net intern
#                     bereikbaar wees).
#   --port 8000     — moet ooreenstem met EXPOSE en docker-compose.yml.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

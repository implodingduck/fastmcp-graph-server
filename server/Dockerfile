FROM python:3.12

RUN apt-get update && apt-get install -y curl tcpdump net-tools vim

WORKDIR /code

COPY ./pyproject.toml ./uv.lock /code/

RUN pip install --no-cache-dir uv==0.12.5 && uv sync --frozen --no-dev

COPY . /code/app

EXPOSE 8000

CMD ["/code/.venv/bin/python", "app/server.py"]
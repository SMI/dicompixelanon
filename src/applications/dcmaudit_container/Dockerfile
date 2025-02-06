FROM ubuntu:24.04
ARG debian_frontend=noninteractive
ENV TZ=Europe/London
RUN apt update && apt install -y git python3-pip python3-virtualenv python3-tk
RUN virtualenv /venv
RUN /venv/bin/python3 -m pip install setuptools boto3 pydicom deid pydal opencv_python_headless pytesseract tkinter-tooltip
RUN git clone https://github.com/SMI/dicompixelanon && cd dicompixelanon/src/library && /venv/bin/python3 ./setup.py install
ENTRYPOINT [ "/venv/bin/python3", "dicompixelanon/src/applications/dcmaudit.py", "--db", "/tmp", "--review" ]

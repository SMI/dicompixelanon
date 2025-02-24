FROM ubuntu:24.04
ARG debian_frontend=noninteractive
ENV TZ=Europe/London
RUN apt update && apt install -y git python3-pip python3-virtualenv python3-tk
RUN virtualenv /venv
RUN /venv/bin/python3 -m pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
RUN /venv/bin/python3 -m pip install setuptools boto3 pydicom deid pydal opencv_python_headless pytesseract numpy easyocr tkinter-tooltip
ARG CACHEDATE=1
RUN git clone https://github.com/SMI/dicompixelanon && cd dicompixelanon/src/library && /venv/bin/python3 -m pip install --upgrade build && /venv/bin/python3 -m build && /venv/bin/python3 -m pip install dist/DicomPixelAnon-0.0.0-py3-none-any.whl
ENTRYPOINT [ "/venv/bin/python3", "dicompixelanon/src/applications/dcmaudit.py", "--db", "/tmp", "--review" ]

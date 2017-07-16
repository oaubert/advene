FROM ubuntu:17.04

RUN apt-get update && apt-get install -y python \
    python-pip \
    python-pil \
    python-h5py

RUN pip install keras==2.0.5 tensorflow==1.2.0rc2

ADD vcd-server.py /vcd-server.py

VOLUME [ "/root/.keras/" ]
VOLUME [ "/var/vcd/cache" ]

ENTRYPOINT [ "python" , "/vcd-server.py"]

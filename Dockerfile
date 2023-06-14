FROM debian:buster-slim as build

RUN apt-get -y update &&\
    apt-get -y install cmake build-essential git ninja-build libsqlite3-dev

RUN cd /usr/src &&\
    git clone https://github.com/icculus/mojozork.git &&\
    cd mojozork &&\
    cmake -B build -GNinja &&\
    cmake --build build/ &&\
    ls build/


FROM debian:buster-slim

RUN mkdir /opt/zork
COPY --from=build /usr/src/mojozork/build/mojozork /opt/zork/
COPY --from=build /usr/src/mojozork/zork1.dat /opt/zork/
COPY zork.py /opt/zork/

RUN apt-get -y update &&\
    apt-get -y install python3 && \
    chmod +x /opt/zork/mojozork

RUN chmod +x /opt/zork/zork.py

WORKDIR /opt/zork

CMD ["python3", "-u", "zork.py"]

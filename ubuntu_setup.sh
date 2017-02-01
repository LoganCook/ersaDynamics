#!/bin/bash

# Install dependent packages and setup a virtual environment

apt-get -y update
apt-get -y install build-essential python3-dev python3-pip libssl-dev libffi-dev

pip3 install --upgrade pip virtualenv setuptools

virtualenv -p python3 /home/ubuntu/adal_env
source /home/ubuntu/adal_env/bin/activate
pip install cryptography adal

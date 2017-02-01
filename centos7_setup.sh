#!/bin/bash

# Install dependent packages and setup a virtual environment

yum -y install epel-release
yum -y update
yum -y install gcc python34 python34-pip python34-devel openssl-devel libffi-devel

pip3 install --upgrade pip virtualenv setuptools

virtualenv -p python3 /home/ec2-user/adal_env
source /home/ec2-user/adal_env/bin/activate
pip install cryptography adal

#!/usr/bin/env python3

from setuptools import setup

setup(name='ersa-Dynamics',
      version='0.0.1',
      description='Utility module at eRSA to MS Dynamics',
      license='GPLv3',
      author='eResearch SA',
      packages=['edynam'],
      install_requires=['cryptography', 'adal'],
      classifiers=[
          'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
          'Programming Language :: Python :: 3',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Module'
      ]
     )

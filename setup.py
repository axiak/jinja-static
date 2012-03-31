# -*- coding: utf-8 -
#


import os
from setuptools import setup, find_packages
import sys


requirements = [
    'networkx',
    'jinja2',
    'jinjatag',
    'watchdog==0.6.0',
    'pyyaml',
    'envoy==0.0.2',
    ]

if sys.version_info[0] == 2 and sys.version_info[1] < 7:
    requirements.append('argparse')
    requirements.append('ordereddict')

setup(
    name = 'jinjastatic',
    version = '0.0.6',

    description = 'Static template compilation',
    long_description = '',
    author = 'Michael Axiak',
    author_email = 'mike@axiak.net',
    license = 'MIT',

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    zip_safe = False,
    packages = find_packages(exclude=['examples', 'tests']),
    include_package_data = True,
    install_requires=requirements,
    entry_points={
        'console_scripts':
            ['jinja-static=jinjastatic:run'],
        },
)

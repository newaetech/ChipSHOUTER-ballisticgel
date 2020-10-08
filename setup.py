#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='ballisticgel',
    version='0.1.1',
    description="CW521 Ballistic Gel Communication Library",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author="Colin O'Flynn",
    author_email='coflynn@newae.com',
    license='GPLv2+',
    url='https://github.com/newaetech/ChipSHOUTER-ballisticgel',
    packages=find_packages("ballisticgel"),
    install_requires=[
        'chipwhisperer',
    ],
    project_urls={
        'Source': 'https://github.com/newaetech/ChipSHOUTER-ballisticgel',
        'Issue Tracker': 'https://github.com/newaetech/ChipSHOUTER-ballisticgel/issues'
    },
    python_requires='~=3.6',
)

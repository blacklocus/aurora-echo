from setuptools import setup, find_packages

with open('requirements.txt') as file_requirements:
    requirements = file_requirements.read().splitlines()

setup(
    name='aurora_echo',
    version='2.0.1',
    packages=find_packages(),
    install_requires=requirements,
    entry_points='''
        [console_scripts]
        aurora_echo=aurora_echo:main
    ''',
)

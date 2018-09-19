from setuptools import setup, find_packages

setup_requirements = [
    'flake8==3.5.0'
]

with open('requirements.txt') as file_requirements:
    requirements = file_requirements.read().splitlines()

setup(
    name='aurora_echo',
    version='2.0.1',
    packages=find_packages(),
    install_requires=requirements,
    setup_requires=setup_requirements,
    entry_points='''
        [console_scripts]
        aurora_echo=aurora_echo:main
    ''',
)

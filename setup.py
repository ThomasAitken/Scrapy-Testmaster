import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='scrapy-testmaster',
    version='1.3.1',
    author='Thomas Aitken',
    author_email='tclaitken@gmail.com',
    description='Automated testing and debugging tool for Scrapy.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ThomasAitken/Scrapy-Testmaster',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'datadiff==2.0.0',
        'requests'
    ],
    entry_points={
        'console_scripts': [
            'testmaster=scrapy_testmaster.cli:main',
        ],
    },
)

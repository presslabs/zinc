from setuptools import setup, find_packages

install_requires = ['Django', 'celery', 'zipa', 'djangorestframework']
tests_require = ['pytest', 'pytest-runner>=2.0,<3dev', 'pytest-flake8']

setup(
    name='zinc',
    version='0.0.1',
    description="Route 53 zone manager",
    author="Presslabs",
    author_email="ping@presslabs.com",
    url="https://github.com/Presslabs/zinc",
    install_requires=install_requires,
    tests_require=tests_require,
    packages=find_packages(exclude=['tests']),
    extras_require={
        'test': tests_require
    },
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ]
)

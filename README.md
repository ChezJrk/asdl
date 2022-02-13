[![codecov](https://codecov.io/gh/ChezJrk/asdl/branch/master/graph/badge.svg?token=K2KN2RC3OX)](https://codecov.io/gh/ChezJrk/asdl)

# ASDL ADT

This is a modern Python (3.8+) library for generating helpful algebraic data types out of ASDL definitions.

## Development setup

First, clone the repo:

```console
$ git clone git@github.com:ChezJrk/asdl.git
$ cd asdl
```

Then create a virtual environment and install the requirements into it:

```console
$ python3 -m venv $HOME/.venv/asdl
$ source $HOME/.venv/asdl/bin/activate
$ python -m pip install -U pip setuptools wheel
$ python -m pip install -r requirements.txt
```

Then install the [pre-commit] hooks:

```
$ pre-commit install
```

Finally, you can run the tests with tox:

```
$ tox
```

This will test on Python 3.8, 3.9, and 3.10.

[pre-commit]: https://pre-commit.com/

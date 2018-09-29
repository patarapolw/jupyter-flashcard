# jupyter-flashcard

Create a database of Jupyter Notebooks and convert them into flashcards.

## Installation

- Clone the project from GitHub
- Navigate to the project folder and `poetry install`
- Run a Python script:

```python
from jupyter_flashcard import JupyterFlashcard

JupyterFlashcard().init(PATH_TO_THE_FOLDER_CONTAINING_JUPYTER_FILES)
```

By default, it uses PostGRESQL of the database named `jupyter-flashcard`, so you have to initialize the database first, before running the script, but you can also use SQLite by specifying:

```python
JupyterFlashcard(engine='sqlite:///PATH_TO_SQLITE_DATABASE')
```

## Usage

In Jupyter Notebook:

```python
>>> from jupyter_flashcard import JupyterFlashcard
>>> jfc = JupyterFlashcard()
>>> iter_fc = jfc.iter_quiz()
>>> fc = next(iter_fc)
>>> fc
'Front side of the flashcard is shown.'
>>> fc.show()
'Back side of the flashcard is shown.'
>>> fc.wrong()
'Mark the flashcard as wrong.'
>>> fc.right()
'Mark the flashcard as right.'
>>> fc.mark()
'Add the tag "marked" to the flashcard.'
```

If you want to quiz only on **"marked"** flashcards, use:

```python
>>> iter_fc = jfc.iter_quiz(tags=['marked'])
```

## Screenshots

![0.png](/screenshots/0.png?raw=true)
![1.png](/screenshots/1.png?raw=true)
![2.png](/screenshots/2.png?raw=true)

## Related Projects

- [ImServ](https://github.com/patarapolw/ImServ) - Spin an image server, store images from Clipboard in single place, and prevent duplication. This can be useful for using in Jupyter Notebook (with having to store images as HEX).
